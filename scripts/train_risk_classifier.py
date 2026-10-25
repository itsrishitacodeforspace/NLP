"""Train the weakly-supervised ML risk classifier.

Weak labels come from the rule engine (`nlp.risk_scoring.risk_model.weak_label`)
applied to the CUAD clause corpus. The resulting TF-IDF + LogisticRegression
model is used only as a recall booster for clauses the rules did not flag, so
imperfect weak labels are acceptable — its job is to generalise to paraphrases.

Usage:
    uv run python scripts/train_risk_classifier.py --limit 6000
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import List

from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

from nlp.risk_scoring.risk_model import save, train, weak_label

csv.field_size_limit(2**31 - 1)


def load_texts(csv_path: Path, limit: int) -> List[str]:
    texts: List[str] = []
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            texts.append(text)
            if limit and len(texts) >= limit:
                break
    return texts


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the ML risk classifier")
    parser.add_argument("--input", default="data/processed/clause_classifier.csv")
    parser.add_argument("--output", default="models/risk_classifier.joblib")
    parser.add_argument("--limit", type=int, default=6000, help="max rows to use")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Corpus not found: {input_path}. Run scripts/build_training_data.py first.")
        return 1

    texts = load_texts(input_path, args.limit)
    if not texts:
        print("No usable rows found.")
        return 1
    print(f"Labelling {len(texts)} clauses with the rule engine...")
    labels = [weak_label(t) for t in texts]

    distribution = Counter(labels)
    print("Weak-label distribution (raw):")
    for label, count in distribution.most_common():
        print(f"  {label:>8}: {count}")

    # Drop classes too rare to survive a stratified split.
    keep = {label for label, count in distribution.items() if count >= 5}
    total_kept = sum(count for label, count in distribution.items() if label in keep)
    if len(keep) < 2 or total_kept < 20:
        keep = {label for label, count in distribution.items() if count >= 2}
    pairs = [(t, label) for t, label in zip(texts, labels, strict=True) if label in keep]
    if len({label for _, label in pairs}) < 2:
        print("Need at least two severity classes with enough rows; aborting.")
        return 1
    print("Training distribution:", dict(Counter(label for _, label in pairs)))

    x_train, x_test, y_train, y_test = train_test_split(
        [t for t, _ in pairs],
        [label for _, label in pairs],
        test_size=0.15,
        random_state=42,
        stratify=[label for _, label in pairs],
    )
    model = train(x_train, y_train)
    print("\nHold-out report (weak labels — indicative only):")
    print(classification_report(y_test, model.pipeline.predict(x_test), zero_division=0))

    out = save(model, Path(args.output))
    print(f"Saved risk classifier to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
