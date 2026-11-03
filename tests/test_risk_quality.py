"""P5 (charter §5.A / §5.C): finding-explanation enrichment + contradiction detector.

Tests that:
  * every populated RiskFlag on the bundled sample carries the enrichment
    fields where the rule logic genuinely knows the answer;
  * contract-level findings carry an ``uncertainty_note`` explaining the
    phrase-based search scope;
  * the schema round-trips (model_dump -> model_validate) all new fields;
  * the RISK_CONFLICT_001 contradiction detector fires on a synthetic
    two-clause document with different liability-cap amounts, and abstains
    on: equal amounts, a fee (not a cap), and different scopes
    (per-incident vs aggregate).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.schemas import (
    AnalysisResult,
    Clause,
    ContractSummary,
    RiskFlag,
    RiskSeverity,
)
from app.services.analyzer import analyse_path
from nlp.risk_scoring.rules import (
    _contract_level_rules,
    rule_contradictory_liability_caps,
)
from nlp.risk_scoring.scorer import score_contract

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "raw" / "sample_msa.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _summary(**kw) -> ContractSummary:
    base = dict(contract_id="x", title="t", file_name="f.txt", jurisdiction="India")
    base.update(kw)
    return ContractSummary(**base)


def _clause(cid: str, *, heading: str = "h", text: str, types: list[str] | None = None) -> Clause:
    return Clause(clause_id=cid, heading=heading, text=text, clause_types=types or [])


def _find(risk_flags: list[RiskFlag], rule_id: str) -> RiskFlag:
    matches = [f for f in risk_flags if f.rule_id == rule_id]
    assert matches, f"no finding with rule_id={rule_id!r} in {[f.rule_id for f in risk_flags]}"
    return matches[0]


# ---------------------------------------------------------------------------
# Task 1: enrichment fields on the bundled sample
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_result():
    from app.models.schemas import ContractType, PartySide

    return analyse_path(
        SAMPLE,
        contract_id="rq_sample",
        contract_type=ContractType.OTHER,
        user_role=PartySide.NEUTRAL,
        jurisdiction="India",
    )


def test_sample_liability_finding_has_impact_and_review(sample_result):
    flag = _find(sample_result.risks, "RISK_LIABILITY_001")
    assert flag.impact_summary is not None and len(flag.impact_summary) > 20
    assert flag.review_action is not None
    assert flag.uncertainty_note is not None
    # affected_parties: the trigger sentence names "Provider", so it must be
    # either the detected party name or the role noun.
    assert flag.affected_parties, "RISK_LIABILITY_001 must carry affected_parties"
    assert any("provider" in p.lower() for p in flag.affected_parties)


def test_sample_contract_level_findings_have_uncertainty_note(sample_result):
    contract_level = [f for f in sample_result.risks if f.clause_id is None]
    assert contract_level, "expected at least one contract-level finding"
    for f in contract_level:
        assert f.uncertainty_note is not None, f"contract-level {f.rule_id} missing uncertainty_note"
        assert "phrase-based" in f.uncertainty_note.lower() or "verify" in f.uncertainty_note.lower()


def test_all_rule_findings_have_impact_summary(sample_result):
    for f in sample_result.risks:
        if f.source == "model":
            continue  # ML booster findings are not enriched (by design)
        assert f.impact_summary is not None, f"{f.rule_id} missing impact_summary"
        assert f.review_action is not None, f"{f.rule_id} missing review_action"


def test_schema_round_trip_preserves_all_new_fields(sample_result):
    dumped = json.loads(sample_result.model_dump_json())
    restored = AnalysisResult.model_validate(dumped)
    for f1, f2 in zip(sample_result.risks, restored.risks, strict=True):
        assert f1.impact_summary == f2.impact_summary
        assert f1.affected_parties == f2.affected_parties
        assert f1.review_action == f2.review_action
        assert f1.uncertainty_note == f2.uncertainty_note
        assert f1.related_clause_ids == f2.related_clause_ids
    assert sample_result.contract.risk_score_breakdown == restored.contract.risk_score_breakdown
    assert sample_result.contract.score_caveat == restored.contract.score_caveat
    for o1, o2 in zip(sample_result.obligations, restored.obligations, strict=True):
        assert o1.frequency == o2.frequency


def test_legacy_payload_still_validates():
    """A RiskFlag dict without the new keys must still validate (additive schema)."""
    legacy = {
        "risk_id": "r1",
        "rule_id": "RISK_LIABILITY_001",
        "name": "n",
        "severity": "critical",
        "explanation": "e",
    }
    flag = RiskFlag.model_validate(legacy)
    assert flag.impact_summary is None
    assert flag.affected_parties is None
    assert flag.review_action is None
    assert flag.uncertainty_note is None
    assert flag.related_clause_ids == []


# ---------------------------------------------------------------------------
# Task 3: missing-protection honesty
# ---------------------------------------------------------------------------


def test_missing_clause_explanation_is_honest():
    clauses = [_clause("c1", heading="1. Definitions", text="Definitions only.")]
    flags = _contract_level_rules(clauses, _summary())
    missing = [f for f in flags if f.rule_id.startswith("MISSING_CLAUSE_")]
    assert missing
    for f in missing:
        assert "not found" in f.explanation
        assert f.uncertainty_note and "phrase-based" in f.uncertainty_note
        assert f.search_scope and "document-wide" in f.search_scope
        assert f.impact_summary is not None


def test_data_missing_fires_only_when_genuinely_absent():
    # A contract that references personal data and has a genuine data-
    # protection clause must NOT trigger RISK_DATA_MISSING.
    clauses = [
        _clause("c1", heading="2. Processing",
                text="The Provider shall process Personal Data only for the purposes of this Agreement."),
    ]
    clauses[0].clause_types = ["Data Protection"]
    flags = _contract_level_rules(clauses, _summary())
    assert not [f for f in flags if f.rule_id == "RISK_DATA_MISSING"]


def test_data_missing_fires_when_only_guarantee_phrase_present():
    """Document the limitation: a data-protection clause phrased as a
    *guarantee* of security ("guarantee the security of Personal Data")
    contains no searched phrase and no classifier label, so
    RISK_DATA_MISSING still fires. The honesty note must say so.
    """
    clauses = [
        _clause("c1", heading="2. Security",
                text="The Provider shall guarantee the security of the Personal Data processed under this Agreement."),
    ]
    flags = _contract_level_rules(clauses, _summary())
    data_missing = [f for f in flags if f.rule_id == "RISK_DATA_MISSING"]
    assert data_missing, (
        "RISK_DATA_MISSING is expected to fire here (known limitation: phrase-"
        "based search misses 'guarantee the security' phrasing)"
    )
    f = data_missing[0]
    assert "annexure" in f.uncertainty_note.lower() or "annex" in f.uncertainty_note.lower()
    assert f.search_scope and "document-wide" in f.search_scope


def test_annexure_dp_clause_suppresses_data_missing_when_classified():
    """A data-protection policy attached as an annexure and classified as
    'Data Protection' must suppress RISK_DATA_MISSING — the classifier
    catches what the phrase search misses.
    """
    clauses = [
        _clause("c1", heading="2. Processing",
                text="The Provider shall process Personal Data only for the purposes of this Agreement."),
        _clause("c2", heading="Annexure 2: DATA PROTECTION POLICY",
                text="Personal Data shall be protected in accordance with the Data Protection Policy attached as Annexure 2."),
    ]
    clauses[1].clause_types = ["Data Protection"]
    flags = _contract_level_rules(clauses, _summary())
    assert not [f for f in flags if f.rule_id == "RISK_DATA_MISSING"]


# ---------------------------------------------------------------------------
# Task 4: RISK_CONFLICT_001 contradiction detector
# ---------------------------------------------------------------------------


def test_contradiction_fires_on_different_cap_amounts():
    clauses = [
        _clause("c1", text="6.1 The aggregate liability of each party shall not exceed INR 5,00,000 in aggregate."),
        _clause("c2", text="9.2 The cap of liability shall be INR 10,00,000."),
    ]
    flag = rule_contradictory_liability_caps(clauses, _summary())
    assert flag is not None
    assert flag.rule_id == "RISK_CONFLICT_001"
    assert flag.severity == RiskSeverity.HIGH
    assert flag.clause_id is None  # contract-level
    assert sorted(flag.related_clause_ids) == ["c1", "c2"]
    assert len(flag.evidence_spans) == 2
    assert flag.evidence_spans[0].clause_id == "c1"
    assert flag.evidence_spans[1].clause_id == "c2"
    assert flag.uncertainty_note and "scope" in flag.uncertainty_note.lower()
    # Both spans are exact slices of their clause text.
    by_id = {c.clause_id: c for c in clauses}
    for span in flag.evidence_spans:
        text = by_id[span.clause_id].text
        assert text[span.char_start:span.char_end] == span.text


def test_contradiction_does_not_fire_on_equal_amounts():
    clauses = [
        _clause("c1", text="Liability shall not exceed INR 5,00,000 in aggregate."),
        _clause("c2", text="The liability cap is INR 5,00,000."),
    ]
    assert rule_contradictory_liability_caps(clauses, _summary()) is None


def test_contradiction_does_not_fire_on_fee_not_cap():
    clauses = [
        _clause("c1", text="The monthly service fee shall be INR 5,00,000."),
        _clause("c2", text="The liability cap is INR 10,00,000."),
    ]
    assert rule_contradictory_liability_caps(clauses, _summary()) is None


def test_contradiction_does_not_fire_on_different_scopes():
    # A scope word ("per incident") in the cap-context sentence means the
    # amount is not comparable to an aggregate figure — abstain.
    clauses = [
        _clause("c1", text="6.1 The maximum liability of either party per incident shall not exceed INR 5,00,000."),
        _clause("c2", text="9.2 The aggregate liability cap is INR 10,00,000."),
    ]
    assert rule_contradictory_liability_caps(clauses, _summary()) is None


def test_contradiction_fires_when_scopes_are_indistinguishable():
    # Neither clause carries a scope word: the amounts are directly comparable.
    clauses = [
        _clause("c1", text="6.1 The maximum liability of either party shall not exceed INR 5,00,000."),
        _clause("c2", text="9.2 The aggregate liability cap is INR 10,00,000."),
    ]
    flag = rule_contradictory_liability_caps(clauses, _summary())
    assert flag is not None


def test_contradiction_does_not_fire_on_different_currencies():
    clauses = [
        _clause("c1", text="Liability shall not exceed USD 5,00,000 in aggregate."),
        _clause("c2", text="The liability cap is INR 10,00,000."),
    ]
    assert rule_contradictory_liability_caps(clauses, _summary()) is None


def test_contradiction_normalises_lakh_units():
    clauses = [
        _clause("c1", text="Maximum liability shall be INR 5 lakh."),
        _clause("c2", text="The liability cap is INR 50 lakh."),
    ]
    flag = rule_contradictory_liability_caps(clauses, _summary())
    assert flag is not None
    assert "500,000" in flag.explanation
    assert "5,000,000" in flag.explanation


def test_contradiction_no_fire_on_single_cap():
    clauses = [
        _clause("c1", text="Liability shall not exceed INR 5,00,000 in aggregate."),
        _clause("c2", text="The Provider shall indemnify the Customer."),
    ]
    assert rule_contradictory_liability_caps(clauses, _summary()) is None


def test_contradiction_zero_false_positives_on_bundled_samples():
    """The detector must not fire on any bundled data/raw sample."""
    from app.services.parser import parse_document
    from app.services.segmenter import segment_clauses
    from nlp.clause_classification.classifier import classify_clause

    raw_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    for path in sorted(raw_dir.glob("*.txt")):
        parsed = parse_document(str(path), contract_id=path.stem, enable_ocr=False)
        raws = segment_clauses(parsed.full_text, contract_id=path.stem)
        clauses = [
            Clause(
                clause_id=r.clause_id,
                section_number=r.section_number,
                heading=r.heading,
                text=r.text,
                clause_types=classify_clause(r.text, heading=r.heading).labels,
            )
            for r in raws
        ]
        flag = rule_contradictory_liability_caps(clauses, _summary())
        assert flag is None, f"RISK_CONFLICT_001 false positive on {path.name}: {flag.explanation if flag else ''}"


# ---------------------------------------------------------------------------
# Task 5: score explainability
# ---------------------------------------------------------------------------


def test_breakdown_sums_consistently_with_score():
    flags = [
        RiskFlag(risk_id=f"r{i}", rule_id=f"R{i}", name="n",
                 severity=RiskSeverity.HIGH if i % 2 else RiskSeverity.MEDIUM,
                 explanation="e", score=72.0)
        for i in range(5)
    ]
    score, level, breakdown = score_contract([], flags)
    total = sum(breakdown[k] for k in ("top", "volume", "severity_mass", "cap_adjustment"))
    assert total == score, f"breakdown terms {breakdown} do not sum to score {score}"


def test_breakdown_is_empty_for_no_risks():
    score, level, breakdown = score_contract([], [])
    assert score == 0.0 and breakdown == {}


def test_sample_caveat_is_set(sample_result):
    assert sample_result.contract.score_caveat is not None
    assert "probability" in sample_result.contract.score_caveat.lower()
    assert sample_result.contract.risk_score_breakdown is not None
    assert "top" in sample_result.contract.risk_score_breakdown
