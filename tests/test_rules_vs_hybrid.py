"""Smoke tests for scripts/eval_rules_vs_hybrid.py (20-row monkeypatched run)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "eval_rules_vs_hybrid.py"
BANNER = "IN-DISTRIBUTION TRAINING-CORPUS COMPARISON"


def _load_module():
    spec = importlib.util.spec_from_file_location("eval_rules_vs_hybrid_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # allow dataclass-like self-references
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_module()


@pytest.fixture()
def tiny_csv(tmp_path):
    """20-row CSV in the clause_classifier.csv schema (subset of real data)."""
    src = REPO_ROOT / "data" / "processed" / "clause_classifier.csv"
    assert src.exists(), "expected data/processed/clause_classifier.csv in the repo"
    import csv

    csv.field_size_limit(2**31 - 1)
    with src.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames
        rows = [next(reader) for _ in range(20)]
    out = tmp_path / "clause_classifier_20.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return out


@pytest.fixture()
def run_module(monkeypatch, tiny_csv, tmp_path, out_names=("rh.json", "rh.md")):
    out_json = tmp_path / out_names[0]
    out_md = tmp_path / out_names[1]
    monkeypatch.setattr(
        sys, "argv",
        ["eval_rules_vs_hybrid", "--csv", str(tiny_csv), "--sample", "20",
         "--skip-risk-delta", "--out-json", str(out_json), "--out-md", str(out_md)],
    )
    return out_json, out_md


def test_script_runs_on_20_rows_and_writes_required_keys(module, run_module):
    out_json, out_md = run_module
    assert module.main() == 0
    assert out_json.exists(), "output JSON was not written"
    assert out_md.exists(), "output markdown was not written"

    report = json.loads(out_json.read_text(encoding="utf-8"))
    for key in ("banner", "input", "active_components", "metrics", "mode_delta", "hybrid_confusion_top1"):
        assert key in report, f"missing required key {key!r}"
    for mode in ("rule_only", "hybrid"):
        m = report["metrics"][mode]
        for mkey in ("top1", "top3", "abstention", "rule_misc_fallback", "accuracy_top1", "accuracy_top3"):
            assert mkey in m, f"missing metrics[{mode}][{mkey!r}]"
    assert report["input"]["evaluated_rows"] == 20
    assert report["input"]["total_rows"] == 20


def test_honesty_banner_present_in_outputs(module, run_module):
    out_json, out_md = run_module
    module.main()
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert BANNER in report["banner"]
    md_text = out_md.read_text(encoding="utf-8")
    assert BANNER in md_text
    assert "NOT A GENERALIZATION ESTIMATE" in md_text
