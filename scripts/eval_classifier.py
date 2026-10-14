"""Per-category top-1 evaluation of the rule-based classifier."""
import csv
import sys
from collections import defaultdict
from pathlib import Path

from nlp.clause_classification.classifier import classify_clause


def main() -> int:
    csv.field_size_limit(2**31 - 1)
    csv_path = Path("data/processed/clause_classifier.csv")
    correct: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    predicted: dict[str, int] = defaultdict(int)
    rows = 0
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if rows >= 2000:
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


if __name__ == "__main__":
    raise SystemExit(main())