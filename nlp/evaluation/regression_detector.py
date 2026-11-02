"""Regression detection for evaluation metrics."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Default tolerances
DEFAULT_TOLERANCES = {
    "classification_f1": {"min": 0.5, "degradation_percent": 5.0},
    "ner_entity_f1": {"min": 0.4, "degradation_percent": 5.0},
    "obligation_detection_f1": {"min": 0.3, "degradation_percent": 5.0},
    "risk_f1": {"min": 0.4, "degradation_percent": 5.0},
    "evidence_mean_iou": {"min": 0.5, "degradation_percent": 5.0},
}


@dataclass
class RegressionCheckResult:
    """Result of one regression check."""
    metric_name: str
    baseline_value: float
    new_value: float
    is_regression: bool
    tolerance: dict[str, Any]
    reason: str = ""


@dataclass
class RegressionReport:
    """Full regression report."""
    is_clean: bool
    regressions: list[RegressionCheckResult]
    new_metrics: list[str]
    missing_metrics: list[str]
    warnings: list[str]
    baseline_version: str
    new_version: str


def load_baseline(baseline_path: Path) -> dict[str, Any]:
    """Load baseline from JSON file."""
    with open(baseline_path) as f:
        return json.load(f)


def check_regression(
    baseline: dict[str, Any],
    new_results: dict[str, Any],
    tolerances: dict[str, dict[str, Any]] = DEFAULT_TOLERANCES,
) -> RegressionReport:
    """Check for regressions between baseline and new results."""
    regressions: list[RegressionCheckResult] = []
    new_metrics: list[str] = []
    missing_metrics: list[str] = []
    warnings: list[str] = []

    # Get baseline metrics
    baseline_metrics = baseline.get("aggregate_metrics", {})
    new_metrics_map = new_results.get("aggregate_metrics", {})

    # Check each metric type
    for metric_type, baseline_vals in baseline_metrics.items():
        if metric_type not in new_metrics_map:
            missing_metrics.append(metric_type)
            warnings.append(f"Missing metric type: {metric_type}")
            continue

        new_vals = new_metrics_map[metric_type]

        # Check each sub-metric
        for sub_metric, baseline_val in baseline_vals.items():
            metric_name = f"{metric_type}_{sub_metric}"

            if sub_metric not in new_vals:
                missing_metrics.append(metric_name)
                warnings.append(f"Missing metric: {metric_name}")
                continue

            new_val = new_vals[sub_metric]

            # Get tolerance for this metric
            tolerance = tolerances.get(metric_name, tolerances.get(metric_type, {}))

            # Check for regression
            is_regression = False
            reason = ""

            # Check degradation percentage
            if baseline_val > 0:
                degradation_percent = ((baseline_val - new_val) / baseline_val) * 100
                max_degradation = tolerance.get("degradation_percent", 5.0)

                if degradation_percent > max_degradation:
                    is_regression = True
                    reason = f"Degraded by {degradation_percent:.1f}% (max allowed: {max_degradation}%)"

            # Check minimum threshold
            min_val = tolerance.get("min", 0.0)
            if new_val < min_val:
                is_regression = True
                reason = reason or f"Below minimum threshold: {min_val}"

            if is_regression:
                regressions.append(RegressionCheckResult(
                    metric_name=metric_name,
                    baseline_value=baseline_val,
                    new_value=new_val,
                    is_regression=True,
                    tolerance=tolerance,
                    reason=reason,
                ))

            # Check for improvement (new metric)
            if baseline_val == 0 and new_val > 0:
                new_metrics.append(metric_name)

    is_clean = len(regressions) == 0

    return RegressionReport(
        is_clean=is_clean,
        regressions=regressions,
        new_metrics=new_metrics,
        missing_metrics=missing_metrics,
        warnings=warnings,
        baseline_version=baseline.get("version", "unknown"),
        new_version=new_results.get("version", "unknown"),
    )


def generate_regression_report_md(report: RegressionReport) -> str:
    """Generate Markdown regression report."""
    lines: list[str] = []

    lines.append("# Regression Detection Report")
    lines.append("")
    lines.append(f"Baseline version: {report.baseline_version}")
    lines.append(f"New version: {report.new_version}")
    lines.append("")

    if report.is_clean:
        lines.append("## ✅ NO REGRESSIONS DETECTED")
        lines.append("")
    else:
        lines.append(f"## ⚠️  {len(report.regressions)} REGRESSION(S) DETECTED")
        lines.append("")

        for reg in report.regressions:
            lines.append(f"### {reg.metric_name}")
            lines.append(f"- Baseline: {reg.baseline_value:.4f}")
            lines.append(f"- New: {reg.new_value:.4f}")
            lines.append(f"- Tolerance: {reg.tolerance}")
            lines.append(f"- **{reg.reason}**")
            lines.append("")

    if report.new_metrics:
        lines.append("## 🆕 New Metrics")
        for m in report.new_metrics:
            lines.append(f"- {m}")
        lines.append("")

    if report.missing_metrics:
        lines.append("## ❌ Missing Metrics")
        for m in report.missing_metrics:
            lines.append(f"- {m}")
        lines.append("")

    if report.warnings:
        lines.append("## ⚠️  Warnings")
        for w in report.warnings:
            lines.append(f"- {w}")
        lines.append("")

    return "\n".join(lines)


def run_regression_check(
    new_results_path: Path,
    baseline_path: Path | None = None,
    tolerances: dict[str, dict[str, Any]] | None = None,
) -> tuple[RegressionReport, str, dict]:
    """Run regression check and return report."""
    if tolerances is None:
        tolerances = DEFAULT_TOLERANCES

    # Load new results
    with open(new_results_path) as f:
        new_results = json.load(f)

    # Load baseline
    baseline_file = baseline_path or new_results_path.parent / "baseline.json"
    if baseline_file.exists():
        baseline = load_baseline(baseline_file)
    else:
        # Create baseline from new results
        baseline = {
            "version": new_results.get("version", "1.0.0"),
            "aggregate_metrics": new_results.get("aggregate_metrics", {}),
            "generated_at": new_results.get("generated_at", "unknown"),
        }
        new_results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_file, "w") as f:
            json.dump(baseline, f, indent=2)

    # Check regressions
    report = check_regression(baseline, new_results, tolerances)

    # Generate Markdown
    md_report = generate_regression_report_md(report)

    return report, md_report, baseline
