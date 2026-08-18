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

CIN_RE = re.compile(r"\bU[A-Z]{5}\d{2}[A-Z]{3}\d{6}\b")
LLPIN_RE = re.compile(r"\b[A-Z]{2}-\d{4}-\d{4}-\d{4}-\d{4}\b")  # LLP IN
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z0-9]\b")
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
NOTICE_PERIOD_RE = re.compile(
    r"\b(?:within|no later than|at least|prior to|after)?\s*(\d+)\s+"
    r"(day|days|week|weeks|month|months|year|years|business day[s]?)\b",
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
    source = clause_text or text
    cleaned = clean_text(source or "")
    entities: List[Entity] = []

    # Indian identifiers
    entities.extend(_scan_regex(CIN_RE, cleaned, "CIN", 0.99))
    entities.extend(_scan_regex(LLPIN_RE, cleaned, "LLPIN", 0.95))
    entities.extend(_scan_regex(PAN_RE, cleaned, "PAN", 0.99))
    entities.extend(_scan_regex(GSTIN_RE, cleaned, "GSTIN", 0.99))
    entities.extend(_scan_regex(TAN_RE, cleaned, "TAN", 0.95))

    # Money
    entities.extend(_scan_regex(INR_RE, cleaned, "PAYMENT_AMOUNT", 0.95))
    entities.extend(_scan_regex(USD_RE, cleaned, "PAYMENT_AMOUNT", 0.95))
    entities.extend(_scan_regex(EUR_RE, cleaned, "PAYMENT_AMOUNT", 0.95))
    entities.extend(_scan_regex(GBP_RE, cleaned, "PAYMENT_AMOUNT", 0.95))

    # Dates
    for regex in DATE_RES:
        entities.extend(_scan_regex(regex, cleaned, "DATE", 0.95))

    # Notice / term durations
    entities.extend(_scan_regex(NOTICE_PERIOD_RE, cleaned, "NOTICE_PERIOD", 0.9))
    entities.extend(_scan_regex(TERM_DURATION_RE, cleaned, "TERM_DURATION", 0.9))
    entities.extend(_scan_regex(CURE_PERIOD_RE, cleaned, "CURE_PERIOD", 0.9))

    # Locations (jurisdictions / cities / seats)
    lowered = cleaned.lower()
    for city in INDIAN_CITIES:
        for m in re.finditer(rf"\b{re.escape(city)}\b", lowered):
            entities.append(
                Entity(
                    text=cleaned[m.start():m.end()],
                    label="JURISDICTION_CITY",
                    start_char=m.start(),
                    end_char=m.end(),
                    confidence=0.9,
                    source="regex",
                )
            )
            break  # one per city per chunk
    for state in INDIAN_STATES:
        for m in re.finditer(rf"\b{re.escape(state)}\b", lowered):
            entities.append(
                Entity(
                    text=cleaned[m.start():m.end()],
                    label="INDIAN_STATE",
                    start_char=m.start(),
                    end_char=m.end(),
                    confidence=0.9,
                    source="regex",
                )
            )
            break
    for seat in INDIAN_SEATS:
        for m in re.finditer(rf"\b{re.escape(seat)}\b", lowered):
            entities.append(
                Entity(
                    text=cleaned[m.start():m.end()],
                    label="ARBITRATION_SEAT_INDIA",
                    start_char=m.start(),
                    end_char=m.end(),
                    confidence=0.85,
                    source="regex",
                )
            )
            break
    for seat in FOREIGN_SEATS:
        for m in re.finditer(rf"\b{re.escape(seat)}\b", lowered):
            entities.append(
                Entity(
                    text=cleaned[m.start():m.end()],
                    label="ARBITRATION_SEAT_FOREIGN",
                    start_char=m.start(),
                    end_char=m.end(),
                    confidence=0.85,
                    source="regex",
                )
            )
            break

    # DeBERTa NER enrichment (optional)
    try:
        from nlp.ner.ner_ml import enrich_entities_with_deberta

        enriched = enrich_entities_with_deberta(cleaned, existing=entities)
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
    """
    cleaned = clean_text(text)
    lowered = cleaned.lower()

    # 1. Explicit phrase
    explicit = re.search(
        r"seat\s+of\s+arbitration\s+(?:shall\s+be|is|means)\s+([A-Za-z][A-Za-z\s,]{2,60})",
        lowered,
    )
    if explicit:
        value = explicit.group(1).strip().rstrip(",.").title()
        if value.lower() not in {"india", "indian"}:
            return value

    # 2. Walk arbitration-context sentences and prefer specific cities
    for sent in re.split(r"(?<=[.!?])\s+", cleaned):
        ls = sent.lower()
        if "arbitration" not in ls and "seat" not in ls and "venue" not in ls:
            continue
        for seat in FOREIGN_SEATS:
            if seat in ls:
                return seat.title()
        for seat in INDIAN_SEATS - {"india"}:
            if seat in ls:
                return seat.title()

    # 3. Anywhere — first foreign seat, then specific Indian city.
    for seat in FOREIGN_SEATS:
        if seat in lowered:
            return seat.title()
    for seat in INDIAN_SEATS - {"india"}:
        if seat in lowered:
            return seat.title()

    # 4. Last resort — return "India" only as generic jurisdiction.
    if "india" in lowered or "indian" in lowered:
        return "India"
    return None


def detect_governing_law(text: str) -> Optional[str]:
    """Return the governing law phrase if found."""
    cleaned = clean_text(text)
    lowered = cleaned.lower()
    patterns = [
        r"governed by the laws of[^.]{0,80}",
        r"governing law[^\.]{0,80}laws of[^.]{0,80}",
        r"subject to the laws of[^.]{0,80}",
        r"laws of the state of[^.]{0,80}",
        r"laws of india",
    ]
    for pat in patterns:
        m = re.search(pat, lowered)
        if m:
            phrase = m.group(0).strip().rstrip(".,")
            return phrase[:160]
    return None


def detect_stamp_duty_mention(text: str) -> bool:
    lowered = clean_text(text).lower()
    return any(kw in lowered for kw in ("stamp duty", "e-stamp", "franking", "indian stamp act"))


def detect_tds_mention(text: str) -> bool:
    lowered = clean_text(text).lower()
    return any(kw in lowered for kw in ("tax deducted at source", "tds", "section 194", "section 195"))


def detect_gstin_mention(text: str) -> bool:
    return bool(GSTIN_RE.search(clean_text(text)))


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


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
