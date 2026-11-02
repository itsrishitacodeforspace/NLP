#!/usr/bin/env python3
"""Check for evaluation regressions by comparing to a baseline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "reports" / "evaluations" / "integrated_synthetic_baseline.json"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "evaluations"

app = typer.Typer(
    name="check-regression",
    help="Check for evaluation regressions by comparing to a baseline.",
)


@app.command()
def main(
    baseline_path: Path = typer.Option(
        DEFAULT_BASELINE,
        "--baseline",
        "-b",
        help="Path to baseline JSON file.",
    ),
    new_results_path: Path | None = typer.Option(
        None,
        "--results",
        "-r",
        help="Path to new evaluation results JSON file (if not provided, run evaluation).",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output-dir",
        "-o",
        help="Directory for output reports.",
    ),
    classification_f1_min: float = typer.Option(
        0.0,
        "--classification-f1-min",
        help="Minimum acceptable classification F1 score.",
    ),
    classification_f1_degradation: float = typer.Option(
        5.0,
        "--classification-f1-degradation",
        help="Maximum acceptable degradation percentage for classification F1.",
    ),
    ner_entity_f1_min: float = typer.Option(
        0.0,
        "--ner-entity-f1-min",
        help="Minimum acceptable NER entity F1 score.",
    ),
    ner_entity_f1_degradation: float = typer.Option(
        5.0,
        "--ner-entity-f1-degradation",
        help="Maximum acceptable degradation percentage for NER entity F1.",
    ),
    obligation_detection_f1_min: float = typer.Option(
        0.0,
        "--obligation-detection-f1-min",
        help="Minimum acceptable obligation detection F1 score.",
    ),
    obligation_detection_f1_degradation: float = typer.Option(
        5.0,
        "--obligation-detection-f1-degradation",
        help="Maximum acceptable degradation percentage for obligation detection F1.",
    ),
    risk_detection_f1_min: float = typer.Option(
        0.0,
        "--risk-detection-f1-min",
        help="Minimum acceptable risk detection F1 score.",
    ),
    risk_detection_f1_degradation: float = typer.Option(
        5.0,
        "--risk-detection-f1-degradation",
        help="Maximum acceptable degradation percentage for risk detection F1.",
    ),
    evidence_mean_iou_min: float = typer.Option(
        0.0,
        "--evidence-mean-iou-min",
        help="Minimum acceptable evidence mean IoU score.",
    ),
    evidence_mean_iou_degradation: float = typer.Option(
        5.0,
        "--evidence-mean-iou-degradation",
        help="Maximum acceptable degradation percentage for evidence mean IoU.",
    ),
) -> int:
    """Check for evaluation regressions by comparing to a baseline."""
    from nlp.evaluation.metrics_integration import generate_integrated_report_json, run_integrated_evaluation
    from nlp.evaluation.regression_detector import (
        load_baseline,
        run_regression_check,
    )

    # Build tolerance config
    tolerances = {
        "classification_f1": {
            "min": classification_f1_min,
            "degradation_percent": classification_f1_degradation,
        },
        "ner_entity_f1": {
            "min": ner_entity_f1_min,
            "degradation_percent": ner_entity_f1_degradation,
        },
        "obligation_detection_f1": {
            "min": obligation_detection_f1_min,
            "degradation_percent": obligation_detection_f1_degradation,
        },
        "risk_detection_f1": {
            "min": risk_detection_f1_min,
            "degradation_percent": risk_detection_f1_degradation,
        },
        "evidence_mean_iou": {
            "min": evidence_mean_iou_min,
            "degradation_percent": evidence_mean_iou_degradation,
        },
    }

    # Load or run new results
    if new_results_path and new_results_path.exists():
        with open(new_results_path) as f:
            new_results = json.load(f)
    else:
        print("Running integrated evaluation...")
        report = run_integrated_evaluation()
        new_results = generate_integrated_report_json(report)
        new_results["version"] = "1.0.0"

    # Check for regressions
    print(f"Loading baseline from: {baseline_path}")
    if not baseline_path.exists():
        print(f"Error: Baseline not found at {baseline_path}")
        print("Creating baseline from current results...")
        # Create baseline from current results
        baseline = {
            "version": new_results.get("version", "1.0.0"),
            "git_revision": new_results.get("git_revision", "unknown"),
            "aggregate_metrics": new_results.get("aggregate_metrics", {}),
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(baseline_path, "w") as f:
            json.dump(baseline, f, indent=2)
        print(f"Created baseline at: {baseline_path}")
        print("No regressions detected (this is the first run).")
        return 0

    baseline = load_baseline(baseline_path)

    # Create temp file for new results
    temp_path = ROOT / "temp_new_results.json"
    with open(temp_path, "w") as f:
        json.dump(new_results, f, indent=2)

    report, md_report, baseline_data = run_regression_check(
        new_results_path=temp_path,
        baseline_path=baseline_path,
        tolerances=tolerances,
    )

    # Clean up temp file
    temp_path.unlink(missing_ok=True)

    # Generate outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "regression_report.md"
    with open(md_path, "w") as f:
        f.write(md_report)
    print(f"Markdown report: {md_path}")

    # Print summary
    print("\n" + "=" * 60)
    if report.is_clean:
        print("✅ NO REGRESSIONS DETECTED")
        print("=" * 60)
        return 0
    else:
        print(f"⚠️  {len(report.regressions)} REGRESSION(S) DETECTED")
        print("=" * 60)
        for reg in report.regressions:
            print(f"\n{reg.metric_name}:")
            print(f"  Baseline: {reg.baseline_value:.4f}")
            print(f"  New: {reg.new_value:.4f}")
            print(f"  Reason: {reg.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(app())
