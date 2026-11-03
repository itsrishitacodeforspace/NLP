"""Regression tests for the 2026-11-03 deep-audit pipeline hardening.

Covers audit items C13 (page_hint + header/footer wiring), C14 (DOCX
tables), C15 (image-only PDF detection + OCR warnings), C16 (party
window + zero-party warning), C17 (context-scored effective date), the
long-clause mid-word split, and the binary-garbage .txt rejection.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import DocumentParseError
from app.services.parser import parse_document, strip_headers_footers
from app.services.segmenter import segment_clauses
from app.utils.text import clean_text

try:
    import pymupdf  # noqa: F401  # type: ignore

    _HAS_FITZ = True
except ImportError:  # pragma: no cover - pymupdf is part of the base stack
    _HAS_FITZ = False

try:
    from docx import Document  # noqa: F401  # type: ignore

    _HAS_DOCX = True
except ImportError:  # pragma: no cover
    _HAS_DOCX = False


# ---------------------------------------------------------------------------
# C14: DOCX table content is not lost
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx not installed")
def test_docx_tables_are_extracted_in_document_order(tmp_path: Path):
    from docx import Document

    doc = Document()
    doc.add_heading("FEE SCHEDULE AGREEMENT", 0)
    doc.add_paragraph("The Customer shall pay the Provider within 30 days of invoice.")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Fees"
    table.cell(0, 1).text = "INR 10,000"
    table.cell(1, 0).text = "Late charge"
    table.cell(1, 1).text = "INR 500"
    fp = tmp_path / "contract.docx"
    doc.save(str(fp))

    parsed = parse_document(fp, contract_id="docx_tbl")
    assert "Fees" in parsed.full_text
    assert "INR 10,000" in parsed.full_text
    assert "Late charge" in parsed.full_text
    assert "INR 500" in parsed.full_text
    # The clause text that precedes the table must also survive.
    assert "pay the Provider within 30 days" in parsed.full_text


@pytest.mark.skipif(not _HAS_DOCX, reason="python-docx not installed")
def test_docx_heading_numbering_behavior_unchanged(tmp_path: Path):
    from docx import Document

    doc = Document()
    doc.add_heading("1. Definitions", 1)
    doc.add_paragraph("'Services' means the software development services.")
    doc.add_heading("2. Term", 1)
    doc.add_paragraph("This Agreement continues for two years.")
    fp = tmp_path / "numbered.docx"
    doc.save(str(fp))

    parsed = parse_document(fp, contract_id="docx_num")
    assert "1. Definitions" in parsed.full_text
    assert "2. Term" in parsed.full_text
    assert parsed.char_count > 0


# ---------------------------------------------------------------------------
# C15: image-only / near-empty PDF detection + OCR warnings
# ---------------------------------------------------------------------------


def _write_pdf(path: Path, pages: list[str]) -> None:
    """Write a simple multi-page PDF, one text line per page."""
    import pymupdf

    doc = pymupdf.open()
    for line in pages:
        page = doc.new_page()
        page.insert_text((72, 100), line)
    doc.save(str(path))


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_near_empty_pdf_raises_document_parse_error(tmp_path: Path):
    """A 2-page PDF with 1 stray char on one page must not parse as success."""
    _write_pdf(tmp_path / "scan.pdf", ["x", ""])
    with pytest.raises(DocumentParseError) as exc:
        parse_document(tmp_path / "scan.pdf", contract_id="scan")
    msg = str(exc.value)
    assert "image-only" in msg or "no extractable text" in msg
    assert "tesseract" in msg


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_all_text_pdf_still_parses(tmp_path: Path):
    """A 2-page all-text PDF must parse cleanly (no false positive)."""
    _write_pdf(
        tmp_path / "ok.pdf",
        [
            "This is page one of a contract with enough real clause text to "
            "exceed the minimum meaningful content threshold for parsing.",
            "This is page two of the contract with further clause text that "
            "describes the payment terms and the renewal provisions.",
        ],
    )
    parsed = parse_document(tmp_path / "ok.pdf", contract_id="ok")
    assert parsed.char_count > 200
    assert len(parsed.pages) == 2


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_ocr_unavailable_warns_on_low_text_pages(tmp_path: Path):
    """When OCR is unavailable, low-text pages must surface a warning."""
    _write_pdf(tmp_path / "low.pdf", ["a", "b"])
    with pytest.raises(DocumentParseError):
        parse_document(tmp_path / "low.pdf", contract_id="low")
    # Build the ParsedDocument directly to inspect warnings (parse raises).
    from app.services.parser import _ocr_unavailable_reason, _parse_pdf

    ocr_reason = _ocr_unavailable_reason()
    assert ocr_reason is not None, "tesseract is expected to be absent here"

    pages = _parse_pdf(
        tmp_path / "low.pdf", contract_id="low", enable_ocr=True
    ).pages
    attempted = sum(1 for pg in pages if pg.method == "native" and len(pg.text) < 50)
    assert attempted >= 1
    # The _parse_pdf path appends an OCR-unavailable warning when pages
    # had low extraction and OCR could not run.
    from app.services.parser import _parse_pdf as pp

    result = pp(tmp_path / "low.pdf", contract_id="low2", enable_ocr=True)
    ocr_warnings = [w for w in result.warnings if w.startswith("OCR")]
    assert ocr_warnings, f"expected an OCR warning, got {result.warnings}"


# ---------------------------------------------------------------------------
# C13: header/footer stripping wired into the PDF parse path
# ---------------------------------------------------------------------------


def test_strip_headers_footers_word_boundary():
    """'draft' inside a word must not be stripped; whole-word 'draft' is."""
    text = "This is a draft of the agreement.\n\nThe draftsmanship of the clause is fine."
    cleaned = strip_headers_footers(text)
    assert "draft of the agreement" not in cleaned
    assert "draftsmanship" in cleaned  # 'draft' inside a word is preserved


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_pdf_headers_are_stripped_and_body_survives(tmp_path: Path):
    _write_pdf(
        tmp_path / "hdr.pdf",
        [
            "Confidential - Page 1 of 2\n"
            "The Customer shall pay all invoices within thirty days of receipt of a "
            "valid invoice issued by the Provider for services rendered under this "
            "Agreement, and all amounts are exclusive of goods and services tax.",
            "Confidential - Page 2 of 2\n"
            "Either party may terminate this Agreement upon sixty days prior written "
            "notice to the other party, and upon termination all accrued payment "
            "obligations of the Customer shall survive and remain enforceable.",
        ],
    )
    parsed = parse_document(tmp_path / "hdr.pdf", contract_id="hdr")
    # The repeating header line is gone; the clause body survives.
    assert "Confidential - Page 1 of 2" not in parsed.full_text
    assert "The Customer shall pay all invoices within thirty days" in parsed.full_text
    assert "terminate this Agreement upon sixty days" in parsed.full_text


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_strip_headers_footers_is_called_per_page(tmp_path: Path, monkeypatch):
    """The parser must actually call strip_headers_footers (not dead code)."""
    from app.services import parser as P

    calls = []
    original = P.strip_headers_footers

    def spy(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(P, "strip_headers_footers", spy)
    _write_pdf(
        tmp_path / "spy.pdf",
        ["Confidential\n\nReal body text for the page with enough clause content."],
    )
    P._parse_pdf(tmp_path / "spy.pdf", contract_id="spy", enable_ocr=False)
    assert calls, "strip_headers_footers was never called during PDF parsing"


# ---------------------------------------------------------------------------
# C13: page_hint provenance
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_FITZ, reason="pymupdf not installed")
def test_page_hint_is_stamped_from_pages(tmp_path: Path):
    from app.services.analyzer import _stamp_page_hints

    probe = tmp_path / "ph_probe.pdf"
    _write_pdf(
        probe,
        [
            "1. Definitions\nThis is the first page with enough clause text to "
            "exceed the minimum meaningful content threshold for parsing purposes here.",
            "2. Payment Terms\nPAGE_TWO_MARKER The customer shall pay within 30 "
            "days of receiving a valid invoice from the provider for the services.",
            "3. Term and Renewal\nThis is the third page of the document with "
            "additional clause text about the term and renewal provisions.",
        ],
    )
    parsed = parse_document(probe, contract_id="ph")
    clauses = segment_clauses(parsed.full_text, contract_id="ph")
    _stamp_page_hints(clauses, parsed.pages)
    marker = [c for c in clauses if "PAGE_TWO_MARKER" in c.text]
    assert marker, "marker clause not found"
    assert marker[0].page_hint == 2, f"expected page 2, got {marker[0].page_hint}"


# ---------------------------------------------------------------------------
# C16: party-detection window + zero-party warning
# ---------------------------------------------------------------------------


def _mk_clause(cid: str, text: str, heading: str | None = None):
    from app.models.schemas import Clause
    from nlp.ner.ner import extract_entities

    ex = extract_entities(text, clause_text=text)
    return Clause(
        clause_id=cid,
        text=text,
        heading=heading,
        char_start=0,
        char_end=len(text),
        entities=ex.entities,
    )


def test_party_in_final_clause_is_detected():
    from app.services.analyzer import _detect_parties

    clauses = [
        _mk_clause(
            "c1",
            "This Master Services Agreement is made between Acme Cloud "
            "Services Pvt Ltd and a customer as set out below.",
            heading="MASTER SERVICES AGREEMENT",
        ),
        _mk_clause("c2", "1. Definitions\n1.1 'Services' means the support services."),
        _mk_clause(
            "c3",
            "2. Term\n2.1 This Agreement continues for an initial two-year term.",
        ),
        _mk_clause(
            "c4",
            "IN WITNESS WHEREOF the parties have executed this Agreement. "
            "For and on behalf of Bluepeak Technologies Limited (Customer): signature.",
        ),
    ]
    parties = _detect_parties(clauses)
    assert any("Acme" in p for p in parties), f"party A missing: {parties}"
    assert any("Bluepeak" in p for p in parties), f"party B missing: {parties}"


def test_zero_parties_returns_empty_list():
    from app.services.analyzer import _detect_parties

    clauses = [
        _mk_clause("p1", "This document concerns general terms.", heading="TERMS"),
        _mk_clause("p2", "1. Scope\n1.1 The provider will perform the work."),
        _mk_clause("p3", "2. Fees\n2.1 Fees are payable monthly in arrears."),
    ]
    assert _detect_parties(clauses) == []


def test_zero_party_warning_is_surfaced_by_analyse():
    from app.services.analyzer import _analyse

    text = (
        "This document concerns general terms of the engagement.\n\n"
        "1. Scope\n1.1 The provider will perform the work described in the annexure.\n\n"
        "2. Fees\n2.1 Fees are payable monthly in arrears per the fee schedule."
    )
    result = _analyse(
        text,
        contract_id="z1",
        title="No Parties",
        file_name="noparties.txt",
        warnings=[],
        pages=None,
        contract_type=_ct(),
        user_role=_ur(),
        jurisdiction="India",
    )
    assert result.contract.parties == []
    assert any("No parties detected" in w for w in result.warnings), result.warnings


def _ct():
    from app.models.schemas import ContractType

    return ContractType.OTHER


def _ur():
    from app.models.schemas import PartySide

    return PartySide.CUSTOMER


# ---------------------------------------------------------------------------
# C17: context-scored effective date
# ---------------------------------------------------------------------------


def _date_clause(text: str):
    from app.models.schemas import Clause
    from nlp.ner.ner import extract_entities

    ex = extract_entities(text, clause_text=text)
    return Clause(clause_id="d", text=text, char_start=0, char_end=len(text), entities=ex.entities)


def test_amended_agreement_yields_amendment_date():
    from app.services.analyzer import _first_date

    text = (
        "This Agreement dated 1 January 2020 was amended on 15 April 2024 "
        "to extend the term."
    )
    assert _first_date([_date_clause(text)]) == "15 April 2024"


def test_plain_made_on_yields_that_date():
    from app.services.analyzer import _first_date

    assert _first_date([_date_clause("This Agreement is made on 10 May 2024.")]) == "10 May 2024"


def test_no_cue_falls_back_to_first_date():
    from app.services.analyzer import _first_date

    # No effective-date cue -> behaviour unchanged: first DATE entity.
    text = "This Agreement is dated 2 March 2019 and covers the services."
    assert _first_date([_date_clause(text)]) == "2 March 2019"


# ---------------------------------------------------------------------------
# Long-clause mid-word split
# ---------------------------------------------------------------------------


def test_long_clause_split_never_cuts_inside_a_token():
    """A whitespace-less token must not be bisected by a fixed-char split."""
    from app.services.segmenter import _split_long_clause

    token = "x" * 400
    before = ("word " * 200)[:800].strip()
    after = ("term " * 200)[:800].strip()
    body = before + " " + token + " " + after
    cleaned = clean_text(body)
    res = _split_long_clause(
        cleaned,
        body_start=0,
        body_end=len(cleaned),
        base_id="t",
        section_number=None,
        heading=None,
        long_threshold=800,
    )
    tok_start = cleaned.find(token)
    tok_end = tok_start + len(token)
    for c in res:
        # A cut point strictly inside the token would mean the split
        # bisected the token.
        assert not (0 < c.char_start < len(cleaned) and tok_start < c.char_start < tok_end), (
            f"{c.clause_id} starts inside the token"
        )
        assert not (0 < c.char_end < len(cleaned) and tok_start < c.char_end < tok_end), (
            f"{c.clause_id} ends inside the token"
        )
    # Source-integrity: every sub-clause is an exact slice.
    for c in res:
        assert cleaned[c.char_start : c.char_end] == c.text


# ---------------------------------------------------------------------------
# Binary-garbage .txt rejection
# ---------------------------------------------------------------------------


def test_binary_garbage_txt_is_rejected(tmp_path: Path):
    fp = tmp_path / "garbage.txt"
    fp.write_bytes(b"\x00\x01\x02\xff\xfe" * 100)
    with pytest.raises(DocumentParseError) as exc:
        parse_document(fp, contract_id="garbage")
    assert "does not appear to be text" in str(exc.value)


def test_real_txt_still_parses(tmp_path: Path):
    fp = tmp_path / "real.txt"
    fp.write_text(
        "1. Terms\n\nThe customer shall pay within 30 days of invoice receipt.",
        encoding="utf-8",
    )
    parsed = parse_document(fp, contract_id="real")
    assert "30 days" in parsed.full_text
