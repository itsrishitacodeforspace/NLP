"""Regression tests for the liability risk rules (general, not fixture-specific)."""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary
from nlp.risk_scoring.rules import rule_uncapped_liability


def _summary() -> ContractSummary:
    return ContractSummary(contract_id="x", title="t", file_name="f.txt", jurisdiction="India")


def _clause(cid: str, *, heading: str, text: str, types: list[str]) -> Clause:
    return Clause(clause_id=cid, heading=heading, text=text, clause_types=types)


def test_indemnification_clause_is_not_treated_as_liability():
    # An indemnification clause (heading says so) is not a limitation-of-liability
    # clause even if the classifier also attached that label.
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
