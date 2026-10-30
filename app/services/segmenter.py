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
      * Group paragraph *spans* into clauses based on numbered/heading lines.
      * If a clause exceeds long_threshold, fall back to per-paragraph chunks.

    Source-integrity contract: every emitted ``Clause.text`` is the exact
    source slice ``cleaned[char_start:char_end]`` — offsets are never
    reconstructed from assumed separators or synthetic newlines, and no source
    content is dropped between the spans.
    """
    if not text:
        return []

    cleaned = clean_text(text)
    if not cleaned:
        return []

    paragraph_spans = _paragraph_spans(cleaned)
    if not paragraph_spans:
        return []

    items = _normalise_items(paragraph_spans)
    raw_blocks = _group_paragraphs_into_clauses(items)

    clauses: List[Clause] = []
    for idx, (heading, section_num, span_start, span_end, body_start) in enumerate(raw_blocks, start=1):
        if span_end - span_start > long_threshold:
            # Split long clause into multiple sub-clauses with exact spans.
            sub_clauses = _split_long_clause(
                cleaned,
                body_start=body_start,
                body_end=span_end,
                base_id=f"{contract_id}_c{idx:03d}",
                section_number=section_num,
                heading=heading,
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
                    text=cleaned[span_start:span_end],
                    char_start=span_start,
                    char_end=span_end,
                    tokens_estimate=_estimate_tokens(cleaned[span_start:span_end]),
                )
            )

    logger.info("Segmented {} clauses (long_threshold={})", len(clauses), long_threshold)
    return clauses


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


_PARA_SEP_RE = re.compile(r"\n\s*\n")


def _paragraph_spans(cleaned: str) -> List[tuple[int, int, str]]:
    """Split cleaned text into (start, end, text) paragraph spans.

    Offsets are document-relative; each span is trimmed of surrounding
    whitespace so ``text == cleaned[start:end]`` always holds exactly.
    """
    spans: List[tuple[int, int, str]] = []
    start = 0
    for m in _PARA_SEP_RE.finditer(cleaned):
        _append_trimmed_span(cleaned, spans, start, m.start())
        start = m.end()
    _append_trimmed_span(cleaned, spans, start, len(cleaned))
    return spans


def _append_trimmed_span(cleaned: str, spans: List[tuple[int, int, str]], start: int, end: int) -> None:
    while start < end and cleaned[start].isspace():
        start += 1
    while end > start and cleaned[end - 1].isspace():
        end -= 1
    if start < end:
        spans.append((start, end, cleaned[start:end]))


def _normalise_items(spans: List[tuple[int, int, str]]) -> List[tuple[int, int, str]]:
    """Split a paragraph whose first line is a heading (with body on the next
    lines) into two exact span items: the heading line and the remainder."""
    items: List[tuple[int, int, str]] = []
    for start, end, text in spans:
        first, sep, rest = text.partition("\n")
        first_stripped = first.strip()
        rest_stripped = rest.strip()
        if sep and rest_stripped and _looks_like_heading_line(first_stripped):
            h_lead = len(first) - len(first.lstrip())
            h_start = start + h_lead
            items.append((h_start, h_start + len(first_stripped), first_stripped))
            r_offset = len(first) + 1  # past the single "\n"
            r_lead = len(rest) - len(rest.lstrip())
            r_start = start + r_offset + r_lead
            r_end = start + r_offset + len(rest.rstrip())
            items.append((r_start, r_end, rest_stripped))
        else:
            items.append((start, end, text))
    return items


def _group_paragraphs_into_clauses(
    items: List[tuple[int, int, str]],
) -> List[tuple[Optional[str], Optional[str], int, int, int]]:
    """Group span items into (heading, section_number, span_start, span_end,
    body_start) tuples.

    Algorithm (unchanged semantics, span-based representation):
      1. Walk through the items. Each time we see a strong-heading line
         (starts with a section number OR is an ALL-CAPS legal title),
         flush the current buffer as one group.
      2. The first item is special: even if it doesn't match a heading
         pattern, its first line is treated as the preamble's heading so all
         the metadata that follows it stays attached as the preamble body.
      3. A group spans from its first item's start to its last item's end, so
         the clause text is an exact source slice and no line is ever dropped
         (a multi-line preamble keeps every line).
    """
    grouped: List[tuple[Optional[str], Optional[str], int, int, int]] = []
    buffer: List[tuple[int, int, str]] = []

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
        first = buffer[0]
        heading = _trim_heading(first[2])
        span_start, span_end = first[0], buffer[-1][1]
        if heading is None:
            # No trimmable heading (e.g. >200-char first line): the whole
            # group is body — previously such lines were silently dropped.
            body_start = span_start
        elif first[2] == heading:
            # First item is exactly the heading line (heading-normalised or
            # single-line): body starts at the next item, if any.
            body_start = buffer[1][0] if len(buffer) > 1 else span_end
        else:
            # Multi-line first item: heading is its first line; the remaining
            # lines are the start of the body (kept, never discarded).
            nl = first[2].find("\n")
            body_start = first[0] + nl + 1 if nl != -1 else span_end
        section_num = detect_section_number(heading) if heading else None
        grouped.append((heading, section_num, span_start, span_end, body_start))
        buffer.clear()

    for idx, (start, end, text) in enumerate(items):
        first_line = text.split("\n", 1)[0].strip()
        # Strong heading only — not every numbered body paragraph.
        is_strong_heading = _looks_like_heading_line(first_line)
        if idx == 0 and not buffer:
            # Force-start the first group with whatever we see.
            buffer.append((start, end, text))
        elif is_strong_heading:
            flush()
            buffer.append((start, end, text))
        else:
            buffer.append((start, end, text))
    flush()

    if not grouped:
        grouped = [(None, None, s, e, s) for s, e, _t in items]

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
    # Section number ("1.", "1.1", "(a)", "Article 5", etc.). Numbered body
    # sentences also match this regex, so reject terminal punctuation and
    # long lines; those are clause text, not headings.
    if detect_section_number(line):
        stripped = line.strip()
        if stripped.endswith((".", ",", ";", ":")):
            return False
        return len(stripped.split()) <= 12
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
    cleaned: str,
    *,
    body_start: int,
    body_end: int,
    base_id: str,
    section_number: Optional[str],
    heading: Optional[str],
    long_threshold: int = LONG_CLAUSE_CHARS,
) -> List[Clause]:
    """Split a clause body span into smaller pieces at paragraph or sentence
    boundaries.

    Every sub-clause's ``text`` is the exact source slice
    ``cleaned[char_start:char_end]`` — offsets are document-relative and never
    reconstructed from assumed separators.

    Three-stage strategy:
      1. Group paragraphs into chunks <= long_threshold.
      2. If a single paragraph is still larger than the threshold, split it
         by sentence boundaries (`.!?`).
      3. As a last resort, perform a fixed-character split.
    """
    body_spans = [
        (s + body_start, e + body_start, t)
        for s, e, t in _paragraph_spans(cleaned[body_start:body_end])
    ]
    clauses: List[Clause] = []
    buffer: List[tuple[int, int]] = []
    buffer_len = 0
    sub_idx = 1

    def flush():
        nonlocal sub_idx, buffer_len
        if not buffer:
            return
        start, end = buffer[0][0], buffer[-1][1]
        text_slice = cleaned[start:end]
        clause_id = f"{base_id}_s{sub_idx:02d}"
        clauses.append(
            Clause(
                clause_id=clause_id,
                section_number=section_number,
                heading=heading,
                text=text_slice,
                char_start=start,
                char_end=end,
                tokens_estimate=_estimate_tokens(text_slice),
                metadata={"split": True, "sub_index": sub_idx},
            )
        )
        sub_idx += 1
        buffer.clear()
        buffer_len = 0

    def _split_oversized_span(start: int, end: int) -> List[tuple[int, int]]:
        """Split one oversized paragraph span into exact sub-spans."""
        if end - start <= long_threshold:
            return [(start, end)]
        text_span = cleaned[start:end]
        # Stage 2: sentence split (span-aware; separators excluded).
        spans: List[tuple[int, int]] = []
        s_start = start
        for m in re.finditer(r"(?<=[.!?])\s+", text_span):
            spans.append((s_start, start + m.start()))
            s_start = start + m.end()
        spans.append((s_start, end))
        spans = [(s, e) for s, e in spans if e > s]
        # Stage 3: fixed-char split if a sentence alone exceeds the threshold.
        out: List[tuple[int, int]] = []
        for s, e in spans:
            if e - s <= long_threshold:
                out.append((s, e))
                continue
            i = s
            while i < e:
                out.append((i, min(i + long_threshold, e)))
                i += long_threshold
        return out or [(start, end)]

    expanded: List[tuple[int, int]] = []
    for s, e, _t in body_spans:
        if e - s > long_threshold:
            expanded.extend(_split_oversized_span(s, e))
        else:
            expanded.append((s, e))

    for s, e in expanded:
        piece_len = e - s
        if buffer and buffer_len + piece_len > long_threshold:
            flush()
        buffer.append((s, e))
        buffer_len += piece_len
    flush()
    return clauses


_TOKEN_RE = re.compile(r"\S+")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (avg 4 chars per token for English)."""
    return max(1, len(text) // 4)
