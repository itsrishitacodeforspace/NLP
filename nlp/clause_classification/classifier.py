"""Rule-based clause classifier.

A deterministic, multi-label classifier that uses keyword + heading hints to
map clauses to one or more of the standard CUAD-style categories. Designed
as the primary classifier for the MVP — fast, debuggable, and good enough
to drive a useful demo. The DeBERTa-v3 classifier (see classifier_ml.py)
sits behind a feature flag and only activates when the heavy ML stack is
installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# Mapping of category -> list of keyword/phrase patterns (lowercased).
CLAUSE_RULES: Dict[str, List[str]] = {
    "Payment Terms": [
        "invoice", "payment", "fees", "consideration", "payable",
        "compensation", "billing", "rate", "price", "usd", "rs.", "inr",
        "tax deducted at source", "tds", "goods and services tax", "gst",
    ],
    "Term and Renewal": [
        "term of this agreement", "effective date", "expiry",
        "renewal", "renew", "auto-renew", "automatically renews",
        "survive termination", "term", "duration",
    ],
    "Termination": [
        "terminate this agreement", "termination for cause",
        "termination for convenience", "right to terminate",
        "may terminate", "material breach", "terminate",
    ],
    "Indemnification": [
        "indemnify", "indemnification", "hold harmless",
        "defend", "third party claim", "third-party claim",
    ],
    "Limitation of Liability": [
        "limitation of liability", "limit of liability",
        "liability cap", "consequential damages",
        "in no event shall", "aggregate liability",
        "total liability",
    ],
    "Warranty": [
        "warrants", "warranty", "warranties", "represents and warrants",
        "as is", "merchantability", "fitness for a particular purpose",
    ],
    "Confidentiality": [
        "confidential information", "non-disclosure", "nda",
        "confidentiality", "confidential", "trade secret",
    ],
    "Data Protection": [
        "data protection", "personal data", "personal information",
        "data breach", "privacy", "gdpr", "data security",
        "customer data", "data processor",
    ],
    "Intellectual Property": [
        "intellectual property", " ip ", "all rights, title",
        "work product", "work product", "inventions",
        "copyright", "patent", "trademark",
        "ownership of",
    ],
    "Non-Compete / Non-Solicit": [
        "non-compete", "non compete", "non-solicit", "non solicit",
        "restrictive covenant", "shall not solicit",
    ],
    "Governing Law": [
        "governed by the laws of", "governing law",
        "laws of india", "laws of the state of",
        "jurisdiction of the courts",
    ],
    "Dispute Resolution": [
        "arbitration", "arbitrator", "seat of arbitration",
        "venue", "dispute resolution", "mediation",
        "disputes arising",
    ],
    "Force Majeure": [
        "force majeure", "act of god", "beyond the reasonable control",
        "unforeseeable", "pandemic",
    ],
    "Assignment": [
        "assignment", "assign", "transfer of rights",
        "may not assign", "shall not assign",
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
    ],
    # Indian-specific additions
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

# Section headings often disambiguate clauses with the same keywords.
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
    rule_based_only: bool = True,
) -> ClassificationResult:
    """Multi-label clause classification using rules (and optionally DeBERTa).

    Args:
        text: The clause body.
        heading: Optional heading text to disambiguate.
        rule_based_only: When True, do not attempt ML even if installed.
    """
    if not text and not heading:
        return ClassificationResult(labels=[], confidence=0.0, method="rule")

    if not rule_based_only:
        try:
            from nlp.clause_classification.classifier_ml import classify_with_deberta

            ml_result = classify_with_deberta(text)
            if ml_result and ml_result.confidence > 0.5:
                return ml_result
        except Exception:
            pass  # fall back to rules

    return _rule_classify(text=text, heading=heading)


# ---------------------------------------------------------------------------
# Rule-based engine
# ---------------------------------------------------------------------------


def _rule_classify(text: str, heading: Optional[str] = None) -> ClassificationResult:
    lowered = (text or "").lower()
    heading_low = (heading or "").lower().strip()
    scores: Dict[str, int] = {}

    # Heading has the highest weight
    if heading_low:
        for k, v in HEADING_HINTS.items():
            if k in heading_low:
                scores[v] = scores.get(v, 0) + 3

    for label, keywords in CLAUSE_RULES.items():
        for kw in keywords:
            if kw in lowered:
                scores[label] = scores.get(label, 0) + 1

    if not scores:
        return ClassificationResult(labels=["Miscellaneous"], confidence=0.3, method="rule")

    # Sort by score then alphabetical for determinism
    sorted_labels = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_score = sorted_labels[0][1]
    total = sum(scores.values()) or 1
    confidence = min(0.95, 0.4 + (top_score / max(8, total)))

    # Threshold: keep labels whose score >= 30% of the top score
    threshold = max(1, int(top_score * 0.3))
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
