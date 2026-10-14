"""Tests that exercise the hybrid (rule + TF-IDF) clause classifier."""
from __future__ import annotations

from pathlib import Path

import pytest

from nlp.clause_classification.classifier import classify_clause, load_cuad_keyword_bank


# Make sure the bank is loaded regardless of import order in other tests.
load_cuad_keyword_bank()


@pytest.fixture(scope="module")
def cuad_corpus():
    path = Path("data/processed/clause_classifier.csv")
    if not path.exists():
        pytest.skip("CUAD corpus not built — run `python scripts/build_training_data.py`")
    import csv
    csv.field_size_limit(2**31 - 1)
    rows: list[dict] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            text = (row.get("text") or "").strip()
            label = (row.get("category") or "").strip()
            if text and label:
                rows.append({"text": text, "category": label})
    return rows


def test_classifier_handles_governing_law():
    res = classify_clause(
        "This Agreement is governed by the laws of the State of New York.",
    )
    assert "Governing Law" in res.labels


def test_classifier_handles_indemnification():
    res = classify_clause(
        "Provider shall indemnify, defend, and hold harmless Customer from any third-party claims."
    )
    assert "Indemnification" in res.labels


def test_classifier_handles_termination():
    res = classify_clause(
        "Customer may terminate this Agreement at any time without cause upon written notice."
    )
    assert "Termination" in res.labels


def test_classifier_handles_payment_terms():
    res = classify_clause(
        "Customer shall pay Provider within 30 days of receipt of invoice."
    )
    assert "Payment Terms" in res.labels


def test_classifier_handles_intellectual_property():
    res = classify_clause(
        "All work product shall be exclusively owned by Customer."
    )
    assert "Intellectual Property" in res.labels


def test_classifier_handles_limitation_of_liability():
    res = classify_clause(
        "Provider's total liability shall be limited to fees paid in the preceding 12 months."
    )
    assert "Limitation of Liability" in res.labels


def test_classifier_handles_renewal():
    res = classify_clause(
        "This Agreement shall automatically renew for successive 12 month periods unless either party gives 60 days notice."
    )
    assert "Term and Renewal" in res.labels


def test_classifier_handles_force_majeure():
    """Force Majeure is not in CUAD — only rule-based detection is expected."""
    res = classify_clause(
        "The Supplier shall not be liable for delays caused by an event beyond its reasonable control."
    )
    assert "Force Majeure" in res.labels


def test_classifier_handles_indian_stamp_duty():
    res = classify_clause(
        "Stamp duty on this Agreement shall be borne by Customer."
    )
    assert "Stamp Duty" in res.labels


def test_classifier_top1_accuracy_on_cuad(cuad_corpus):
    """Spot-check top-1 accuracy against a CUAD sample."""
    import random

    random.seed(2026)
    sample = random.sample(cuad_corpus, k=min(200, len(cuad_corpus)))
    ok = sum(1 for r in sample if r["category"] in classify_clause(r["text"]).labels[:1])
    # We expect at least ~30% top-1 accuracy on CUAD gold given the
    # multi-label nature of the data; raise this bar over time as more
    # training data is added.
    accuracy = ok / len(sample)
    assert accuracy >= 0.30, f"Top-1 accuracy dropped to {accuracy:.1%} on CUAD sample"


def test_classifier_top3_accuracy_on_cuad(cuad_corpus):
    """Multi-label top-3 accuracy — should comfortably exceed 50%."""
    import random

    random.seed(2026)
    sample = random.sample(cuad_corpus, k=min(200, len(cuad_corpus)))
    ok = sum(1 for r in sample if r["category"] in classify_clause(r["text"]).labels)
    accuracy = ok / len(sample)
    assert accuracy >= 0.55, f"Top-3 accuracy dropped to {accuracy:.1%} on CUAD sample"