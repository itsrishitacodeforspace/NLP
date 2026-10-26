"""Fail-closed provenance + row-level lineage verification for generated artifacts.

Two independent layers must both pass:
  1. **Manifest** - artifact hash, source hashes and split identity (may be forged).
  2. **Row lineage** - every row's ``doc_id``/``split`` must belong to an approved,
     training-only document set. This is what prevents a forged manifest from
     rescuing an artifact whose rows actually come from held-out documents.

Exit code 0 only when every required artifact passes *both* layers. A manifest
proves data lineage only - never model accuracy or predictive validity.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable

from nlp.datasets.manifest import verify
from nlp.datasets.splits import ProvenanceError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CUAD_TRAIN = PROJECT_ROOT / "data" / "datasets" / "cuad" / "train_separate_questions.json"
CUAD_TEST = PROJECT_ROOT / "data" / "datasets" / "cuad" / "test.json"

CSV_COLUMNS = ("text", "category", "source", "doc_id", "split")

# Artifacts with no per-row lineage: reported explicitly, never assumed valid.
LINEAGE_EXEMPT = {
    "cuad_keyword_bank.json": "aggregated keyword bank; no per-row lineage exists (manifest-only)",
}

# artifact name -> splits permitted in its sources AND in its rows
REQUIRED: list[tuple[str, tuple[str, ...]]] = [
    ("clause_classifier.csv", ("train",)),
    ("cuad_keyword_bank.json", ("train",)),
    ("cuad_examples.jsonl", ("train",)),
    ("maud_examples.jsonl", ("train", "dev")),
    ("unified_examples.jsonl", ("train", "dev")),
]


def _titles(path: Path) -> set[str]:
    """Approved document titles, whitespace-normalised on both sides of the compare.

    NOTE: some CUAD titles carry trailing spaces (e.g. 'Sonos, Inc. - Manufacturing
    Agreement '), so the approved set is stripped here and row values are stripped
    in ``_check_row`` - otherwise a valid row would fail a naive exact match.
    """
    with path.open(encoding="utf-8") as fh:
        return {(d.get("title") or "").strip() for d in json.load(fh)["data"] if d.get("title")}


def _approved_docs() -> dict:
    return {"train": _titles(CUAD_TRAIN), "held_out": _titles(CUAD_TEST)}


def _check_row(row: dict, *, idx: int, name: str, allowed: tuple[str, ...], approved: dict) -> None:
    doc_id = (row.get("doc_id") or "").strip()
    split = (row.get("split") or "").strip()
    if not doc_id:
        raise ProvenanceError(f"{name}: empty doc_id at line {idx}")
    if split not in allowed:
        raise ProvenanceError(f"{name}: split '{split}' not permitted at line {idx}")
    if doc_id in approved["held_out"]:
        raise ProvenanceError(f"{name}: held-out document '{doc_id}' at line {idx}")
    if split == "train" and doc_id not in approved["train"]:
        raise ProvenanceError(f"{name}: unknown training document '{doc_id}' at line {idx}")


def check_csv_lineage(path: Path, allowed_splits: Iterable[str]) -> dict:
    """Validate every clause_classifier.csv row against approved documents."""
    allowed = tuple(allowed_splits)
    approved = _approved_docs()
    csv.field_size_limit(2**31 - 1)
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ProvenanceError(f"{path.name}: missing lineage columns {missing}")
        rows = 0
        for idx, row in enumerate(reader, start=2):
            _check_row(row, idx=idx, name=path.name, allowed=allowed, approved=approved)
            rows += 1
    return {"kind": "csv", "rows": rows, "allowed_splits": list(allowed)}


def check_jsonl_lineage(path: Path, allowed_splits: Iterable[str]) -> dict:
    """Validate CUAD/MAUD JSONL rows: split always, document id for CUAD rows."""
    allowed = tuple(allowed_splits)
    approved = _approved_docs()
    rows = 0
    with path.open(encoding="utf-8") as fh:
        for idx, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            meta = record.get("metadata") or {}
            split = (meta.get("split") or "").strip()
            source = record.get("source")
            if source == "cuad":
                title = meta.get("title")
                if not title:
                    raise ProvenanceError(f"{path.name}: CUAD row without title at line {idx}")
                _check_row(
                    {"doc_id": title, "split": split},
                    idx=idx,
                    name=path.name,
                    allowed=allowed,
                    approved=approved,
                )
            elif split not in allowed:
                raise ProvenanceError(f"{path.name}: split '{split}' not permitted at line {idx}")
            rows += 1
    return {"kind": "jsonl", "rows": rows, "allowed_splits": list(allowed)}


def check_row_lineage(path: Path, allowed_splits: Iterable[str]) -> dict:
    name = Path(path).name
    if name.endswith(".csv"):
        return check_csv_lineage(Path(path), allowed_splits)
    if name.endswith(".jsonl"):
        return check_jsonl_lineage(Path(path), allowed_splits)
    raise ProvenanceError(f"no row-lineage checker for {name}")


def verify_artifact(path: Path, allowed_splits: Iterable[str]) -> dict:
    """Manifest verification + row-level lineage. Raises ProvenanceError on failure.

    Aggregated artifacts without rows (e.g. the keyword bank) have no per-row
    lineage; they are explicitly reported as manifest-only rather than silently
    treated as verified lineage.
    """
    artifact = Path(path)
    allowed = tuple(allowed_splits)
    manifest_result = verify(artifact, allowed_splits=allowed, require=True, deep=True)
    if artifact.name in LINEAGE_EXEMPT:
        lineage = {"kind": "none", "rows": None, "note": LINEAGE_EXEMPT[artifact.name]}
    else:
        lineage = check_row_lineage(artifact, allowed)
    return {"manifest": manifest_result, "lineage": lineage}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify provenance + row lineage")
    parser.add_argument("--out-dir", default="data/processed")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="skip absent artifacts explicitly (exploratory mode); never silently passes",
    )
    args = parser.parse_args()

    failures = 0
    skipped = 0
    for name, allowed in REQUIRED:
        path = Path(args.out_dir) / name
        if not path.exists():
            if args.allow_missing:
                print(f"SKIP  {path} (absent; exploratory mode)")
                skipped += 1
                continue
            print(f"FAIL  {path} (missing)", file=sys.stderr)
            failures += 1
            continue
        try:
            result = verify_artifact(path, allowed)
        except ProvenanceError as exc:
            print(f"FAIL  {path}: {exc}", file=sys.stderr)
            failures += 1
            continue
        man = result["manifest"]
        lin = result["lineage"]
        print(
            f"OK    {path} sources={man['source_count']} allowed={man['allowed_splits']} "
            f"rows={lin['rows']} lineage={lin['kind']}"
        )

    print(f"\n{failures} failure(s), {skipped} skipped")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
