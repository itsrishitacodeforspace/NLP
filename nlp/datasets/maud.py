"""MAUD (Merger Agreement Understanding Dataset) loader.

MAUD rows are extractive QA pairs over merger agreements. The real columns
are: ``data_type, contract_name, text, answer, label, question, subquestion,
text_type, id, category``. ``text_type`` is the clause-level taxonomy; the
other columns describe the specific question and its answer class.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable, Iterator, List

from nlp.datasets.splits import ProvenanceError, resolve_source
from nlp.datasets.unified import TrainingExample, write_jsonl
from nlp.taxonomy import map_maud_label

MAX_SNIPPET_CHARS = 1500


def split_for(split_csv: Path) -> str:
    """Split derived from file identity; ``unknown`` when not allowlisted."""
    try:
        return resolve_source(split_csv).split
    except ProvenanceError:
        return "unknown"


def _snippet(text: str, answer: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= MAX_SNIPPET_CHARS:
        return text
    answer = (answer or "").strip()
    if 2 < len(answer) <= 120:
        idx = text.lower().find(answer.lower())
        if idx != -1:
            start = max(0, idx - MAX_SNIPPET_CHARS // 3)
            return text[start : start + MAX_SNIPPET_CHARS].strip()
    return text[:MAX_SNIPPET_CHARS].strip()


def iter_examples(split_csv: Path) -> Iterator[TrainingExample]:
    split_csv = Path(split_csv)
    split = split_for(split_csv)
    with split_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row_idx, row in enumerate(reader):
            text_type = (row.get("text_type") or "").strip()
            question = (row.get("question") or "").strip()
            subquestion = (row.get("subquestion") or "").strip()
            internal = map_maud_label(text_type) or map_maud_label(question)
            if not internal:
                internal = map_maud_label(subquestion)
            if not internal:
                continue

            text = _snippet(row.get("text") or "", row.get("answer") or "")
            if not text:
                continue
            contract = (row.get("contract_name") or f"maud_{row_idx}").strip()
            contract_id = re.sub(r"[^A-Za-z0-9]+", "_", contract).strip("_").lower()
            row_id = (row.get("id") or row_idx)
            metadata = {
                "text_type": text_type,
                "question": question,
                "subquestion": subquestion,
                "answer": (row.get("answer") or "")[:400],
                "label": row.get("label", ""),
                "data_type": row.get("data_type", ""),
                "category": row.get("category", ""),
                "split": split,
            }
            yield TrainingExample(
                example_id=f"maud_{contract_id}_{row_id}",
                source="maud",
                contract_id=contract_id,
                text=text,
                category=internal,
                spans=[],
                metadata=metadata,
            )


def build_corpus(split_csvs: Iterable[Path], out_path: Path) -> int:
    rows: List[TrainingExample] = []
    for csv_path in split_csvs:
        spec = resolve_source(csv_path)
        if spec.split in {"test", "mixed"}:
            raise ProvenanceError(
                f"refusing to build a training corpus from MAUD split '{spec.split}': {spec.path}"
            )
        rows.extend(iter_examples(csv_path))
    return write_jsonl(rows, out_path)


def main() -> int:  # pragma: no cover - CLI helper
    import argparse

    parser = argparse.ArgumentParser(description="Build MAUD training corpus")
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=[
            "data/datasets/maud/data/MAUD_train.csv",
            "data/datasets/maud/data/MAUD_dev.csv",
            "data/datasets/maud/data/MAUD_test.csv",
        ],
    )
    parser.add_argument(
        "--output",
        default="data/processed/maud_examples.jsonl",
    )
    args = parser.parse_args()

    n = build_corpus([Path(p) for p in args.inputs], Path(args.output))
    print(f"Wrote {n} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
