"""Tests for regression detection module."""
from __future__ import annotations

import json
from pathlib import Path


class TestRegressionDetector:
    """Tests for regression detection functionality."""

    def test_load_baseline(self) -> None:
        """Baseline should be loadable from JSON."""
        baseline_path = Path(__file__).parent.parent / "reports" / "evaluations" / "integrated_synthetic_baseline.json"
        if not baseline_path.exists():
            return
        with open(baseline_path) as f:
            baseline = json.load(f)
        assert "aggregate_metrics" in baseline
        assert "version" in baseline

    def test_baseline_has_expected_structure(self) -> None:
        """Baseline should have expected aggregate metrics."""
        baseline_path = Path(__file__).parent.parent / "reports" / "evaluations" / "integrated_synthetic_baseline.json"
        if not baseline_path.exists():
            return
        with open(baseline_path) as f:
            baseline = json.load(f)
        assert "aggregate_metrics" in baseline
        assert "classification" in baseline["aggregate_metrics"]
        assert "ner" in baseline["aggregate_metrics"]
        assert "obligations" in baseline["aggregate_metrics"]
        assert "risks" in baseline["aggregate_metrics"]
        assert "evidence" in baseline["aggregate_metrics"]
