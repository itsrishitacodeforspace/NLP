"""Train a TF-IDF + Logistic Regression classifier on CUAD gold data.

This produces a *real* ML model (no torch needed) that we can drop in as a
stronger alternative to the keyword-based rule classifier. It's small,
fast, and persists to ``models/tfidf_classifier.joblib`` so subsequent
runs avoid retraining.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import List, Tuple

import joblib  # type: ignore
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
from sklearn.linear_model import LogisticRegression  # type: ignore
from sklearn.metrics import classification_report  # type: ignore
from sklearn.model_selection import train_test_split  # type: ignore
from sklearn.pipeline import Pipeline  # type: ignore

from nlp.clause_classification.tfidf_model import TrainedClassifier

ROOT = Path(__file__).resolve().parents[1]


def load_corpus(csv_path: Path) -> Tuple[List[str], List[str]]:
    csv.field_size_limit(2**31 - 1)
    texts: List[str] = []
    labels: List[str] = []
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            text = (row.get("text") or "").strip()
            label = (row.get("category") or "").strip()
            if not text or not label:
                continue
            texts.append(text)
            labels.append(label)
    return texts, labels


def train(corpus_path: Path, model_path: Path) -> TrainedClassifier:
    texts, labels = load_corpus(corpus_path)
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.15, random_state=42, stratify=labels,
    )
    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=2,
                    max_df=0.95,
                    sublinear_tf=True,
                    stop_words="english",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    C=4.0,
                    class_weight="balanced",
                    solver="liblinear",
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)

    print("Validation report (top-1):")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "labels": sorted(set(labels))}, model_path)
    print(f"Saved model to {model_path}")
    return TrainedClassifier(pipeline=pipeline, labels=sorted(set(labels)))


def load_trained(model_path: Path) -> TrainedClassifier:
    from nlp.clause_classification.tfidf_model import load_trained as _load

    model = _load(model_path)
    if model is None:
        raise FileNotFoundError(model_path)
    return model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/processed/clause_classifier.csv")
    parser.add_argument("--output", default="models/tfidf_classifier.joblib")
    args = parser.parse_args()
    train(Path(args.input), Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
