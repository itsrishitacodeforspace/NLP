"""P4: whole-contract context integration in liability/renewal rules.

After adversarial review, suppression based on keyword presence in a related
clause was found to be unsafe (a cap for a different party/loss category, a
cap mentioned only in a definition, or a reminder rather than an opt-out right
could wrongly suppress a genuine finding). The current implementation therefore
preserves findings and records context as advisory only.
"""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary, ContractType
from nlp.risk_scoring.rules import apply_rules


def _clause(cid, text, ctype, context=None):
    return Clause(
        clause_id=cid,
        text=text,
        clause_types=[ctype],
        context=context,
    )


def _summary():
    return ContractSummary(
        contract_id="t", title="t", file_name="t.txt",
        contract_type=ContractType.OTHER, jurisdiction="India",
    )


def test_liability_cap_in_related_clause_does_not_suppress():
    c = _clause(
        "c7",
        "Limitation of Liability. Provider's liability is subject to Section 7.4.",
        "Limitation of Liability",
        context={
            "status": "complete",
            "related_clause_ids": ["c7_4"],
            "related_clause_texts": [
                "Liability cap. Provider's total liability shall not exceed fees paid in the preceding 12 months."
            ],
            "unresolved_references": [],
        },
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "keyword presence in a related clause must not suppress the finding"


def test_liability_cap_absent_everywhere_still_flags():
    c = _clause(
        "c7",
        "Limitation of Liability. Provider's liability is subject to Section 7.4.",
        "Limitation of Liability",
        context={
            "status": "complete",
            "related_clause_ids": ["c7_4"],
            "related_clause_texts": ["Section 7.4 has no cap language at all."],
            "unresolved_references": [],
        },
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "no cap anywhere should still flag"


def test_renewal_notice_in_related_clause_does_not_suppress_escalation():
    c = _clause(
        "c1",
        "Term and Renewal. This agreement automatically renews for successive one-year terms.",
        "Term and Renewal",
        context={
            "status": "complete",
            "related_clause_ids": ["c2"],
            "related_clause_texts": [
                "Notice. Either party may terminate by giving 60 days notice of non-renewal."
            ],
            "unresolved_references": [],
        },
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_RENEWAL_001"]
    assert flags, "auto-renewal finding should still fire"
    # A notice in a related clause is advisory; the escalation is preserved
    # because applicability (opt-out right vs reminder) cannot be verified.
    assert "No notice period" in flags[0].explanation
