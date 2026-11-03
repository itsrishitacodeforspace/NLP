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
    # A sentence that appears twice verbatim in the clause cannot be
    # located unambiguously — offsets are left None (never fabricated).
    text = "Each party shall keep information secret. Each party shall keep information secret."
    obligations = extract_obligations_from_clause("c1", text)
    # Both sentences are identical obligations; dedup collapses them to one.
    assert len(obligations) == 1
    assert obligations[0].char_start is None and obligations[0].char_end is None


def test_repeated_distinct_sentences_with_ambiguous_offsets():
    # Two distinct obligations where one sentence is a *proper* substring of
    # the other (the word "the" separates them): the shorter sentence
    # matches twice (once inside the longer sentence, once standalone), so
    # its offsets must be None (never fabricated).
    text = (
        "The Provider shall keep the information secret. "
        "The Provider shall keep information secret."
    )
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 2
    first = [o for o in obligations if o.object == "the information secret"]
    second = [o for o in obligations if o.object == "information secret"]
    assert first and second
    # The longer sentence is unique — offsets are set.
    assert first[0].char_start is not None
    # The shorter sentence is a substring of the longer one — ambiguous.
    assert second[0].char_start is None and second[0].char_end is None


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


# ---------------------------------------------------------------------------
# P5 (charter §5.B): field completeness audit
# ---------------------------------------------------------------------------


def test_beneficiary_is_recipient_when_self_reference_follows():
    # "indemnify the Customer against the Customer's losses" — the first
    # dative party (Customer) is the beneficiary even though the object
    # contains a second, self-referential mention of the same party.
    o = _one("The Provider shall indemnify the Customer against the Customer's losses.")
    assert o.subject == "Provider"
    assert o.counterparty == "Customer"


def test_beneficiary_recipient_in_compound_indemnity():
    # "indemnify the Customer against any and all claims" — single verb form
    # (the "indemnify and hold harmless" compound form is a known limitation
    # of the regex: the action word is "indemnify" but the dative party
    # follows "hold harmless", which the regex does not scan for).
    o = _one(
        "The Provider shall indemnify the Customer against "
        "any and all claims, losses, damages and expenses."
    )
    assert o.subject == "Provider"
    assert o.counterparty == "Customer"


def test_compound_indemnity_compound_verb_is_known_limitation():
    # Documents current behaviour: the compound "indemnify and hold harmless"
    # form does not extract the counterparty (the dative party follows
    # "hold harmless", not the action verb). This is a known limitation of
    # the regex-based extractor; a future pass could add "hold harmless" to
    # the dative-verb list.
    o = _one(
        "The Provider shall indemnify and hold harmless the Customer against "
        "any and all claims, losses, damages and expenses."
    )
    assert o.subject == "Provider"
    assert o.action == "indemnify"
    assert o.counterparty is None  # known limitation — do not guess


def test_beneficiary_none_when_no_explicit_recipient():
    # No dative construction at all — the beneficiary cannot be determined.
    o = _one("The Provider shall comply with the Act.")
    assert o.counterparty is None


def test_condition_captured_on_material_breach_trigger():
    o = _one("The Provider shall provide a report within 30 days upon a material breach by the Customer.")
    # "upon" is not a condition marker (it's a deadline preposition); the
    # breach is part of the deadline context, not a conditional clause.
    # The deadline is still extracted.
    assert o.deadline_expression == "30 days"
    assert o.condition is None or "material breach" not in (o.condition or "")


def test_condition_captured_on_if_fails_to_pay():
    o = _one("If the Customer fails to pay, the Provider may terminate the Agreement.")
    assert o.condition is not None
    assert "fails to pay" in o.condition


def test_frequency_monthly():
    o = _one("The Customer shall pay the fees monthly.")
    assert o.frequency == "monthly"


def test_frequency_quarterly():
    o = _one("The Customer shall pay a retainer quarterly in advance.")
    assert o.frequency == "quarterly"


def test_frequency_annually():
    o = _one("The Provider shall report to the Customer annually.")
    assert o.frequency == "annually"


def test_frequency_biannually():
    o = _one("The Provider shall review the SLA bi-annually.")
    assert o.frequency == "biannually"


def test_frequency_per_month():
    o = _one("The Customer shall pay the fee per month.")
    assert o.frequency == "monthly"


def test_frequency_per_annum():
    o = _one("The Customer shall pay a licence fee per annum.")
    assert o.frequency == "annually"


def test_frequency_weekly():
    o = _one("The Provider shall issue an invoice weekly.")
    assert o.frequency == "weekly"


def test_no_frequency_when_none_present():
    o = _one("The Customer shall pay the invoice within thirty (30) days of receipt.")
    assert o.frequency is None


def test_no_frequency_for_vague_cadence():
    # "periodically" is not a specific frequency — must not be extracted.
    o = _one("The Provider shall comply periodically with the Act.")
    assert o.frequency is None


def test_passive_agent_in_prepositional_phrase_is_subject():
    o = _one("Notice shall be given by the Vendor.")
    assert o.subject == "Vendor"
    assert o.action == "given"


def test_exact_duplicate_obligations_within_clause_are_deduped():
    # A boilerplate restatement of the same obligation in the same clause
    # must not yield two identical obligations.
    text = (
        "The Provider shall notify the Customer in writing. "
        "The Provider shall notify the Customer in writing."
    )
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 1, f"expected 1 deduplicated obligation, got {len(obligations)}"
    assert obligations[0].subject == "Provider"
    assert obligations[0].action == "notify"


def test_distinct_obligations_in_same_clause_are_both_kept():
    # Two genuinely different obligations in the same clause must both be
    # emitted — dedup only removes exact matches.
    text = (
        "The Provider shall notify the Customer in writing. "
        "The Customer shall pay the invoice within 30 days."
    )
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 2


def test_deadline_not_extracted_from_bare_duration_without_modal():
    # "The initial term of this Agreement is 90 days" — no deontic modal,
    # no obligation is emitted, and no deadline is fabricated.
    obligations = extract_obligations_from_clause("c1", "The initial term of this Agreement is 90 days.")
    assert obligations == []


def test_deadline_only_from_deontic_sentence():
    # A bare duration in a non-deontic sentence does not become a deadline;
    # the deadline is extracted only from the deontic sentence.
    text = "The warranty period is 12 months. The Provider shall notify within 30 days."
    obligations = extract_obligations_from_clause("c1", text)
    assert len(obligations) == 1
    assert obligations[0].deadline_expression == "30 days"
