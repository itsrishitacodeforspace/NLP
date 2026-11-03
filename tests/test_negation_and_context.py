"""Regression tests for negation-aware risk rules, context-gated seat detection,
notice-period vs duration, governing-law coverage, obligation severity, and
tight evidence spans (DEEP_AUDIT C3-C7)."""
from __future__ import annotations

from app.models.schemas import Clause, ContractSummary, ContractType, RiskSeverity
from nlp.ner.ner import detect_arbitration_seat, extract_entities
from nlp.obligation_extraction.extractor import extract_obligations_from_clause
from nlp.risk_scoring.rules import (
    apply_rules,
    rule_broad_indemnity,
    rule_governing_law_mismatch,
    rule_uncapped_liability,
)


def _summary(jurisdiction: str = "India") -> ContractSummary:
    return ContractSummary(
        contract_id="t", title="t", file_name="t.txt",
        contract_type=ContractType.OTHER, jurisdiction=jurisdiction,
    )


def _clause(cid: str, text: str, *types: str) -> Clause:
    return Clause(clause_id=cid, text=text, clause_types=list(types))


# ---------------------------------------------------------------------------
# C5: negation blindness in risk rules
# ---------------------------------------------------------------------------


def test_negated_uncapped_liability_is_not_flagged():
    """'neither party shall be unlimited' is a NEGATION of unlimited liability."""
    clause = _clause(
        "c1",
        "The liability of neither party shall be unlimited or uncapped; "
        "all claims are capped at fees paid.",
        "Limitation of Liability",
    )
    assert rule_uncapped_liability(clause, _summary()) is None


def test_negated_indemnity_is_not_flagged():
    """'the indemnity does not extend to any and all claims' narrows scope."""
    clause = _clause(
        "c2",
        "The indemnity does not extend to any and all claims; "
        "it covers only third-party IP claims.",
        "Indemnification",
    )
    assert rule_broad_indemnity(clause, _summary()) is None


def test_cap_present_suppresses_missing_cap_finding():
    """A clause that explicitly caps liability must not fire RISK_LIABILITY_002."""
    clause = _clause(
        "c3",
        "All claims are capped at fees paid in the preceding 12 months.",
        "Limitation of Liability",
    )
    assert rule_uncapped_liability(clause, _summary()) is None


def test_cap_with_shall_not_exceed_suppresses_missing_cap():
    clause = _clause(
        "c4",
        "Each party's total aggregate liability shall not exceed the fees paid.",
        "Limitation of Liability",
    )
    assert rule_uncapped_liability(clause, _summary()) is None


def test_uncapped_liability_still_fires_on_positive_phrasing():
    clause = _clause(
        "c5",
        "The Provider shall have unlimited liability for all losses arising under this Agreement.",
        "Limitation of Liability",
    )
    flag = rule_uncapped_liability(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_LIABILITY_001"


def test_broad_indemnity_still_fires_on_positive_phrasing():
    clause = _clause(
        "c6",
        "The Provider shall indemnify and hold harmless the Customer "
        "against any and all claims, losses, damages and expenses.",
        "Indemnification",
    )
    flag = rule_broad_indemnity(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_INDEMNITY_001"


def test_missing_cap_still_fires_without_cap_language():
    clause = _clause(
        "c7",
        "Each party's liability for breach of this Agreement is allocated as set out herein.",
        "Limitation of Liability",
    )
    flag = rule_uncapped_liability(clause, _summary())
    assert flag is not None and flag.rule_id == "RISK_LIABILITY_002"


def test_negated_cap_phrase_does_not_suppress_missing_cap():
    """'there is no limitation of liability' is NOT cap language."""
    clause = _clause(
        "c8",
        "There is no limitation of liability in this Agreement.",
        "Limitation of Liability",
    )
    flag = rule_uncapped_liability(clause, _summary())
    # "no limitation" triggers the uncapped trigger, so this fires 001 not 002.
    assert flag is not None


# ---------------------------------------------------------------------------
# C3: NOTICE_PERIOD_RE over-match on bare durations
# ---------------------------------------------------------------------------


def test_bare_durations_are_not_notice_periods():
    result = extract_entities(
        "The initial term of this Agreement is 90 days. "
        "The warranty period is 12 months."
    )
    labels = [e.label for e in result.entities]
    assert "NOTICE_PERIOD" not in labels, labels
    # Bare durations are emitted as DURATION.
    assert "DURATION" in labels


def test_real_notice_period_is_still_labelled():
    result = extract_entities(
        "Either party may give 30 days prior written notice of non-renewal."
    )
    labels = [(e.label, e.text) for e in result.entities if e.label == "NOTICE_PERIOD"]
    assert labels, "expected a NOTICE_PERIOD entity"
    assert labels[0][1].startswith("30 days")


def test_within_prefix_is_still_a_notice_period():
    result = extract_entities(
        "The Processor shall notify the Controller of any data breach within 24 hours."
    )
    labels = [(e.label, e.text) for e in result.entities if e.label == "NOTICE_PERIOD"]
    assert any("24 hours" in t for _, t in labels)


def test_notice_entity_text_has_no_leading_whitespace():
    result = extract_entities("Either party shall give 30 days written notice.")
    for e in result.entities:
        if e.label == "NOTICE_PERIOD":
            assert not e.text.startswith(" "), repr(e.text)
            assert not e.text.endswith(" "), repr(e.text)


# ---------------------------------------------------------------------------
# C4: arbitration seat any-city false positive
# ---------------------------------------------------------------------------


def test_city_in_payment_address_is_not_an_arbitration_seat():
    assert detect_arbitration_seat(
        "All payments shall be made to our bank account in Mumbai, India. "
        "There is no arbitration clause in this agreement."
    ) is None


def test_city_in_data_hosting_is_not_an_arbitration_seat():
    assert detect_arbitration_seat(
        "The data shall be hosted in Singapore. "
        "Notices shall be sent to the addresses listed in Annex A."
    ) is None


def test_city_in_arbitration_sentence_is_a_seat():
    assert detect_arbitration_seat(
        "Any dispute shall be finally settled by arbitration seated in London."
    ) == "London"


def test_explicit_seat_of_arbitration_still_works():
    assert detect_arbitration_seat(
        "The seat of arbitration shall be Singapore. "
        "The venue of arbitration shall be Mumbai."
    ) == "Singapore"


def test_indian_city_in_arbitration_context_is_a_seat():
    assert detect_arbitration_seat(
        "All disputes shall be resolved by arbitration in Mumbai, India."
    ) == "Mumbai"


def test_no_arbitration_context_no_seat():
    assert detect_arbitration_seat(
        "The parties are based in Chennai and Bengaluru. "
        "Payments are due within 30 days."
    ) is None


# ---------------------------------------------------------------------------
# C6: governing law false negatives
# ---------------------------------------------------------------------------


def _gov_law(phrase: str) -> Clause:
    return _clause("g1", f"This Agreement is {phrase}.", "Governing Law")


def test_foreign_law_republic_of_singapore_fires():
    flag = rule_governing_law_mismatch(_gov_law("governed by the laws of the Republic of Singapore"), _summary())
    assert flag is not None and flag.rule_id == "RISK_GOV_001"


def test_foreign_law_delaware_fires():
    flag = rule_governing_law_mismatch(_gov_law("governed by the laws of Delaware"), _summary())
    assert flag is not None and flag.rule_id == "RISK_GOV_001"


def test_foreign_law_new_york_fires():
    flag = rule_governing_law_mismatch(_gov_law("governed by the laws of the State of New York"), _summary())
    assert flag is not None and flag.rule_id == "RISK_GOV_001"


def test_foreign_law_england_wales_fires():
    flag = rule_governing_law_mismatch(_gov_law("governed by the laws of England and Wales"), _summary())
    assert flag is not None and flag.rule_id == "RISK_GOV_001"


def test_indian_law_does_not_fire():
    assert rule_governing_law_mismatch(_gov_law("governed by the laws of India"), _summary()) is None


def test_indian_state_law_does_not_fire():
    assert rule_governing_law_mismatch(_gov_law("governed by the laws of the State of Maharashtra"), _summary()) is None


def test_indian_law_short_form_does_not_fire():
    assert rule_governing_law_mismatch(_gov_law("governed by Indian law"), _summary()) is None


def test_non_indian_jurisdiction_does_not_fire():
    summary = _summary(jurisdiction="United States")
    assert rule_governing_law_mismatch(_gov_law("governed by the laws of Delaware"), summary) is None


# ---------------------------------------------------------------------------
# C7: obligation severity decoupled from deadline urgency
# ---------------------------------------------------------------------------


def test_one_hour_typo_notice_is_not_critical():
    o = extract_obligations_from_clause(
        "c1",
        "The Provider shall notify the Client within one hour of discovering a typo in the invoice.",
    )[0]
    assert o.risk_level != RiskSeverity.CRITICAL
    assert o.risk_level == RiskSeverity.MEDIUM


def test_thirty_day_indemnity_is_high():
    o = extract_obligations_from_clause(
        "c1",
        "The Provider shall indemnify the Client within 30 days of a data breach.",
    )[0]
    assert o.risk_level == RiskSeverity.HIGH


def test_one_hour_indemnity_is_critical():
    """Urgent deadline on HIGH content gets the +1 boost to CRITICAL."""
    o = extract_obligations_from_clause(
        "c1",
        "The Provider shall indemnify the Client within one hour of a data breach.",
    )[0]
    assert o.risk_level == RiskSeverity.CRITICAL


def test_thirty_day_pay_is_high_not_medium():
    o = extract_obligations_from_clause(
        "c1",
        "The Customer shall pay the invoice within 30 days.",
    )[0]
    assert o.risk_level == RiskSeverity.HIGH


# ---------------------------------------------------------------------------
# C6 (evidence spans): tight spans slice the exact source
# ---------------------------------------------------------------------------


def test_evidence_span_is_tight_sentence_slice():
    clause = _clause(
        "c1",
        "The Provider shall have unlimited liability for all losses. "
        "This is a second sentence that should not be in the span.",
        "Limitation of Liability",
    )
    flags = apply_rules([clause], _summary())
    liab = [f for f in flags if f.rule_id == "RISK_LIABILITY_001" and f.clause_id]
    assert liab, "expected RISK_LIABILITY_001"
    for span in liab[0].evidence_spans:
        assert clause.text[span.char_start:span.char_end] == span.text
        # The span should be the first sentence, not the whole clause.
        assert "second sentence" not in span.text


def test_evidence_span_falls_back_to_full_clause_when_no_trigger():
    """A rule without a trigger phrase gets the full clause as evidence."""
    clause = _clause(
        "c1",
        "The Provider may terminate this Agreement at any time.",
        "Termination",
    )
    flags = apply_rules([clause], _summary())
    term = [f for f in flags if f.rule_id == "RISK_TERM_001" and f.clause_id]
    assert term, "expected RISK_TERM_001"
    for span in term[0].evidence_spans:
        assert clause.text[span.char_start:span.char_end] == span.text
