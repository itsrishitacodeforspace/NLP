"""MAUD (Merger Agreement Understanding Dataset) loader.

MAUD ships pre-extracted clauses for ~150 merger agreements. Each row in
``MAUD_train.csv``/``MAUD_dev.csv``/``MAUD_test.csv`` has a
``clause_id``, ``contract_id``, ``clause_type`` (sub-question), ``clause_text``,
and a list of ``answer_choices`` with labels.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Iterator, List

from nlp.datasets.unified import (
    TrainingExample,
    map_maud_label,
    write_jsonl,
)


# Mapping from MAUD sub-question -> our internal clause category.
MAUD_TYPE_TO_INTERNAL = {
    "Affiliate": "Miscellaneous",
    "Anti-Assignment": "Assignment",
    "Audit Rights": "Audit Rights",
    "Books and Records": "Audit Rights",
    "Cap on Liability": "Limitation of Liability",
    "Change of Control": "Assignment",
    "Competitive Restriction Exception": "Non-Compete / Non-Solicit",
    "Covenant Not To Sue": "Miscellaneous",
    "Effective Date": "Term and Renewal",
    "Exclusivity": "Non-Compete / Non-Solicit",
    "Expiration Date": "Term and Renewal",
    "Governing Law": "Governing Law",
    "Indemnification": "Indemnification",
    "Insurance": "Insurance",
    "IP Ownership Assignment": "Intellectual Property",
    "Joint IP Ownership": "Intellectual Property",
    "License Grant": "Intellectual Property",
    "Limitation of Liability": "Limitation of Liability",
    "Liquidated Damages": "Limitation of Liability",
    "Minimum Commitment": "Payment Terms",
    "Most Favored Nation": "Payment Terms",
    "Non-Compete": "Non-Compete / Non-Solicit",
    "Non-Solicit of Customers": "Non-Compete / Non-Solicit",
    "Non-Solicit of Employees": "Non-Compete / Non-Solicit",
    "Non-Transferable License": "Intellectual Property",
    "Notice Period to Terminate Renewal": "Term and Renewal",
    "Post-Termination Services": "Termination",
    "Price Restrictions": "Payment Terms",
    "Renewal Term": "Term and Renewal",
    "Revenue/Profit Sharing": "Payment Terms",
    "Rofr/Rofo/Rofn": "Assignment",
    "Source Code Escrow": "Intellectual Property",
    "Term": "Term and Renewal",
    "Termination for Convenience": "Termination",
    "Third Party Beneficiary": "Miscellaneous",
    "Uncapped Liability": "Limitation of Liability",
    "Volume Restriction": "Payment Terms",
    "Warranty Duration": "Warranty",
    "Drag-Along": "Miscellaneous",
    "Tag-Along": "Miscellaneous",
    "Right of First Refusal/Offer": "Assignment",
    "No-Shop": "Non-Compete / Non-Solicit",
}


def iter_examples(split_csv: Path) -> Iterator[TrainingExample]:
    split_csv = Path(split_csv)
    with split_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row_idx, row in enumerate(reader):
            clause_type = row.get("clause_type", "").strip()
            if not clause_type:
                continue
            internal = MAUD_TYPE_TO_INTERNAL.get(clause_type) or map_maud_label(clause_type)
            if not internal:
                continue
            clause_text = (row.get("clause_text") or "").strip()
            if not clause_text:
                continue

            contract_id = (row.get("contract_id") or row.get("filename") or f"maud_{row_idx}").strip()
            answer_choices = row.get("answer_choices") or ""
            answer_label = row.get("answer_label", "").strip()
            metadata = {
                "clause_type": clause_type,
                "answer_label": answer_label,
                "answer_choices": answer_choices[:400],
            }
            yield TrainingExample(
                example_id=f"maud_{contract_id}_{clause_type.replace(' ', '_')}_{row_idx}",
                source="maud",
                contract_id=str(contract_id).lower(),
                text=clause_text,
                category=internal,
                spans=[],
                metadata=metadata,
            )


def build_corpus(split_csvs: Iterable[Path], out_path: Path) -> int:
    rows: List[TrainingExample] = []
    for csv_path in split_csvs:
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