"""Document parser supporting PDF, DOCX, TXT/Markdown with OCR fallback.

The parser focuses on robustness over completeness: it must never crash on
malformed input. If a parser fails, the next strategy is attempted, and
finally we return whatever text we could salvage.
"""
from __future__ import annotations

import io
import re
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
        raise DocumentParseError(
            "Document parsed but no text could be extracted. The file may be empty or corrupted."
        )

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


# ---------------------------------------------------------------------------
# PDF strategies
# ---------------------------------------------------------------------------


def _parse_pdf(path: Path, *, contract_id: str, enable_ocr: bool) -> ParsedDocument:
    pages: List[ParsedPage] = []

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
                text = clean_text(text)
                method = "native"
                if len(text) < OCR_PAGE_CHAR_THRESHOLD and enable_ocr:
                    ocr_text = _ocr_pdf_page(path, idx)
                    if ocr_text:
                        text = ocr_text
                        method = "ocr"
                pages.append(ParsedPage(idx, text, method, len(text)))
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
                text = page.get_text("text") or ""
                text = clean_text(text)
                method = "native"
                if len(text) < OCR_PAGE_CHAR_THRESHOLD and enable_ocr:
                    ocr_text = _ocr_pdf_page(path, idx)
                    if ocr_text:
                        text = ocr_text
                        method = "ocr"
                pages.append(ParsedPage(idx, text, method, len(text)))
            doc.close()
        except Exception as exc:
            logger.error("PyMuPDF failed entirely: {}", exc)

    if not pages:
        raise DocumentParseError("Unable to extract any pages from PDF.")

    full_text = "\n\n".join(pg.text for pg in pages if pg.text)
    return ParsedDocument(
        contract_id=contract_id,
        title=path.stem.replace("_", " ").title(),
        file_name=path.name,
        full_text=full_text,
        pages=pages,
        metadata={"ext": ".pdf", "page_count": len(pages)},
    )


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

    for para in doc.paragraphs:
        text = clean_text(para.text)
        if not text:
            continue
        if sum(len(p) for p in buffer) + len(text) > char_budget:
            flush_page()
        buffer.append(text)
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
    encodings = ["utf-8", "utf-16", "latin-1", "cp1252"]
    text: Optional[str] = None
    last_exc: Optional[Exception] = None
    for enc in encodings:
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError as exc:
            last_exc = exc
            continue
    if text is None:
        # last-resort binary decode
        text = path.read_bytes().decode("utf-8", errors="replace")

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


_HEADER_FOOTER_HINTS = re.compile(
    r"(page\s*\d+\s*of\s*\d+|confidential|"
    r"draft|private\s*and\s*confidential)",
    re.IGNORECASE,
)


def strip_headers_footers(text: str) -> str:
    """Best-effort removal of repeating headers/footers."""
    if not text:
        return ""
    lines = text.split("\n")
    kept = [ln for ln in lines if not _HEADER_FOOTER_HINTS.search(ln)]
    return "\n".join(kept).strip()
