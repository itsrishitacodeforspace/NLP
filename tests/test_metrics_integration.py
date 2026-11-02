"""Tests for metrics integration module."""
from __future__ import annotations

import json
from pathlib import Path


class TestMetricsIntegration:
    """Tests for the metrics integration module."""

    def test_gold_annotations_exist(self) -> None:
        """Gold annotations file should exist."""
        gold_path = Path(__file__).parent.parent / "nlp" / "evaluation" / "gold_annotations" / "cases_gold.json"
        assert gold_path.exists(), f"Gold annotations file not found at {gold_path}"

        with open(gold_path) as f:
            data = json.load(f)

        assert "cases" in data
        assert len(data["cases"]) == 17

    def test_gold_annotations_valid_json(self) -> None:
        """Gold annotations should be valid JSON."""
        gold_path = Path(__file__).parent.parent / "nlp" / "evaluation" / "gold_annotations" / "cases_gold.json"
        with open(gold_path) as f:
            data = json.load(f)

        # Check required fields
        assert "version" in data
        assert "cases" in data
        assert len(data["cases"]) == 17

        # Check first case structure
        first_case = list(data["cases"].values())[0]
        assert "classification_gold" in first_case
        assert "ner_gold" in first_case
        assert "obligation_gold" in first_case
        assert "risk_gold" in first_case
        assert "evidence_gold" in first_case

    def test_gold_annotations_match_cases(self) -> None:
        """Gold annotations should match actual case IDs."""
        from nlp.evaluation.cases import CASES

        gold_path = Path(__file__).parent.parent / "nlp" / "evaluation" / "gold_annotations" / "cases_gold.json"
        with open(gold_path) as f:
            data = json.load(f)

        cases = data["cases"]
        case_ids = {c.case_id for c in CASES}

        assert set(cases.keys()) == case_ids
