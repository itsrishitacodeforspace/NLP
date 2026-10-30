"""P4: cross-reference analysis produces an advisory, non-suppressing note."""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary, ContractType
from nlp.risk_scoring.rules import apply_rules


def _clause(cid, text, ctype, context=None):
    return Clause(clause_id=cid, text=text, clause_types=[ctype], context=context)


def _summary():
    return ContractSummary(
        contract_id="t", title="t", file_name="t.txt",
        contract_type=ContractType.OTHER, jurisdiction="India",
    )


def _liability_flags(clause):
    return [f for f in apply_rules([clause], _summary()) if f.rule_id == "RISK_LIABILITY_002"]


def test_missing_reference_is_recorded():
    c = _clause(
        "c7",
        "Limitation of Liability. Liability is subject to Section 99.",
        "Limitation of Liability",
        context={"references": [{"raw": "Section 99", "status": "missing"}],
                 "related_clause_ids": [], "unresolved_references": ["Section 99"]},
    )
    flags = _liability_flags(c)
    assert flags, "finding must not be suppressed"
    assert flags[0].cross_reference_note is not None
    assert "missing reference" in flags[0].cross_reference_note
    assert "advisory" in flags[0].cross_reference_note


def test_ambiguous_reference_is_recorded():
    c = _clause(
        "c7",
        "Limitation of Liability. Liability is subject to Section 1.",
        "Limitation of Liability",
        context={"references": [{"raw": "Section 1", "status": "ambiguous"}],
                 "related_clause_ids": [], "unresolved_references": []},
    )
    flags = _liability_flags(c)
    assert flags and "ambiguous reference" in flags[0].cross_reference_note


def test_resolved_related_clause_is_recorded_with_text_and_kept_advisory():
    # The referenced cap excludes indirect damages, so it does NOT verifiably
    # cover the assessed liability: the finding stands and the advisory note
    # surfaces the considered text. (A resolved, fully applicable cap now
    # suppresses the finding — see tests/test_p4_cap_resolution.py.)
    c = _clause(
        "c7",
        "Limitation of Liability. Liability is subject to Section 7.4.",
        "Limitation of Liability",
        context={
            "references": [{"raw": "Section 7.4", "status": "resolved", "target_clause_ids": ["c7_4"]}],
            "related_clause_ids": ["c7_4"],
            "related_clause_texts": ["Each party's total liability shall not exceed the fees paid, excluding indirect damages."],
            "unresolved_references": [],
        },
    )
    flags = _liability_flags(c)
    assert flags, "a cap that excludes the assessed liability must not suppress the finding"
    note = flags[0].cross_reference_note
    assert note is not None
    assert "related clause" in note
    assert "shall not exceed" in note  # the considered related text is surfaced
    assert "advisory" in note
    assert "c7_4" in flags[0].related_clause_ids


def test_matching_keyword_in_related_clause_does_not_resolve():
    c = _clause(
        "c7",
        "Limitation of Liability. Liability is subject to Section 7.4.",
        "Limitation of Liability",
        context={
            "references": [{"raw": "Section 7.4", "status": "resolved", "target_clause_ids": ["c7_4"]}],
            "related_clause_ids": ["c7_4"],
            "related_clause_texts": ["Liability cap. Total liability shall not exceed the fees paid."],
            "unresolved_references": [],
        },
    )
    flags = _liability_flags(c)
    assert flags, "keyword presence in a related clause must not suppress"
    # The note is advisory, never a claim of resolution.
    assert "advisory" in flags[0].cross_reference_note
    assert "resolved" not in flags[0].cross_reference_note.lower().replace("unresolved", "")


def test_no_related_clauses_produces_no_note():
    c = _clause("c7", "Limitation of Liability. No cap is stated.", "Limitation of Liability")
    flags = _liability_flags(c)
    assert flags and flags[0].cross_reference_note is None
