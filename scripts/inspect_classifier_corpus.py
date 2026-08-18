"""Inspect the unified classifier corpus."""
import csv
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    csv.field_size_limit(2**31 - 1)
    csv_path = Path("data/processed/clause_classifier.csv")
    rows: list[dict] = []
    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    print(f"Total rows: {len(rows)}")
    print(f"Columns: {list(rows[0].keys())}")

    by_cat: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r["text"][:140])

    for cat in ("Indemnification", "Limitation of Liability", "Termination", "Governing Law"):
        print(f"\n{cat}:")
        for t in by_cat.get(cat, [])[:3]:
            print(f"  - {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())