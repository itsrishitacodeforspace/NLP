"""Build training corpora from public legal datasets (split-aware).

Split identity is resolved from the *source file* (path + SHA-256) via
``nlp.datasets.splits``, never from a caller-supplied label. Held-out sources are
recorded in manifests but never used to build training artifacts.

Nothing here runs automatically: rebuilding ``data/processed/`` is a separate,
explicitly approved step (Stage 3 gate A3).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from nlp.datasets.cuad import build_corpus as build_cuad
from nlp.datasets.cuad import collect_keyword_bank, doc_ids
from nlp.datasets.cuad import iter_examples as iter_cuad
from nlp.datasets.manifest import build_manifest, source_record, write_manifest
from nlp.datasets.maud import build_corpus as build_maud
from nlp.datasets.maud import iter_examples as iter_maud
from nlp.datasets.splits import ProvenanceError, validate_training_sources
from nlp.datasets.unified import write_jsonl

ROOT = Path(__file__).resolve().parents[1]

CUAD_TRAIN_DEFAULT = "data/datasets/cuad/train_separate_questions.json"
CUAD_TEST_DEFAULT = "data/datasets/cuad/test.json"
MAUD_TRAIN_DEFAULT = "data/datasets/maud/data/MAUD_train.csv"
MAUD_DEV_DEFAULT = "data/datasets/maud/data/MAUD_dev.csv"


def validate_sources(
    cuad_train,
    cuad_test,
    maud_train,
    maud_dev,
    *,
    allow_whole_corpus: bool = False,
) -> dict:
    """Delegate to the shared validator (kept for script-level callers)."""
    return validate_training_sources(
        cuad_train,
        cuad_test,
        maud_train,
        maud_dev,
        allow_whole_corpus=allow_whole_corpus,
    )


def _command(argv) -> str:
    return "python scripts/build_training_data.py " + " ".join(argv)


def build_keyword_bank(cuad_train: Path, out_dir: Path, *, command: str = "") -> Path:
    """Keyword bank from the *training* CUAD spans only."""
    bank = collect_keyword_bank(cuad_train)
    out = Path(out_dir) / "cuad_keyword_bank.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(bank, fh, indent=2, ensure_ascii=False)
    manifest = build_manifest(
        out,
        sources=[source_record(cuad_train)],
        command=command,
        row_count=sum(len(v) for v in bank.values()),
        label_counts={k: len(v) for k, v in bank.items()},
        extra={"doc_count": len(doc_ids(cuad_train))},
    )
    write_manifest(out, manifest)
    return out


def build_cuad_examples(cuad_train: Path, out_dir: Path, *, command: str = "") -> Path:
    out = Path(out_dir) / "cuad_examples.jsonl"
    count = build_cuad(cuad_train, out)
    manifest = build_manifest(
        out,
        sources=[source_record(cuad_train)],
        command=command,
        row_count=count,
        extra={"doc_count": len(doc_ids(cuad_train))},
    )
    write_manifest(out, manifest)
    return out


def build_maud_examples(maud_train: Path, maud_dev: Path, out_dir: Path, *, command: str = "") -> Path:
    out = Path(out_dir) / "maud_examples.jsonl"
    count = build_maud([maud_train, maud_dev], out)
    manifest = build_manifest(
        out,
        sources=[source_record(maud_train), source_record(maud_dev)],
        command=command,
        row_count=count,
    )
    write_manifest(out, manifest)
    return out


def build_unified_corpus(
    cuad_train: Path, maud_train: Path, maud_dev: Path, out_dir: Path, *, command: str = ""
) -> Path:
    examples = list(iter_cuad(cuad_train))
    examples.extend(iter_maud(maud_train))
    examples.extend(iter_maud(maud_dev))
    out = Path(out_dir) / "unified_examples.jsonl"
    count = write_jsonl(examples, out)
    counts = Counter(ex.category for ex in examples)
    manifest = build_manifest(
        out,
        sources=[source_record(cuad_train), source_record(maud_train), source_record(maud_dev)],
        command=command,
        row_count=count,
        label_counts=dict(counts),
    )
    write_manifest(out, manifest)
    return out


def write_clause_classifier_csv(cuad_train: Path, out_dir: Path, *, command: str = "") -> Path:
    """Clause-level classification corpus from *present* CUAD spans (train only)."""
    out = Path(out_dir) / "clause_classifier.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    examples = list(iter_cuad(cuad_train))
    seen: set[tuple[str, str]] = set()
    written = 0
    label_counts: Counter = Counter()
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        # doc_id/split give every training row stable source lineage (Rev. 7 / A3).
        writer.writerow(["text", "category", "source", "doc_id", "split"])
        for ex in examples:
            if ex.metadata.get("label") != "present":
                continue
            text = ex.text.replace("\n", " ").strip()
            key = (text, ex.category)
            if not text or key in seen:
                continue
            seen.add(key)
            writer.writerow(
                [
                    text,
                    ex.category,
                    ex.source,
                    ex.metadata.get("title", ""),
                    ex.metadata.get("split", "unknown"),
                ]
            )
            label_counts[ex.category] += 1
            written += 1
    manifest = build_manifest(
        out,
        sources=[source_record(cuad_train)],
        command=command,
        row_count=written,
        label_counts=dict(label_counts),
        extra={"doc_count": len(doc_ids(cuad_train))},
    )
    write_manifest(out, manifest)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Build split-aware training corpora")
    parser.add_argument("--cuad-train", default=CUAD_TRAIN_DEFAULT)
    parser.add_argument("--cuad-test", default=CUAD_TEST_DEFAULT, help="held-out; recorded only")
    parser.add_argument("--maud-train", default=MAUD_TRAIN_DEFAULT)
    parser.add_argument("--maud-dev", default=MAUD_DEV_DEFAULT)
    parser.add_argument("--out-dir", default="data/processed")
    parser.add_argument("--skip-keywords", action="store_true")
    parser.add_argument(
        "--allow-whole-corpus",
        action="store_true",
        help="permit a whole-corpus source (e.g. CUADv1.json); the output is leaky by construction",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    try:
        specs = validate_sources(
            args.cuad_train,
            args.cuad_test,
            args.maud_train,
            args.maud_dev,
            allow_whole_corpus=args.allow_whole_corpus,
        )
    except ProvenanceError as exc:
        print(f"PROVENANCE ERROR: {exc}", file=sys.stderr)
        return 2

    command = _command(sys.argv[1:])
    print(f"Sources: {specs['cuad_train'].path} [{specs['cuad_train'].split}] -> {out_dir}")

    build_cuad_examples(Path(args.cuad_train), out_dir, command=command)
    build_maud_examples(Path(args.maud_train), Path(args.maud_dev), out_dir, command=command)
    build_unified_corpus(Path(args.cuad_train), Path(args.maud_train), Path(args.maud_dev), out_dir, command=command)
    write_clause_classifier_csv(Path(args.cuad_train), out_dir, command=command)
    if not args.skip_keywords:
        build_keyword_bank(Path(args.cuad_train), out_dir, command=command)
    print("Done. Manifests written alongside each artifact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
