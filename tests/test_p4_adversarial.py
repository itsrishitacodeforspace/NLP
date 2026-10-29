"""Adversarial review of P4 context-aware suppression."""
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


CTX_OK = {
    "status": "complete",
    "related_clause_ids": ["rel"],
    "unresolved_references": [],
}


def _with_related(related_text):
    return {**CTX_OK, "related_clause_texts": [related_text]}


# --- Liability: cap must actually apply to the assessed liability ---

def test_liability_cap_different_party_does_not_suppress():
    c = _clause(
        "c_liab",
        "Limitation of Liability. The Customer's liability is unlimited.",
        "Limitation of Liability",
        context=_with_related(
            "Liability cap. The Provider's total liability shall not exceed fees paid."
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "cap for a different party must not suppress the finding"


def test_liability_cap_different_loss_category_does_not_suppress():
    c = _clause(
        "c_liab",
        "Limitation of Liability. Indirect and consequential damages are uncapped.",
        "Limitation of Liability",
        context=_with_related(
            "Liability cap. Direct damages shall not exceed fees paid in the preceding 12 months."
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "cap for a different loss category must not suppress"


def test_liability_cap_in_definition_only_does_not_suppress():
    c = _clause(
        "c_liab",
        "Limitation of Liability. No cap is stated.",
        "Limitation of Liability",
        context=_with_related(
            'Definitions. "Liability Cap" means the maximum liability agreed by the parties.'
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "cap mentioned only in a definition must not suppress"


def test_liability_cap_with_carveout_excluding_assessed_does_not_suppress():
    c = _clause(
        "c_liab",
        "Limitation of Liability. Indirect damages are uncapped.",
        "Limitation of Liability",
        context=_with_related(
            "Liability cap. Direct damages shall not exceed fees paid, excluding indirect damages."
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "cap that excludes the assessed liability must not suppress"


def test_liability_conflicting_provisions_keeps_finding():
    c = _clause(
        "c_liab",
        "Limitation of Liability. Liability is unlimited.",
        "Limitation of Liability",
        context=_with_related(
            "Liability cap. Provider's liability shall not exceed fees paid. "
            "Notwithstanding the foregoing, liability for IP infringement is unlimited."
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "conflicting provisions must keep the finding (ambiguous)"


def test_liability_unresolved_reference_keeps_finding():
    c = _clause(
        "c_liab",
        "Limitation of Liability. No cap stated; see Section 99.",
        "Limitation of Liability",
        context={
            "status": "partial",
            "related_clause_ids": [],
            "related_clause_texts": [
                "Liability cap. Provider's total liability shall not exceed fees paid."
            ],
            "unresolved_references": ["Section 99"],
        },
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_LIABILITY_002"]
    assert flags, "unresolved reference must not suppress"


# --- Renewal: notice must be an actual opt-out right, not a reminder ---

def test_renewal_reminder_without_optout_keeps_escalation():
    c = _clause(
        "c_ren",
        "Term and Renewal. This agreement automatically renews for successive one-year terms.",
        "Term and Renewal",
        context=_with_related(
            "Reminder. The parties will send a courtesy reminder 30 days before renewal."
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_RENEWAL_001"]
    assert flags and flags[0].severity.value == "high", \
        "a reminder without an opt-out right must keep the high-severity escalation"


def test_renewal_notice_unrelated_to_renewal_keeps_escalation():
    c = _clause(
        "c_ren",
        "Term and Renewal. This agreement automatically renews for successive one-year terms.",
        "Term and Renewal",
        context=_with_related(
            "Notice. Either party may give 30 days notice to terminate for convenience."
        ),
    )
    # termination notice != non-renewal opt-out; keep escalation
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_RENEWAL_001"]
    assert flags and "No notice period" in flags[0].explanation, \
        "generic termination notice must not be treated as a renewal opt-out"


def test_renewal_conflicting_provisions_keeps_escalation():
    c = _clause(
        "c_ren",
        "Term and Renewal. This agreement automatically renews for successive one-year terms.",
        "Term and Renewal",
        context=_with_related(
            "Opt-out. Either party may opt out with 60 days notice of non-renewal. "
            "Notwithstanding, renewal is automatic and cannot be terminated."
        ),
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_RENEWAL_001"]
    assert flags, "conflicting provisions must keep the concern"
    # Should not silently escalate to medium without evidence
    assert "No notice period" not in flags[0].explanation or flags[0].severity.value == "high"


def test_renewal_unresolved_reference_keeps_escalation():
    c = _clause(
        "c_ren",
        "Term and Renewal. This agreement automatically renews; see Section 99.",
        "Term and Renewal",
        context={
            "status": "partial",
            "related_clause_ids": [],
            "related_clause_texts": [
                "Opt-out. Either party may opt out with 60 days notice of non-renewal."
            ],
            "unresolved_references": ["Section 99"],
        },
    )
    flags = [f for f in apply_rules([c], _summary()) if f.rule_id == "RISK_RENEWAL_001"]
    assert flags and "No notice period" in flags[0].explanation, \
        "unresolved reference must not suppress the escalation"
