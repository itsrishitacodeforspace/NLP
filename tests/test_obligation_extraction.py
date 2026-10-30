"""Regression tests for obligation extraction correctness."""
from __future__ import annotations

from nlp.obligation_extraction.extractor import extract_obligations_from_clause


def _one(text: str):
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 1, obligations
    return obligations[0]


def test_written_out_number_with_parenthetical_digit():
    o = _one("The Customer shall pay the invoice within thirty (30) days of receipt.")
    assert o.deadline_expression == "30 days"


def test_calendar_date_populates_deadline_date_not_expression():
    o = _one("The Customer shall pay on or before 15 April 2024.")
    assert o.deadline_date == "15 April 2024"
    assert o.deadline_expression is None


def test_passive_voice_uses_agent_as_subject():
    o = _one("The services shall be provided by the Provider.")
    assert o.subject == "Provider"


def test_passive_voice_without_agent_leaves_subject_unknown():
    o = _one("The services shall be provided.")
    assert o.subject is None


def test_prohibition_subject_and_action():
    o = _one("The Customer shall not disclose the confidential information.")
    assert o.subject == "Customer"
    assert o.action == "disclose"
    assert o.obligation_type.value == "prohibition"


def test_offsets_are_exact_source_slices():
    text = "2.1 The Provider shall deliver the report. The Customer shall pay the invoice."
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 2
    for o in obligations:
        assert o.char_start is not None and o.char_end is not None
        assert text[o.char_start:o.char_end] == o.text


def test_repeated_sentences_leave_offsets_unknown():
    text = "Each party shall keep information secret. Each party shall keep information secret."
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 2
    assert all(o.char_start is None and o.char_end is None for o in obligations)


def test_counterparty_is_not_greedy_around_amounts():
    o = _one("The Customer shall pay the Supplier INR 100000.")
    assert o.subject == "Customer"
    assert o.counterparty == "Supplier"


def test_beneficiary_recipient_patterns():
    cases = [
        ("The Provider shall deliver the report to the Customer.", "Provider", "Customer"),
        ("The Customer shall pay the Supplier INR 100000.", "Customer", "Supplier"),
        ("The Supplier shall notify the Customer of any breach.", "Supplier", "Customer"),
    ]
    for text, subject, counterparty in cases:
        o = _one(text)
        assert o.subject == subject
        assert o.counterparty == counterparty


def test_ambiguous_recipient_is_not_promoted_to_party():
    assert _one("The Provider shall deliver the report to Mumbai.").counterparty is None
    assert _one("The Provider shall comply with the Act.").counterparty is None


def test_party_alias_is_canonicalised_without_losing_source_name():
    obligations = extract_obligations_from_clause(
        "c1",
        "The Customer shall pay Acme Technologies Pvt Ltd.",
        party_aliases={"Acme Technologies Pvt Ltd": "Provider"},
    )
    assert len(obligations) == 1
    assert obligations[0].counterparty == "Provider"
    assert "Acme Technologies Pvt Ltd" in (obligations[0].object or "")


def test_leading_condition_keeps_main_clause_subject_and_deadline():
    o = _one("If the Customer fails to pay within 10 days, the Supplier may suspend the Services.")
    assert o.obligation_type.value == "right"
    assert o.subject == "Supplier"
    assert o.condition == "If the Customer fails to pay within 10 days"
    assert o.deadline_expression is None


def test_mid_conditional_does_not_replace_action():
    o = _one("The Supplier shall, if requested by the Customer, provide the report.")
    assert o.action == "provide"
    assert o.condition == "if requested by the Customer"


def test_exception_is_recorded_as_condition():
    o = _one("The Provider shall deliver the report unless the Customer waives this requirement.")
    assert o.condition == "unless the Customer waives this requirement"
    assert o.deadline_expression is None


def test_multiple_conditions_are_joined():
    o = _one("If the Customer fails, unless the Supplier waives, the Provider shall deliver the report.")
    assert o.subject == "Provider"
    assert o.condition == "If the Customer fails, unless the Supplier waives"


def test_negated_leading_condition_does_not_create_conditional_party_obligation():
    assert extract_obligations_from_clause(
        "c1", "If the Customer shall fail to pay, the agreement terminates."
    ) == []


def test_protasis_modal_does_not_become_main_subject():
    o = _one("If the Customer shall fail to pay, the Supplier may terminate.")
    assert o.subject == "Supplier"
    assert o.obligation_type.value == "right"


def test_subject_to_cross_reference_is_condition_not_party():
    o = _one("Subject to Clause 5, the Provider shall deliver the report to the Customer.")
    assert o.subject == "Provider"
    assert o.counterparty == "Customer"
    assert o.condition == "Subject to Clause 5"


def test_explicit_to_recipient_beats_possessive_object():
    o = _one("The Supplier shall pay the Customer's invoice to the Provider.")
    assert o.subject == "Supplier"
    assert o.counterparty == "Provider"


def test_passive_agent_and_recipient_are_both_preserved():
    o = _one("The report shall be delivered by the Provider to the Customer.")
    assert o.subject == "Provider"
    assert o.counterparty == "Customer"


def test_passive_without_agent_keeps_subject_unknown():
    o = _one("The report shall be delivered to the Customer.")
    assert o.subject is None
    assert o.counterparty == "Customer"


def test_condition_calendar_date_is_not_attributed_as_deadline():
    o = _one("If the invoice is unpaid on 15 April 2024, the Provider may terminate.")
    assert o.deadline_date is None
    assert o.deadline_expression is None
    assert "15 April 2024" in (o.condition or "")


def test_written_out_deadline_is_normalised():
    o = _one("The Provider shall deliver within two business days.")
    assert o.deadline_expression == "2 business days"


# ---------------------------------------------------------------------------
# Passive voice with data-protection roles + compound written deadlines
# (eval case obligation_passive)
# ---------------------------------------------------------------------------


def test_passive_by_agent_processor_role_is_recovered():
    o = _one(
        "Personal data shall be encrypted by the Processor within twenty-four "
        "(24) hours of a security incident."
    )
    assert o.subject == "Processor"
    assert o.action == "encrypted"
    assert o.deadline_expression == "24 hours"


def test_passive_by_agent_controller_role_is_recovered():
    o = _one("The data shall be deleted by the Controller within thirty (30) days.")
    assert o.subject == "Controller"
    assert o.deadline_expression == "30 days"


def test_passive_irregular_participle_with_agent():
    o = _one("The fee shall be paid by the Customer within twenty-four days.")
    assert o.subject == "Customer"
    assert o.deadline_expression == "24 days"


def test_passive_irregular_participle_sent():
    o = _one("The report shall be sent by the Provider.")
    assert o.subject == "Provider"
    assert o.action == "sent"


def test_passive_agent_that_is_not_a_party_stays_unknown():
    o = _one("The report shall be delivered by Friday.")
    assert o.subject is None


def test_passive_without_agent_compound_deadline():
    o = _one("Personal data shall be encrypted within twenty-four (24) hours.")
    assert o.subject is None
    assert o.deadline_expression == "24 hours"


def test_compound_written_deadline_without_parenthetical():
    o = _one("The Provider shall deliver the goods within twenty-four days.")
    assert o.deadline_expression == "24 days"


def test_compound_written_deadline_sixty_five():
    o = _one("The Customer shall pay within sixty-five days of the invoice.")
    assert o.deadline_expression == "65 days"


def test_seventy_written_deadline_is_normalised():
    o = _one("The Provider shall deliver within seventy days.")
    assert o.deadline_expression == "70 days"


def test_passive_with_leading_condition_preserves_condition_and_deadline():
    o = _one(
        "If a security incident occurs, personal data shall be encrypted by "
        "the Processor within twenty-four (24) hours."
    )
    assert o.subject == "Processor"
    assert o.condition == "If a security incident occurs"
    assert o.deadline_expression == "24 hours"


def test_passive_with_exception_preserves_exception():
    o = _one("The fee shall be refunded by the Provider unless the Customer waives it.")
    assert o.subject == "Provider"
    assert o.condition == "unless the Customer waives it"


def test_passive_adjective_is_not_treated_as_passive():
    # "available" is an adjective, not a participle; the active-voice path and
    # its subject must be preserved.
    o = _one("The services shall be available at all times.")
    assert o.subject == "services"
    assert o.action == "available"


def test_active_voice_obligation_unchanged_with_compound_deadline():
    o = _one("The Customer shall pay the invoice within thirty (30) days.")
    assert o.subject == "Customer"
    assert o.action == "pay"
    assert o.deadline_expression == "30 days"


def test_cross_reference_sentence_stays_clause_local():
    # A sentence that points at another clause yields at most its own
    # obligation (here: passive, no agent -> unknown subject). No obligation is
    # fabricated from the referenced clause's content; cross-reference handling
    # is advisory-only and lives in the risk layer, not obligation extraction.
    text = "Personal data shall be encrypted as set out in Clause 4.2."
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 1
    assert obligations[0].subject is None
    assert obligations[0].action == "encrypted"


def test_passive_offsets_are_exact_source_slices():
    text = (
        "4.1 Personal data shall be encrypted by the Processor within "
        "twenty-four (24) hours."
    )
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 1
    o = obligations[0]
    assert o.char_start is not None and o.char_end is not None
    assert text[o.char_start:o.char_end] == o.text
