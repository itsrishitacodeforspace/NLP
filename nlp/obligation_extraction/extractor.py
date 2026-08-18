"""Obligation extraction using spaCy dependency patterns + regex.

This module emits structured Obligation objects for every detected duty,
right, prohibition, or conditional clause. It is deliberately rule-based
to remain explainable and fast on the MVP; an LLM-based extractor can
augment this in a later phase.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from app.models.schemas import Obligation, ObligationType, RiskSeverity


# Modal verbs used to detect obligation flavour
OBLIGATION_MODALS = {"shall", "must", "agrees to", "is required to", "will", "undertakes to"}
RIGHT_MODALS = {"may", "is entitled to", "has the right to", "can", "reserves the right to"}
PROHIBITION_MODALS = {"shall not", "may not", "must not", "is prohibited from", "will not"}

DEADLINE_RE = re.compile(
    r"\b(?:within|no later than|at least|prior to|after|by|on)\s+(\d+\s+(?:day|days|week|weeks|month|months|year|years|business days))\b",
    re.IGNORECASE,
)
DATE_DEADLINE_RE = re.compile(
    r"\b(?:by|on|before|after)\s+(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})\b",
    re.IGNORECASE,
)

# Subject detection — first noun-chunk near the modal
SUBJECT_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&,'.\-_ ]{1,40}(?:Pvt\.?\s+Ltd\.?|Limited|LLP|Inc\.?|Corp(?:oration)?|LLC|PLC|Company|Co\.?)?)\b"
)

CONDITIONAL_RE = re.compile(
    r"\b(if|provided that|subject to|unless|upon|in case|where)\b", re.IGNORECASE
)


@dataclass
class ObligationHit:
    text: str
    obligation_type: ObligationType
    subject: Optional[str]
    counterparty: Optional[str]
    action: Optional[str]
    object: Optional[str]
    condition: Optional[str]
    deadline_expression: Optional[str]
    deadline_date: Optional[str]
    risk_level: RiskSeverity
    confidence: float


def extract_obligations_from_clause(
    clause_id: str,
    clause_text: str,
    *,
    obligation_counter: int = 0,
) -> List[Obligation]:
    """Parse a clause into structured Obligation rows."""
    if not clause_text or not clause_text.strip():
        return []

    # Split by sentence-like boundaries while keeping them in order
    sentences = _split_sentences(clause_text)
    obligations: List[Obligation] = []
    for sent in sentences:
        hit = _analyse_sentence(sent)
        if not hit:
            continue
        obligation_counter += 1
        obligations.append(
            Obligation(
                obligation_id=f"{clause_id}_obg{obligation_counter:03d}",
                clause_id=clause_id,
                text=sent.strip(),
                obligation_type=hit.obligation_type,
                subject=hit.subject,
                counterparty=hit.counterparty,
                action=hit.action,
                object=hit.object,
                condition=hit.condition,
                deadline_expression=hit.deadline_expression,
                deadline_date=hit.deadline_date,
                risk_level=hit.risk_level,
                confidence=hit.confidence,
                source="rule",
            )
        )
    return obligations


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> List[str]:
    """Sentence splitter that respects legal abbreviations."""
    text = re.sub(r"\s+", " ", text).strip()
    # Protect common abbreviations
    placeholders = {
        "Pvt.": "Pvt\u0001",
        "Ltd.": "Ltd\u0001",
        "Inc.": "Inc\u0001",
        "Corp.": "Corp\u0001",
        "Co.": "Co\u0001",
        "Mr.": "Mr\u0001",
        "Ms.": "Ms\u0001",
        "Mrs.": "Mrs\u0001",
        "Dr.": "Dr\u0001",
        "No.": "No\u0001",
        "vs.": "vs\u0001",
        "etc.": "etc\u0001",
        "i.e.": "i\u0001e\u0001",
        "e.g.": "e\u0001g\u0001",
    }
    for k, v in placeholders.items():
        text = text.replace(k, v)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text)
    sentences = []
    for p in parts:
        for k, v in placeholders.items():
            p = p.replace(v, k)
        if p.strip():
            sentences.append(p.strip())
    return sentences


def _analyse_sentence(sentence: str) -> Optional[ObligationHit]:
    s_low = sentence.lower()

    obligation_type: Optional[ObligationType] = None
    risk_level = RiskSeverity.LOW
    confidence = 0.7

    for modal in OBLIGATION_MODALS:
        if modal in s_low:
            obligation_type = ObligationType.OBLIGATION
            confidence = 0.85
            break
    if obligation_type is None:
        for modal in RIGHT_MODALS:
            if modal in s_low:
                obligation_type = ObligationType.RIGHT
                confidence = 0.7
                break
    if obligation_type is None:
        for modal in PROHIBITION_MODALS:
            if modal in s_low:
                obligation_type = ObligationType.PROHIBITION
                confidence = 0.8
                risk_level = RiskSeverity.MEDIUM
                break
    if obligation_type is None:
        return None

    subject, counterparty = _extract_subjects(sentence)
    action = _extract_action(s_low)
    obj = _extract_object(sentence)
    condition = _extract_condition(sentence)
    deadline_expr = _extract_deadline(sentence)
    risk_level = _derive_risk_level(obligation_type, deadline_expr, s_low)

    return ObligationHit(
        text=sentence,
        obligation_type=obligation_type,
        subject=subject,
        counterparty=counterparty,
        action=action,
        object=obj,
        condition=condition,
        deadline_expression=deadline_expr,
        deadline_date=None,
        risk_level=risk_level,
        confidence=confidence,
    )


def _extract_subjects(sentence: str) -> tuple[Optional[str], Optional[str]]:
    matches = SUBJECT_RE.findall(sentence)
    if not matches:
        return None, None
    subject = matches[0].strip()
    counterparty = matches[1].strip() if len(matches) > 1 else None
    return subject, counterparty


def _extract_action(sentence_low: str) -> Optional[str]:
    candidates = [
        "pay", "notify", "indemnify", "terminate", "renew", "deliver",
        "provide", "submit", "comply", "maintain", "return", "execute",
        "perform", "reimburse", "refund", "transfer", "assign", "audit",
        "report", "ensure", "warrant", "represent", "disclose", "file",
        "cure", "remediate", "give notice", "make payment", "withdraw",
    ]
    for verb in candidates:
        if verb in sentence_low:
            return verb
    # Try lemmatised verbs near "shall/must"
    m = re.search(r"\b(?:shall|must|may|will)\s+(?:not\s+)?([a-z]+)\b", sentence_low)
    if m:
        return m.group(1)
    return None


def _extract_object(sentence: str) -> Optional[str]:
    # Take the substring after the verb up to next punctuation.
    m = re.search(
        r"(?:shall|must|may|will|agrees to|undertakes to)\s+(?:not\s+)?"
        r"([a-zA-Z][a-zA-Z\s,'.\-_/]{1,80}?)(?:within|by|no later than|prior|on|under|pursuant|if|unless|subject|where|$)",
        sentence,
        re.IGNORECASE,
    )
    if m:
        obj = m.group(1).strip().rstrip(",.;:")
        if obj:
            return obj
    return None


def _extract_condition(sentence: str) -> Optional[str]:
    m = CONDITIONAL_RE.search(sentence)
    if not m:
        return None
    start = m.start()
    cond = sentence[start:].strip().rstrip(".")
    return cond[:280]


def _extract_deadline(sentence: str) -> Optional[str]:
    m = DEADLINE_RE.search(sentence)
    if m:
        return m.group(1).strip()
    m = DATE_DEADLINE_RE.search(sentence)
    if m:
        return m.group(1).strip()
    return None


def _derive_risk_level(typ: ObligationType, deadline: Optional[str], sentence_low: str) -> RiskSeverity:
    text = sentence_low
    risk = RiskSeverity.LOW
    if typ == ObligationType.PROHIBITION:
        risk = RiskSeverity.MEDIUM
    if deadline:
        # Tight deadlines (<=7 days) raise risk
        m = re.match(r"(\d+)\s+(day|days|week|weeks|month|months|year|years)", deadline.lower())
        if m:
            value = int(m.group(1))
            unit = m.group(2)
            days = value * (1 if "day" in unit else 7 if "week" in unit else 30 if "month" in unit else 365)
            if days <= 1:
                risk = RiskSeverity.CRITICAL
            elif days <= 7:
                risk = RiskSeverity.HIGH
            elif days <= 30:
                risk = RiskSeverity.MEDIUM
    if "indemnif" in text and "all losses" in text:
        risk = RiskSeverity.HIGH
    return risk