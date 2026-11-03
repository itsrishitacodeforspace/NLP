"""Named Entity Recognition for legal contracts.

The MVP is regex-first because:
  * Indian identifiers (CIN/PAN/GSTIN) have deterministic formats.
  * The heavy NER model (DeBERTa) is optional and degrades gracefully.
  * Regex matches give us high precision on dates, amounts, and notice periods.

When the DeBERTa model is available, `extract_entities_with_deberta` enriches
the result with general entities (PARTY, ORG, DATE) where regex missed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.models.schemas import Entity
from app.utils.text import clean_text

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# CIN: 21 characters, e.g. U63040MH2019PTC123456.
CIN_RE = re.compile(r"\b[LUFE]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b")
LLPIN_RE = re.compile(r"\b[A-Z]{3}-\d{4}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b")
TAN_RE = re.compile(r"\b[A-Z]{4}\d{5}[A-Z]\b")

# Indian cities (abbreviated — covers top commercial centres)
INDIAN_CITIES = {
    "mumbai", "delhi", "new delhi", "bengaluru", "bangalore", "chennai",
    "kolkata", "hyderabad", "pune", "ahmedabad", "jaipur", "lucknow",
    "kanpur", "nagpur", "indore", "thane", "bhopal", "visakhapatnam",
    "patna", "vadodara", "ghaziabad", "ludhiana", "agra", "nashik",
    "faridabad", "meerut", "rajkot", "varanasi", "srinagar", "aurangabad",
    "dhanbad", "amritsar", "navi mumbai", "allahabad", "prayagraj",
    "guwahati", "chandigarh", "ranchi", "coimbatore", "mysuru", "mysore",
    "kochi", "trivandrum", "thiruvananthapuram", "gurugram", "gurgaon",
    "noida", "greater noida", "dehradun", "shimla", "manali",
}

INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "orissa", "punjab", "rajasthan",
    "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh",
    "uttarakhand", "west bengal", "delhi", "jammu and kashmir",
    "ladakh", "chandigarh", "puducherry",
}

# Foreign arbitration seats commonly seen in Indian cross-border contracts
FOREIGN_SEATS = {
    "singapore", "london", "hong kong", "dubai", "new york", "zurich",
    "paris", "geneva", "kuala lumpur", "shanghai", "tokyo", "frankfurt",
    "amsterdam", "stockholm", "vienna", "madrid", "rome", "seoul",
}

INDIAN_SEATS = {
    "new delhi", "mumbai", "bengaluru", "bangalore", "chennai", "kolkata",
    "hyderabad", "pune", "ahmedabad", "jaipur", "lucknow", "kochi",
    "guwahati", "chandigarh", "india",
}

INR_RE = re.compile(
    r"(?:(?:Rs\.?|INR|₹)\s?[\d,]+(?:\.\d+)?\s*(?:crore|lakh|lac|crore[s]?|/-)?)",
    re.IGNORECASE,
)
USD_RE = re.compile(r"\$\s?[\d,]+(?:\.\d+)?(?:\s?(?:USD|US dollars?))?", re.IGNORECASE)
EUR_RE = re.compile(r"(?:€|EUR)\s?[\d,]+(?:\.\d+)?", re.IGNORECASE)
GBP_RE = re.compile(r"(?:£|GBP)\s?[\d,]+(?:\.\d+)?", re.IGNORECASE)

DATE_RES = [
    re.compile(r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(r"\b\d{1,2}-\d{1,2}-\d{2,4}\b"),
    re.compile(r"\bFY\s?\d{4}-?\d{0,4}", re.IGNORECASE),
    re.compile(r"\b\d{1,2}\s?(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b", re.IGNORECASE),
    # Abbreviated month forms: "07 Jan 2025", "Jan 7, 2025"
    re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{2,4}\b", re.IGNORECASE),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b", re.IGNORECASE),
]
# A deontic prefix (within / no later than / at least / ...) is REQUIRED for
# the NOTICE_PERIOD label: bare durations ("the term is 90 days") are not
# notice periods. The prefix is a non-capturing group so the match never
# includes leading whitespace.
NOTICE_PERIOD_RE = re.compile(
    r"\b(?:within|no later than|at least|prior to|before|after)\s+(\d+)\s+"
    r"(hour|hours|day|days|week|weeks|month|months|year|years|business day[s]?)\b",
    re.IGNORECASE,
)
# "30 days prior written notice" — the number is followed (through optional
# adjectives) by the word "notice". Anchored to "notice" so a bare duration
# without a notice context is not labelled as a notice period.
NOTICE_PERIOD_SUFFIX_RE = re.compile(
    r"\b(\d+)\s+"
    r"(hour|hours|day|days|week|weeks|month|months|year|years|business day[s]?)"
    r"(?:\s+(?:prior|written|advance|sufficient|reasonable))*\s+notice\b",
    re.IGNORECASE,
)
# Bare durations without a deontic prefix ("term of 90 days", "12 months").
DURATION_RE = re.compile(
    r"\b(\d+)\s+"
    r"(hour|hours|day|days|week|weeks|month|months|year|years|business day[s]?)\b",
    re.IGNORECASE,
)
TERM_DURATION_RE = re.compile(
    r"\bfor a (?:period|term) of\s+(\d+)\s+"
    r"(day|days|week|weeks|month|months|year|years)\b",
    re.IGNORECASE,
)
CURE_PERIOD_RE = re.compile(
    r"(?:cure period|to cure|within)\s+(\d+)\s+"
    r"(day|days|week|weeks|month|months)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    entities: List[Entity]
    methods: Dict[str, str]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_entities(text: str, *, clause_text: Optional[str] = None) -> ExtractionResult:
    """Extract entities from clause text using regex rules.

    Returns a list of Entity objects with char offsets relative to the
    supplied text. Falls back to the contract-wide text if clause-level
    text isn't useful.
    """
    scan_text = clause_text or text or ""
    entities: List[Entity] = []

    # Indian identifiers
    entities.extend(_scan_regex(CIN_RE, scan_text, "CIN", 0.99))
    entities.extend(_scan_regex(LLPIN_RE, scan_text, "LLPIN", 0.95))
    entities.extend(_scan_regex(PAN_RE, scan_text, "PAN", 0.99))
    entities.extend(_scan_regex(GSTIN_RE, scan_text, "GSTIN", 0.99))
    entities.extend(_scan_regex(TAN_RE, scan_text, "TAN", 0.95))

    # Money
    entities.extend(_scan_regex(INR_RE, scan_text, "PAYMENT_AMOUNT", 0.95))
    entities.extend(_scan_regex(USD_RE, scan_text, "PAYMENT_AMOUNT", 0.95))
    entities.extend(_scan_regex(EUR_RE, scan_text, "PAYMENT_AMOUNT", 0.95))
    entities.extend(_scan_regex(GBP_RE, scan_text, "PAYMENT_AMOUNT", 0.95))

    # Dates
    for regex in DATE_RES:
        entities.extend(_scan_regex(regex, scan_text, "DATE", 0.95))

    # Notice / term durations
    notice_entities = _scan_regex(NOTICE_PERIOD_RE, scan_text, "NOTICE_PERIOD", 0.9)
    notice_suffix = _scan_regex(NOTICE_PERIOD_SUFFIX_RE, scan_text, "NOTICE_PERIOD", 0.9)
    entities.extend(notice_entities)
    entities.extend(notice_suffix)
    # Bare durations without a deontic prefix are DURATION, not notice periods.
    notice_spans = [(e.start_char, e.end_char) for e in notice_entities + notice_suffix]
    entities.extend(_scan_durations(scan_text, notice_spans=notice_spans))
    entities.extend(_scan_regex(TERM_DURATION_RE, scan_text, "TERM_DURATION", 0.9))
    entities.extend(_scan_regex(CURE_PERIOD_RE, scan_text, "CURE_PERIOD", 0.9))

    # Locations (jurisdictions / cities / seats)
    entities.extend(_scan_locations(scan_text))

    # DeBERTa NER enrichment (optional)
    try:
        from nlp.ner.ner_ml import enrich_entities_with_deberta

        enriched = enrich_entities_with_deberta(scan_text, existing=entities)
        entities = enriched
    except Exception:
        pass

    # Dedup
    seen = set()
    deduped: List[Entity] = []
    for e in entities:
        key = (e.label, e.text.lower(), e.start_char)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)
    return ExtractionResult(entities=deduped, methods={"primary": "regex"})


def detect_arbitration_seat(text: str) -> Optional[str]:
    """Return the most likely arbitration seat mentioned in text.

    Heuristic:
      1. Prefer explicit phrases: "seat of arbitration shall be X".
      2. Inside arbitration-context sentences, prefer FOREIGN seats, then
         Indian *cities* (not the generic "India").
      3. Skip the generic "India" entry unless nothing more specific was found.

    A city only counts as a seat when it appears in a sentence with an
    arbitration-context cue (arbitration, seat, venue, dispute resolution,
    tribunal, ...). A bare city mention in a payment address, data-hosting
    location or elsewhere in the document yields ``None``.
    """
    cleaned = clean_text(text)
    lowered = cleaned.lower()

    # 1. Explicit phrase
    explicit = re.search(
        r"seat\s+of\s+arbitration\s+(?:shall\s+be|is|means)\s+([A-Za-z][A-Za-z\s,]{2,60})",
        lowered,
    )
    if explicit:
        raw = explicit.group(1)
        known = sorted(FOREIGN_SEATS | (INDIAN_SEATS - {"india"}), key=len, reverse=True)
        for seat in known:
            if re.search(rf"\b{re.escape(seat)}\b", raw):
                return seat.title()
        value = re.split(r"\b(?:and|or)\b|[.;]", raw, maxsplit=1)[0].strip().rstrip(",.")
        if value and value.lower() not in {"india", "indian"}:
            return value.title()

    # 2/3. Walk arbitration-context sentences; a seat is only accepted from a
    #      sentence that actually discusses arbitration / dispute resolution.
    for sent in re.split(r"(?<=[.!?])\s+", cleaned):
        ls = sent.lower()
        if not _has_arbitration_context(ls):
            continue
        for seat in FOREIGN_SEATS:
            if seat in ls:
                return seat.title()
        for seat in INDIAN_SEATS - {"india"}:
            if seat in ls:
                return seat.title()

    # 4. Last resort — return "India" only as generic jurisdiction, and only
    #    when the document actually references arbitration / a seat / venue.
    if _has_arbitration_context(lowered) and ("india" in lowered or "indian" in lowered):
        return "India"
    return None


# A city only counts as an arbitration seat when its sentence actually talks
# about arbitration / dispute resolution. A payment address, data-centre
# location or registered office must not become the "seat".
_ARBITRATION_CONTEXT_CUES = (
    "arbitration", "arbitral", "seat", "venue", "dispute resolution",
    "tribunal", "siac", "icc", "lcia", "ciarb", "finally settled",
)


def _has_arbitration_context(sentence_low: str) -> bool:
    """True when a sentence positively references arbitration / dispute
    resolution. A *negated* mention ("there is no arbitration clause") does
    NOT count — the sentence is saying arbitration is absent."""
    for cue in _ARBITRATION_CONTEXT_CUES:
        for match in re.finditer(re.escape(cue), sentence_low):
            # A negation cue within 3 tokens before the cue negates it.
            prefix_tokens = sentence_low[: match.start()].split()[-3:]
            if not any(t in ("not", "no", "never", "without", "neither", "nor") for t in prefix_tokens):
                return True
    return False


def detect_arbitration_venue(text: str) -> Optional[str]:
    """Return the arbitration venue if explicitly stated, else ``None``."""
    cleaned = clean_text(text)
    m = re.search(
        r"(?:venue|place)\s+of\s+arbitration\s+(?:shall\s+be|is|at)\s+([A-Za-z][A-Za-z\s,]{2,60})",
        cleaned,
        re.IGNORECASE,
    )
    if not m:
        return None
    raw = m.group(1)
    known = sorted(FOREIGN_SEATS | (INDIAN_SEATS - {"india"}), key=len, reverse=True)
    for seat in known:
        if re.search(rf"\b{re.escape(seat)}\b", raw, re.IGNORECASE):
            return seat.title()
    return raw.split(".")[0].strip().rstrip(",.").title() or None


def detect_governing_law(text: str) -> Optional[str]:
    """Return the governing law phrase if found, preserving source casing."""
    cleaned = clean_text(text)
    patterns = [
        r"governed by the laws of[^.]{0,80}",
        r"governing law[^.]{0,80}laws of[^.]{0,80}",
        r"subject to the laws of[^.]{0,80}",
        r"laws of the state of[^.]{0,80}",
        r"laws of india",
    ]
    for pat in patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            phrase = m.group(0).strip().rstrip(".,")
            return phrase[:160]
    return None


# Negation handling: a statutory mention that is explicitly negated or denied
# in its immediate scope ("was not executed on duly stamped paper", "without
# deduction of tax at source", "exempt from stamp duty") is NOT confirmation
# that the requirement was addressed, so it must not suppress the review
# prompt. The cue must sit within a few tokens before the match, in the same
# sentence: distant or unrelated negation ("no later than 30 days ... duly
# stamped paper", a negated previous sentence) never hides a valid mention.
_NEGATION_CUES = ("not", "no", "never", "without", "neither", "nor", "exempt")
# Extended cue set used by the risk-rule trigger guard (rules.py): in addition
# to the stamp/TDS cue list it covers scoping words that narrow a claim
# ("except", "excludes"). Multi-word negators ("shall not", "does not") are
# handled by the "not" cue — the auxiliary verbs themselves are NOT negation
# cues, so "shall indemnify" is not negated.
RISK_NEGATION_CUES = _NEGATION_CUES + (
    "exclude", "excludes", "except", "excepted",
)
_NEGATION_WINDOW_TOKENS = 6


def is_negated_mention(lowered: str, start: int, cues: tuple[str, ...] = _NEGATION_CUES) -> bool:
    """True when a negation cue appears within a few tokens before ``start``,
    inside the same sentence (sentence punctuation and newlines bound the
    window; commas do not, so "..., without deduction of tax at source, ..."
    is still negated). ``cues`` extends the cue vocabulary; the stamp/TDS
    detectors pass the tight default list, the risk-rule trigger guard passes
    ``RISK_NEGATION_CUES``."""
    prefix = lowered[:start]
    boundary = max(
        prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"),
        prefix.rfind(";"), prefix.rfind("\n"),
    )
    window = prefix[boundary + 1:] if boundary != -1 else prefix
    tokens = [t.strip("(),:\"'") for t in window.split()]
    tail = [t for t in tokens if t]
    return any(tok in cues for tok in tail[-_NEGATION_WINDOW_TOKENS:])


def _is_negated_mention(lowered: str, start: int) -> bool:
    return is_negated_mention(lowered, start)


# Stamp-duty wording beyond the plain keyword list: "duly stamped paper",
# "non-judicial stamp paper", "stamping of this Agreement". Deliberately tight:
# unrelated senses ("rubber-stamped", "postage stamp", "timestamp") must not
# count as stamp-duty language.
_STAMP_DUTY_KEYWORDS = ("stamp duty", "e-stamp", "franking", "indian stamp act")
_STAMP_DUTY_RE = re.compile(
    r"\b(?:"
    r"(?:duly|non-judicial|properly|sufficiently|adequately|appropriately)\s+stamped"
    r"|stamped\s+(?:paper|papers|certificate|document|instrument|agreement|copy|copies)"
    r"|stamp\s+papers?"
    r"|stamping\s+of\s+(?:this|the|such)"
    r")",
    re.IGNORECASE,
)

# TDS wording: the statutory phrase has several surface forms. A bare "tax" or
# "deduction" never counts; a match always needs the at-source construction
# (or the "tds" abbreviation / section reference).
_TDS_RE = re.compile(
    r"\b(?:"
    r"tax\s+deduct(?:ed|ion)\s+at\s+source"
    r"|deduct(?:ed|ing|ion)?\s+(?:of\s+)?tax\s+at\s+source"
    r"|deduct(?:ed|ing)?\s+at\s+source"
    r"|tds"
    r"|section\s+19[45]"
    r")\b",
    re.IGNORECASE,
)


def detect_stamp_duty_mention(text: str) -> bool:
    lowered = clean_text(text).lower()
    for kw in _STAMP_DUTY_KEYWORDS:
        for m in re.finditer(re.escape(kw), lowered):
            if not _is_negated_mention(lowered, m.start()):
                return True
    return any(
        not _is_negated_mention(lowered, m.start())
        for m in _STAMP_DUTY_RE.finditer(lowered)
    )


def detect_tds_mention(text: str) -> bool:
    lowered = clean_text(text).lower()
    return any(
        not _is_negated_mention(lowered, m.start())
        for m in _TDS_RE.finditer(lowered)
    )


def detect_gstin_mention(text: str) -> bool:
    return bool(GSTIN_RE.search(clean_text(text)))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _scan_locations(text: str) -> List[Entity]:
    """Match city/state/seat names, preferring longer names over substrings."""
    lowered = text.lower()
    groups = (
        ("JURISDICTION_CITY", INDIAN_CITIES, 0.9),
        ("INDIAN_STATE", INDIAN_STATES, 0.9),
        ("ARBITRATION_SEAT_INDIA", INDIAN_SEATS, 0.85),
        ("ARBITRATION_SEAT_FOREIGN", FOREIGN_SEATS, 0.85),
    )
    entities: List[Entity] = []
    for label, names, confidence in groups:
        taken: List[tuple[int, int]] = []
        for name in sorted(names, key=len, reverse=True):
            for m in re.finditer(rf"\b{re.escape(name)}\b", lowered):
                if any(m.start() < end and m.end() > start for start, end in taken):
                    continue
                if len(taken) >= 25:
                    break
                taken.append((m.start(), m.end()))
                entities.append(
                    Entity(
                        text=text[m.start() : m.end()],
                        label=label,
                        start_char=m.start(),
                        end_char=m.end(),
                        confidence=confidence,
                        source="regex",
                    )
                )
    return entities


def _scan_regex(pattern: re.Pattern, text: str, label: str, confidence: float) -> List[Entity]:
    matches: List[Entity] = []
    for m in pattern.finditer(text):
        matches.append(
            Entity(
                text=m.group(0),
                label=label,
                start_char=m.start(),
                end_char=m.end(),
                confidence=confidence,
                source="regex",
            )
        )
    return matches


def _scan_durations(
    text: str,
    *,
    notice_spans: List[tuple[int, int]] | None = None,
) -> List[Entity]:
    """Emit bare durations ("90 days") as ``DURATION`` entities.

    Spans already claimed by a NOTICE_PERIOD match are skipped so "within
    30 days" is labelled exactly once, as a notice period.
    """
    claimed = list(notice_spans or [])
    matches: List[Entity] = []
    for m in DURATION_RE.finditer(text):
        if any(start < m.end() and m.start() < end for start, end in claimed):
            continue
        matches.append(
            Entity(
                text=m.group(0),
                label="DURATION",
                start_char=m.start(),
                end_char=m.end(),
                confidence=0.85,
                source="regex",
            )
        )
    return matches
