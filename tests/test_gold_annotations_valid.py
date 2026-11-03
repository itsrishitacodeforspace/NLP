"""Verify the gold annotations are grounded in reality.

For every case:
- each ``ner_gold`` entity's offsets must slice the actual case text back to
  the entity text (no fabricated party names, no invented offsets);
- each ``risk_gold`` rule_id must exist in the engine's ``RISK_RULES``
  registry (no invented rule IDs);
- ``evidence_gold`` spans must slice to real, non-empty text;
- ``obligation_gold`` ``locate`` substrings must appear in the case text.

These checks need only the source tree (``nlp/``) — no external artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nlp.evaluation.cases import CASES
from nlp.risk_scoring.rules import RISK_RULES

GOLD_PATH = (
    Path(__file__).parent.parent / "nlp" / "evaluation" / "gold_annotations" / "cases_gold.json"
)
KNOWN_RULE_IDS = {rule.rule_id for rule in RISK_RULES}


@pytest.fixture(scope="module")
def gold() -> dict:
    with open(GOLD_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def cases_by_id() -> dict:
    return {c.case_id: c for c in CASES}


def test_gold_case_ids_match_corpus(gold: dict, cases_by_id: dict) -> None:
    assert set(gold["cases"].keys()) == set(cases_by_id.keys())
    assert len(gold["cases"]) == 17


@pytest.mark.parametrize("case_id", [c.case_id for c in CASES])
def test_ner_gold_offsets_slice_real_text(gold: dict, cases_by_id: dict, case_id: str) -> None:
    """Every ner_gold entity must slice the case text back to its own text."""
    text = cases_by_id[case_id].text
    for entity in gold["cases"][case_id].get("ner_gold", []):
        start, end, label = entity["start"], entity["end"], entity["text"]
        assert 0 <= start < end <= len(text), (
            f"{case_id}: entity offsets {start}:{end} out of bounds for text of length {len(text)}"
        )
        sliced = text[start:end]
        assert sliced == label, (
            f"{case_id}: entity text {label!r} does not slice the case text "
            f"at {start}:{end} (got {sliced!r})"
        )


@pytest.mark.parametrize("case_id", [c.case_id for c in CASES])
def test_risk_gold_rule_ids_exist(gold: dict, case_id: str) -> None:
    """Every risk_gold rule_id must be a real engine rule ID."""
    for risk in gold["cases"][case_id].get("risk_gold", []):
        assert risk["risk_id"] in KNOWN_RULE_IDS, (
            f"{case_id}: risk rule {risk['risk_id']!r} does not exist in the engine's "
            f"RISK_RULES registry (known: {sorted(KNOWN_RULE_IDS)})"
        )


@pytest.mark.parametrize("case_id", [c.case_id for c in CASES])
def test_evidence_gold_spans_are_real(gold: dict, cases_by_id: dict, case_id: str) -> None:
    """Every evidence_gold span must anchor to real, non-empty text."""
    text = cases_by_id[case_id].text
    for span in gold["cases"][case_id].get("evidence_gold", []):
        start, end = span["start"], span["end"]
        assert 0 <= start < end <= len(text), (
            f"{case_id}: evidence span {start}:{end} out of bounds for text of length {len(text)}"
        )
        assert text[start:end].strip(), (
            f"{case_id}: evidence span {start}:{end} does not anchor to real text"
        )


@pytest.mark.parametrize("case_id", [c.case_id for c in CASES])
def test_obligation_gold_locate_exists_in_text(gold: dict, cases_by_id: dict, case_id: str) -> None:
    """Every obligation_gold locate must appear in the case text."""
    text = cases_by_id[case_id].text.lower()
    for obligation in gold["cases"][case_id].get("obligation_gold", []):
        locate = obligation.get("locate", "")
        assert locate and locate.lower() in text, (
            f"{case_id}: obligation locate {locate!r} does not appear in the case text"
        )
