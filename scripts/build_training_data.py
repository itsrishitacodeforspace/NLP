"""Build a unified training corpus from public legal datasets."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from nlp.datasets.cuad import build_corpus as build_cuad, collect_keyword_bank, iter_examples as iter_cuad
from nlp.datasets.maud import build_corpus as build_maud
from nlp.datasets.unified import write_jsonl


ROOT = Path(__file__).resolve().parents[1]


def build_keyword_bank() -> Path:
    """Persist CUAD spans as a JSON file the rule engine can consult."""
    bank = collect_keyword_bank(ROOT / "data/datasets/cuad/CUADv1.json")
    out = ROOT / "data/processed/cuad_keyword_bank.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(bank, fh, indent=2, ensure_ascii=False)
    return out


def build_unified_corpus() -> Path:
    """Build a single merged JSONL from CUAD + MAUD."""
    examples = []
    examples.extend(iter_cuad(ROOT / "data/datasets/cuad/CUADv1.json"))
    for split in ("train", "dev", "test"):
        path = ROOT / f"data/datasets/maud/data/MAUD_{split}.csv"
        if not path.exists():
            continue
        from nlp.datasets.maud import iter_examples as iter_maud

        examples.extend(iter_maud(path))
    out = ROOT / "data/processed/unified_examples.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = write_jsonl(examples, out)
    counts = Counter(ex.category for ex in examples)
    print(f"Wrote {n} unified rows to {out}")
    print("Top categories:")
    for cat, c in counts.most_common(20):
        print(f"  {c:6d}  {cat}")
    return out


def write_clause_classifier_csv() -> Path:
    """Build a CSV suitable for fine-tuning a sequence classifier.

    Columns: text, category
    """
    out = ROOT / "data/processed/clause_classifier.csv"
    examples = list(iter_cuad(ROOT / "data/datasets/cuad/CUADv1.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["text", "category", "source"])
        for ex in examples:
            writer.writerow([ex.text.replace("\n", " ").strip(), ex.category, ex.source])
    print(f"Wrote {len(examples)} rows to {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-keywords", action="store_true")
    args = parser.parse_args()
    build_cuad(ROOT / "data/datasets/cuad/CUADv1.json", ROOT / "data/processed/cuad_examples.jsonl")
    print("CUAD corpus built.")
    build_maud(
        [
            ROOT / "data/datasets/maud/data/MAUD_train.csv",
            ROOT / "data/datasets/maud/data/MAUD_dev.csv",
            ROOT / "data/datasets/maud/data/MAUD_test.csv",
        ],
        ROOT / "data/processed/maud_examples.jsonl",
    )
    print("MAUD corpus built.")
    build_unified_corpus()
    write_clause_classifier_csv()
    if not args.skip_keywords:
        bank_path = build_keyword_bank()
        print(f"Keyword bank written to {bank_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())