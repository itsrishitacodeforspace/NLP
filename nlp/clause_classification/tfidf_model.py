"""Runtime loader for the bundled TF-IDF clause classifier.

The repository ships the model compressed as ``models/tfidf_classifier.7z``
because the raw joblib is ~100 MB. We extract it on first use, so a plain
``pip install`` of the project has a working classifier without requiring a
7-Zip executable on PATH.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import joblib  # type: ignore

from nlp.taxonomy import INTERNAL_LABELS

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
ARCHIVE_PATH = MODEL_DIR / "tfidf_classifier.7z"
MODEL_PATH = MODEL_DIR / "tfidf_classifier.joblib"

MODEL_LABEL_ALIASES = {"Pricing Terms": "Payment Terms"}
_CANONICAL_LABELS = frozenset(INTERNAL_LABELS)


def canonical_label(label: str) -> Optional[str]:
    """Map a legacy model label into the canonical taxonomy, or drop it."""
    mapped = MODEL_LABEL_ALIASES.get(label, label)
    return mapped if mapped in _CANONICAL_LABELS else None


@dataclass
class TrainedClassifier:
    pipeline: object
    labels: List[str]

    def predict_one(self, text: str) -> List[str]:
        if not text:
            return []
        proba = self.pipeline.predict_proba([text])[0]
        classes = list(self.pipeline.classes_)
        ranked = sorted(zip(classes, proba, strict=False), key=lambda kv: -kv[1])
        out: List[str] = []
        for label, p in ranked:
            if p < 0.15:
                continue
            label = canonical_label(label)
            if label and label not in out:
                out.append(label)
            if len(out) >= 5:
                break
        if out:
            return out
        if ranked:
            top = canonical_label(ranked[0][0])
            return [top] if top else []
        return []

    def predict_top1(self, text: str) -> str:
        if not text:
            return "Miscellaneous"
        label = canonical_label(self.pipeline.predict([text])[0])
        return label or "Miscellaneous"


def ensure_model_file() -> Optional[Path]:
    """Return the extracted joblib path, extracting the archive if needed."""
    if MODEL_PATH.exists():
        return MODEL_PATH
    if not ARCHIVE_PATH.exists():
        return None
    try:
        import py7zr  # type: ignore

        with py7zr.SevenZipFile(ARCHIVE_PATH, mode="r") as archive:
            members = archive.getnames()
            target = next((n for n in members if n.endswith("tfidf_classifier.joblib")), None)
            if target is None:
                return None
            archive.extract(path=MODEL_DIR, targets=[target])
        extracted = MODEL_DIR / target
        if extracted != MODEL_PATH and extracted.exists():
            extracted.replace(MODEL_PATH)
    except Exception:
        return None
    return MODEL_PATH if MODEL_PATH.exists() else None


def _suppress_version_warning():
    try:
        from sklearn.exceptions import InconsistentVersionWarning

        warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
    except Exception:
        pass


def load_trained(model_path: Optional[Path] = None) -> Optional[TrainedClassifier]:
    model_path = Path(model_path) if model_path else ensure_model_file()
    if model_path is None or not model_path.exists():
        return None
    from nlp import provenance

    provenance.record_loaded_model("tfidf_classifier.7z", model_path)
    _suppress_version_warning()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        blob = joblib.load(model_path)
    if isinstance(blob, dict):
        return TrainedClassifier(pipeline=blob["pipeline"], labels=blob["labels"])
    return TrainedClassifier(pipeline=blob.pipeline, labels=blob.labels)
