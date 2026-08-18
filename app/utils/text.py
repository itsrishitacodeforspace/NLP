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


def normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace and trim each line, while preserving
    paragraph breaks (consecutive blank lines)."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_RE.sub("", text)
    cleaned_lines: list[str] = []
    blank_groups: list[int] = []  # how many consecutive blanks at each position
    run: list[str] = []
    blanks = 0
    for line in text.split("\n"):
        normalised = _WS_RE.sub(" ", line).strip()
        if not normalised:
            blanks += 1
            continue
        if blanks > 0 and run:
            # separator — keep as a single blank line between paragraphs.
            cleaned_lines.append("")
        run.append(normalised)
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
    r"""^(?P<num>
        (?:\d+(?:\.\d+)*)            # 1, 1.1, 1.1.1
        |(?:[A-Z]\.)                 # A.
        |(?:\([a-z0-9]+\))           # (a), (1)
        |(?:Article\s+\d+)           # Article 5
    )[\.\):]?\s+(?P<heading>.+)$""",
    re.VERBOSE,
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
