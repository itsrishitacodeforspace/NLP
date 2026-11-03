"""Document parser supporting PDF, DOCX, TXT/Markdown with OCR fallback.

The parser focuses on robustness over completeness: it must never crash on
malformed input. If a parser fails, the next strategy is attempted, and
finally we return whatever text we could salvage.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.core.exceptions import DocumentParseError, UnsupportedFormatError
from app.core.logging import get_logger
from app.utils.text import clean_text, split_into_paragraphs

logger = get_logger()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# If a page produces fewer characters than this threshold we trigger OCR.
OCR_PAGE_CHAR_THRESHOLD = 50

# Soft cap for total extracted characters (prevents pathological inputs).
MAX_TOTAL_CHARS = 2_000_000

# Minimum meaningful content: below this we treat the document as not
# extractable (e.g. a scanned PDF where OCR is unavailable) rather than
# letting a handful of stray glyphs pass as a successful parse.
MIN_MEANINGFUL_CHARS = 200
MIN_MEANINGFUL_PAGE_FRACTION = 0.5

# Above this share of non-printable/non-text characters a .txt file is
# almost certainly binary garbage mislabeled as text.
MAX_BINARY_CHAR_RATIO = 0.30

# {"reason": Optional[str]} — populated lazily by _ocr_unavailable_reason.
_OCR_UNAVAILABLE: dict = {}


@dataclass
class ParsedPage:
    """Represents a single page or logical chunk of a document."""

    page_number: int
    text: str
    method: str  # 'native', 'ocr', 'docx', 'text'
    char_count: int = 0


@dataclass
class ParsedDocument:
    """Structured output of the parser."""

    contract_id: str
    title: str
    file_name: str
    full_text: str
    pages: List[ParsedPage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def paragraphs(self) -> List[str]:
        return split_into_paragraphs(self.full_text)

    @property
    def char_count(self) -> int:
        return len(self.full_text)


# ---------------------------------------------------------------------------
# Strategy dispatch
# ---------------------------------------------------------------------------


def _ext_of(path: str | Path) -> str:
    return Path(path).suffix.lower()


def parse_document(
    file_path: str | Path,
    *,
    contract_id: str,
    enable_ocr: bool = True,
) -> ParsedDocument:
    """Parse any supported file type. Returns ParsedDocument.

    Strategy order:
      PDF -> pdfplumber -> PyMuPDF -> OCR (per page)
      DOCX -> python-docx
      TXT/MD -> direct read with cleaning
    """
    p = Path(file_path)
    if not p.exists():
        raise DocumentParseError(f"File not found: {file_path}")

    ext = _ext_of(p)
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(ext)

    if ext == ".pdf":
        parsed = _parse_pdf(p, contract_id=contract_id, enable_ocr=enable_ocr)
    elif ext == ".docx":
        parsed = _parse_docx(p, contract_id=contract_id)
    else:
        parsed = _parse_text(p, contract_id=contract_id)

    if not parsed.full_text.strip():
        _raise_no_extractable_text(parsed)

    _check_min_meaningful_content(parsed)

    if parsed.char_count > MAX_TOTAL_CHARS:
        parsed.warnings.append(
            f"Document exceeded the {MAX_TOTAL_CHARS:,} char safety cap; truncated."
        )
        parsed.full_text = parsed.full_text[:MAX_TOTAL_CHARS]

    logger.info(
        "Parsed {} ({} pages, {} chars, method={})",
        parsed.file_name,
        len(parsed.pages),
        parsed.char_count,
        ",".join({pg.method for pg in parsed.pages}) or "n/a",
    )
    return parsed


def _raise_no_extractable_text(parsed: ParsedDocument) -> None:
    """Raise for a document with no extractable text, with an OCR hint when the
    document is a multi-page PDF that went through (or attempted) the OCR path.

    An image-only (scanned) PDF with tesseract absent is the common case: the
    operator needs to know to install tesseract-ocr, not a vague "empty or
    corrupted" message.
    """
    if parsed.metadata.get("ext") == ".pdf" and len(parsed.pages) > 1:
        raise DocumentParseError(
            "Document has no extractable text. The document may be image-only "
            "(scanned); install tesseract-ocr for OCR support."
        )
    # Single-page PDFs that attempted OCR also get the hint.
    if parsed.metadata.get("ext") == ".pdf" and any(
        w.startswith("OCR") for w in parsed.warnings
    ):
        raise DocumentParseError(
            "Document has no extractable text. The document may be image-only "
            "(scanned); install tesseract-ocr for OCR support."
        )
    raise DocumentParseError(
        "Document parsed but no text could be extracted. The file may be empty or corrupted."
    )


def _check_min_meaningful_content(parsed: ParsedDocument) -> None:
    """Reject near-empty parses that would otherwise pass silently.

    A scanned PDF with OCR unavailable can yield a handful of stray glyphs
    (page numbers, ligatures) on most pages. That is *not* a successful
    parse, so we fail with a specific message instead of letting it look
    healthy downstream.
    """
    total_pages = len(parsed.pages)
    non_empty = sum(1 for pg in parsed.pages if pg.text.strip())
    chars = len(parsed.full_text.strip())
    # The gate only applies to genuinely multi-page documents (real PDF
    # pages). DOCX/TXT pseudo-pages are a grouping artefact and short
    # single-page notes are legitimate, so near-empty single-chunk docs
    # still parse (the empty-text check above already catches the truly
    # empty case).
    if total_pages <= 1:
        return
    page_fraction = non_empty / total_pages
    under_min_chars = chars < MIN_MEANINGFUL_CHARS
    under_min_pages = page_fraction < MIN_MEANINGFUL_PAGE_FRACTION
    if not (under_min_chars or under_min_pages):
        return
    if any(pg.method == "ocr" for pg in parsed.pages) or any(
        w.startswith("OCR") for w in parsed.warnings
    ):
        parsed.warnings.append(
            "Degraded parsing: most pages had no extractable text and OCR was "
            "attempted or unavailable; the document appears to be image-only."
        )
    if total_pages and total_pages > 1 and non_empty == 0:
        raise DocumentParseError(
            "Document has no extractable text. The document may be "
            "image-only (scanned); install tesseract-ocr for OCR support."
        )
    detail = (
        f"Only {chars} characters were extracted from {non_empty} of "
        f"{total_pages} pages."
        if total_pages > 1
        else f"Only {chars} characters could be extracted in total."
    )
    raise DocumentParseError(
        "Document appears to be image-only (scanned) or has no extractable "
        f"text; install tesseract-ocr for OCR support. {detail}"
    )


# ---------------------------------------------------------------------------
# PDF strategies
# ---------------------------------------------------------------------------


def _parse_pdf(path: Path, *, contract_id: str, enable_ocr: bool) -> ParsedDocument:
    """Parse a PDF via pdfplumber, falling back to PyMuPDF.

    ``ocr_stats`` tracks how many pages went through the OCR path and how
    many of those produced no text, so degraded parses are surfaced as
    warnings instead of looking successful.
    """
    ocr_stats = {"attempted": 0, "no_text": 0}
    pages: List[ParsedPage] = []

    def _handle_page(idx: int, raw_text: str) -> ParsedPage:
        text = strip_headers_footers(clean_text(raw_text))
        method = "native"
        if len(text) < OCR_PAGE_CHAR_THRESHOLD and enable_ocr:
            ocr_stats["attempted"] += 1
            ocr_text = _ocr_pdf_page(path, idx)
            if ocr_text:
                text = ocr_text
                method = "ocr"
            else:
                ocr_stats["no_text"] += 1
        return ParsedPage(idx, text, method, len(text))

    # Strategy 1: pdfplumber (best for tables / digital text)
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(path)) as pdf:
            for idx, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("pdfplumber failed on page {}: {}", idx, exc)
                    text = ""
                pages.append(_handle_page(idx, text))
    except Exception as exc:
        logger.warning("pdfplumber failed entirely: {} — falling back to PyMuPDF", exc)
        pages = []

    # Strategy 2: PyMuPDF if pdfplumber produced nothing
    if not pages or all(not pg.text for pg in pages):
        try:
            import fitz  # type: ignore

            doc = fitz.open(str(path))
            pages = []
            for idx, page in enumerate(doc, start=1):
                pages.append(_handle_page(idx, page.get_text("text") or ""))
            doc.close()
        except Exception as exc:
            logger.error("PyMuPDF failed entirely: {}", exc)

    if not pages:
        raise DocumentParseError("Unable to extract any pages from PDF.")

    full_text = "\n\n".join(pg.text for pg in pages if pg.text)
    warnings: List[str] = []
    unavailable = _ocr_unavailable_reason() if ocr_stats["attempted"] else None
    if ocr_stats["attempted"]:
        if unavailable:
            warnings.append(
                f"OCR unavailable ({unavailable}); {ocr_stats['attempted']} of "
                f"{len(pages)} pages had low text extraction."
            )
        if ocr_stats["no_text"]:
            warnings.append(
                f"OCR attempted on {ocr_stats['attempted']} pages; "
                f"{ocr_stats['no_text']} produced no text."
            )

    return ParsedDocument(
        contract_id=contract_id,
        title=path.stem.replace("_", " ").title(),
        file_name=path.name,
        full_text=full_text,
        pages=pages,
        metadata={"ext": ".pdf", "page_count": len(pages)},
        warnings=warnings,
    )


def _ocr_unavailable_reason() -> Optional[str]:
    """Return a human-readable reason if the OCR toolchain is unusable.

    Covers missing Python libraries *and* a missing tesseract binary
    (the common case in slim containers). Result is cached after the first
    check because the environment does not change during a parse.
    """
    cached = _OCR_UNAVAILABLE.get("reason")
    if cached is not None:
        return cached
    reason: Optional[str] = None
    try:
        import pytesseract  # type: ignore

        if pytesseract.get_tesseract_version() is None:
            reason = "tesseract not installed"
    except Exception as exc:  # missing lib or binary raises various types
        reason = f"OCR unavailable ({exc})"
    _OCR_UNAVAILABLE["reason"] = reason
    return reason


def _ocr_pdf_page(pdf_path: Path, page_number: int) -> str:
    """Render a single page to image and run Tesseract OCR on it."""
    try:
        import fitz  # type: ignore
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning("OCR libraries unavailable; skipping OCR fallback.")
        return ""

    try:
        doc = fitz.open(str(pdf_path))
        if page_number - 1 >= doc.page_count:
            doc.close()
            return ""
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        text = pytesseract.image_to_string(img)
        doc.close()
        return clean_text(text)
    except Exception as exc:  # pragma: no cover - depends on system OCR
        logger.warning("OCR failed for page {}: {}", page_number, exc)
        # A tesseract-not-in-PATH failure is environment-level: remember it
        # so the parse can warn once instead of per page.
        _ocr_unavailable_reason()
        return ""


# ---------------------------------------------------------------------------
# DOCX strategy
# ---------------------------------------------------------------------------


def _parse_docx(path: Path, *, contract_id: str) -> ParsedDocument:
    try:
        from docx import Document  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise DocumentParseError(f"python-docx not installed: {exc}") from exc

    try:
        doc = Document(str(path))
    except Exception as exc:
        raise DocumentParseError(f"Failed to open DOCX: {exc}") from exc

    pages: List[ParsedPage] = []
    buffer: List[str] = []
    approx_pages: List[List[str]] = []
    char_budget = 1800  # rough chars per page

    def flush_page():
        if buffer:
            approx_pages.append(buffer.copy())
            buffer.clear()

    def add_block(text: str) -> None:
        if not text:
            return
        if sum(len(p) for p in buffer) + len(text) > char_budget:
            flush_page()
        buffer.append(text)

    # Walk the body in document order so tables (fee schedules, signature
    # blocks) are not lost — ``doc.paragraphs`` excludes ``w:tbl`` content.
    from docx.table import Table as _DocxTable  # type: ignore
    from docx.text.paragraph import Paragraph as _DocxParagraph  # type: ignore

    body = doc.element.body
    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            text = clean_text(_DocxParagraph(child, doc).text)
            add_block(text)
        elif child.tag.endswith("}tbl"):
            table = _DocxTable(child, doc)
            rows = [" | ".join(cell.text for cell in row.cells) for row in table.rows]
            add_block(clean_text("\n".join(rows)))
    flush_page()

    for idx, page_paras in enumerate(approx_pages, start=1):
        joined = "\n\n".join(page_paras)
        pages.append(ParsedPage(idx, joined, "docx", len(joined)))

    full_text = "\n\n".join(pp.text for pp in pages if pp.text)
    title = path.stem.replace("_", " ").title()
    core = getattr(doc.core_properties, "title", None) or title

    return ParsedDocument(
        contract_id=contract_id,
        title=str(core),
        file_name=path.name,
        full_text=full_text,
        pages=pages,
        metadata={"ext": ".docx", "page_count": len(pages)},
    )


# ---------------------------------------------------------------------------
# Plain text strategy
# ---------------------------------------------------------------------------


def _parse_text(path: Path, *, contract_id: str) -> ParsedDocument:
    data = path.read_bytes()
    # UTF-16 is only a realistic encoding for text files that carry a BOM;
    # without one, decoding binary garbage as UTF-16 can produce plausible-
    # looking letters and mask the garbage.
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        encodings = ["utf-16", "utf-8", "latin-1", "cp1252"]
    else:
        encodings = ["utf-8", "latin-1", "cp1252"]
    text: Optional[str] = None
    last_exc: Optional[Exception] = None
    for enc in encodings:
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError as exc:
            last_exc = exc
            continue
    if text is None:
        # last-resort binary decode
        text = data.decode("utf-8", errors="replace")
    # latin-1 (and cp1252) never fail to decode, so binary garbage with a
    # .txt extension must be caught here: real text is overwhelmingly
    # letters, digits, punctuation and whitespace by Unicode category.
    if _binary_char_ratio(text) > MAX_BINARY_CHAR_RATIO:
        raise DocumentParseError("File does not appear to be text")

    cleaned = clean_text(text)
    paragraphs = split_into_paragraphs(cleaned)

    # Group paragraphs into pseudo-pages of ~1800 chars.
    pages: List[ParsedPage] = []
    char_budget = 1800
    buffer: List[str] = []
    for p in paragraphs:
        if sum(len(x) for x in buffer) + len(p) > char_budget and buffer:
            joined = "\n\n".join(buffer)
            pages.append(ParsedPage(len(pages) + 1, joined, "text", len(joined)))
            buffer = []
        buffer.append(p)
    if buffer:
        joined = "\n\n".join(buffer)
        pages.append(ParsedPage(len(pages) + 1, joined, "text", len(joined)))

    return ParsedDocument(
        contract_id=contract_id,
        title=path.stem.replace("_", " ").title(),
        file_name=path.name,
        full_text=cleaned,
        pages=pages or [ParsedPage(1, cleaned, "text", len(cleaned))],
        metadata={"ext": _ext_of(path), "page_count": len(pages)},
        warnings=([f"Used fallback encoding after {last_exc}"] if last_exc else []),
    )


def _binary_char_ratio(text: str) -> float:
    """Fraction of characters that are not letters/digits/punct/whitespace.

    Uses Unicode categories: letters (L*), numbers (N*), punctuation (P*),
    whitespace (Z*). Control characters, C1/L1 symbols, surrogates and the
    like all count as 'binary' — a share above ``MAX_BINARY_CHAR_RATIO``
    means the file is almost certainly not text.
    """
    if not text:
        return 0.0
    text_chars = 0
    for ch in text:
        if ch.isspace():
            text_chars += 1
        else:
            cat = unicodedata.category(ch)
            if cat[0] in ("L", "N", "P", "Z"):
                text_chars += 1
    return 1.0 - text_chars / len(text)


# ---------------------------------------------------------------------------
# Convenience: parse raw bytes (used by upload endpoint)
# ---------------------------------------------------------------------------


def parse_bytes(
    file_bytes: bytes,
    original_name: str,
    *,
    contract_id: str,
    enable_ocr: bool = True,
) -> ParsedDocument:
    """Persist bytes to disk, parse, and return ParsedDocument."""
    from app.utils.fs import derive_title_from_filename, save_upload

    path, derived_id = save_upload(file_bytes, original_name)
    parsed = parse_document(
        path,
        contract_id=contract_id or derived_id,
        enable_ocr=enable_ocr,
    )
    # Use the original filename for the title (not the prefixed on-disk name).
    parsed.title = derive_title_from_filename(original_name)
    parsed.file_name = original_name
    return parsed


# A real page header/footer is short. Requiring the matching line to be at or
# under this length stops the bare ``confidential`` / ``draft`` hints from
# stripping clause *body* lines that merely contain those words (e.g.
# "Confidentiality is paramount." or "This is a draft of the agreement.").
# "Page N of M" is unambiguous enough that it is stripped at any length.
_MAX_HEADER_LEN = 60

_HEADER_FOOTER_HINTS = re.compile(
    r"(page\s*\d+\s*of\s*\d+|private\s+and\s+confidential|\bconfidential\b|\bdraft\b)",
    re.IGNORECASE,
)

_PAGE_OF_RE = re.compile(r"page\s*\d+\s*of\s*\d+", re.IGNORECASE)


def strip_headers_footers(text: str) -> str:
    """Best-effort removal of repeating headers/footers.

    A line is dropped when it looks like a running header/footer: a short
    line (<= ``_MAX_HEADER_LEN`` chars) matching a header hint, or *any* line
    containing "Page N of M" (unambiguous pagination). Clause body lines that
    happen to contain "confidential", "draft" or "3 of the 6 parties" are
    preserved because they are long or lack the pagination marker.
    """
    if not text:
        return ""
    kept: List[str] = []
    for ln in text.split("\n"):
        stripped = ln.strip()
        if not stripped:
            kept.append(ln)
            continue
        if _PAGE_OF_RE.search(stripped):
            continue  # "Page N of M" is always a header/footer
        if len(stripped) <= _MAX_HEADER_LEN and _HEADER_FOOTER_HINTS.search(stripped):
            continue  # short line with a header hint (confidential / draft / ...)
        kept.append(ln)
    return "\n".join(kept).strip()
