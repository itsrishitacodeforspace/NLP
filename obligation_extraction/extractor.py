"""Obligation extraction using spaCy dependency patterns + regex.

This module emits structured Obligation objects for every detected duty,
right, prohibition, or conditional clause. It is deliberately rule-based
to remain explainable and fast on the MVP; an LLM-based extractor can
augment this in a later phase.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Mapping, Optional

from app.models.schemas import Obligation, ObligationType, RiskSeverity
from app.utils.text import NUMBER_TOKEN_RE, written_number_to_int

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

# Shared number token: digits or (possibly hyphenated) written numbers such as
# "sixty" or "twenty-four" (see app.utils.text; the renewal rule uses the same
# vocabulary, which also covers seventy/eighty).
DEADLINE_RE = re.compile(
    r"\b(?:within|no later than|at least|prior to|after|by|on)\s+"
    r"(" + NUMBER_TOKEN_RE + r"((?:\s*\(\d+\))?\s+(?:hour|hours|day|days|week|weeks|month|months|year|years|business\s+days)))\b",
    re.IGNORECASE,
)
DATE_DEADLINE_RE = re.compile(
    r"\b(?:on\s+or\s+before|by|on|before|after)\s+"
    r"(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})\b",
    re.IGNORECASE,
)

# Recurring cadence adverbs ("monthly", "quarterly", ...) — not deadlines.
# "per X" / "every X" forms map onto the same normalised vocabulary.
# Deliberately tight: only unambiguous frequency words are accepted; vague
# cadences ("periodically", "as needed") are NOT extracted.
_FREQUENCY_RE = re.compile(
    r"\b(?:"
    r"(monthly|quarterly|annually|weekly|biannually|bi-annually|semiannually|semi-annually|daily|yearly)"
    r"|(?:per|every)\s+(?:month|quarter|year|week|day|annum)\b"
    r")",
    re.IGNORECASE,
)
_FREQUENCY_NORMALISE = {
    "monthly": "monthly", "per month": "monthly", "every month": "monthly",
    "quarterly": "quarterly", "per quarter": "quarterly", "every quarter": "quarterly",
    "annually": "annually", "yearly": "annually", "per annum": "annually",
    "per year": "annually", "every year": "annually",
    "weekly": "weekly", "per week": "weekly", "every week": "weekly",
    "daily": "daily", "per day": "daily", "every day": "daily",
    "biannually": "biannually", "bi-annually": "biannually",
    "semiannually": "semiannually", "semi-annually": "semiannually",
}

_PASSIVE_PARTICIPLE_RE = re.compile(
    r"^(?:be|is|are|was|were)\s+(?!entitled\b)"
    r"(?:[A-Za-z]+(?:ed|en)|sent|made|paid|done|taken|met|held)\b",
    re.IGNORECASE,
)

OBJECT_CUT_RE = re.compile(
    r"\b(?:within|by|no\s+later\s+than|prior\s+to|on\s+or\s+before|if|unless|subject\s+to|"
    r"provided\s+that|in\s+the\s+event\s+that|in\s+case|"
    r"pursuant\s+to|under\s+this|in\s+accordance\s+with)\b|[.;]",
    re.IGNORECASE,
)

# Conditional / exception markers. ``where`` is only accepted clause-initially
# (or after punctuation); elsewhere it is usually a relative adverb.
_CONDITION_MARKER = (
    r"if|unless|provided\s+that|subject\s+to|in\s+the\s+event\s+that|in\s+case|where|"
    r"except(?:\s+(?:where|as|for))?"
)
_CONDITION_SCAN_RE = re.compile(r"\b(?P<marker>" + _CONDITION_MARKER + r")\b", re.IGNORECASE)
_CONDITION_AT_START_RE = re.compile(r"^(?P<marker>" + _CONDITION_MARKER + r")\b", re.IGNORECASE)

_CLAUSE_PREFIX_RE = re.compile(r"^\s*(?:\(?[A-Za-z0-9]{1,4}[.)]\s*|\d+(?:\.\d+)*\.?\s+)")
_HEADING_PREFIX_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:"
    r"\d+(?:\.\d+)*"
    r"|[A-Z]\."
    r"|\([a-z0-9]+\)"
    r"|(?i:Article\s+\d+)"
    r"|(?i:Section\s+[IVXLC]+)"
    r")[.):]?\s+[A-Z][^\n]{0,120}\n"
)

# Party vocabulary. Role nouns are accepted case-insensitively; proper names
# additionally need a corporate suffix or at least two capitalised tokens.
_PARTY_ROLE = (
    r"(?:Service\s+Provider|Disclosing\s+Party|Receiving\s+Party|Subcontractor|"
    r"Processor|Controller|"
    r"Consultant|Contractor|Distributor|Purchaser|Indemnifier|Guarantor|"
    r"Arbitrator|Transferee|Assignor|Assignee|Customer|Supplier|Provider|"
    r"Vendor|Buyer|Seller|Client|Licensor|Licensee|Lessor|Lessee|Borrower|"
    r"Lender|Employer|Employee|Partner|Reseller|Recipient|Insurer|Bank|"
    r"Agent|Company|Firm|Party)"
)
_PARTY_ARTICLE_RE = re.compile(r"(?:the|a|an)\s+", re.IGNORECASE)
_PARTY_ROLE_RE = re.compile(_PARTY_ROLE + r"\b", re.IGNORECASE)
_CORP_NAME_RE = re.compile(
    r"(?:[A-Z][\w&.'-]*\s+){1,5}(?:Ltd|Limited|LLP|Inc|Corp|Corporation|LLC|PLC|Pvt)\b\.?"
)
_PROPER_NAME_RE = re.compile(
    r"[A-Z][\w&.'-]*(?:\s+(?:of|and|&)\s+[A-Z][\w&.'-]*|\s+[A-Z][\w&.'-]*)+"
)
_RECIPIENT_VERB = (
    r"(?:pay|paid|pays|paying|"
    r"deliver(?:s|ed|ing)?|"
    r"provide(?:s|d|ing)?|"
    r"send|sent|sends|sending|"
    r"submit(?:s|ted|ting)?|"
    r"notif(?:y|ies|ied|ying)|"
    r"give|gave|given|gives|giving|"
    r"furnish(?:es|ed|ing)?|"
    r"supply|supplies|supplied|supplying|"
    r"transfer(?:s|red|ring)?|"
    r"refund(?:s|ed|ing)?|"
    r"reimburse(?:s|d|ing)?|"
    r"indemnif(?:y|ies|ied|ying)|"
    r"compensate(?:s|d|ing)?|"
    r"assign(?:s|ed|ing)?|"
    r"disclos(?:e|es|ed|ing)|"
    r"shar(?:e|es|ed|ing)|"
    r"serv(?:e|es|ed|ing)|"
    r"issu(?:e|es|ed|ing)|"
    r"offer(?:s|ed|ing)?)"
)
_TO_RECIPIENT_RE = re.compile(
    r"\b" + _RECIPIENT_VERB + r"\b[^.;:]{0,120}?\bto\s+", re.IGNORECASE
)
_DOUBLE_OBJECT_RE = re.compile(
    r"\b(?:pay|paid|notif(?:y|ies|ied|ying)|reimburse(?:s|d|ing)?|"
    r"indemnif(?:y|ies|ied|ying)|compensate(?:s|d|ing)?|advis(?:e|es|ed|ing)|"
    r"inform(?:s|ed|ing)?|give|gave|given|send|sent|provide(?:s|d|ing)?)\b\s+",
    re.IGNORECASE,
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
    frequency: Optional[str]
    risk_level: RiskSeverity
    confidence: float


def extract_obligations_from_clause(
    clause_id: str,
    clause_text: str,
    *,
    obligation_counter: int = 0,
    party_aliases: Optional[Mapping[str, str]] = None,
) -> List[Obligation]:
    """Parse a clause into structured Obligation rows.

    ``char_start``/``char_end`` are zero-based, end-exclusive offsets into
    ``clause_text``. ``Obligation.text`` is the exact source substring when the
    sentence can be located unambiguously; offsets are ``None`` otherwise.
    ``party_aliases`` maps an alternate spelling (e.g. a defined company name)
    to its canonical party label.
    """
    if not clause_text or not clause_text.strip():
        return []

    # Split by sentence-like boundaries while keeping them in order
    sentences = _split_sentences(clause_text)
    obligations: List[Obligation] = []
    seen_in_clause: set[tuple] = set()
    for sent in sentences:
        hit = _analyse_sentence(sent, party_aliases=party_aliases)
        if not hit:
            continue
        # Deduplicate EXACT duplicates within this clause (boilerplate
        # restatements: same subject+action+object+condition). Keep the first
        # occurrence; the duplicate is silently dropped.
        dedup_key = (hit.subject, hit.action, hit.object, hit.condition)
        if dedup_key in seen_in_clause:
            continue
        seen_in_clause.add(dedup_key)
        obligation_counter += 1
        char_start, char_end = _locate_sentence(clause_text, sent.strip())
        cited_text = (
            clause_text[char_start:char_end]
            if char_start is not None and char_end is not None
            else sent.strip()
        )
        obligations.append(
            Obligation(
                obligation_id=f"{clause_id}_obg{obligation_counter:03d}",
                clause_id=clause_id,
                text=cited_text,
                obligation_type=hit.obligation_type,
                subject=hit.subject,
                counterparty=hit.counterparty,
                action=hit.action,
                object=hit.object,
                condition=hit.condition,
                deadline_expression=hit.deadline_expression,
                deadline_date=hit.deadline_date,
                frequency=hit.frequency,
                risk_level=hit.risk_level,
                confidence=hit.confidence,
                source="rule",
                char_start=char_start,
                char_end=char_end,
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
    text = _HEADING_PREFIX_RE.sub("", text, count=1)
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


def _analyse_sentence(
    sentence: str,
    *,
    party_aliases: Optional[Mapping[str, str]] = None,
) -> Optional[ObligationHit]:
    sentence = sentence.strip()
    if not sentence:
        return None

    obligation_type, modal_match = _choose_modal(sentence)
    if obligation_type is None or modal_match is None:
        return None

    confidence = {
        ObligationType.OBLIGATION: 0.85,
        ObligationType.RIGHT: 0.7,
        ObligationType.PROHIBITION: 0.8,
    }[obligation_type]

    condition_spans = _condition_spans(sentence, modal_match.start())
    masked = _mask_spans(sentence, condition_spans)

    # The subject belongs to the first deontic verb outside a condition, even
    # when the sentence later contains a prohibition
    # ("shall keep ... and shall not disclose").
    first_modal_start = min(
        (
            match.start()
            for _, pattern in _DEONTIC_PATTERNS
            for match in pattern.finditer(sentence)
            if not _inside_span(match.start(), condition_spans)
        ),
        default=modal_match.start(),
    )
    subject_src = _subject_source(sentence, condition_spans, first_modal_start)
    subject = _extract_subject(subject_src)

    raw_tail = re.sub(r"^[\s,;:]+", "", masked[modal_match.end():])
    if re.match(r"be\s+", raw_tail, re.IGNORECASE) and re.search(
        r"\b(seat|venue)\b", subject or "", re.IGNORECASE
    ):
        return None
    # Passive voice: "The services shall be provided by the Provider" — the
    # grammatical subject is the object, not the obligor. The obligor is the
    # agent after "by"; when no agent is stated, leave it unknown rather than
    # inventing the object as the responsible party. Regular -ed/-en
    # participles plus common irregulars (sent/made/paid/...) are recognised.
    if obligation_type in (ObligationType.OBLIGATION, ObligationType.PROHIBITION):
        passive = _PASSIVE_PARTICIPLE_RE.match(raw_tail)
        if passive:
            agent_m = re.search(r"\bby\s+", raw_tail, re.IGNORECASE)
            subject = _party_after(raw_tail, agent_m.end()) if agent_m else None
    action, obj = _extract_action_object(raw_tail)
    # "shall fail" in a conditional protasis is an event, not a duty.
    if action == "fail":
        return None
    counterparty = _extract_counterparty(raw_tail, subject, party_aliases)
    if action == "governed":
        return None
    if action == "resolved" and subject and re.search(r"\b(seat|venue|dispute)\b", subject):
        return None
    condition = _extract_condition(sentence, condition_spans)
    # Deadlines inside a condition belong to the condition, not the duty.
    deadline_expr = _extract_deadline(masked)
    deadline_date = _extract_deadline_date(masked)
    frequency = _extract_frequency(sentence)
    risk_level = _derive_risk_level(obligation_type, deadline_expr, sentence.lower(), action)

    return ObligationHit(
        text=sentence,
        obligation_type=obligation_type,
        subject=subject,
        counterparty=counterparty,
        action=action,
        object=obj,
        condition=condition,
        deadline_expression=deadline_expr,
        deadline_date=deadline_date,
        frequency=frequency,
        risk_level=risk_level,
        confidence=confidence,
    )


def _choose_modal(sentence: str) -> tuple[Optional[ObligationType], Optional[re.Match]]:
    """Pick the deontic modal, preferring the main clause over a protasis."""
    first_type, first_match = _find_modal(sentence, 0)
    if first_match is None:
        return None, None
    leading_start = _leading_condition_start(sentence)
    if leading_start is None:
        return first_type, first_match
    comma = _next_top_level_comma(sentence, leading_start, len(sentence))
    if comma is not None:
        later_type, later_match = _find_modal(sentence, comma + 1)
        if later_match is not None:
            return later_type, later_match
    return first_type, first_match


def _find_modal(sentence: str, start: int) -> tuple[Optional[ObligationType], Optional[re.Match]]:
    for candidate_type, pattern in _DEONTIC_PATTERNS:
        match = pattern.search(sentence, start)
        if match:
            return candidate_type, match
    return None, None


def _leading_condition_start(sentence: str) -> Optional[int]:
    stripped = _CLAUSE_PREFIX_RE.sub("", sentence, count=1)
    offset = len(sentence) - len(stripped)
    match = _CONDITION_AT_START_RE.match(stripped)
    if not match:
        return None
    return offset + match.start()


def _only_prefix(prefix: str) -> bool:
    return not re.search(r"[A-Za-z]", _CLAUSE_PREFIX_RE.sub("", prefix, count=1))


def _next_top_level_comma(text: str, start: int, limit: int) -> Optional[int]:
    depth = 0
    for index in range(start, min(limit, len(text))):
        char = text[index]
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            return index
    return None


def _last_top_level_comma(text: str, start: int, limit: int) -> Optional[int]:
    last: Optional[int] = None
    depth = 0
    for index in range(start, min(limit, len(text))):
        char = text[index]
        if char in "([":
            depth += 1
        elif char in ")]":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            last = index
    return last


def _condition_spans(sentence: str, modal_start: int) -> list[tuple[int, int]]:
    """Return (start, end) spans of conditional / exception clauses."""
    spans: list[tuple[int, int]] = []
    for match in _CONDITION_SCAN_RE.finditer(sentence):
        marker = match.group("marker").lower()
        if marker == "where" and not _where_is_conditional(sentence, match.start()):
            continue
        if _inside_span(match.start(), spans):
            continue
        if match.start() < modal_start:
            if _only_prefix(sentence[: match.start()]):
                end = _last_top_level_comma(sentence, match.start(), modal_start)
            else:
                end = _next_top_level_comma(sentence, match.end(), modal_start)
            if end is None:
                end = modal_start
            spans.append((match.start(), end))
        else:
            end = _next_top_level_comma(sentence, match.end(), len(sentence))
            if end is None:
                end = len(sentence)
            spans.append((match.start(), end))
    return spans


def _where_is_conditional(sentence: str, start: int) -> bool:
    prefix = sentence[:start].rstrip()
    if not prefix or _only_prefix(prefix):
        return True
    return prefix.endswith((",", ";", ":"))


def _inside_span(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        for index in range(start, min(end, len(chars))):
            chars[index] = " "
    return "".join(chars)


def _subject_source(sentence: str, spans: list[tuple[int, int]], modal_start: int) -> str:
    for start, end in spans:
        if start >= modal_start:
            continue
        if _only_prefix(sentence[:start]):
            return sentence[end:modal_start]
        return sentence[:start]
    return sentence[:modal_start]


def _extract_subject(prefix: str) -> Optional[str]:
    subject = _CLAUSE_PREFIX_RE.sub("", prefix, count=1)
    subject = re.sub(r"^\s*#+\s*", "", subject)
    # Fallback for callers that pass a full clause rather than a subject span.
    subject = re.sub(
        r"^(?:if|provided\s+that|subject\s+to|unless|in\s+the\s+event\s+that)\b[^,]{0,250},\s*",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    subject = re.sub(
        r"^(?:thereafter|however|notwithstanding(?:\s+the\s+foregoing)?|further|additionally)\s+",
        "",
        subject.strip(),
        flags=re.IGNORECASE,
    )
    subject = subject.strip().lstrip(",;:").strip().rstrip(",;:")
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
    rest = re.sub(r"^(?:not|hereby|also)\b[,\s]*", "", rest, flags=re.IGNORECASE)
    rest = rest.lstrip(",;: ")
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


def _party_after(text: str, position: int) -> Optional[str]:
    rest = text[position:]
    article = _PARTY_ARTICLE_RE.match(rest)
    if article:
        rest = rest[article.end():]
    role = _PARTY_ROLE_RE.match(rest)
    if role:
        return role.group(0).strip()
    corp = _CORP_NAME_RE.match(rest)
    if corp:
        return corp.group(0).strip().rstrip(".")
    proper = _PROPER_NAME_RE.match(rest)
    if proper:
        return proper.group(0).strip()
    return None


def _norm_party(name: Optional[str]) -> str:
    value = re.sub(r"^(?:the|a|an)\s+", "", (name or "").strip(), flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _canonical_party(
    name: str,
    party_aliases: Optional[Mapping[str, str]],
) -> str:
    if not party_aliases:
        return name
    key = _norm_party(name)
    for alias, canonical in party_aliases.items():
        if key == _norm_party(alias):
            return canonical
    return name


def _extract_counterparty(
    raw_tail: str,
    subject: Optional[str],
    party_aliases: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Conservatively extract the recipient/beneficiary of the obligation.

    Only explicit dative constructions are used ("pay X", "deliver ... to X",
    "notify X"). A party is never inferred merely from its presence in the
    clause; ambiguous or unnamed recipients stay ``None``.
    """
    candidates = [match.end() for match in _TO_RECIPIENT_RE.finditer(raw_tail)]
    candidates.extend(match.end() for match in _DOUBLE_OBJECT_RE.finditer(raw_tail))
    for position in candidates:
        party = _party_after(raw_tail, position)
        if not party:
            continue
        if subject and _norm_party(party) == _norm_party(subject):
            continue
        return _canonical_party(party, party_aliases)
    # Second pass: an explicit dative party appears immediately after the
    # action verb, but the object phrase contains a second, unrelated
    # reference to the same party ("indemnify the Customer against the
    # Customer's losses"). The verb-adjacent party is still the beneficiary;
    # the self-reference is not a new candidate.
    if subject:
        self_ref = re.escape(_norm_party(subject))
        for match in _DOUBLE_OBJECT_RE.finditer(raw_tail):
            rest = raw_tail[match.end():]
            first = _party_after(rest, 0)
            if first and _norm_party(first) != _norm_party(subject):
                continue
            if not re.search(r"\b(?:for|against|of)\s+(?:the\s+)?" + self_ref, rest, re.IGNORECASE):
                continue
            return _canonical_party(first, party_aliases)
    return None


def _locate_sentence(clause_text: str, sentence: str) -> tuple[Optional[int], Optional[int]]:
    """Locate ``sentence`` within ``clause_text``, allowing whitespace differences.

    Returns zero-based half-open (start, end) offsets, or (None, None) when the
    sentence is not found or matches more than once (never fabricate a location).
    """
    if not sentence or not clause_text:
        return None, None
    tokens = [t for t in re.split(r"\s+", sentence) if t]
    pattern = r"(?<![A-Za-z0-9])" + r"\s+".join(re.escape(t) for t in tokens) + r"(?![A-Za-z0-9])"
    matches = list(re.finditer(pattern, clause_text))
    if len(matches) != 1:
        return None, None
    match = matches[0]
    return match.start(), match.end()


def _extract_condition(sentence: str, spans: list[tuple[int, int]]) -> Optional[str]:
    parts = [sentence[start:end].strip(" \t\r\n,;:.") for start, end in spans]
    parts = [part for part in parts if part]
    if not parts:
        return None
    return "; ".join(parts)[:280]


def _extract_deadline(sentence: str) -> Optional[str]:
    """Extract a relative deadline (e.g. '30 days'), not a calendar date."""
    match = DEADLINE_RE.search(sentence)
    if not match:
        return None
    raw = match.group(1).strip()
    # Drop any parenthetical numeric, e.g. "thirty (30) days" -> "thirty days".
    raw = re.sub(r"\(\d+\)", "", raw).strip()
    raw = re.sub(r"\)\s*", " ", raw).strip()
    raw = re.sub(r"\s+", " ", raw)
    # Convert a leading written number (incl. hyphenated compounds such as
    # "twenty-four") to digits when possible.
    parts = raw.split(" ", 1)
    value = written_number_to_int(parts[0]) if parts else None
    if len(parts) == 2 and value is not None:
        raw = f"{value} {parts[1]}"
    return raw


def _extract_deadline_date(sentence: str) -> Optional[str]:
    """Extract a calendar-date deadline (e.g. '15 April 2024')."""
    match = DATE_DEADLINE_RE.search(sentence)
    if not match:
        return None
    return match.group(1).strip()


def _extract_frequency(sentence: str) -> Optional[str]:
    """Extract a recurring cadence from a frequency adverb, if present.

    Only unambiguous words are accepted ("monthly", "quarterly", "per
    annum", ...); vague cadences ("periodically", "as needed") yield None.
    """
    for match in _FREQUENCY_RE.finditer(sentence):
        token = match.group(0).lower()
        normalised = _FREQUENCY_NORMALISE.get(token)
        if normalised:
            return normalised
    return None


# Severity is driven by obligation TYPE/content, not deadline urgency. A
# 1-hour deadline on a trivial notification must not outrank a 30-day
# indemnity. The table is intentionally small and explicit:
#   - HIGH: obligations that can trigger a material financial or contractual
#     consequence (indemnify, terminate, pay, deliver, refund, compensate).
#   - MEDIUM: obligations with operational impact (notify, report, inform,
#     maintain, encrypt, delete, protect, keep, ensure, provide, supply).
#   - LOW: anything else (general compliance, acknowledge, cooperate, ...).
# Deadline urgency is a *bounded* modifier: +1 level at most, and only when
# the deadline is <=24h AND the content is already HIGH. A CRITICAL deadline
# boost is never applied (it would conflate urgency with severity).
_OBLIGATION_SEVERITY_TABLE = {
    # HIGH — material financial / contractual consequence
    "indemnify": RiskSeverity.HIGH, "indemnifies": RiskSeverity.HIGH,
    "indemnified": RiskSeverity.HIGH, "indemnifying": RiskSeverity.HIGH,
    "terminate": RiskSeverity.HIGH, "terminates": RiskSeverity.HIGH,
    "terminated": RiskSeverity.HIGH, "terminating": RiskSeverity.HIGH,
    "pay": RiskSeverity.HIGH, "pays": RiskSeverity.HIGH,
    "paid": RiskSeverity.HIGH, "paying": RiskSeverity.HIGH,
    "deliver": RiskSeverity.HIGH, "delivers": RiskSeverity.HIGH,
    "delivered": RiskSeverity.HIGH, "delivering": RiskSeverity.HIGH,
    "refund": RiskSeverity.HIGH, "refunds": RiskSeverity.HIGH,
    "refunded": RiskSeverity.HIGH, "refunding": RiskSeverity.HIGH,
    "compensate": RiskSeverity.HIGH, "compensates": RiskSeverity.HIGH,
    "compensated": RiskSeverity.HIGH, "compensating": RiskSeverity.HIGH,
    # MEDIUM — operational impact
    "notify": RiskSeverity.MEDIUM, "notifies": RiskSeverity.MEDIUM,
    "notified": RiskSeverity.MEDIUM, "notifying": RiskSeverity.MEDIUM,
    "report": RiskSeverity.MEDIUM, "reports": RiskSeverity.MEDIUM,
    "reported": RiskSeverity.MEDIUM, "reporting": RiskSeverity.MEDIUM,
    "inform": RiskSeverity.MEDIUM, "informs": RiskSeverity.MEDIUM,
    "informed": RiskSeverity.MEDIUM, "informing": RiskSeverity.MEDIUM,
    "maintain": RiskSeverity.MEDIUM, "maintains": RiskSeverity.MEDIUM,
    "maintained": RiskSeverity.MEDIUM, "maintaining": RiskSeverity.MEDIUM,
    "encrypt": RiskSeverity.MEDIUM, "encrypts": RiskSeverity.MEDIUM,
    "encrypted": RiskSeverity.MEDIUM, "encrypting": RiskSeverity.MEDIUM,
    "delete": RiskSeverity.MEDIUM, "deletes": RiskSeverity.MEDIUM,
    "deleted": RiskSeverity.MEDIUM, "deleting": RiskSeverity.MEDIUM,
    "protect": RiskSeverity.MEDIUM, "protects": RiskSeverity.MEDIUM,
    "protected": RiskSeverity.MEDIUM, "protecting": RiskSeverity.MEDIUM,
    "keep": RiskSeverity.MEDIUM, "keeps": RiskSeverity.MEDIUM,
    "kept": RiskSeverity.MEDIUM, "keeping": RiskSeverity.MEDIUM,
    "ensure": RiskSeverity.MEDIUM, "ensures": RiskSeverity.MEDIUM,
    "ensured": RiskSeverity.MEDIUM, "ensuring": RiskSeverity.MEDIUM,
    "provide": RiskSeverity.MEDIUM, "provides": RiskSeverity.MEDIUM,
    "provided": RiskSeverity.MEDIUM, "providing": RiskSeverity.MEDIUM,
    "supply": RiskSeverity.MEDIUM, "supplies": RiskSeverity.MEDIUM,
    "supplied": RiskSeverity.MEDIUM, "supplying": RiskSeverity.MEDIUM,
    "furnish": RiskSeverity.MEDIUM, "furnishes": RiskSeverity.MEDIUM,
    "furnished": RiskSeverity.MEDIUM, "furnishing": RiskSeverity.MEDIUM,
    "issue": RiskSeverity.MEDIUM, "issues": RiskSeverity.MEDIUM,
    "issued": RiskSeverity.MEDIUM, "issuing": RiskSeverity.MEDIUM,
    # LOW — everything else
}

_SEVERITY_ORDER = {
    RiskSeverity.LOW: 0,
    RiskSeverity.MEDIUM: 1,
    RiskSeverity.HIGH: 2,
    RiskSeverity.CRITICAL: 3,
}


def _deadline_days(deadline: Optional[str]) -> Optional[float]:
    """Convert a deadline expression to days (for the bounded urgency boost)."""
    if not deadline:
        return None
    match = re.match(
        r"(\d+)\s+(hour|hours|day|days|week|weeks|month|months|year|years|business\s+days)",
        deadline.lower(),
    )
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if "hour" in unit:
        return value / 24
    if "week" in unit:
        return value * 7
    if "month" in unit:
        return value * 30
    if "year" in unit:
        return value * 365
    return float(value)


def _derive_risk_level(typ: ObligationType, deadline: Optional[str], sentence_low: str, action: Optional[str] = None) -> RiskSeverity:
    # Start from the content table (action verb), falling back to a
    # text-based scan of the sentence when no action verb is in the table.
    content = RiskSeverity.LOW
    if action:
        content = _OBLIGATION_SEVERITY_TABLE.get(action.lower(), RiskSeverity.LOW)
    if content == RiskSeverity.LOW:
        for verb, sev in _OBLIGATION_SEVERITY_TABLE.items():
            if re.search(rf"\b{re.escape(verb)}\b", sentence_low):
                content = sev
                break
    # Prohibitions are at least MEDIUM (a "shall not" is a binding constraint).
    if typ == ObligationType.PROHIBITION and content == RiskSeverity.LOW:
        content = RiskSeverity.MEDIUM
    # Bounded urgency modifier: +1 level at most, only for <=24h deadlines
    # on already-HIGH content. Never escalates to CRITICAL.
    days = _deadline_days(deadline)
    if days is not None and days <= 1 and content == RiskSeverity.HIGH:
        content = RiskSeverity.CRITICAL
    return content
