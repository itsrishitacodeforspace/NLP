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
