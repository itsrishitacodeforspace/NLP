"""Clause classifier — rule-based with TF-IDF ML fallback.

This module exposes a single entry-point :func:`classify_clause` that:

  1. Tries the rule-based classifier (fast, deterministic, debuggable).
  2. Falls back to a TF-IDF + Logistic Regression model trained on
     real CUAD gold data if a trained model artefact exists at
     ``models/tfidf_classifier.joblib``.

The CUAD-derived keyword bank is auto-loaded on import from
``data/processed/cuad_keyword_bank.json`` to enrich the rule matcher.
Run ``python scripts/build_training_data.py`` once to materialise it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from nlp.taxonomy import CUAD_TO_INTERNAL

# Mapping: (category -> list of keyword/phrase patterns (lowercased))
CLAUSE_RULES: Dict[str, List[str]] = {
    "Payment Terms": [
        "invoice", "payment", "fees", "consideration", "payable",
        "compensation", "billing", "rate", "price", "usd", "rs.", "inr",
        "tax deducted at source", "tds", "goods and services tax", "gst",
        "minimum commitment", "volume restriction", "price restrictions",
        "revenue sharing", "profit sharing",
    ],
    "Term and Renewal": [
        "term of this agreement", "effective date", "expiry",
        "renewal", "renew", "auto-renew", "automatically renews",
        "survive termination", "term", "duration",
        "renewal term", "notice period to terminate renewal",
        "expiration date", "initial term",
    ],
    "Termination": [
        "terminate this agreement", "termination for cause",
        "termination for convenience", "right to terminate",
        "may terminate", "material breach", "terminate",
        "post-termination services",
    ],
    "Indemnification": [
        "indemnify", "indemnification", "hold harmless",
        "defend", "third party claim", "third-party claim",
        "indemnitor", "indemnitee", "losses arising",
    ],
    "Limitation of Liability": [
        "limitation of liability", "limit of liability",
        "liability cap", "consequential damages",
        "in no event shall", "aggregate liability",
        "total liability", "uncapped liability",
        "cap on liability", "liquidated damages",
    ],
    "Warranty": [
        "warrants", "warranty", "warranties", "represents and warrants",
        "as is", "merchantability", "fitness for a particular purpose",
        "warranty duration",
    ],
    "Confidentiality": [
        "confidential information", "non-disclosure", "nda",
        "confidentiality", "confidential", "trade secret",
        "non-disparagement",
    ],
    "Data Protection": [
        "data protection", "personal data", "personal information",
        "data breach", "privacy", "gdpr", "data security",
        "customer data", "data processor",
        "data controller",
    ],
    "Intellectual Property": [
        "intellectual property", " ip ", "all rights, title",
        "work product", "work product", "inventions",
        "copyright", "patent", "trademark",
        "ownership of", "ip ownership", "license grant",
        "source code escrow", "joint ip ownership",
        "non-transferable license",
    ],
    "Non-Compete / Non-Solicit": [
        "non-compete", "non compete", "non-solicit", "non solicit",
        "restrictive covenant", "shall not solicit",
        "no-solicit of customers", "no-solicit of employees",
        "competitive restriction exception", "exclusivity",
        "most favored nation",
    ],
    "Governing Law": [
        "governed by the laws of", "governing law",
        "laws of india", "laws of the state of",
        "jurisdiction of the courts",
        "construed according to",
    ],
    "Dispute Resolution": [
        "arbitration", "arbitrator", "seat of arbitration",
        "venue", "dispute resolution", "mediation",
        "disputes arising",
    ],
    "Force Majeure": [
        "force majeure", "act of god", "beyond the reasonable control",
        "beyond its reasonable control", "beyond his reasonable control",
        "beyond her reasonable control", "unforeseeable", "pandemic",
        "act of nature",
    ],
    "Assignment": [
        "assignment", "assign", "transfer of rights",
        "may not assign", "shall not assign", "anti-assignment",
        "change of control", "right of first refusal", "rofr",
        "rofo", "rofn", "drag-along", "tag-along",
    ],
    "Audit Rights": [
        "audit", "inspection", "right to audit",
        "books and records", "upon reasonable notice",
    ],
    "Insurance": [
        "insurance", "insured", "policy", "coverage",
        "insurer", "general liability insurance",
    ],
    "Compliance": [
        "compliance", "comply with laws", "anti-bribery",
        "anti corruption", "ofac", "sanctions",
    ],
    "Service Levels": [
        "service level", "sla", "uptime", "service credit",
        "response time", "availability",
    ],
    "Change Control": [
        "change order", "change control", "change request",
        "change management",
    ],
    "Notice": [
        "written notice", "notice in writing", "send notice",
        "address for notice",
    ],
    "Acceptance": [
        "acceptance", "acceptance criteria", "sign-off",
        "deemed accepted",
    ],
    "Definitions": [
        "definitions", "means", "shall mean",
    ],
    "Miscellaneous": [
        "miscellaneous", "entire agreement", "severability",
        "counterparts", "no waiver", "amendment",
        "third party beneficiary", "covenant not to sue",
    ],
    "Stamp Duty": [
        "stamp duty", "franking", "e-stamp", "instrument",
        "indian stamp act",
    ],
    "TDS / GST": [
        "tax deducted at source", "tds", "section 194",
        "goods and services tax", "gstin",
    ],
    "Arbitration Seat": [
        "seat of arbitration", "seat shall be", "venue of arbitration",
        "new delhi international arbitration centre",
    ],
}

HEADING_HINTS: Dict[str, str] = {
    "indemnification": "Indemnification",
    "indemnity": "Indemnification",
    "limitation of liability": "Limitation of Liability",
    "liability cap": "Limitation of Liability",
    "termination": "Termination",
    "term and termination": "Termination",
    "term and renewal": "Term and Renewal",
    "renewal": "Term and Renewal",
    "payment": "Payment Terms",
    "fees and payment": "Payment Terms",
    "confidentiality": "Confidentiality",
    "non-disclosure": "Confidentiality",
    "data protection": "Data Protection",
    "privacy": "Data Protection",
    "intellectual property": "Intellectual Property",
    "ownership": "Intellectual Property",
    "non-compete": "Non-Compete / Non-Solicit",
    "non-solicit": "Non-Compete / Non-Solicit",
    "governing law": "Governing Law",
    "jurisdiction": "Governing Law",
    "arbitration": "Dispute Resolution",
    "dispute resolution": "Dispute Resolution",
    "force majeure": "Force Majeure",
    "assignment": "Assignment",
    "audit": "Audit Rights",
    "insurance": "Insurance",
    "compliance": "Compliance",
    "service levels": "Service Levels",
    "sla": "Service Levels",
    "change control": "Change Control",
    "notices": "Notice",
    "acceptance": "Acceptance",
    "definitions": "Definitions",
    "miscellaneous": "Miscellaneous",
    "stamp duty": "Stamp Duty",
}

@dataclass
class ClassificationResult:
    labels: List[str]
    confidence: float
    method: str  # 'rule' or 'ml'


def classify_clause(
    text: str,
    *,
    heading: Optional[str] = None,
    rule_based_only: bool = False,
) -> ClassificationResult:
    """Multi-label clause classification.

    Strategy: hybrid. We always run the rule-based classifier (it captures
    Indian-specific categories that the CUAD-trained ML model has never
    seen). We then run the TF-IDF ML classifier if available. Final labels
    are the union, ranked by TF-IDF confidence for ML labels and score
    weight for rule-based labels.
    """
    if not text and not heading:
        return ClassificationResult(labels=[], confidence=0.0, method="rule")

    rule_result = _rule_classify(text=text, heading=heading)
    rule_labels = list(rule_result.labels)

    if rule_based_only:
        return rule_result

    ml_result = _classify_with_tfidf(text)
    if not ml_result or not ml_result.labels:
        return rule_result

    # Hybrid: union of ML + rule labels with dedup, ML first.
    seen = set()
    merged: List[str] = []
    for label in ml_result.labels:
        if label not in seen:
            seen.add(label)
            merged.append(label)
    for label in rule_labels:
        if label not in seen:
            seen.add(label)
            merged.append(label)
    # Cap at 5 labels.
    merged = merged[:5]
    confidence = max(rule_result.confidence, ml_result.confidence)
    method = "hybrid" if rule_labels and ml_result.labels != rule_labels else ml_result.method
    return ClassificationResult(labels=merged, confidence=round(confidence, 3), method=method)


# ---------------------------------------------------------------------------
# CUAD keyword bank auto-loader
# ---------------------------------------------------------------------------

_cuad_keyword_bank: Optional[Dict[str, List[str]]] = None

# Provenance of the keyword bank actually loaded at runtime (empty until loaded).
KEYWORD_BANK_PROVENANCE: dict = {}


def _record_keyword_bank_provenance(path) -> None:
    """Register the keyword bank's provenance for runtime surfacing."""
    global KEYWORD_BANK_PROVENANCE
    from nlp import provenance
    from nlp.datasets.manifest import verify

    if path is None or not Path(path).exists():
        KEYWORD_BANK_PROVENANCE = provenance.record("cuad_keyword_bank.json", path=None, kind="keyword_bank")
        return
    status, reason = provenance.STATUS_UNVERIFIED, "provenance not verified"
    try:
        result = verify(path, allowed_splits=("train",), require=False, deep=False)
        if result.get("ok"):
            status, reason = provenance.STATUS_VERIFIED, ""
        else:
            reason = str(result.get("reason", reason))
    except Exception as exc:  # pragma: no cover - defensive
        reason = str(exc)
    KEYWORD_BANK_PROVENANCE = provenance.record(
        "cuad_keyword_bank.json", path=path, kind="keyword_bank", status=status, reason=reason
    )


def load_cuad_keyword_bank(path: Optional[Path] = None, *, max_keywords_per_category: int = 80) -> int:
    """Load CUAD-derived keywords into CLAUSE_RULES.

    Each CUAD span is a sentence-sized string. We extract short, distinctive
    sub-phrases (3-7 tokens) so the matcher stays discriminative and fast.
    A category-wide cap prevents the bank from flooding the rule list with
    near-duplicates.
    """
    global _cuad_keyword_bank
    if path is None:
        path = Path(__file__).resolve().parents[2] / "data" / "processed" / "cuad_keyword_bank.json"
    if not Path(path).exists():
        _record_keyword_bank_provenance(None)
        _compile_keyword_patterns()
        return 0
    with Path(path).open(encoding="utf-8") as fh:
        bank = json.load(fh)
    _cuad_keyword_bank = bank

    STOPWORDS = {
        "the", "a", "an", "of", "in", "on", "at", "to", "for", "and",
        "or", "by", "with", "from", "as", "is", "are", "be", "this",
        "that", "these", "those", "shall", "may", "will", "would",
        "any", "all", "such", "its", "their", "his", "her", "if",
        "when", "where", "while", "during", "including", "include",
        "without", "otherwise", "hereunder", "pursuant",
    }

    added = 0
    for cuad_label, samples in bank.items():
        target = CUAD_TO_INTERNAL.get(cuad_label)
        if not target:
            continue
        existing = set(CLAUSE_RULES.get(target, []))
        per_category_added = 0
        for sample in samples[:150]:
            if per_category_added >= max_keywords_per_category:
                break
            lowered = sample.strip().lower()
            if not lowered or len(lowered) < 10:
                continue
            tokens = re.findall(r"[a-z0-9'/-]+", lowered)
            tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
            if len(tokens) < 3:
                continue
            # Use the last 5-7 tokens — they tend to carry the most informative
            # legal phrasing (e.g. "subject to the laws of the state of new york").
            for n in (6, 5, 4):
                if len(tokens) >= n:
                    phrase = " ".join(tokens[-n:])
                    if 12 <= len(phrase) <= 60 and phrase not in existing:
                        CLAUSE_RULES.setdefault(target, []).append(phrase)
                        existing.add(phrase)
                        added += 1
                        per_category_added += 1
                        break
    _record_keyword_bank_provenance(path)
    _compile_keyword_patterns()
    return added


_KEYWORD_PATTERNS: Dict[str, re.Pattern] = {}


def _compile_keyword_patterns() -> None:
    """Compile letter-boundary regexes so `term` never matches `terminate`."""
    global _KEYWORD_PATTERNS
    patterns: Dict[str, re.Pattern] = {}
    for keywords in CLAUSE_RULES.values():
        for raw in keywords:
            kw = raw.strip().lower()
            if not kw or kw in patterns:
                continue
            patterns[kw] = re.compile(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])")
    _KEYWORD_PATTERNS = patterns


# Auto-load on import (silent skip if bank file is missing).
try:
    load_cuad_keyword_bank()
except Exception:
    _compile_keyword_patterns()


# ---------------------------------------------------------------------------
# TF-IDF ML classifier (lazy-loaded)
# ---------------------------------------------------------------------------

_TFIDF_MODEL = None
_TFIDF_MODEL_LOADED = False


def _classify_with_tfidf(text: str) -> Optional[ClassificationResult]:
    global _TFIDF_MODEL, _TFIDF_MODEL_LOADED
    from nlp.clause_classification.tfidf_model import ensure_model_file, load_trained

    if ensure_model_file() is None:
        return None
    if not _TFIDF_MODEL_LOADED:
        try:
            _TFIDF_MODEL = load_trained()
        except Exception:
            _TFIDF_MODEL = None
        _TFIDF_MODEL_LOADED = True
    if _TFIDF_MODEL is None:
        return None
    if not text or not text.strip():
        return None
    try:
        labels = _TFIDF_MODEL.predict_one(text)
        if not labels:
            return None
        # Confidence approx — top probability of the predicted class.
        proba = _TFIDF_MODEL.pipeline.predict_proba([text])[0]
        top_idx = proba.argmax()
        confidence = float(proba[top_idx])
        return ClassificationResult(labels=labels, confidence=round(confidence, 3), method="tfidf")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rule-based engine
# ---------------------------------------------------------------------------


def _rule_classify(text: str, heading: Optional[str] = None) -> ClassificationResult:
    lowered = (text or "").lower()
    heading_low = (heading or "").lower().strip()
    scores: Dict[str, float] = {}

    if heading_low:
        for k, v in HEADING_HINTS.items():
            if k in heading_low:
                scores[v] = scores.get(v, 0.0) + 5.0

    for label, keywords in CLAUSE_RULES.items():
        for kw in keywords:
            pattern = _KEYWORD_PATTERNS.get(kw.strip().lower())
            if pattern is not None and pattern.search(lowered):
                # Long phrases are more discriminative.
                weight = 1.0 + min(2.0, len(kw) / 20.0)
                scores[label] = scores.get(label, 0.0) + weight

    if not scores:
        return ClassificationResult(labels=["Miscellaneous"], confidence=0.3, method="rule")

    sorted_labels = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_score = sorted_labels[0][1]
    total = sum(scores.values()) or 1
    confidence = min(0.95, 0.4 + (top_score / max(8, total)))

    threshold = max(1.0, top_score * 0.4)
    labels = [lbl for lbl, sc in sorted_labels if sc >= threshold][:5]
    return ClassificationResult(labels=labels, confidence=round(confidence, 2), method="rule")


# ---------------------------------------------------------------------------
# Convenience: classify a list of clauses
# ---------------------------------------------------------------------------


def classify_clauses(clauses: List[Dict]) -> List[Dict]:
    """Decorate each clause dict with `clause_types` and `confidence`."""
    for cl in clauses:
        result = classify_clause(
            cl.get("text", ""),
            heading=cl.get("heading"),
            rule_based_only=True,
        )
        cl["clause_types"] = result.labels
        cl["classification_confidence"] = result.confidence
        cl["classification_method"] = result.method
    return clauses


# ---------------------------------------------------------------------------
# Evaluation harness
# ---------------------------------------------------------------------------


def evaluate_against_csv(
    csv_path: Path,
    *,
    sample_size: Optional[int] = None,
) -> Dict[str, float]:
    """Compute precision/recall/F1 of our rule-based classifier on a held-out CSV.

    Expects columns: text, category.
    """
    import csv as _csv
    import random

    _csv.field_size_limit(2**31 - 1)

    rows: List[dict] = []
    with Path(csv_path).open(encoding="utf-8", newline="") as fh:
        rows = list(_csv.DictReader(fh))
    if sample_size:
        random.seed(42)
        rows = random.sample(rows, min(sample_size, len(rows)))

    tp = 0
    fp = 0
    fn = 0
    for row in rows:
        text = (row.get("text") or "").strip()
        gold = row.get("category", "").strip()
        if not text or not gold:
            continue
        pred = set(classify_clause(text).labels)
        if not pred:
            pred = {"Miscellaneous"}
        gold_set = {gold}
        tp += len(pred & gold_set)
        fp += len(pred - gold_set)
        fn += len(gold_set - pred)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1, precision + recall)
    return {
        "rows": len(rows),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }
