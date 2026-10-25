"""Tests for the weakly-supervised ML risk classifier."""
from __future__ import annotations

import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.models.schemas import Clause, RiskFlag, RiskSeverity
from nlp.risk_scoring import risk_model
from nlp.risk_scoring.risk_model import RiskClassifier, RiskPrediction, weak_label

_TRAIN_TEXTS = [
    "customer shall pay the fees within thirty days",
    "this agreement is governed by the laws of india",
    "the provider shall have unlimited liability for all damages",
    "there is no cap on liability whatsoever",
]
_TRAIN_LABELS = ["low", "low", "high", "high"]


def _fitted_model() -> RiskClassifier:
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )
    pipeline.fit(_TRAIN_TEXTS, _TRAIN_LABELS)
    return RiskClassifier(pipeline)


def test_weak_label_uses_rules_and_type_priors():
    # An explicit rule trigger -> high/critical.
    risky = weak_label(
        "The Provider shall have unlimited liability for all losses arising under this Agreement."
    )
    assert risky in {"high", "critical"}
    # A high-exposure clause type with no explicit trigger -> at least medium.
    assert weak_label("The Provider shall indemnify the Customer against claims.") in {"medium", "high"}
    # Boilerplate -> low.
    assert (
        weak_label("The headings are for convenience only and shall not affect interpretation.")
        == "low"
    )


def test_risk_classifier_predicts_and_maps_severity():
    model = _fitted_model()
    prediction = model.predict("the provider shall have unlimited liability for all damages")
    assert prediction is not None
    assert prediction.severity == RiskSeverity.HIGH
    assert 0.0 <= prediction.confidence <= 1.0
    assert model.predict("") is None


def test_predict_clause_risk_filters_low_severity(monkeypatch):
    model = _fitted_model()
    monkeypatch.setattr(risk_model, "load_cached", lambda: model)
    # Benign clause -> "low" -> filtered out (None).
    assert risk_model.predict_clause_risk("this agreement is governed by the laws of india") is None
    # Risky clause -> kept.
    caught = risk_model.predict_clause_risk("there is no cap on liability whatsoever")
    assert caught is not None and caught.severity == RiskSeverity.HIGH


def test_predict_clause_risk_noop_without_model(monkeypatch):
    monkeypatch.setattr(risk_model, "load_cached", lambda: None)
    assert risk_model.predict_clause_risk("anything at all") is None


class _StubModel:
    def predict(self, text):
        return RiskPrediction(severity=RiskSeverity.HIGH, confidence=0.9)


def test_analyzer_augmentation_noop_without_model(monkeypatch):
    from app.services.analyzer import _augment_with_ml_risks

    monkeypatch.setattr(risk_model, "load_cached", lambda: None)
    clause = Clause(clause_id="c1", text="some clause text")
    flags = [
        RiskFlag(
            risk_id="r1",
            rule_id="RISK_X",
            name="x",
            severity=RiskSeverity.LOW,
            explanation="e",
        )
    ]
    assert _augment_with_ml_risks([clause], flags) == flags


def test_analyzer_augmentation_adds_model_finding(monkeypatch):
    from app.services.analyzer import _augment_with_ml_risks

    monkeypatch.setattr(risk_model, "load_cached", lambda: _StubModel())
    clauses = [Clause(clause_id="c1", text="some unflagged clause")]
    augmented = _augment_with_ml_risks(clauses, [])
    assert len(augmented) == 1
    assert augmented[0].rule_id == "ML_RISK_001"
    assert augmented[0].severity == RiskSeverity.HIGH
    assert augmented[0].clause_id == "c1"


@pytest.mark.skipif(risk_model.ensure_model_file() is None, reason="no bundled risk model")
def test_bundled_risk_model_loads():
    assert risk_model.load() is not None
