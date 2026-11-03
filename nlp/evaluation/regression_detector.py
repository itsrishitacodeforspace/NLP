"""Regression detection for evaluation metrics.

Honesty rules enforced here (see DEEP_AUDIT_20261103.md §C2):

- Comparing a file to itself is always a failure: it carries no information.
  Callers can detect this up front with :func:`is_same_results_file`, and
  :func:`run_regression_check` refuses a bare self-comparison on its own.
- A metric whose baseline is 0.0 cannot show percentage degradation; such a
  metric is reported as *uninformative* (not as a pass, and not as a
  regression) in :attr:`RegressionReport.uninformative`.
- The baseline is never created silently: :func:`run_regression_check` raises
  ``FileNotFoundError`` unless ``create_baseline=True`` is passed explicitly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
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
    uninformative: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    baseline_version: str = "unknown"
    new_version: str = "unknown"
    is_self_comparison: bool = False


class SelfComparisonError(ValueError):
    """Raised when a regression check is asked to compare results to themselves."""


def load_baseline(baseline_path: Path) -> dict[str, Any]:
    """Load baseline from JSON file."""
    with open(baseline_path) as f:
        return json.load(f)


def content_hash(data: dict[str, Any]) -> str:
    """Stable content hash of a results payload (ignores volatile top-level keys)."""
    import hashlib

    volatile = {"generated_at", "git_revision"}
    normalized = {k: v for k, v in data.items() if k not in volatile}
    blob = json.dumps(normalized, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def is_same_results_file(
    baseline_path: Path | None,
    new_results_path: Path,
    baseline: dict[str, Any] | None = None,
) -> bool:
    """True when the baseline and the new results are the same file (or payload).

    Checks identity of the resolved paths first, then the content hash when
    the files differ (so a copy of the same results still fails loudly).
    """
    if baseline_path is None:
        return False
    try:
        if Path(baseline_path).resolve() == Path(new_results_path).resolve():
            return True
    except OSError:
        pass
    if baseline is None:
        return False
    new_results_path = Path(new_results_path)
    if not new_results_path.exists():
        return False
    try:
        with open(new_results_path) as f:
            return content_hash(json.load(f)) == content_hash(baseline)
    except (OSError, json.JSONDecodeError):
        return False


def check_regression(
    baseline: dict[str, Any],
    new_results: dict[str, Any],
    tolerances: dict[str, dict[str, Any]] = DEFAULT_TOLERANCES,
    *,
    self_comparison: bool = False,
) -> RegressionReport:
    """Check for regressions between baseline and new results.

    ``self_comparison=True`` marks the report as a tautology (baseline and new
    results are the same payload) and forces ``is_clean`` to False regardless
    of the individual metric checks.
    """
    regressions: list[RegressionCheckResult] = []
    new_metrics: list[str] = []
    missing_metrics: list[str] = []
    uninformative: list[str] = []
    warnings: list[str] = []

    if self_comparison:
        warnings.append(
            "SELF-COMPARISON: baseline and new results are identical — this "
            "check carries no information and is reported as a failure."
        )

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

            # Check degradation percentage. A zero baseline cannot express a
            # degradation percentage; the metric is uninformative, NOT a pass.
            if baseline_val > 0:
                degradation_percent = ((baseline_val - new_val) / baseline_val) * 100
                max_degradation = tolerance.get("degradation_percent", 5.0)

                if degradation_percent > max_degradation:
                    is_regression = True
                    reason = f"Degraded by {degradation_percent:.1f}% (max allowed: {max_degradation}%)"
            else:
                uninformative.append(metric_name)
                warnings.append(
                    f"UNINFORMATIVE: {metric_name} baseline is 0.0 — no degradation "
                    f"percentage is computable; not counted as a pass."
                )

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

    is_clean = len(regressions) == 0 and not self_comparison

    return RegressionReport(
        is_clean=is_clean,
        regressions=regressions,
        new_metrics=new_metrics,
        missing_metrics=missing_metrics,
        uninformative=uninformative,
        warnings=warnings,
        baseline_version=baseline.get("version", "unknown"),
        new_version=new_results.get("version", "unknown"),
        is_self_comparison=self_comparison,
    )


def generate_regression_report_md(report: RegressionReport) -> str:
    """Generate Markdown regression report."""
    lines: list[str] = []

    lines.append("# Regression Detection Report")
    lines.append("")
    lines.append(f"Baseline version: {report.baseline_version}")
    lines.append(f"New version: {report.new_version}")
    lines.append("")

    if report.is_self_comparison:
        lines.append("## ⛔ SELF-COMPARISON — RESULT INVALID")
        lines.append("")
        lines.append(
            "The baseline and the new results are the same payload. A run compared "
            "against itself cannot detect any regression; this report must not be "
            "read as 'no regressions'. Regenerate the baseline from an "
            "independently reviewed run."
        )
        lines.append("")

    elif report.is_clean:
        lines.append("## ✅ NO REGRESSIONS DETECTED")
        lines.append("")
        if report.uninformative:
            lines.append(
                f"> Note: {len(report.uninformative)} metric(s) were UNINFORMATIVE "
                "(zero baseline — nothing to measure) and are not counted as passes:"
            )
            for m in report.uninformative:
                lines.append(f"> - {m}")
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

        if report.uninformative:
            lines.append("## ⚠️  Uninformative Metrics (zero baseline — not counted as passes)")
            for m in report.uninformative:
                lines.append(f"- {m}")
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


def _write_baseline(
    new_results: dict[str, Any],
    baseline_path: Path,
    *,
    git_revision: str = "",
) -> dict[str, Any]:
    """Persist an explicit baseline from ``new_results`` at ``baseline_path``."""
    baseline = {
        "version": new_results.get("version", "1.0.0"),
        "git_revision": git_revision or new_results.get("git_revision") or "unknown",
        "generated_at": new_results.get("generated_at", "unknown"),
        "aggregate_metrics": new_results.get("aggregate_metrics", {}),
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)
    return baseline


def create_baseline(
    new_results: dict[str, Any],
    baseline_path: Path,
    *,
    git_revision: str = "",
) -> dict[str, Any]:
    """Persist an explicit baseline from ``new_results`` at ``baseline_path``."""
    return _write_baseline(new_results, baseline_path, git_revision=git_revision)


def run_regression_check(
    new_results_path: Path,
    baseline_path: Path | None = None,
    tolerances: dict[str, dict[str, Any]] | None = None,
    *,
    create_baseline: bool = False,
    git_revision: str = "",
) -> tuple[RegressionReport, str, dict]:
    """Run regression check and return report.

    Raises:
        FileNotFoundError: when no baseline exists and ``create_baseline`` is
            not explicitly True (baselines must be created deliberately).
        SelfComparisonError: when the baseline and the new results are the
            same file/payload (comparing a run to itself is a tautology).
    """
    if tolerances is None:
        tolerances = DEFAULT_TOLERANCES

    # Load new results
    with open(new_results_path) as f:
        new_results = json.load(f)

    # Load or (explicitly) create the baseline
    if baseline_path is None:
        if not create_baseline:
            raise FileNotFoundError(
                "No baseline path given and create_baseline was not requested. "
                "Pass baseline_path, or pass create_baseline=True explicitly "
                "to stamp a new baseline from these results."
            )
        baseline_path = new_results_path.parent / "integrated_synthetic_baseline.json"

    if baseline_path.exists():
        baseline = load_baseline(baseline_path)
        if is_same_results_file(baseline_path, new_results_path, baseline):
            raise SelfComparisonError(
                f"Baseline {baseline_path} is identical to the new results at "
                f"{new_results_path} (same file or same content). Comparing a "
                "run to itself is a tautology and must not pass. Regenerate the "
                "baseline from an independently reviewed run, or compare "
                "against a different results file."
            )
    elif create_baseline:
        baseline = _write_baseline(new_results, baseline_path, git_revision=git_revision)
        # The baseline was just created from these very results: nothing to measure.
        raise SelfComparisonError(
            f"Baseline {baseline_path} was just created from the new results at "
            f"{new_results_path} — the comparison is a tautology. Review the new "
            "baseline, then run the check against a subsequent run's results."
        )
    else:
        raise FileNotFoundError(
            f"Baseline not found at {baseline_path}. Run the check with "
            "--create-baseline to establish a baseline explicitly, or pass an "
            "existing --baseline path."
        )

    # Check regressions (content identity already rejected above)
    report = check_regression(baseline, new_results, tolerances, self_comparison=False)

    # Generate Markdown
    md_report = generate_regression_report_md(report)

    return report, md_report, baseline
