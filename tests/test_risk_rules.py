"""Regression tests for the liability and contract-level risk rules (general)."""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary, RiskSeverity
from nlp.risk_scoring.rules import (
    rule_missing_stamp_duty,
    rule_tds_missing,
    rule_uncapped_liability,
)


def _summary() -> ContractSummary:
    return ContractSummary(contract_id="x", title="t", file_name="f.txt", jurisdiction="India")


def _summary_with(*, jurisdiction: str = "India", stamp: bool = False, tds: bool = False) -> ContractSummary:
    return ContractSummary(
        contract_id="x",
        title="t",
        file_name="f.txt",
        jurisdiction=jurisdiction,
        stamp_duty_mentioned=stamp,
        tds_mentioned=tds,
    )


def _clause(cid: str, *, heading: str, text: str, types: list[str]) -> Clause:
    return Clause(clause_id=cid, heading=heading, text=text, clause_types=types)


# --------------------------------------------------------------------------- liability


def test_indemnification_clause_is_not_treated_as_liability():
    clause = _clause(
        "c1",
        heading="5. Indemnification",
        text="The Provider shall indemnify and hold harmless the Customer against any and all claims, losses, damages and expenses.",
        types=["Limitation of Liability", "Indemnification"],
    )
    assert rule_uncapped_liability(clause, _summary()) is None


def test_uncapped_liability_is_detected():
    clause = _clause(
        "c2",
        heading="6. Limitation of Liability",
        text="The Provider shall have unlimited liability for all losses arising under this Agreement.",
        types=["Limitation of Liability"],
    )
    flag = rule_uncapped_liability(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_LIABILITY_001"


def test_capped_liability_is_not_flagged():
    clause = _clause(
        "c3",
        heading="6. Limitation of Liability",
        text="Each party's total aggregate liability shall not exceed the fees paid in the prior 12 months.",
        types=["Limitation of Liability"],
    )
    assert rule_uncapped_liability(clause, _summary()) is None


def test_missing_cap_is_detected():
    clause = _clause(
        "c4",
        heading="6. Limitation of Liability",
        text="Each party's liability for breach of this Agreement is allocated as set out herein.",
        types=["Limitation of Liability"],
    )
    flag = rule_uncapped_liability(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_LIABILITY_002"


# ----------------------------------------------------------------------- stamp duty


def test_stamp_duty_not_detected_is_review_not_critical():
    clause = _clause("c5", heading="1. Definitions", text="Definitions only.", types=["Definitions"])
    flag = rule_missing_stamp_duty(clause, _summary_with(stamp=False))
    assert flag is not None and flag.rule_id == "RISK_STAMP_001"
    assert flag.severity == RiskSeverity.MEDIUM  # "not found" is not "confirmed absent"
    assert "not found" in flag.explanation


def test_stamp_duty_mentioned_suppresses_finding():
    clause = _clause("c5", heading="1. Definitions", text="Definitions only.", types=["Definitions"])
    assert rule_missing_stamp_duty(clause, _summary_with(stamp=True)) is None


def test_stamp_duty_out_of_scope_for_non_indian_jurisdiction():
    clause = _clause("c5", heading="1. Definitions", text="Definitions only.", types=["Definitions"])
    assert rule_missing_stamp_duty(clause, _summary_with(jurisdiction="United States", stamp=False)) is None


# ------------------------------------------------------------------------------ TDS


def test_tds_not_detected_is_review():
    clause = _clause("c6", heading="3. Payment Terms", text="Customer shall pay fees within 30 days.", types=["Payment Terms"])
    flag = rule_tds_missing(clause, _summary_with(tds=False))
    assert flag is not None and flag.rule_id == "RISK_TDS_001"
    assert flag.severity == RiskSeverity.LOW
    assert "not found" in flag.explanation


def test_tds_mentioned_suppresses_finding():
    clause = _clause("c6", heading="3. Payment Terms", text="Fees subject to TDS.", types=["Payment Terms"])
    assert rule_tds_missing(clause, _summary_with(tds=True)) is None


def test_tds_out_of_scope_for_non_indian_jurisdiction():
    clause = _clause("c6", heading="3. Payment Terms", text="Fees.", types=["Payment Terms"])
    assert rule_tds_missing(clause, _summary_with(jurisdiction="United Kingdom", tds=False)) is None


def test_tds_requires_payment_terms_clause():
    clause = _clause("c7", heading="4. Confidentiality", text="Keep information secret.", types=["Confidentiality"])
    assert rule_tds_missing(clause, _summary_with(tds=False)) is None
