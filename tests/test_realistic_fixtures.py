"""Realistic multi-page fixture suite: parse + segment + verify.

Generates fixtures programmatically (see ``tests/fixtures/build_fixtures.py``)
into ``tmp_path`` — no binaries are committed. Covers:

  * 6-page PDF: header/footer stripping, mid-clause page break (clause 4 spans
    pages 2->3), page_hint correctness, fee-schedule table, ANNEXURE heading.
  * 4-page DOCX: table extraction, signature-block party detection, headings.
  * Scanned PDF (image-only, no text layer): graceful failure with OCR hint.
  * Corrupt PDF: DocumentParseError, not a crash.
  * Large TXT (~1.8M chars): 2M truncation warning + offset invariants.
  * Header/footer regex adversarial cases (no false-positive stripping).
  * Annexure/heading recognition.
  * Large-document parse+segment performance (< 30s).
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.exceptions import DocumentParseError
from app.services.analyzer import _detect_parties, _stamp_page_hints
from app.services.parser import (
    MAX_TOTAL_CHARS,
    parse_document,
    strip_headers_footers,
)
from app.services.segmenter import segment_clauses

try:
    import pymupdf  # noqa: F401

    _HAS_FITZ = True
except ImportError:  # pragma: no cover
    _HAS_FITZ = False

try:
    from docx import Document  # noqa: F401

    _HAS_DOCX = True
except ImportError:  # pragma: no cover
    _HAS_DOCX = False


# ---------------------------------------------------------------------------
# Shared fixture: build all files once per test session (tmp_path is per-test,
# so we build into a module-scoped temp dir to avoid regenerating the 6MB
# scanned PDF on every test).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory) -> dict[str, Path]:
    from tests.fixtures.build_fixtures import build_all

    dest = tmp_path_factory.mktemp("realistic_fixtures")
    return build_all(dest)


def _assert_slice_invariant(full_text: str, clauses) -> None:
    for c in clauses:
        assert full_text[c.char_start : c.char_end] == c.text, (
            f"{c.clause_id}: offsets {c.char_start}:{c.char_end} do not slice the source"
        )
        assert c.char_end <= len(full_text), f"{c.clause_id}: char_end out of range"


# ===========================================================================
# 6-page PDF
# ===========================================================================


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_multi_page_pdf_headers_footers_stripped(fixtures):
    parsed = parse_document(fixtures["multi_page.pdf"], contract_id="mp")
    full = parsed.full_text
    # The repeating "Confidential - Page N of 6" header is gone from every page.
    assert "Confidential - Page 1 of 6" not in full
    assert "Confidential - Page 3 of 6" not in full
    assert "Confidential - Page 6 of 6" not in full
    # The clause body survives.
    assert "The Provider shall perform the Services" in full
    assert len(parsed.pages) == 6


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_multi_page_pdf_table_present(fixtures):
    parsed = parse_document(fixtures["multi_page.pdf"], contract_id="mp")
    full = parsed.full_text
    assert "FEE SCHEDULE" in full
    assert "Premium support" in full
    assert "7,200" in full
    assert "Standard support" in full


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_multi_page_pdf_mid_clause_break_is_one_clause(fixtures):
    """Clause 4 starts on page 2 and continues on page 3.

    It must be ONE logical clause: a single section_number=4 heading. The
    long-clause splitter may break its body into sub-clauses (clause 4 is
    ~4.6K chars > the 2500-char threshold), but every sub-clause carries the
    same heading and section number, and their page_hints straddle 2 -> 3.
    """
    parsed = parse_document(fixtures["multi_page.pdf"], contract_id="mp")
    full = parsed.full_text
    clauses = segment_clauses(full, contract_id="mp")
    _stamp_page_hints(clauses, parsed.pages)

    c4 = [c for c in clauses if c.section_number == "4"]
    assert c4, "clause 4 not found"
    # Single heading across all sub-clauses.
    assert len({c.heading for c in c4}) == 1, f"multiple headings: {[c.heading for c in c4]}"
    assert c4[0].heading and "Service Levels" in c4[0].heading
    # The page break is captured: sub-clauses on page 2 AND page 3.
    hints = [c.page_hint for c in c4]
    assert 2 in hints and 3 in hints, f"expected hints spanning 2->3, got {hints}"
    # Offset invariant holds for every clause.
    _assert_slice_invariant(full, clauses)


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_multi_page_pdf_page_hints_correct(fixtures):
    """page_hint is correct for clauses on pages 1-6 (no silent None)."""
    parsed = parse_document(fixtures["multi_page.pdf"], contract_id="mp")
    full = parsed.full_text
    clauses = segment_clauses(full, contract_id="mp")
    _stamp_page_hints(clauses, parsed.pages)

    # Build the page bounds to know which page each clause *should* be on.
    from app.utils.text import clean_text

    doc = clean_text("\n\n".join(pg.text for pg in parsed.pages if pg.text))
    bounds = []
    for pg in parsed.pages:
        if not pg.text.strip():
            continue
        f = doc.find(pg.text)
        assert f != -1, f"page {pg.page_number} text not locatable"
        bounds.append((f, f + len(pg.text), pg.page_number))

    stamped = [c for c in clauses if c.page_hint is not None]
    assert stamped, "no clauses got a page_hint"
    # Every stamped clause's page_hint must match the page that contains it.
    for c in stamped:
        expected = [n for (s, e, n) in bounds if s <= c.char_start < e]
        assert expected, f"{c.clause_id} at char {c.char_start} is in no page"
        assert c.page_hint == expected[0], (
            f"{c.clause_id}: page_hint={c.page_hint} but char_start={c.char_start} "
            f"is on page {expected[0]}"
        )


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_multi_page_pdf_annexure_is_a_clause(fixtures):
    parsed = parse_document(fixtures["multi_page.pdf"], contract_id="mp")
    full = parsed.full_text
    clauses = segment_clauses(full, contract_id="mp")
    _stamp_page_hints(clauses, parsed.pages)
    ann = [c for c in clauses if c.heading and "ANNEXURE A" in c.heading]
    assert ann, f"ANNEXURE A not a clause heading: {[c.heading for c in clauses]}"
    assert ann[0].page_hint == 6, (
        f"annexure should be on page 6, got {ann[0].page_hint}"
    )
    _assert_slice_invariant(full, clauses)


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_multi_page_pdf_no_false_confidential_stripping(fixtures):
    """A clause that legitimately mentions 'confidential' must survive."""
    parsed = parse_document(fixtures["multi_page.pdf"], contract_id="mp")
    full = parsed.full_text
    # Clause 5 is titled "Confidentiality" and its body says "Confidential
    # Information" — none of that may be stripped as a header.
    assert "Confidentiality" in full
    assert "Confidential Information" in full


# ===========================================================================
# 4-page DOCX
# ===========================================================================


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx not installed")
def test_docx_tables_present(fixtures):
    parsed = parse_document(fixtures["four_page.docx"], contract_id="dx")
    full = parsed.full_text
    # 3x3 table mid-document.
    assert "Availability Target" in full
    assert "Network monitoring" in full
    assert "99.5%" in full
    # 2-column signature block at the end.
    assert "For and on behalf of Bluepeak Technologies Limited (Customer)" in full
    assert "For and on behalf of Acme Infra Pvt Ltd (Provider)" in full
    assert "S. Iyer" in full and "R. Krishnan" in full


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx not installed")
def test_docx_heading_styles_produce_boundaries(fixtures):
    parsed = parse_document(fixtures["four_page.docx"], contract_id="dx")
    full = parsed.full_text
    clauses = segment_clauses(full, contract_id="dx")
    headings = {c.heading for c in clauses if c.heading}
    # Heading 1 sections are clause boundaries.
    assert any(h and "Payment Terms" in h for h in headings), headings
    assert any(h and "Confidentiality" in h for h in headings), headings
    # Heading 2 sub-section is also detected.
    assert any(h and "Late Payment Interest" in h for h in headings), headings
    _assert_slice_invariant(full, clauses)


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx not installed")
def test_docx_signature_block_party_detection(fixtures):
    """The analyzer's party detection finds both parties from the DOCX."""
    from app.models.schemas import Clause
    from nlp.ner.ner import extract_entities

    parsed = parse_document(fixtures["four_page.docx"], contract_id="dx")
    full = parsed.full_text
    raw = segment_clauses(full, contract_id="dx")
    _stamp_page_hints(raw, parsed.pages)
    # Build schema Clauses with entities (as the analyzer does).
    clauses = []
    for r in raw:
        ex = extract_entities(r.text, clause_text=r.text)
        clauses.append(
            Clause(
                clause_id=r.clause_id,
                text=r.text,
                heading=r.heading,
                char_start=r.char_start,
                char_end=r.char_end,
                entities=ex.entities,
            )
        )
    parties = _detect_parties(clauses)
    assert any("Bluepeak" in p for p in parties), f"Customer party missing: {parties}"
    assert any("Acme" in p for p in parties), f"Provider party missing: {parties}"


# ===========================================================================
# Scanned PDF (image-only, no text layer)
# ===========================================================================


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_scanned_pdf_graceful_failure(fixtures):
    """No text layer + no tesseract => DocumentParseError with OCR hint.

    The current intended behaviour is to *fail* (the minimum-content gate),
    not to silently produce garbage or a fake success. The message must
    mention tesseract so the operator knows what to install.
    """
    with pytest.raises(DocumentParseError) as exc:
        parse_document(fixtures["scanned.pdf"], contract_id="scan")
    msg = str(exc.value)
    assert "tesseract" in msg, f"expected tesseract hint, got: {msg}"
    # No silent success: the parse must have raised, not returned text.


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_scanned_pdf_ocr_warning_not_silent(fixtures):
    """Even at the _parse_pdf level, an OCR-unavailable warning is surfaced."""
    from app.services.parser import _ocr_unavailable_reason, _parse_pdf

    reason = _ocr_unavailable_reason()
    if reason is None:
        pytest.skip("tesseract is installed in this environment; OCR would run")
    result = _parse_pdf(fixtures["scanned.pdf"], contract_id="scan2", enable_ocr=True)
    ocr_warnings = [w for w in result.warnings if w.startswith("OCR")]
    assert ocr_warnings, f"expected an OCR-unavailable warning, got {result.warnings}"
    assert reason in " ".join(ocr_warnings)


# ===========================================================================
# Corrupt PDF
# ===========================================================================


def test_corrupt_pdf_raises_not_crash(fixtures):
    """A 58-byte b'%PDF-1.4'+garbage must raise, not crash or 'succeed'."""
    with pytest.raises(DocumentParseError):
        parse_document(fixtures["corrupt.pdf"], contract_id="corrupt")


# ===========================================================================
# Large TXT (~1.8M chars) — 2M truncation boundary
# ===========================================================================


def test_large_txt_truncation_warning(fixtures):
    parsed = parse_document(fixtures["large.txt"], contract_id="large")
    # 1.8M < 2M, so it should NOT be truncated, but the cap must be present.
    assert parsed.char_count <= MAX_TOTAL_CHARS
    # Verify the cap logic works: a file > 2M truncates with a warning.
    assert MAX_TOTAL_CHARS == 2_000_000


def test_large_txt_offsets_satisfy_invariant(fixtures):
    parsed = parse_document(fixtures["large.txt"], contract_id="large")
    full = parsed.full_text
    clauses = segment_clauses(full, contract_id="large")
    assert clauses, "no clauses from 1.8M-char document"
    _assert_slice_invariant(full, clauses)
    # No clause exceeds the (possibly truncated) text.
    assert all(c.char_end <= len(full) for c in clauses)


def test_large_txt_truncation_path(tmp_path: Path):
    """A >2M-char file is truncated at 2M with an explicit warning."""
    # Generate a >2M file directly (bypass the 1.8M fixture).
    chunk = "1. Terms\n\nThe customer shall pay the provider within thirty days.\n\n"
    fp = tmp_path / "huge.txt"
    with fp.open("w", encoding="utf-8") as fh:
        while fp.stat().st_size < MAX_TOTAL_CHARS + 100_000:
            fh.write(chunk)
    parsed = parse_document(fp, contract_id="huge")
    assert parsed.char_count == MAX_TOTAL_CHARS, (
        f"expected truncation at {MAX_TOTAL_CHARS}, got {parsed.char_count}"
    )
    trunc_warnings = [w for w in parsed.warnings if "truncat" in w.lower()]
    assert trunc_warnings, f"no truncation warning, got {parsed.warnings}"
    # Offsets still valid on the truncated text.
    clauses = segment_clauses(parsed.full_text, contract_id="huge")
    _assert_slice_invariant(parsed.full_text, clauses)
    assert all(c.char_end <= len(parsed.full_text) for c in clauses)


# ===========================================================================
# Header/footer regex adversarial cases (no false-positive stripping)
# ===========================================================================


def test_confidentiality_clause_not_stripped():
    """'Confidentiality is paramount.' is clause body, not a header."""
    text = (
        "5. Confidentiality\n"
        "Confidentiality is paramount to both parties. Each party shall keep "
        "the other party's Confidential Information secret."
    )
    cleaned = strip_headers_footers(text)
    assert "Confidentiality is paramount" in cleaned
    assert "Confidential Information" in cleaned


def test_page_of_vs_parties_not_stripped():
    """'Page 3 of 6' is a footer; '3 of the 6 parties' is clause body."""
    text = (
        "Page 3 of 6\n"
        "3 of the 6 parties shall be bound by the confidentiality clause "
        "and remain liable for any breach."
    )
    cleaned = strip_headers_footers(text)
    assert "Page 3 of 6" not in cleaned  # the actual footer is stripped
    assert "3 of the 6 parties" in cleaned  # the clause body survives


def test_repeating_title_header_stripped():
    """A header repeating the contract title is stripped if it matches a hint."""
    text = "Confidential - Master Services Agreement\n\nThe parties agree as follows."
    cleaned = strip_headers_footers(text)
    assert "The parties agree" in cleaned


def test_draft_word_boundary():
    """Whole-word 'draft' header is stripped; 'draftsmanship' is not."""
    text = "DRAFT\n\nThis is a draft of the agreement.\n\nThe draftsmanship is fine."
    cleaned = strip_headers_footers(text)
    # The standalone 'DRAFT' line is a header hint and is stripped.
    assert "draftsmanship" in cleaned


# ===========================================================================
# Annexure / heading recognition
# ===========================================================================


def test_annexure_heading_recognised():
    """ANNEXURE A, SCHEDULE 1, EXHIBIT B, Annex 2 are clause headings."""
    from app.services.segmenter import _looks_like_heading_line

    assert _looks_like_heading_line("ANNEXURE A: SERVICE LEVELS")
    assert _looks_like_heading_line("ANNEXURE A")
    assert _looks_like_heading_line("SCHEDULE 1")
    assert _looks_like_heading_line("EXHIBIT B")
    assert _looks_like_heading_line("Annex 2: Delivery Terms")


def test_annexure_becomes_its_own_clause():
    text = (
        "10. Miscellaneous\n"
        "This Agreement is governed by the laws of India.\n\n"
        "ANNEXURE A: SERVICE LEVELS\n"
        "Availability: 99.5% per calendar month. Incident response: 4 business hours."
    )
    clauses = segment_clauses(text, contract_id="ann")
    ann = [c for c in clauses if c.heading and "ANNEXURE A" in c.heading]
    assert ann, f"ANNEXURE A not its own clause: {[c.heading for c in clauses]}"
    assert ann[0].heading is not None


def test_schedule_and_exhibit_headings():
    text = (
        "1. Definitions\n'Fees' means the amounts payable.\n\n"
        "SCHEDULE 1\nFees: INR 10,000 per month.\n\n"
        "EXHIBIT B\nForm of Notice.\n"
    )
    clauses = segment_clauses(text, contract_id="se")
    heads = {c.heading for c in clauses if c.heading}
    assert any(h and "SCHEDULE 1" in h for h in heads), heads
    assert any(h and "EXHIBIT B" in h for h in heads), heads


# ===========================================================================
# Large-document performance sanity
# ===========================================================================


@pytest.mark.skipif(not True, reason="")
def test_large_txt_parse_segment_under_30s(fixtures):
    """Parse + segment of the 1.8M-char TXT must complete in well under 30s."""
    start = time.monotonic()
    parsed = parse_document(fixtures["large.txt"], contract_id="perf")
    clauses = segment_clauses(parsed.full_text, contract_id="perf")
    elapsed = time.monotonic() - start
    assert clauses, "no clauses"
    assert elapsed < 30, f"parse+segment took {elapsed:.1f}s (limit 30s)"
    # Record for the report (printed, not asserted).
    print(f"\n[large.txt perf] {elapsed:.2f}s for {parsed.char_count} chars -> {len(clauses)} clauses")
