"""Machine-readable coverage of the clause taxonomy by the ML training corpus.

The TF-IDF classifier can only learn categories that actually have training
rows in ``data/processed/clause_classifier.csv``. Several internal taxonomy
labels (notably all Indian-specific ones) have **zero** CUAD-derived rows, so
the ML half of the hybrid classifier can only emit the categories that are
covered; the rest are detected by the rule classifier alone. This module makes
that coverage explicit and machine-readable. It never fabricates data: it
reports what is in the corpus, or ``None`` when the corpus is absent.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Optional

from nlp.taxonomy import INTERNAL_LABELS

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "processed" / "clause_classifier.csv"


def category_counts(csv_path: Optional[Path] = None) -> Optional[Counter[str]]:
    """Count training rows per internal label, or ``None`` when the corpus is absent."""
    path = Path(csv_path) if csv_path else DEFAULT_CORPUS
    if not path.exists():
        return None
    csv.field_size_limit(2**31 - 1)
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            label = (row.get("category") or "").strip()
            text = (row.get("text") or "").strip()
            if label and text:
                counts[label] += 1
    return counts


def coverage(csv_path: Optional[Path] = None) -> dict[str, dict]:
    """Per-label coverage table over all ``INTERNAL_LABELS``.

    Each entry: ``{"label", "rows", "ml_supported"}`` where ``ml_supported``
    means the label has at least one training row in the corpus (and so the
    ML classifier can emit it). Unknown labels present in the corpus but not in
    the taxonomy are reported under a synthetic key ``"<other>: <label>"`` so
    nothing is silently dropped.
    """
    counts = category_counts(csv_path)
    if counts is None:
        return {}
    table: dict[str, dict] = {}
    for label in INTERNAL_LABELS:
        rows = counts.get(label, 0)
        table[label] = {"label": label, "rows": rows, "ml_supported": rows > 0}
    for label, rows in sorted(counts.items()):
        if label not in INTERNAL_LABELS:
            table[f"<other>: {label}"] = {"label": label, "rows": rows, "ml_supported": rows > 0}
    return table


def ml_supported_labels(csv_path: Optional[Path] = None) -> Optional[set[str]]:
    """The internal labels the ML classifier can emit (>= 1 training row)."""
    table = coverage(csv_path)
    if not table:
        return None
    return {entry["label"] for entry in table.values() if entry["ml_supported"]}


def unsupported_labels(csv_path: Optional[Path] = None) -> Optional[list[str]]:
    """Internal labels with zero training rows — rule-based detection only."""
    table = coverage(csv_path)
    if not table:
        return None
    return [label for label in INTERNAL_LABELS if table[label]["rows"] == 0]


def summary(csv_path: Optional[Path] = None) -> str:
    """One-paragraph human summary suitable for module docstrings/reports."""
    table = coverage(csv_path)
    if not table:
        return "Training corpus unavailable; taxonomy coverage unknown."
    supported = [e["label"] for e in table.values() if e["label"] in INTERNAL_LABELS and e["ml_supported"]]
    unsupported = [label for label in INTERNAL_LABELS if table[label]["rows"] == 0]
    return (
        f"ML-supported categories ({len(supported)} of {len(INTERNAL_LABELS)}): "
        + ", ".join(supported)
        + f". Rule-only categories (0 training rows, {len(unsupported)}): "
        + ", ".join(unsupported)
    )
