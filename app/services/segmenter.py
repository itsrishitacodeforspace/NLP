"""Clause segmentation: split a contract into individual clauses.

Two stages:
  1. Rule-based heading detection (section numbers, capitalised headings)
  2. Sub-paragraph re-segmentation when a 'clause' is still too long.

The output is a list of `Clause` objects with char offsets relative to the
full cleaned text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.logging import get_logger
from app.utils.text import (
    clean_text,
    detect_section_number,
    split_into_paragraphs,
)

logger = get_logger()


@dataclass
class Clause:
    """A logical clause extracted from a contract."""

    clause_id: str
    section_number: Optional[str]
    heading: Optional[str]
    text: str
    char_start: int
    char_end: int
    page_hint: Optional[int] = None
    tokens_estimate: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def length(self) -> int:
        return self.char_end - self.char_start


# A clause is considered "long" beyond this char count and will be split further.
LONG_CLAUSE_CHARS = 2500


def segment_clauses(
    text: str,
    *,
    contract_id: str,
    long_threshold: int = LONG_CLAUSE_CHARS,
) -> List[Clause]:
    """Split the full contract text into a list of Clauses.

    Strategy:
      * Group paragraphs into clauses based on numbered/heading lines.
      * If a clause exceeds long_threshold, fall back to per-paragraph chunks.
    """
    if not text:
        return []

    cleaned = clean_text(text)
    if not cleaned:
        return []

    paragraphs = split_into_paragraphs(cleaned)
    if not paragraphs:
        return []

    raw_blocks = _group_paragraphs_into_clauses(paragraphs)

    clauses: List[Clause] = []
    cursor = 0
    for idx, (heading, section_num, body) in enumerate(raw_blocks, start=1):
        full_text = body if not heading else f"{heading}\n\n{body}"
        # Find char offsets relative to the entire cleaned text.
        start = cleaned.find(full_text[:120], cursor)
        if start == -1:
            start = cursor
        end = start + len(full_text)
        cursor = end

        if len(full_text) > long_threshold:
            # Split long clause into multiple sub-clauses.
            sub_clauses = _split_long_clause(
                body,
                base_id=f"{contract_id}_c{idx:03d}",
                section_number=section_num,
                heading=heading,
                char_start=start,
                long_threshold=long_threshold,
            )
            for sc in sub_clauses:
                sc.metadata.setdefault("parent_index", idx)
            clauses.extend(sub_clauses)
        else:
            clauses.append(
                Clause(
                    clause_id=f"{contract_id}_c{idx:03d}",
                    section_number=section_num,
                    heading=heading,
                    text=full_text.strip(),
                    char_start=start,
                    char_end=start + len(full_text.strip()),
                    tokens_estimate=_estimate_tokens(full_text),
                )
            )

    logger.info("Segmented {} clauses (long_threshold={})", len(clauses), long_threshold)
    return clauses


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _group_paragraphs_into_clauses(paragraphs: List[str]) -> List[tuple[Optional[str], Optional[str], str]]:
    """Group paragraphs into (heading, section_number, body) tuples.

    Algorithm:
      1. Normalise: split any paragraph that starts with a heading line and
         has a body on subsequent lines.
      2. Walk through the items. Each time we see a strong-heading line
         (starts with a section number OR is an ALL-CAPS legal title),
         flush the current buffer as one (heading, body) pair.
      3. The first item is special: even if it doesn't match a heading
         pattern, we treat it as the preamble's heading so all the
         metadata that follows it stays attached as the preamble body.
    """
    grouped: List[tuple[Optional[str], Optional[str], str]] = []
    buffer: List[str] = []

    def _trim_heading(h: str) -> Optional[str]:
        if not h:
            return None
        first_line = h.split("\n", 1)[0].strip()
        if not first_line:
            return None
        if len(first_line) > 200:
            return None
        return first_line

    def flush():
        if not buffer:
            return
        heading_raw = buffer[0]
        heading = _trim_heading(heading_raw)
        body = "\n\n".join(buffer[1:]) if len(buffer) > 1 else ""
        section_num = (
            detect_section_number(heading.split("\n", 1)[0]) if heading else None
        )
        grouped.append((heading, section_num, body))
        buffer.clear()

    # Normalise: a heading + body joined by a single newline should be split.
    normalised: List[str] = []
    for p in paragraphs:
        lines = p.split("\n")
        first = lines[0].strip()
        rest = "\n".join(lines[1:]).strip()
        if _looks_like_heading_line(first) and rest:
            normalised.append(first)
            normalised.append(rest)
        else:
            normalised.append(p)

    for idx, para in enumerate(normalised):
        first_line = para.split("\n", 1)[0].strip()
        # Strong heading: section-number prefix OR ALL-CAPS legal title.
        is_strong_heading = bool(detect_section_number(first_line)) or (
            first_line == first_line.upper()
            and len(first_line) <= 100
            and any(c.isalpha() for c in first_line)
            and any(
                kw in first_line.lower()
                for kw in (
                    "agreement",
                    "terms",
                    "conditions",
                    "section",
                    "article",
                    "clause",
                    "schedule",
                    "annexure",
                    "chapter",
                )
            )
        )
        if idx == 0 and not buffer:
            # Force-start the first group with whatever we see.
            buffer.append(para)
        elif is_strong_heading:
            flush()
            buffer.append(para)
        else:
            buffer.append(para)
    flush()

    if not grouped:
        grouped = [(None, None, p) for p in paragraphs]

    return grouped


def _looks_like_heading_line(line: str) -> bool:
    """Return True if a single line looks like a clause heading.

    Heuristic is intentionally strict to avoid false positives on body text.
    A line qualifies only if it has either a section number or it is short,
    ALL-CAPS and has no terminal punctuation.
    """
    if not line:
        return False
    if len(line) > 120:
        return False
    # Section number ("1.", "1.1", "(a)", "Article 5", etc.)
    if detect_section_number(line):
        return True
    stripped = line.strip()
    # Strip out parenthetical / quoted segments before checking case so
    # 'RESIDENT ACCOMMODATION SERVICE AGREEMENT ("Agreement")' is treated as
    # an all-caps heading.
    cleaned = re.sub(r"\([^)]*\)", "", stripped)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)
    cleaned = re.sub(r"'[^']*'", "", cleaned).strip()
    has_alpha = any(c.isalpha() for c in cleaned)
    if (
        has_alpha
        and cleaned == cleaned.upper()
        and len(stripped) <= 120
        and not stripped.endswith(".")
        and not stripped.endswith(",")
    ):
        return True
    # Keyword hint — only if the line is very short (<= 60 chars) and is title-cased.
    if (
        len(stripped) <= 60
        and not stripped.endswith(".")
        and not stripped.endswith(",")
        and not any(c.isdigit() for c in stripped)
        and stripped == stripped.title()
        and any(t in stripped.lower() for t in _HEADING_HINTS)
    ):
        return True
    return False


_HEADING_HINTS = (
    "indemnif",
    "liability",
    "termination",
    "payment",
    "confidential",
    "data protection",
    "intellectual property",
    "non-compete",
    "non-solicit",
    "governing law",
    "dispute",
    "force majeure",
    "assignment",
    "audit",
    "insurance",
    "compliance",
    "service level",
    "sla",
    "change control",
    "notice",
    "acceptance",
    "definitions",
    "miscellaneous",
    "term",
    "renewal",
    "warranty",
    "obligation",
    "stamp duty",
    "arbitration",
    "jurisdiction",
    "venue",
    "severability",
)


def _split_long_clause(
    body: str,
    *,
    base_id: str,
    section_number: Optional[str],
    heading: Optional[str],
    char_start: int,
    long_threshold: int = LONG_CLAUSE_CHARS,
) -> List[Clause]:
    """Split a clause body into smaller pieces at paragraph or sentence
    boundaries.

    Three-stage strategy:
      1. Group paragraphs into chunks <= long_threshold.
      2. If a single paragraph is still larger than the threshold, split it
         by sentence boundaries (`.!?`).
      3. As a last resort, perform a fixed-character split.
    """
    paragraphs = split_into_paragraphs(body)
    clauses: List[Clause] = []
    buffer: List[str] = []
    buffer_len = 0
    sub_idx = 1

    def flush():
        nonlocal sub_idx, buffer_len
        if not buffer:
            return
        joined = "\n\n".join(buffer).strip()
        clause_id = f"{base_id}_s{sub_idx:02d}"
        prior_len = sum(len(c.text) + 2 for c in clauses)
        local_start = char_start + prior_len
        clauses.append(
            Clause(
                clause_id=clause_id,
                section_number=section_number,
                heading=heading,
                text=joined,
                char_start=local_start,
                char_end=local_start + len(joined),
                tokens_estimate=_estimate_tokens(joined),
                metadata={"split": True, "sub_index": sub_idx},
            )
        )
        sub_idx += 1
        buffer.clear()
        buffer_len = 0

    def _split_oversized_paragraph(p: str) -> List[str]:
        """Split a single oversized paragraph into sentence-sized chunks."""
        if len(p) <= long_threshold:
            return [p]
        # Stage 2: sentence split
        sentence_chunks = [s for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]
        # Stage 3: fixed-char split if a sentence alone exceeds threshold
        out: List[str] = []
        for s in sentence_chunks:
            if len(s) <= long_threshold:
                out.append(s)
                continue
            for i in range(0, len(s), long_threshold):
                out.append(s[i : i + long_threshold])
        return out or [p]

    expanded: List[str] = []
    for p in paragraphs:
        if len(p) > long_threshold:
            expanded.extend(_split_oversized_paragraph(p))
        else:
            expanded.append(p)

    for p in expanded:
        if buffer_len + len(p) > long_threshold and buffer:
            flush()
        buffer.append(p)
        buffer_len += len(p)
    flush()
    return clauses


_TOKEN_RE = re.compile(r"\S+")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (avg 4 chars per token for English)."""
    return max(1, len(text) // 4)
