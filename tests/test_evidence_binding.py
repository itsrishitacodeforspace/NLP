"""P2: evidence binding for risk findings (general-purpose)."""
from __future__ import annotations

import json
from pathlib import Path

from app.models.schemas import Clause, ContractSummary, EvidenceSpan, RiskFlag, RiskSeverity
from nlp.risk_scoring.rules import _bind_evidence, apply_rules

TC05 = Path("uploads/c_20261026_134911_fc805c301d8d_TC-05_cross_reference_traps.md")


def _clause(cid="c1", text="Provider shall have unlimited liability for all losses.", sec="7.1"):
    return Clause(clause_id=cid, section_number=sec, heading="Liability", text=text)


def _summary():
    return ContractSummary(contract_id="x", title="t", file_name="f.txt", jurisdiction="India")


def _flag(clause_id, rule_id="R"):
    return RiskFlag(risk_id=f"{rule_id}_1", clause_id=clause_id, rule_id=rule_id, name="n",
                    severity=RiskSeverity.HIGH, explanation="e", score=10.0)


def test_single_span_matches_source_text():
    cl = _clause()
    f = _flag("c1")
    _bind_evidence([f], [cl])
    assert f.evidence_status == "direct" and len(f.evidence_spans) == 1
    span = f.evidence_spans[0]
    assert cl.text[span.char_start:span.char_end] == span.text == cl.text
    assert span.clause_id == "c1" and span.locator == "clause_text"


def test_multiple_passages_supported_by_schema():
    f = _flag("c1")
    f.evidence_spans = [
        EvidenceSpan(text="A", char_start=0, char_end=1, clause_id="c1", role="direct"),
        EvidenceSpan(text="B", char_start=2, char_end=3, clause_id="c2", role="contextual"),
    ]
    payload = json.loads(f.model_dump_json())
    assert len(payload["evidence_spans"]) == 2
    assert {s["role"] for s in payload["evidence_spans"]} == {"direct", "contextual"}


def test_contract_level_finding_declares_scope_and_no_span():
    f = _flag(None, "RISK_STAMP_001")
    _bind_evidence([f], [_clause()])
    assert f.evidence_spans == []
    assert f.evidence_status == "unverified"
    assert f.search_scope and "document-wide" in f.search_scope
    assert "no single supporting span" in f.search_scope


def test_missing_clause_is_unverified_not_invented():
    f = _flag("does_not_exist")
    _bind_evidence([f], [_clause()])
    assert f.evidence_spans == [] and f.evidence_status == "unverified"


def test_evidence_can_point_at_related_clause():
    f = _flag("c1")
    _bind_evidence([f], [_clause()])
    f.related_clause_ids = ["c2"]
    assert f.related_clause_ids == ["c2"] and f.evidence_status == "direct"


def test_unicode_and_punctuation_offsets_are_exact():
    text = 'Parties agree: “Cap” means ₹10,00,000 — subject to Clause 2.1; end.'
    cl = _clause(cid="c9", text=text, sec="1.3")
    f = _flag("c9")
    _bind_evidence([f], [cl])
    span = f.evidence_spans[0]
    assert cl.text[span.char_start:span.char_end] == text
    assert "₹" in span.text and "—" in span.text


def test_document_wide_search_does_not_claim_proof_of_absence():
    f = _flag(None, "MISSING_CLAUSE_GOVERNING_LAW")
    _bind_evidence([f], [_clause(), _clause(cid="c2")])
    assert f.evidence_status == "unverified"
    assert "2 clause(s)" in f.search_scope
    # no assertion of proof, and no fabricated span
    assert f.evidence_spans == []


def test_backward_compatible_defaults_and_serialization():
    old = RiskFlag(risk_id="r", rule_id="R", name="n", severity=RiskSeverity.LOW, explanation="e")
    assert old.source == "rule" and old.evidence_status == "unavailable"
    assert old.evidence_spans == [] and old.search_scope is None
    payload = json.loads(old.model_dump_json())
    assert payload["evidence_status"] == "unavailable"
    # a minimal legacy dict still validates
    again = RiskFlag.model_validate({"risk_id": "r", "rule_id": "R", "name": "n",
                                     "severity": "low", "explanation": "e"})
    assert again.evidence_spans == []


def test_apply_rules_binds_every_flag_and_preserves_severity():
    cl = _clause()
    flags = apply_rules([cl], _summary())
    assert flags, "expected at least one rule finding"
    for f in flags:
        if f.clause_id:
            assert f.evidence_spans and f.evidence_status == "direct"
            s = f.evidence_spans[0]
            assert cl.text[s.char_start:s.char_end] == s.text
        else:
            assert f.evidence_status == "unverified" and f.search_scope
    # severities/rules untouched by binding
    assert all(f.source == "rule" for f in flags)


def test_tc05_contract_level_findings_have_scope_and_clause_findings_have_text():
    from app.models.schemas import ContractType, PartySide
    from app.services.analyzer import analyse_path

    r = analyse_path(TC05, contract_id="tc05", contract_type=ContractType.OTHER,
                     user_role=PartySide.NEUTRAL, jurisdiction="India")
    by_id = {c.clause_id: c.text for c in r.clauses}
    seen_clause_level = seen_contract_level = False
    for f in r.risks:
        if f.clause_id:
            seen_clause_level = True
            assert f.evidence_spans or f.evidence_status in {"unverified", "unavailable"}
            for s in f.evidence_spans:
                assert by_id[s.clause_id][s.char_start:s.char_end] == s.text
        else:
            seen_contract_level = True
            assert f.search_scope and f.evidence_status == "unverified"
    assert seen_clause_level and seen_contract_level
