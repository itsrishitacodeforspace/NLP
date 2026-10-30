"""Audit-only integration tests (zero-trust audit, 2026-10-30).

Two kinds of tests live here:

* **Passing integration tests** — lock cross-feature behaviour that was
  verified empirically at the audit commit (offsets, cross-reference caps,
  obligations, dedupe, fail-safety, evidence invariants). They must keep
  passing.

* **xfail(strict=True) defect records** — each documents a confirmed
  integration defect (AUDIT-D1 .. AUDIT-D6) with the *derived* expected
  behaviour. They fail today; strict xfail means the suite goes red the day a
  fix makes them pass, forcing the record to be updated. They do not weaken
  any existing test.

See ``reports/audit/integration_audit_20261030.md`` for evidence and analysis.
"""
from __future__ import annotations

import pytest

from app.models.schemas import ContractType, PartySide
from app.services.analyzer import analyse_bytes
from app.services.segmenter import segment_clauses


def _run(text: str, cid: str = "audit"):
    return analyse_bytes(
        text.encode(), f"{cid}.txt", contract_id=cid,
        contract_type=ContractType.OTHER, user_role=PartySide.NEUTRAL,
        jurisdiction="India",
    )


def _rule_ids(result):
    return [f.rule_id for f in result.risks]


# ---------------------------------------------------------------------------
# Passing integration tests (verified-good cross-feature behaviour)
# ---------------------------------------------------------------------------


def test_crossref_cap_in_indemnity_clause_with_exclusion_keeps_finding():
    """A cap referenced from an LoL clause but living in an indemnity clause,
    with exclusions, must NOT suppress the missing-cap finding."""
    r = _run(
        "7.1 LIMITATION OF LIABILITY\n"
        "Except as set out in Clause 9, neither party shall be liable for indirect damages.\n\n"
        "9. INDEMNIFICATION\n"
        "The Provider shall indemnify the Customer against third party claims. "
        "Each party's aggregate liability shall not exceed the fees paid, "
        "excluding indirect and consequential damages."
    )
    flags = [f for f in r.risks if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "excluding cap must keep the human-review finding"
    assert flags[0].cross_reference_note is not None
    assert "advisory" in flags[0].cross_reference_note


def test_crossref_cap_for_different_party_keeps_finding():
    r = _run(
        "7.1 LIMITATION OF LIABILITY\n"
        "The Customer's liability under this Agreement is subject to Clause 7.4.\n\n"
        "7.4 LIABILITY CAP\n"
        "The Provider's total liability shall not exceed the fees paid."
    )
    assert "RISK_LIABILITY_002" in _rule_ids(r)


def test_crossref_applicable_cap_suppresses_finding_end_to_end():
    """Positive control for D14: resolved, mutual, exclusion-free cap."""
    r = _run(
        "7.1 LIMITATION OF LIABILITY\n"
        "Except as set out in Clause 7.4, neither party shall be liable for indirect damages.\n\n"
        "7.4 LIABILITY CAP\n"
        "Each party's aggregate liability shall not exceed the total fees paid "
        "under this Agreement in the preceding 12 months."
    )
    assert "RISK_LIABILITY_002" not in _rule_ids(r)


def test_compound_deadline_with_condition_and_beneficiary_preserved():
    r = _run(
        "4. SECURITY\nIf a breach occurs, the Processor shall notify the "
        "Controller within twenty-four (24) hours."
    )
    assert len(r.obligations) == 1
    o = r.obligations[0]
    assert o.subject == "Processor"
    assert o.counterparty == "Controller"
    assert o.condition == "If a breach occurs"
    assert o.deadline_expression == "24 hours"


def test_passive_with_non_party_agent_phrase_stays_unknown():
    r = _run("4. SECURITY\nPersonal data shall be encrypted by the data processing team.")
    assert len(r.obligations) == 1
    assert r.obligations[0].subject is None


def test_missing_reference_is_advisory_and_finding_kept():
    r = _run("7. LIMITATION OF LIABILITY\nLiability is subject to Section 99; no cap is stated.")
    flags = [f for f in r.risks if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "unresolved reference must not suppress"
    assert "missing reference" in (flags[0].cross_reference_note or "")
    contract_level = [f for f in r.risks if f.clause_id is None and f.source != "model"]
    assert contract_level, "expected contract-level findings"
    for f in contract_level:
        assert f.evidence_status == "unverified" and f.search_scope


def test_rule_layer_dedupes_repeated_rule_ids():
    r = _run(
        "7.1 LIMITATION OF LIABILITY\nNeither party shall be liable for indirect damages.\n\n"
        "7.2 EXCLUSIONS\nEach party excludes all implied warranties; liability is not limited."
    )
    assert _rule_ids(r).count("RISK_LIABILITY_002") <= 1


def test_no_contradiction_between_present_and_missing_liability_channels():
    """A clause classified LoL without a cap yields the cap finding and must
    NOT simultaneously yield the missing-clause finding for the same type."""
    r = _run("7. LIMITATION OF LIABILITY\nNeither party shall be liable for indirect damages.")
    ids = _rule_ids(r)
    assert "RISK_LIABILITY_002" in ids
    assert "MISSING_CLAUSE_LIMITATION_OF_LIABILITY" not in ids


def test_cross_referenced_obligations_stay_clause_local():
    """Each clause yields only its own obligations; a referenced clause's
    duties are not imported (cross-reference handling is advisory-only)."""
    r = _run(
        "2. DELIVERY\nSubject to Clause 5, the Provider shall deliver within twenty-four days.\n\n"
        "5. ACCEPTANCE\nThe Customer shall accept conforming goods within 10 days."
    )
    by_clause = {}
    for o in r.obligations:
        by_clause.setdefault(o.clause_id, []).append(o)
    delivery = [o for c in by_clause for o in by_clause[c] if o.subject == "Provider"]
    assert len(delivery) == 1
    assert delivery[0].condition == "Subject to Clause 5"
    assert delivery[0].deadline_expression == "24 days"


def test_offsets_exact_for_double_newline_layout():
    text = (
        "1. PAYMENT\n\nThe Customer shall pay within 30 days.\n\n"
        "2. TERMINATION\n\nThe Provider may terminate for cause."
    )
    for c in segment_clauses(text, contract_id="off"):
        assert text[c.char_start:c.char_end] == c.text


def test_taxonomy_and_classifier_rule_keys_stay_in_sync():
    """Drift guard: the taxonomy sync contract is comment-only; lock it here."""
    from nlp.clause_classification.classifier import CLAUSE_RULES, HEADING_HINTS
    from nlp.taxonomy import INTERNAL_LABELS

    labels = set(INTERNAL_LABELS)
    assert set(CLAUSE_RULES) <= labels
    assert set(HEADING_HINTS.values()) <= labels


def test_rule_exception_is_skipped_and_other_findings_survive(monkeypatch):
    """Fail-safe: a rule that raises must not take down the rule pass."""
    from nlp.risk_scoring import rules

    def _boom(clause, summary):
        raise RuntimeError("deliberate audit fault")

    monkeypatch.setattr(rules.RISK_RULES[0], "check", _boom)
    clauses = [
        # one termination clause so a different rule still fires
    ]
    from app.models.schemas import Clause
    clauses.append(Clause(clause_id="c1", text="The Provider may terminate this agreement at any time.",
                          clause_types=["Termination"]))
    from app.models.schemas import ContractSummary
    flags = rules.apply_rules(clauses, ContractSummary(contract_id="t", title="t", file_name="t.txt"))
    assert any(f.rule_id == "RISK_TERM_001" for f in flags)


def test_ml_booster_findings_stay_unverified_even_on_suppressed_clauses():
    """When cross-reference verification clears the rule finding, the ML
    booster may still suggest risk — but only as unverified model output."""
    r = _run(
        "7.1 LIMITATION OF LIABILITY\n"
        "Except as set out in Clause 7.4, neither party shall be liable for indirect damages.\n\n"
        "7.4 LIABILITY CAP\n"
        "Each party's aggregate liability shall not exceed the total fees paid "
        "under this Agreement in the preceding 12 months."
    )
    for f in r.risks:
        if f.rule_id == "ML_RISK_001":
            assert f.source == "model" and f.evidence_status == "unverified"


def test_applicable_stamp_and_tds_mentions_still_suppress_prompts():
    """Positive controls for the D4 negation defect: protective mentions must
    keep suppressing the review prompts."""
    r = _run(
        "2. PAYMENT\nThe Customer shall pay invoices within 30 days, subject to "
        "deduction of tax at source under the Income Tax Act, 1961. "
        "This Agreement is executed on duly stamped paper."
    )
    ids = _rule_ids(r)
    assert "RISK_STAMP_001" not in ids
    assert "RISK_TDS_001" not in ids


# ---------------------------------------------------------------------------
# Defect records — xfail(strict=True). Derived expected behaviour, evidence in
# reports/audit/integration_audit_20261030.md. Suite goes red when fixed.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="AUDIT-D1: heading+body separated by a single newline reconstructs "
                                       "Clause.text with a synthetic \\n\\n, so char offsets do not slice the source")
def test_d1_clause_offsets_slice_source_for_single_newline_headings():
    text = (
        "7.1 LIMITATION OF LIABILITY\n"
        "Except as set out in Clause 7.4, neither party shall be liable.\n\n"
        "7.4 LIABILITY CAP\n"
        "Each party's aggregate liability shall not exceed the fees paid."
    )
    for c in segment_clauses(text, contract_id="d1"):
        assert text[c.char_start:c.char_end] == c.text


@pytest.mark.xfail(strict=True, reason="AUDIT-D2: a multi-line preamble paragraph keeps only its first "
                                       "line; remaining lines are silently dropped from every clause")
def test_d2_segmentation_does_not_lose_preamble_lines():
    text = (
        "This Agreement is made today.\nIt is between A and B.\n\n"
        "1. PAYMENT\nThe Customer shall pay within 30 days."
    )
    clauses = segment_clauses(text, contract_id="d2")
    assert any("between A and B" in c.text for c in clauses)


@pytest.mark.xfail(strict=True, reason="AUDIT-D3: long-clause sub-offsets assume \\n\\n separators and "
                                       "ignore the heading length, so split-clause offsets drift")
def test_d3_long_clause_sub_offsets_slice_source():
    body = (
        "The Supplier shall not be liable for failures beyond its reasonable control, "
        "including acts of God, war, terrorism, civil unrest, government action, pandemic, "
        "epidemic, natural disaster, fire, flood, earthquake, or failure of networks. "
    ) * 6
    text = "1. FORCE MAJEURE\n" + body
    for c in segment_clauses(text, contract_id="d3", long_threshold=600):
        assert text[c.char_start:c.char_end] == c.text


@pytest.mark.xfail(strict=True, reason="AUDIT-D4: negated/disclaiming statutory mentions suppress the "
                                       "stamp/TDS review prompts exactly when review is most needed")
def test_d4_negated_tds_mention_still_prompts_review():
    r = _run(
        "2. PAYMENT\nThe Customer shall pay invoices within 30 days. "
        "Payments shall be made without deduction of tax at source."
    )
    assert "RISK_TDS_001" in _rule_ids(r)


@pytest.mark.xfail(strict=True, reason="AUDIT-D4: negated stamp-duty mention suppresses the review prompt")
def test_d4_negated_stamp_mention_still_prompts_review():
    r = _run(
        "2. PAYMENT\nThe Customer shall pay invoices within 30 days. "
        "This Agreement was not executed on duly stamped paper."
    )
    assert "RISK_STAMP_001" in _rule_ids(r)


@pytest.mark.xfail(strict=True, reason="AUDIT-D5: the breach-window rule parses digit-only notice "
                                       "periods while the obligation layer normalises written numbers")
def test_d5_written_number_breach_window_is_flagged():
    r = _run(
        "4. SECURITY\nThe Processor shall notify the Controller of any security "
        "incident within twenty-four (24) hours."
    )
    assert "RISK_DATA_001" in _rule_ids(r)


@pytest.mark.xfail(strict=True, reason="AUDIT-D6: _detect_parties treats 'services' as a noise word and "
                                       "silently drops a party whose legal name contains it")
def test_d6_similar_party_names_are_both_detected():
    r = _run(
        "1. PARTIES\nThis Agreement is between ABC Services Pvt Ltd (the Customer) "
        "and ABC Technologies Pvt Ltd (the Provider)."
    )
    names = " | ".join(r.contract.parties)
    assert "ABC Services" in names and "ABC Technologies" in names
