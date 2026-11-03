"""Tests for regression detection module and CLI exit-code logic."""
from __future__ import annotations

import importlib  # noqa: E402
import json
import sys
from pathlib import Path

import pytest

from nlp.evaluation.regression_detector import (
    SelfComparisonError,
    check_regression,
    create_baseline,
    is_same_results_file,
    run_regression_check,
)

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

cli = importlib.import_module("check_evaluation_regression")


def _results(aggregate: dict) -> dict:
    return {"version": "1.0.0", "aggregate_metrics": aggregate}


_SIMPLE_AGGREGATE = {
    "classification": {"macro_f1": 0.8},
    "risks": {"detection_f1": 0.6},
}


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

    def test_baseline_records_real_git_revision(self) -> None:
        """The committed baseline must record a real git revision, not 'unknown'."""
        baseline_path = Path(__file__).parent.parent / "reports" / "evaluations" / "integrated_synthetic_baseline.json"
        if not baseline_path.exists():
            return
        with open(baseline_path) as f:
            baseline = json.load(f)
        revision = baseline.get("git_revision")
        assert revision and revision != "unknown" and len(revision) == 40

    # ------------------------------------------------------------------
    # Real unit tests (construct small payloads in tmp_path)
    # ------------------------------------------------------------------

    def test_same_file_comparison_fails(self, tmp_path: Path) -> None:
        """Comparing results to themselves must fail, never pass silently."""
        payload = _results(_SIMPLE_AGGREGATE)
        path = tmp_path / "results.json"
        path.write_text(json.dumps(payload))

        with pytest.raises(SelfComparisonError):
            run_regression_check(new_results_path=path, baseline_path=path)

        # Same payload in a *different* file must also be detected.
        copy = tmp_path / "copy.json"
        copy.write_text(json.dumps(payload))
        assert is_same_results_file(path, copy, baseline=json.loads(path.read_text()))
        report = check_regression(payload, payload, self_comparison=True)
        assert report.is_self_comparison
        assert not report.is_clean

    def test_zero_baseline_is_uninformative_not_pass(self) -> None:
        """A zero-baseline metric must be reported uninformative, not silently skipped."""
        baseline = _results({"classification": {"macro_f1": 0.0}, "risks": {"detection_f1": 0.0}})
        # New value differs so the payloads are not a self-comparison.
        new = _results({"classification": {"macro_f1": 0.0}, "risks": {"detection_f1": 0.01}})
        report = check_regression(baseline, new)
        assert set(report.uninformative) == {"classification_macro_f1", "risks_detection_f1"}
        # Uninformative metrics are not regressions, but they must show up.
        assert report.regressions == []
        assert "classification_macro_f1" in " ".join(report.warnings)
        # They are NOT counted as passes either: the report calls them out.
        assert report.uninformative

    def test_zero_baseline_with_new_value_is_improvement_not_regression(self) -> None:
        baseline = _results({"risks": {"detection_f1": 0.0}})
        new = _results({"risks": {"detection_f1": 0.5}})
        report = check_regression(baseline, new)
        assert report.regressions == []
        assert "risks_detection_f1" in report.new_metrics
        assert report.is_clean

    def test_degradation_detection_triggers(self) -> None:
        """A real degradation beyond tolerance must be flagged."""
        baseline = _results({"classification": {"macro_f1": 0.8}})
        new = _results({"classification": {"macro_f1": 0.5}})
        tolerances = {"classification": {"min": 0.0, "degradation_percent": 5.0}}
        report = check_regression(baseline, new, tolerances)
        assert not report.is_clean
        assert len(report.regressions) == 1
        reg = report.regressions[0]
        assert reg.metric_name == "classification_macro_f1"
        assert "Degraded" in reg.reason

    def test_min_threshold_triggers_on_low_new_value(self) -> None:
        baseline = _results({"risks": {"detection_f1": 0.6}})
        new = _results({"risks": {"detection_f1": 0.59}})
        tolerances = {"risks": {"min": 0.6, "degradation_percent": 50.0}}
        report = check_regression(baseline, new, tolerances)
        assert not report.is_clean
        assert "Below minimum threshold" in report.regressions[0].reason

    def test_missing_baseline_raises_without_flag(self, tmp_path: Path) -> None:
        """Absent baseline must not be silently created: FileNotFoundError."""
        path = tmp_path / "results.json"
        path.write_text(json.dumps(_results(_SIMPLE_AGGREGATE)))
        with pytest.raises(FileNotFoundError):
            run_regression_check(new_results_path=path, baseline_path=tmp_path / "baseline.json")
        assert not (tmp_path / "baseline.json").exists()

    def test_create_baseline_requires_flag(self, tmp_path: Path) -> None:
        """create_baseline=True writes the baseline; without it nothing is written."""
        path = tmp_path / "results.json"
        payload = _results(_SIMPLE_AGGREGATE)
        payload["git_revision"] = "a" * 40
        path.write_text(json.dumps(payload))
        baseline_path = tmp_path / "baseline.json"

        # Creating a baseline from the very results being checked is a
        # tautology: the baseline is written (loudly) but the comparison fails.
        with pytest.raises(SelfComparisonError):
            run_regression_check(
                new_results_path=path,
                baseline_path=baseline_path,
                create_baseline=True,
            )
        assert baseline_path.exists()
        stored = json.loads(baseline_path.read_text())
        assert stored["aggregate_metrics"] == _SIMPLE_AGGREGATE
        assert stored["git_revision"] == "a" * 40

    def test_create_baseline_helper_stamps_git_revision(self, tmp_path: Path) -> None:
        out = create_baseline(_results(_SIMPLE_AGGREGATE), tmp_path / "b.json", git_revision="b" * 40)
        assert out["git_revision"] == "b" * 40
        assert json.loads((tmp_path / "b.json").read_text())["git_revision"] == "b" * 40

    # ------------------------------------------------------------------
    # CLI exit-code logic (scripts/check_evaluation_regression.py)
    # ------------------------------------------------------------------

    def _cli(self, tmp_path: Path, baseline: dict, new: dict, **kwargs) -> int:
        b = tmp_path / "baseline.json"
        r = tmp_path / "results.json"
        b.write_text(json.dumps(baseline))
        r.write_text(json.dumps(new))
        out = tmp_path / "out"
        return cli.run_check(
            baseline_path=b,
            new_results_path=r,
            output_dir=out,
            temp_path=tmp_path / "temp_new_results.json",
            **kwargs,
        )

    def test_cli_same_content_results_fails(self, tmp_path: Path) -> None:
        """CLI: baseline identical in content to the new results must exit 1."""
        baseline = _results(_SIMPLE_AGGREGATE)
        new = _results(_SIMPLE_AGGREGATE)
        assert self._cli(tmp_path, baseline, new) == 1
        md = (tmp_path / "out" / "regression_report.md").read_text()
        assert "SELF-COMPARISON" in md

    def test_cli_missing_baseline_no_flag_exits_2(self, tmp_path: Path) -> None:
        """CLI: no baseline, no --create-baseline => nothing to measure (exit 2)."""
        payload = _results(_SIMPLE_AGGREGATE)
        r = tmp_path / "results.json"
        r.write_text(json.dumps(payload))
        assert (
            cli.run_check(
                baseline_path=tmp_path / "nope.json",
                new_results_path=r,
                output_dir=tmp_path / "out",
                temp_path=tmp_path / "t.json",
            )
            == 2
        )

    def test_cli_create_baseline_exits_2_and_writes(self, tmp_path: Path) -> None:
        """CLI: --create-baseline writes the baseline and exits 2 (not a pass)."""
        payload = _results(_SIMPLE_AGGREGATE)
        r = tmp_path / "results.json"
        r.write_text(json.dumps(payload))
        code = cli.run_check(
            baseline_path=tmp_path / "baseline.json",
            new_results_path=r,
            output_dir=tmp_path / "out",
            create_baseline=True,
            temp_path=tmp_path / "t.json",
        )
        assert code == 2
        stored = json.loads((tmp_path / "baseline.json").read_text())
        assert stored["aggregate_metrics"] == _SIMPLE_AGGREGATE

    def test_cli_normal_clean_comparison_exits_0(self, tmp_path: Path) -> None:
        """CLI: distinct payloads with a zero-baseline metric => exit 0 with an
        uninformative note (nothing to measure for that metric, not a hidden pass)."""
        baseline = _results({"classification": {"macro_f1": 0.0}, "risks": {"detection_f1": 0.5}})
        new = _results({"classification": {"macro_f1": 0.0}, "risks": {"detection_f1": 0.51}})
        assert self._cli(tmp_path, baseline, new) == 0
        md = (tmp_path / "out" / "regression_report.md").read_text()
        assert "NO REGRESSIONS" in md
        assert "UNINFORMATIVE" in md
