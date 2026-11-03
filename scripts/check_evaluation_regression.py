#!/usr/bin/env python3
"""Check for evaluation regressions by comparing to a baseline.

Exit codes:
  0 = no regressions detected
  1 = regressions detected, or the check is invalid (self-comparison)
  2 = nothing to measure (no baseline and --create-baseline not given, or the
      baseline was just created from these very results)
"""
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


def run_check(
    baseline_path: Path = DEFAULT_BASELINE,
    new_results_path: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    create_baseline: bool = False,
    classification_f1_min: float = 0.0,
    classification_f1_degradation: float = 5.0,
    ner_entity_f1_min: float = 0.0,
    ner_entity_f1_degradation: float = 5.0,
    obligation_detection_f1_min: float = 0.0,
    obligation_detection_f1_degradation: float = 5.0,
    risk_detection_f1_min: float = 0.0,
    risk_detection_f1_degradation: float = 5.0,
    evidence_mean_iou_min: float = 0.0,
    evidence_mean_iou_degradation: float = 5.0,
    *,
    temp_path: Path | None = None,
) -> int:
    """Core logic for the regression check CLI (unit-testable without typer)."""
    from nlp.evaluation.metrics_integration import (
        current_git_revision,
        generate_integrated_report_json,
        run_integrated_evaluation,
    )
    from nlp.evaluation.regression_detector import (
        create_baseline as write_baseline,
    )
    from nlp.evaluation.regression_detector import (
        is_same_results_file,
        load_baseline,
        run_regression_check,
    )

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

    print(f"Loading baseline from: {baseline_path}")
    if not baseline_path.exists() and not create_baseline:
        print(f"Error: Baseline not found at {baseline_path}")
        print("There is nothing to measure against. Establish a baseline with")
        print("--create-baseline (explicit) or pass an existing --baseline path.")
        print("Status: NOTHING TO MEASURE (exit 2).")
        return 2

    if create_baseline:
        # Loud, deliberate act: this overwrites the baseline with the current
        # results, so the comparison is a self-comparison by construction and
        # carries no information. Write the baseline and stop — do NOT print a
        # pass.
        print("⚠️  --create-baseline: OVERWRITING the baseline with the CURRENT results.")
        write_baseline(new_results, baseline_path, git_revision=current_git_revision())
        print(f"Baseline written to: {baseline_path} (git revision: {current_git_revision()})")
        print("   The immediate comparison is a self-comparison and carries no")
        print("   information; review this baseline before treating it as authoritative.")
        print("   Next run: compare a later run's results against this baseline.")
        print("Status: BASELINE CREATED — NOTHING COMPARED (exit 2).")
        return 2

    # Materialise new results so content-hash comparison can see them
    temp = temp_path or (ROOT / "temp_new_results.json")
    with open(temp, "w") as f:
        json.dump(new_results, f, indent=2)

    try:
        baseline_data = load_baseline(baseline_path)
        if is_same_results_file(baseline_path, temp, baseline_data):
            print(
                "⛔ SELF-COMPARISON DETECTED — check INVALID: baseline and new "
                "results are identical (same file or same content). Comparing a "
                "run to itself is a tautology. Do not treat this as a clean "
                "pass. Establish the baseline from a reviewed run, then "
                "re-check against a later run's results."
            )
            md_report = (
                "# Regression Detection Report\n\n"
                "## ⛔ SELF-COMPARISON — RESULT INVALID\n\n"
                "The baseline and the new results are the same payload. A run "
                "compared against itself cannot detect any regression; this "
                "report must not be read as 'no regressions'. Regenerate the "
                "baseline from an independently reviewed run.\n"
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "regression_report.md").write_text(md_report, encoding="utf-8")
            print(f"Markdown report: {output_dir / 'regression_report.md'}")
            print("Status: SELF-COMPARISON (exit 1).")
            return 1

        report_obj, md_report, _ = run_regression_check(
            new_results_path=temp,
            baseline_path=baseline_path,
            tolerances=tolerances,
        )
    finally:
        temp.unlink(missing_ok=True)

    # Generate outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / "regression_report.md"
    with open(md_path, "w") as f:
        f.write(md_report)
    print(f"Markdown report: {md_path}")

    # Print summary
    print("\n" + "=" * 60)
    if report_obj.is_self_comparison:
        print("⛔ SELF-COMPARISON: baseline == new results. The check is INVALID.")
        print("   Do not treat this as a clean pass. Regenerate the baseline from an")
        print("   independently reviewed run, then re-check against it.")
        print("=" * 60)
        return 1
    if report_obj.is_clean:
        print("✅ NO REGRESSIONS DETECTED")
        if report_obj.uninformative:
            print(
                f"(note: {len(report_obj.uninformative)} uninformative metric(s) with a "
                f"zero baseline — nothing to measure for those)"
            )
        print("=" * 60)
        return 0
    print(f"⚠️  {len(report_obj.regressions)} REGRESSION(S) DETECTED")
    print("=" * 60)
    for reg in report_obj.regressions:
        print(f"\n{reg.metric_name}:")
        print(f"  Baseline: {reg.baseline_value:.4f}")
        print(f"  New: {reg.new_value:.4f}")
        print(f"  Reason: {reg.reason}")
    return 1


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
    create_baseline: bool = typer.Option(
        False,
        "--create-baseline",
        help=(
            "Explicitly create/overwrite the baseline from the current results. "
            "Loud on purpose: a self-created baseline makes the first run "
            "uninformative, so it must be a deliberate act, not a silent default."
        ),
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
    return run_check(
        baseline_path=baseline_path,
        new_results_path=new_results_path,
        output_dir=output_dir,
        create_baseline=create_baseline,
        classification_f1_min=classification_f1_min,
        classification_f1_degradation=classification_f1_degradation,
        ner_entity_f1_min=ner_entity_f1_min,
        ner_entity_f1_degradation=ner_entity_f1_degradation,
        obligation_detection_f1_min=obligation_detection_f1_min,
        obligation_detection_f1_degradation=obligation_detection_f1_degradation,
        risk_detection_f1_min=risk_detection_f1_min,
        risk_detection_f1_degradation=risk_detection_f1_degradation,
        evidence_mean_iou_min=evidence_mean_iou_min,
        evidence_mean_iou_degradation=evidence_mean_iou_degradation,
    )


if __name__ == "__main__":
    # Typer's app() returns None for a single-command app (it calls sys.exit
    # internally in some versions). To guarantee the exit code from run_check
    # propagates, parse argv ourselves and call run_check directly.
    _defaults: dict = {
        "baseline_path": DEFAULT_BASELINE,
        "new_results_path": None,
        "output_dir": DEFAULT_OUTPUT_DIR,
        "create_baseline": False,
        "classification_f1_min": 0.0,
        "classification_f1_degradation": 5.0,
        "ner_entity_f1_min": 0.0,
        "ner_entity_f1_degradation": 5.0,
        "obligation_detection_f1_min": 0.0,
        "obligation_detection_f1_degradation": 5.0,
        "risk_detection_f1_min": 0.0,
        "risk_detection_f1_degradation": 5.0,
        "evidence_mean_iou_min": 0.0,
        "evidence_mean_iou_degradation": 5.0,
    }
    _arg_map = {
        "--baseline": ("baseline_path", Path),
        "-b": ("baseline_path", Path),
        "--results": ("new_results_path", Path),
        "-r": ("new_results_path", Path),
        "--output-dir": ("output_dir", Path),
        "-o": ("output_dir", Path),
        "--create-baseline": ("create_baseline", bool),
        "--classification-f1-min": ("classification_f1_min", float),
        "--classification-f1-degradation": ("classification_f1_degradation", float),
        "--ner-entity-f1-min": ("ner_entity_f1_min", float),
        "--ner-entity-f1-degradation": ("ner_entity_f1_degradation", float),
        "--obligation-detection-f1-min": ("obligation_detection_f1_min", float),
        "--obligation-detection-f1-degradation": ("obligation_detection_f1_degradation", float),
        "--risk-detection-f1-min": ("risk_detection_f1_min", float),
        "--risk-detection-f1-degradation": ("risk_detection_f1_degradation", float),
        "--evidence-mean-iou-min": ("evidence_mean_iou_min", float),
        "--evidence-mean-iou-degradation": ("evidence_mean_iou_degradation", float),
    }
    _args = sys.argv[1:]
    _i = 0
    while _i < len(_args):
        _a = _args[_i]
        if _a == "--create-baseline":
            _defaults["create_baseline"] = True
        elif _a in _arg_map:
            _key, _conv = _arg_map[_a]
            _i += 1
            _defaults[_key] = _conv(_args[_i])
        _i += 1
    sys.exit(run_check(**_defaults))
