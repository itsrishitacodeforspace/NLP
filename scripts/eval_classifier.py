"""Per-category top-1 diagnostic for the clause classifier.

This is an **exploratory diagnostic, not a benchmark**. A metric computed on a
corpus that overlaps training data (the historical default) is training-overlapping
and cannot be reported as generalization performance. A provenance manifest proves
data lineage only — never model accuracy or predictive validity.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from nlp.clause_classification.classifier import classify_clause
from nlp.datasets.manifest import load_manifest, verify
from nlp.datasets.splits import ProvenanceError, sha256_file

BANNER = "EXPLORATORY - NOT A BENCHMARK"
DEFAULT_INPUT = "data/processed/clause_classifier.csv"


def describe_input(path: Path, *, require_provenance: bool) -> dict:
    """Describe the corpus and its provenance; never writes anything."""
    if not path.exists():
        print(f"ERROR: input corpus not found: {path}", file=sys.stderr)
        return {"ok": False}

    info: dict = {
        "ok": True,
        "input": str(path),
        "sha256": sha256_file(path),
        "manifest_present": False,
        "provenance": "unverified",
    }
    manifest = load_manifest(path)
    if manifest:
        info.update(
            {
                "manifest_present": True,
                "code_revision": manifest.get("code_revision"),
                "row_count": manifest.get("row_count"),
                "sources": manifest.get("sources"),
                "source_authentication": manifest.get("source_authentication"),
            }
        )

    if require_provenance:
        try:
            verify(path, allowed_splits=("train",), require=True, deep=True)
            info["provenance"] = "verified"
        except ProvenanceError as exc:
            info["provenance"] = "unverified"
            info["provenance_error"] = str(exc)
    else:
        info["provenance"] = "verified" if manifest else "unverified"
    return info


def run(csv_path: Path, limit: int) -> int:
    csv.field_size_limit(2**31 - 1)
    correct: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    predicted: dict[str, int] = defaultdict(int)
    rows = 0
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if rows >= limit:
                break
            text = (row.get("text") or "").strip()
            gold = row.get("category", "").strip()
            if not text or not gold:
                continue
            result = classify_clause(text)
            pred = result.labels[0] if result.labels else "Miscellaneous"
            total[gold] += 1
            predicted[pred] += 1
            if pred == gold:
                correct[gold] += 1
            rows += 1

    overall_total = sum(total.values())
    overall_correct = sum(correct.values())
    overall_acc = overall_correct / max(1, overall_total)
    print(f"Top-1 accuracy over {overall_total} rows: {overall_acc:.1%}")
    print()
    print(f"{'Category':<35} {'Total':>6} {'Pred':>6} {'Correct':>8} {'Acc':>7}")
    for cat in sorted(total.keys(), key=lambda c: -total[c]):
        acc = correct[cat] / max(1, total[cat])
        print(f"{cat:<35} {total[cat]:>6} {predicted[cat]:>6} {correct[cat]:>8} {acc:>7.1%}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Exploratory clause-classifier diagnostic")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument(
        "--require-provenance",
        action="store_true",
        help="fail (exit 3) unless the corpus has a verifiable provenance manifest",
    )
    args = parser.parse_args()

    print(BANNER)
    print("A manifest proves data lineage only; it never proves accuracy or predictive validity.")
    info = describe_input(Path(args.input), require_provenance=args.require_provenance)
    if not info.get("ok"):
        return 2
    for key in ("input", "sha256", "provenance", "manifest_present", "code_revision", "row_count"):
        if key in info:
            print(f"  {key}: {info[key]}")
    if "provenance_error" in info:
        print(f"  provenance_error: {info['provenance_error']}")
    if info.get("provenance") != "verified":
        print("  NOTE: corpus provenance is not verified; metrics are training-overlapping.")
    print()

    if args.require_provenance and info.get("provenance") != "verified":
        print("ERROR: --require-provenance set but provenance is not verified.", file=sys.stderr)
        return 3

    return run(Path(args.input), args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
