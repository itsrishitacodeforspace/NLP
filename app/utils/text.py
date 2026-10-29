"""Text cleaning and normalisation utilities used across the pipeline."""
from __future__ import annotations

import re
import unicodedata
from typing import List

# Whitespace normalisation regexes
_WS_RE = re.compile(r"[ \t\f\v]+")
_NL_RE = re.compile(r"\n{3,}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# Smart quote mapping (preserve readability while keeping tokens stable)
_SMART_QUOTE_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-",
    "\u2026": "...",
})

# Common Indian legal abbreviations and their expansions (used in token-pass hint).
INDIAN_LEGAL_TERMS = {
    "MSA": "Master Services Agreement",
    "NDA": "Non-Disclosure Agreement",
    "SPA": "Share Purchase Agreement",
    "SHA": "Shareholders Agreement",
    "CIN": "Corporate Identity Number",
    "PAN": "Permanent Account Number",
    "GSTIN": "Goods and Services Tax Identification Number",
    "TDS": "Tax Deducted at Source",
    "FY": "Financial Year",
    "INR": "Indian Rupee",
}


# Written cardinal numbers for parsing notice/deadline periods ("sixty days").
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
_TENS = {20, 30, 40, 50, 60, 70, 80, 90}

# Regex alternation that matches a digit run or a (possibly hyphenated) written
# number such as "sixty" or "twenty-four". Longer words first so "sixty" wins
# over "six". Callers wrap this in a capturing group.
_WORD_ALT = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
NUMBER_TOKEN_RE = r"(?:\d+|(?:" + _WORD_ALT + r")(?:-(?:" + _WORD_ALT + r"))?)"


def written_number_to_int(token: str) -> int | None:
    """Convert a digit run or written cardinal ('sixty', 'twenty-four') to an int."""
    if not token:
        return None
    value = token.strip().lower()
    if value.isdigit():
        return int(value)
    if "-" in value:
        tens, _, units = value.partition("-")
        if NUMBER_WORDS.get(tens) in _TENS and units in NUMBER_WORDS and NUMBER_WORDS[units] < 10:
            return NUMBER_WORDS[tens] + NUMBER_WORDS[units]
    return NUMBER_WORDS.get(value)


def normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace and trim each line, while preserving
    paragraph breaks (consecutive blank lines)."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    cleaned_lines: list[str] = []
    blanks = 0
    for line in text.split("\n"):
        normalised = _WS_RE.sub(" ", line).strip()
        if not normalised:
            blanks += 1
            continue
        if blanks > 0 and cleaned_lines:
            # separator — keep as a single blank line between paragraphs.
            cleaned_lines.append("")
        cleaned_lines.append(normalised)
        blanks = 0
    return _NL_RE.sub("\n\n", "\n".join(cleaned_lines)).strip()


def normalise_unicode(text: str) -> str:
    """Normalise smart quotes, dashes, ellipsis to ASCII equivalents."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    return text.translate(_SMART_QUOTE_MAP)


def clean_text(text: str) -> str:
    """Full cleaning pipeline: unicode -> whitespace."""
    if not text:
        return ""
    return normalise_whitespace(normalise_unicode(text))


_SECTION_HEADING_RE = re.compile(
    r"""^(?:[#]+\s*)?(?P<num>
        (?:\d+(?:\.\d+)*)            # 1, 1.1, 1.1.1
        |(?:[A-Z]\.)                 # A.
        |(?:\([a-z0-9]+\))           # (a), (1)
        |(?:Article\s+\d+)           # Article 5
        |(?:Section\s+[IVXLC]+)      # Section IV
    )[\.\):]?\s+(?P<heading>.+)$""",
    re.VERBOSE | re.IGNORECASE,
)


def looks_like_section_heading(line: str) -> bool:
    """Heuristic check: does this line look like a clause heading?"""
    if not line:
        return False
    if len(line) > 180:
        return False
    return bool(_SECTION_HEADING_RE.match(line.strip()))


def detect_section_number(line: str) -> str | None:
    """Extract the section number if present, else None."""
    if not line:
        return None
    match = _SECTION_HEADING_RE.match(line.strip())
    return match.group("num") if match else None


def split_into_paragraphs(text: str) -> List[str]:
    """Split cleaned text into non-empty paragraphs."""
    if not text:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
