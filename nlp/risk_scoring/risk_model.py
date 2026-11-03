"""ML risk classifier — a weakly-supervised severity model.

The rule engine in :mod:`nlp.risk_scoring.rules` is precise but brittle: it only
fires on the phrasings it explicitly encodes. This module trains a small
TF-IDF + Logistic-Regression model on **weak labels produced by the rule engine
itself** over the *train-only* CUAD clause corpus, so it can generalise to
paraphrases the rules miss. The labels are weak supervision (no gold severity
data exists); a clause type alone contributes at most a MEDIUM prior and never
inflates severity by itself. Predictions are **not a calibrated probability**.

It is used as a *recall booster*: for clauses the rules did **not** flag, if the
model confidently predicts a non-trivial severity we emit an explainable
``ML_RISK_001`` finding. Everything degrades to a no-op when no trained artefact
is present, so the pipeline never depends on it.

The artefact lives at ``models/risk_classifier.joblib`` and is produced by
``scripts/train_risk_classifier.py``.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import joblib  # type: ignore

from app.models.schemas import RiskSeverity

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"
MODEL_PATH = MODEL_DIR / "risk_classifier.joblib"
# Committed compressed artefact so the feature works out of the box without
# shipping the raw joblib in git.
ARCHIVE_PATH = MODEL_DIR / "risk_classifier.7z"

SEVERITY_ORDER = ["low", "medium", "high", "critical"]
_MIN_CONFIDENCE = 0.55


@dataclass
class RiskPrediction:
    severity: RiskSeverity
    confidence: float


class RiskClassifier:
    """Thin wrapper around a fitted sklearn pipeline."""

    def __init__(self, pipeline: object) -> None:
        self.pipeline = pipeline

    def predict(self, text: str) -> Optional[RiskPrediction]:
        if not text or not text.strip():
            return None
        proba = self.pipeline.predict_proba([text])[0]
        classes = list(self.pipeline.classes_)
        top = max(range(len(classes)), key=lambda i: proba[i])
        label = str(classes[top])
        try:
            severity = RiskSeverity(label)
        except ValueError:
            return None
        return RiskPrediction(severity=severity, confidence=float(proba[top]))


def build_pipeline():
    """Create an untrained TF-IDF + LogisticRegression pipeline."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    return Pipeline(
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
                    max_iter=3000,
                    C=1.0,
                    class_weight="balanced",
                    # lbfgs (not liblinear) because the target is multiclass
                    # (low / medium / high / critical).
                    solver="lbfgs",
                ),
            ),
        ]
    )


def train(texts: Sequence[str], labels: Sequence[str]) -> RiskClassifier:
    """Fit a classifier on (text, severity-label) pairs."""
    if len(texts) != len(labels):
        raise ValueError("texts and labels must be the same length")
    if len(set(labels)) < 2:
        raise ValueError("need at least two distinct severity labels to train")
    pipeline = build_pipeline()
    pipeline.fit(list(texts), list(labels))
    return RiskClassifier(pipeline)


def save(model: RiskClassifier, path: Optional[Path] = None) -> Path:
    path = Path(path) if path else MODEL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": model.pipeline}, path)
    return path


def ensure_model_file() -> Optional[Path]:
    """Return the extracted joblib path, extracting the bundled archive if needed."""
    if MODEL_PATH.exists():
        return MODEL_PATH
    if not ARCHIVE_PATH.exists():
        return None
    try:
        import py7zr  # type: ignore

        with py7zr.SevenZipFile(ARCHIVE_PATH, mode="r") as archive:
            names = archive.getnames()
            target = next((n for n in names if n.endswith("risk_classifier.joblib")), None)
            if target is None:
                return None
            archive.extract(path=MODEL_DIR, targets=[target])
        extracted = MODEL_DIR / target
        if extracted != MODEL_PATH and extracted.exists():
            extracted.replace(MODEL_PATH)
    except Exception:
        return None
    return MODEL_PATH if MODEL_PATH.exists() else None


_CACHED: Optional["RiskClassifier"] = None
_CACHE_LOADED = False


def load_cached() -> Optional["RiskClassifier"]:
    """Load the model once per process (loading joblib per contract is costly)."""
    global _CACHED, _CACHE_LOADED
    if not _CACHE_LOADED:
        _CACHED = load()
        _CACHE_LOADED = True
    return _CACHED


def load(path: Optional[Path] = None) -> Optional[RiskClassifier]:
    """Load the trained classifier, or ``None`` when no artefact exists."""
    path = Path(path) if path else ensure_model_file()
    if path is None or not path.exists():
        return None
    from nlp import provenance

    provenance.record_loaded_model("risk_classifier.7z", path)
    try:
        from sklearn.exceptions import InconsistentVersionWarning

        warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
    except Exception:
        pass
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        blob = joblib.load(path)
    pipeline = blob["pipeline"] if isinstance(blob, dict) else blob
    return RiskClassifier(pipeline)


# Mild baseline exposure by clause type, used ONLY as a weak-label floor for
# high-scrutiny clause types. Deliberately capped at MEDIUM: a clause's *type*
# alone must not teach the model that every Limitation of Liability or
# Indemnification clause is HIGH risk (the old HIGH priors made the weak
# supervision severity-inflated by construction). Actual severity comes from
# what the clause says — if a rule trigger fires, the rule severity wins.
# Rationale: the model is a recall booster for paraphrases of *flagged*
# phrasings, and a type-only prior would make it fire on routine boilerplate.
_TYPE_BASELINE = {
    "Limitation of Liability": RiskSeverity.MEDIUM,
    "Indemnification": RiskSeverity.MEDIUM,
    "Termination": RiskSeverity.MEDIUM,
    "Non-Compete / Non-Solicit": RiskSeverity.MEDIUM,
    "Data Protection": RiskSeverity.MEDIUM,
    "Assignment": RiskSeverity.MEDIUM,
}


def weak_label(text: str) -> str:
    """Derive a severity label for ``text`` from the rule engine (no model).

    The label is the stronger of (a) the highest severity any rule assigns to
    the clause and (b) a *mild* (at most MEDIUM) clause-type baseline floor for
    high-scrutiny types. The floor keeps usable signal on short snippets where
    no specific trigger matched, without teaching the model that a clause type
    alone implies high severity. Used offline to build the training set; kept
    here so the training script and any future evaluation share exactly one
    definition of the label. Labels are weak supervision, not gold.
    """
    from app.models.schemas import Clause, ContractSummary
    from nlp.clause_classification.classifier import classify_clause
    from nlp.ner.ner import extract_entities
    from nlp.risk_scoring.rules import apply_rules
    from nlp.risk_scoring.scorer import severity_to_score

    classification = classify_clause(text)
    entities = extract_entities(text, clause_text=text).entities
    clause = Clause(
        clause_id="weak",
        text=text,
        clause_types=classification.labels,
        entities=entities,
    )
    summary = ContractSummary(contract_id="weak", title="", file_name="", jurisdiction="India")
    per_clause = [f for f in apply_rules([clause], summary) if f.clause_id == "weak"]

    candidates = [f.severity for f in per_clause]
    candidates.extend(_TYPE_BASELINE[t] for t in clause.clause_types if t in _TYPE_BASELINE)
    if not candidates:
        return RiskSeverity.LOW.value
    return max(candidates, key=severity_to_score).value


def predict_clause_risk(
    text: str,
    model: Optional[RiskClassifier] = None,
    *,
    min_confidence: float = _MIN_CONFIDENCE,
) -> Optional[RiskPrediction]:
    """Predict a clause's severity, or ``None`` when the model is unavailable
    or the prediction is low-severity / low-confidence."""
    model = model or load_cached()
    if model is None:
        return None
    prediction = model.predict(text)
    if prediction is None:
        return None
    if prediction.severity == RiskSeverity.LOW or prediction.confidence < min_confidence:
        return None
    return prediction


def build_weak_dataset(rows: Iterable[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
    """Turn ``(text, _ignored)`` rows into ``(text, weak_severity)`` pairs."""
    texts: List[str] = []
    labels: List[str] = []
    for text, _ in rows:
        text = (text or "").strip()
        if not text:
            continue
        texts.append(text)
        labels.append(weak_label(text))
    return texts, labels
