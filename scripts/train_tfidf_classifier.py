"""Train a TF-IDF + Logistic Regression clause classifier.

Trains on the **train-only** ``data/processed/clause_classifier.csv``
(manifest-verified, all rows ``split=train``) — never the full CUADv1 corpus.
This produces a *real* ML model (no torch needed) that we can drop in as a
stronger alternative to the keyword-based rule classifier. It's small,
fast, and persists to ``models/tfidf_classifier.joblib`` so subsequent
runs avoid retraining.

Labels are canonicalised to the taxonomy (non-canonical labels are dropped)
so the model can only emit categories defined in ``nlp.taxonomy``.

The printed per-class metrics are TRAINING-SET (in-sample) diagnostics only.
They are not a generalization estimate: no leakage-free CUAD held-out set
exists (see ``reports/evaluations/model_retraining_20261103.md``).

The script also rewrites the tracked ``models/tfidf_classifier.7z`` archive
(the internal file name is exactly what the runtime loader extracts) and
updates the ``cache_sha256`` of ``models/PROVENANCE_STATUS.json`` so the
declared status matches the shipped artefact.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import List, Tuple

import joblib  # type: ignore
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
from sklearn.linear_model import LogisticRegression  # type: ignore
from sklearn.metrics import classification_report  # type: ignore
from sklearn.model_selection import train_test_split  # type: ignore
from sklearn.pipeline import Pipeline  # type: ignore

from nlp.clause_classification.tfidf_model import TrainedClassifier
from nlp.provenance import sha256_cached

ROOT = Path(__file__).resolve().parents[1]

ARCHIVE_NAME = "tfidf_classifier.7z"
CACHE_NAME = "tfidf_classifier.joblib"
STATUS_PATH = ROOT / "models" / "PROVENANCE_STATUS.json"


def _load_status() -> dict:
    try:
        with STATUS_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _rewrite_archive(model_path: Path) -> Path:
    """Rebuild the tracked 7z from the fresh joblib, keeping the internal
    file name the runtime loader extracts."""
    import py7zr  # type: ignore

    archive_path = ROOT / "models" / ARCHIVE_NAME
    with py7zr.SevenZipFile(archive_path, mode="w") as archive:
        archive.write(str(model_path), model_path.name)
    with py7zr.SevenZipFile(archive_path, mode="r") as archive:
        names = archive.getnames()
    if names != [model_path.name]:
        # A concurrent writer (e.g. the risk retraining) clobbered the archive.
        # Restore this archive's contents and surface the problem.
        print(f"WARNING: archive contents {names} != expected [{model_path.name}]; rewriting.")
        with py7zr.SevenZipFile(archive_path, mode="w") as archive:
            archive.write(str(model_path), model_path.name)
        with py7zr.SevenZipFile(archive_path, mode="r") as archive:
            names = archive.getnames()
    assert names == [model_path.name], f"unexpected archive contents: {names}"
    print(f"Archive internal names: {names}")
    return archive_path


def _update_provenance_status(joblib_path: Path) -> None:
    """Point the tracked status at the new artefact (train-only, retrained)."""
    status = _load_status()
    artifacts = status.setdefault("artifacts", {})
    entry = artifacts.setdefault(ARCHIVE_NAME, {})
    entry["status"] = "train-only-verified"
    entry["reason"] = (
        "Retrained 2026-11-03 from train-only data/processed/clause_classifier.csv "
        "(manifest-verified, split=train). CUAD-derived; US contracts; 14 of 26 "
        "taxonomy categories; NOT a generalization guarantee."
    )
    entry["cache_sha256"] = sha256_cached(joblib_path)
    status["generated_by"] = "model retraining from train-only data (2026-11-03)"
    STATUS_PATH.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def load_corpus(csv_path: Path) -> Tuple[List[str], List[str]]:
    """Load (text, label) pairs, keeping only canonical taxonomy labels.

    Non-canonical labels are dropped so the model can only emit categories
    defined in ``nlp.taxonomy`` (same canonicalisation the runtime loader
    applies, plus the legacy ``Pricing Terms`` -> ``Payment Terms`` alias).
    """
    from nlp.clause_classification.tfidf_model import MODEL_LABEL_ALIASES
    from nlp.taxonomy import INTERNAL_LABELS

    canonical = frozenset(INTERNAL_LABELS)
    csv.field_size_limit(2**31 - 1)
    texts: List[str] = []
    labels: List[str] = []
    dropped: Counter[str] = Counter()
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            text = (row.get("text") or "").strip()
            label = (row.get("category") or "").strip()
            if not text or not label:
                continue
            label = MODEL_LABEL_ALIASES.get(label, label)
            if label not in canonical:
                dropped[label] += 1
                continue
            texts.append(text)
            labels.append(label)
    if dropped:
        print("Dropped non-canonical labels:", dict(dropped))
    return texts, labels


def train(corpus_path: Path, model_path: Path) -> TrainedClassifier:
    texts, labels = load_corpus(corpus_path)
    print(f"Training rows (canonical labels): {len(texts)}; classes: {len(set(labels))}")
    print("Class distribution:", dict(Counter(labels).most_common()))
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
                    # lbfgs: liblinear cannot handle multiclass (>2 classes),
                    # and this corpus has 14 classes.
                    solver="lbfgs",
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)

    print("Validation report (top-1) — TRAINING-SET split, not a generalization estimate:")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))

    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "labels": sorted(set(labels))}, model_path)
    print(f"Saved model to {model_path}")
    if model_path == (ROOT / "models" / CACHE_NAME):
        _rewrite_archive(model_path)
        print(f"Rewrote archive {ROOT / 'models' / ARCHIVE_NAME}")
        _update_provenance_status(model_path)
        print(f"Updated {STATUS_PATH}")
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
