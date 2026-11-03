"""Regression tests for the liability and contract-level risk rules (general)."""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary, RiskFlag, RiskSeverity
from nlp.risk_scoring.rules import (
    apply_rules,
    rule_auto_renewal,
    rule_missing_stamp_duty,
    rule_section_124_indemnity,
    rule_tds_missing,
    rule_uncapped_liability,
)
from nlp.risk_scoring.scorer import score_contract


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


def _flag(rule_id: str, severity: RiskSeverity, score: float) -> RiskFlag:
    return RiskFlag(risk_id=f"{rule_id}_1", rule_id=rule_id, name=rule_id, severity=severity, explanation="e", score=score)


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


# --------------------------------------------------------------------- Section 124


def test_s124_fires_when_indemnity_lacks_direct_loss_coverage():
    clause = _clause(
        "c8",
        heading="9. Indemnification",
        text="The Provider shall indemnify the Customer against third-party claims arising from the Services.",
        types=["Indemnification"],
    )
    flag = rule_section_124_indemnity(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_S124_001"
    assert flag.severity == RiskSeverity.MEDIUM
    assert "may" in flag.explanation  # uncertain, not a confirmed defect


def test_s124_suppressed_when_direct_losses_expressly_covered():
    clause = _clause(
        "c8",
        heading="9. Indemnification",
        text="The Provider shall indemnify the Customer for direct losses and breach of contract claims.",
        types=["Indemnification"],
    )
    assert rule_section_124_indemnity(clause, _summary()) is None


def test_s124_suppressed_when_breach_of_contract_expressly_covered():
    clause = _clause(
        "c8",
        heading="9. Indemnification",
        text="The Provider shall indemnify the Customer for any breach of contract.",
        types=["Indemnification"],
    )
    assert rule_section_124_indemnity(clause, _summary()) is None


def test_s124_suppressed_when_no_indemnity_clause():
    clause = _clause("c9", heading="1. Definitions", text="Definitions only.", types=["Definitions"])
    assert rule_section_124_indemnity(clause, _summary()) is None


def test_s124_out_of_scope_for_non_indian_jurisdiction():
    clause = _clause(
        "c8",
        heading="9. Indemnification",
        text="The Provider shall indemnify the Customer against third-party claims.",
        types=["Indemnification"],
    )
    assert rule_section_124_indemnity(clause, _summary_with(jurisdiction="United States")) is None


def test_s124_not_suppressed_by_unrelated_breach_of_contract_language():
    clauses = [
        _clause(
            "c8",
            heading="9. Indemnification",
            text="The Provider shall indemnify the Customer against third-party claims.",
            types=["Indemnification"],
        ),
        _clause(
            "c9",
            heading="10. Limitation of Liability",
            text="Neither party is liable for indirect losses; this does not limit liability for breach of contract.",
            types=["Limitation of Liability"],
        ),
    ]
    findings = [f for f in apply_rules(clauses, _summary()) if f.rule_id == "RISK_S124_001"]
    assert len(findings) == 1
    assert findings[0].evidence_status == "unverified"
    assert "indemnification clauses only" in findings[0].search_scope
    assert "Verify" in findings[0].explanation


# --------------------------------------------------------------- auto-renewal notice


def _renewal(text: str) -> Clause:
    return _clause("cr", heading="3. Term and Renewal", text=text, types=["Term and Renewal"])


def test_renewal_no_notice_is_high():
    clause = _renewal("This Agreement automatically renews for successive one-year terms.")
    flag = rule_auto_renewal(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_RENEWAL_001"
    assert flag.severity == RiskSeverity.HIGH
    assert "No notice period" in flag.explanation


def test_renewal_short_notice_is_high():
    clause = _renewal(
        "This Agreement automatically renews unless either party gives notice of "
        "non-renewal at least 15 days before the end of the term."
    )
    flag = rule_auto_renewal(clause, _summary())
    assert flag is not None and flag.severity == RiskSeverity.HIGH


def test_renewal_digit_notice_is_medium():
    clause = _renewal(
        "This Agreement automatically renews unless either party gives notice of "
        "non-renewal at least 60 days before the end of the term."
    )
    flag = rule_auto_renewal(clause, _summary())
    assert flag is not None and flag.severity == RiskSeverity.MEDIUM


def test_renewal_parenthetical_notice_is_medium():
    # "sixty (60) days" is a clearly stated 60-day notice; the digit-only regex
    # previously missed it and left the finding at high severity.
    clause = _renewal(
        "This Agreement automatically renews for successive one-year terms unless "
        "either party gives written notice of non-renewal at least sixty (60) days "
        "before the end of the then-current term."
    )
    flag = rule_auto_renewal(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_RENEWAL_001"
    assert flag.severity == RiskSeverity.MEDIUM


def test_renewal_written_notice_is_medium():
    clause = _renewal(
        "This Agreement automatically renews unless either party gives notice of "
        "non-renewal at least ninety days before the end of the term."
    )
    flag = rule_auto_renewal(clause, _summary())
    assert flag is not None and flag.severity == RiskSeverity.MEDIUM


# --------------------------------------------------------------------- scoring


def test_no_findings_scores_zero_low():
    score, level, breakdown = score_contract([], [])
    assert score == 0.0 and level == RiskSeverity.LOW and breakdown == {}


def test_single_critical_finding_is_critical_but_not_100():
    score, level, breakdown = score_contract([], [_flag("RISK_LIABILITY_001", RiskSeverity.CRITICAL, 85.0)])
    assert level == RiskSeverity.CRITICAL
    assert 76.0 <= score < 100.0  # one finding does not saturate the scale
    assert breakdown["findings_by_severity"] == {"critical": 1}


def test_score_is_capped_at_100():
    flags = [_flag(f"R{i}", RiskSeverity.CRITICAL, 85.0) for i in range(15)]
    score, level, breakdown = score_contract([], flags)
    assert score == 100.0 and level == RiskSeverity.CRITICAL
    # The cap adjustment is explicit: the terms overshoot the 100 cap.
    assert breakdown["cap_adjustment"] < 0
    assert sum(breakdown[k] for k in ("top", "volume", "severity_mass", "cap_adjustment")) == score


# ----------------------------------------------------------------- data breach


def _dp_clause(text: str) -> Clause:
    return _clause("cd", heading="4. Security", text=text, types=["Data Protection"])


def test_breach_window_digit_hours_is_flagged():
    from nlp.risk_scoring.rules import rule_data_breach_window

    flag = rule_data_breach_window(_dp_clause("The Processor shall notify the Controller of any data breach within 24 hours."), _summary())
    assert flag is not None and flag.rule_id == "RISK_DATA_001"


def test_breach_window_written_compound_with_parenthetical_is_flagged():
    from nlp.risk_scoring.rules import rule_data_breach_window

    flag = rule_data_breach_window(
        _dp_clause("The Processor shall notify the Controller of any security incident within twenty-four (24) hours."),
        _summary(),
    )
    assert flag is not None and flag.rule_id == "RISK_DATA_001"


def test_breach_window_written_compound_without_parenthetical_is_flagged():
    from nlp.risk_scoring.rules import rule_data_breach_window

    flag = rule_data_breach_window(
        _dp_clause("The Provider shall report any data breach within twenty-four hours."),
        _summary(),
    )
    assert flag is not None and flag.rule_id == "RISK_DATA_001"


def test_breach_window_loose_periods_are_not_flagged():
    from nlp.risk_scoring.rules import rule_data_breach_window

    for text in (
        "The Processor shall notify the Controller of any data breach within 48 hours.",
        "The Processor shall notify the Controller of any data breach within seventy-two (72) hours.",
        "The Processor shall notify the Controller of any data breach within 2 days.",
    ):
        assert rule_data_breach_window(_dp_clause(text), _summary()) is None, text


def test_breach_window_one_day_boundary_is_flagged():
    from nlp.risk_scoring.rules import rule_data_breach_window

    flag = rule_data_breach_window(
        _dp_clause("The Processor shall notify the Controller of any security incident within 1 day."),
        _summary(),
    )
    assert flag is not None and flag.rule_id == "RISK_DATA_001"
