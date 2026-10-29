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

# Modal patterns are checked in priority order: prohibition, right, obligation.
_DEONTIC_PATTERNS = (
    (
        ObligationType.PROHIBITION,
        re.compile(
            r"\b(?:shall|may|must|will)\s+not\b|\bis\s+prohibited\s+from\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObligationType.RIGHT,
        re.compile(
            r"\b(?:is\s+entitled\s+to|has\s+the\s+right\s+to|reserves\s+the\s+right\s+to)\b"
            r"|\b(?:may|can)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObligationType.OBLIGATION,
        re.compile(
            r"\b(?:agrees\s+to|is\s+required\s+to|undertakes\s+to)\b|\b(?:shall|must|will)\b",
            re.IGNORECASE,
        ),
    ),
)

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "ninety": 90, "hundred": 100,
}
_NUM_ALT = r"(?:\d+|" + "|".join(_NUMBER_WORDS) + r")"
DEADLINE_RE = re.compile(
    r"\b(?:within|no later than|at least|prior to|after|by|on)\s+"
    r"(" + _NUM_ALT + r"((?:\s*\(\d+\))?\s+(?:hour|hours|day|days|week|weeks|month|months|year|years|business\s+days)))\b",
    re.IGNORECASE,
)
DATE_DEADLINE_RE = re.compile(
    r"\b(?:on\s+or\s+before|by|on|before|after)\s+"
    r"(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})\b",
    re.IGNORECASE,
)

OBJECT_CUT_RE = re.compile(
    r"\b(?:within|by|no\s+later\s+than|prior\s+to|on\s+or\s+before|if|unless|subject\s+to|"
    r"pursuant\s+to|under\s+this|in\s+accordance\s+with)\b|[.;]",
    re.IGNORECASE,
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
) -> list:
    """Parse a clause into structured Obligation rows."""
    if not clause_text or not clause_text.strip():
        return []

    # Split by sentence-like boundaries while keeping them in order
    sentences = _split_sentences(clause_text)
    obligations: list = []
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
    """Sentence splitter that respects legal abbreviations and headings."""
    # First, split on double-newlines / headings.
    # Strip the leading heading-like prefix (e.g. "1. Limitation of Liability").
    text = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+[A-Z][^\n]{0,120}\n", "", text, count=1)
    # Normalise whitespace but keep newlines as sentence boundaries for now.
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"\n+", " ", text)
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
    sentence = sentence.strip()
    if not sentence:
        return None

    obligation_type: Optional[ObligationType] = None
    modal_match: Optional[re.Match] = None
    for candidate_type, pattern in _DEONTIC_PATTERNS:
        match = pattern.search(sentence)
        if match:
            obligation_type = candidate_type
            modal_match = match
            break
    if obligation_type is None or modal_match is None:
        return None

    confidence = {
        ObligationType.OBLIGATION: 0.85,
        ObligationType.RIGHT: 0.7,
        ObligationType.PROHIBITION: 0.8,
    }[obligation_type]

    # The subject belongs to the first deontic verb, even when the sentence
    # later contains a prohibition ("shall keep ... and shall not disclose").
    first_modal_start = min(
        (match.start() for _, pattern in _DEONTIC_PATTERNS if (match := pattern.search(sentence))),
        default=modal_match.start(),
    )
    subject = _extract_subject(sentence[:first_modal_start])
    raw_tail = sentence[modal_match.end():].strip()
    if re.match(r"be\s+", raw_tail, re.IGNORECASE) and re.search(
        r"\b(seat|venue)\b", subject or "", re.IGNORECASE
    ):
        return None
    # Passive voice: "The services shall be provided by the Provider" — the
    # grammatical subject is the object, not the obligor. The obligor is the
    # agent after "by"; when no agent is stated, leave it unknown rather than
    # inventing the object as the responsible party.
    if obligation_type in (ObligationType.OBLIGATION, ObligationType.PROHIBITION):
        passive = re.match(
            r"^(?:be|is|are|was|were)\s+(?!entitled\b)[A-Za-z]+(?:ed|en)\b",
            raw_tail,
            re.IGNORECASE,
        )
        if passive:
            agent_m = re.search(r"\bby\s+(?:the\s+)?(?P<agent>[A-Z][A-Za-z0-9 ,&'.\-]{1,80})", raw_tail)
            subject = agent_m.group("agent").strip().rstrip(".") if agent_m else None
    action, obj = _extract_action_object(raw_tail)
    if action == "governed":
        return None
    if action == "resolved" and subject and re.search(r"\b(seat|venue|dispute)\b", subject):
        return None
    condition = _extract_condition(sentence)
    deadline_expr = _extract_deadline(sentence)
    deadline_date = _extract_deadline_date(sentence)
    risk_level = _derive_risk_level(obligation_type, deadline_expr, sentence.lower())

    return ObligationHit(
        text=sentence,
        obligation_type=obligation_type,
        subject=subject,
        counterparty=None,
        action=action,
        object=obj,
        condition=condition,
        deadline_expression=deadline_expr,
        deadline_date=deadline_date,
        risk_level=risk_level,
        confidence=confidence,
    )


def _extract_subject(prefix: str) -> Optional[str]:
    subject = re.sub(r"^\s*\(?[a-z0-9]+[.)]\s*", "", prefix)
    subject = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", subject)
    subject = re.sub(
        r"^(?:thereafter|however|notwithstanding(?:\s+the\s+foregoing)?|further|additionally)\s+",
        "",
        subject.strip(),
        flags=re.IGNORECASE,
    )
    subject = subject.strip().rstrip(",;:")
    if len(subject) > 100:
        subject = re.split(r"[,;]", subject)[-1].strip()
    subject = re.sub(r"^(?:the|this|that|a|an)\s+", "", subject, flags=re.IGNORECASE)
    subject = re.sub(r"\s+(?:to|of|from|in|under|pursuant|for|by)\s*$", "", subject)
    subject = subject.strip().rstrip(",;:")
    if len(subject) < 2:
        return None
    return subject[:120]


def _extract_action_object(rest: str) -> tuple[Optional[str], Optional[str]]:
    rest = rest.strip().lstrip(",;: ")
    rest = re.sub(r"^(?:not|hereby|also)\s+", "", rest, flags=re.IGNORECASE)
    unlimited = re.match(r"have\s+(unlimited|no|full)\s+liability\b", rest, re.IGNORECASE)
    if unlimited:
        return "bear", f"{unlimited.group(1).lower()} liability{rest[unlimited.end():]}".strip()
    rest = re.sub(r"^(?:be|have)\s+", "", rest, flags=re.IGNORECASE)
    if not rest:
        return None, None

    match = re.match(r"([A-Za-z][A-Za-z-]{1,40})\b", rest)
    if not match:
        return None, None
    action = match.group(1).lower()

    remainder = rest[match.end() :].strip()
    cut = OBJECT_CUT_RE.search(remainder)
    if cut:
        remainder = remainder[: cut.start()]
    obj = remainder.strip(" ,;:.-")
    return action, obj[:160] or None


def _extract_condition(sentence: str) -> Optional[str]:
    m = CONDITIONAL_RE.search(sentence)
    if not m:
        return None
    cond = sentence[m.start() :].strip().rstrip(".")
    return cond[:280]


def _extract_deadline(sentence: str) -> Optional[str]:
    """Extract a relative deadline (e.g. '30 days'), not a calendar date."""
    m = DEADLINE_RE.search(sentence)
    if not m:
        return None
    raw = m.group(1).strip()
    # Drop any parenthetical numeric, e.g. "thirty (30) days" -> "thirty days".
    raw = re.sub(r"\(\d+\)", "", raw).strip()
    raw = re.sub(r"\)\s*", " ", raw).strip()
    raw = re.sub(r"\s+", " ", raw)
    # Convert a leading written number to digits when possible.
    parts = raw.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() in _NUMBER_WORDS:
        raw = f"{_NUMBER_WORDS[parts[0].lower()]} {parts[1]}"
    return raw


def _extract_deadline_date(sentence: str) -> Optional[str]:
    """Extract a calendar-date deadline (e.g. '15 April 2024')."""
    m = DATE_DEADLINE_RE.search(sentence)
    if not m:
        return None
    return m.group(1).strip()


def _derive_risk_level(typ: ObligationType, deadline: Optional[str], sentence_low: str) -> RiskSeverity:
    text = sentence_low
    risk = RiskSeverity.MEDIUM if typ == ObligationType.PROHIBITION else RiskSeverity.LOW
    if deadline:
        m = re.match(
            r"(\d+)\s+(hour|hours|day|days|week|weeks|month|months|year|years|business\s+days)",
            deadline.lower(),
        )
        if m:
            value = int(m.group(1))
            unit = m.group(2)
            if "hour" in unit:
                days = value / 24
            elif "week" in unit:
                days = value * 7
            elif "month" in unit:
                days = value * 30
            elif "year" in unit:
                days = value * 365
            else:
                days = value
            if days <= 1:
                risk = RiskSeverity.CRITICAL
            elif days <= 7:
                risk = RiskSeverity.HIGH
            elif days <= 30:
                risk = RiskSeverity.MEDIUM
    if "indemnif" in text and "all losses" in text:
        risk = RiskSeverity.HIGH
    return risk
