"""Programmatic builders for realistic multi-page test fixtures.

Every builder is deterministic and idempotent; tests call
:func:`build_all` into a ``tmp_path`` (binaries are never committed).

Fixtures:
  * multi_page.pdf    6 pages: repeating header/footer, numbered clauses 1-12
                      with clause 4 continuing across a page break (2 -> 3),
                      a fee-schedule table on page 5 and
                      "ANNEXURE A: SERVICE LEVELS" on page 6.
  * four_page.docx    Heading 1/Heading 2 styles, numbered clauses, a 3x3
                      table mid-document, a 2-column signature block at the end.
  * scanned.pdf       contract text rendered to a PNG (PIL ImageDraw) with no
                      PDF text layer.
  * corrupt.pdf       b'%PDF-1.4' + 50 random bytes (fixed seed).
  * large.txt         ~1.8M chars of structured, repetitive contract text.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Layout constants (A4 = 595 x 842 pt; base-14 11pt text -> ~98 chars/line,
# 13pt leading fits ~54 body lines between the header and footer).
# ---------------------------------------------------------------------------
W, H = 595, 842
MARGIN = 72
FONT_SIZE = 10
LEADING = 12
HEADER_Y = 50
FOOTER_Y = 810
BODY_Y0 = 90
BODY_YMAX = 780
# At 10pt base-14 on A4 the right margin sits at ~120 chars. Lines wrapped at
# 95 chars stay clear of pdfplumber's re-wrap threshold (which produces
# spurious mid-word breaks like "stateme\nnt" when lines are ~100 chars at
# this font). 95 keeps the per-page line budget workable too.
CHARS_PER_LINE = 95


def _wrap(text: str, width: int = CHARS_PER_LINE) -> List[str]:
    out: List[str] = []
    for paragraph in text.split("\n"):
        while len(paragraph) > width:
            out.append(paragraph[:width])
            paragraph = paragraph[width:]
        out.append(paragraph)
    return out


# ---------------------------------------------------------------------------
# Fixture (a): 6-page multi-page PDF
# ---------------------------------------------------------------------------

_COMPANY_FOOTER = "Acme Infra Pvt Ltd | +91 80 4040 1000"
_PREAMBLE = (
    "This Master Services Agreement is made on 15 March 2024 by and between "
    "Acme Infra Pvt Ltd with its registered office at 12 MG Road, Bengaluru "
    "(the \"Provider\") and Bluepeak Technologies Limited with its registered "
    "office at 74 Linking Road, Bengaluru (the \"Customer\")."
)

_CLAUSES: List[tuple[str, str]] = [
    ("Definitions", (
        "\"Services\" means the IT infrastructure support and managed network "
        "services described in the statement of work and the schedules to this "
        "Agreement, including monitoring, patching, incident response and "
        "capacity planning. \"Fees\" means the amounts set out in the fee "
        "schedule attached to this Agreement, exclusive of taxes. "
        "\"Confidential Information\" means all non-public information, "
        "whether written, oral or electronic, disclosed by either party in "
        "connection with this Agreement, including technical data, pricing, "
        "business plans and the terms of this Agreement itself. "
        "\"Personal Data\" has the meaning given to it under the applicable "
        "data protection laws of India."
    )),
    ("Scope of Services", (
        "The Provider shall perform the Services with the degree of skill, "
        "care and diligence expected of a reputable professional services "
        "firm in India. The Customer shall provide reasonable access to "
        "facilities, systems, networks and personnel required for the "
        "performance of the Services, and shall designate a single point of "
        "contact responsible for day-to-day coordination. Changes to the "
        "scope of the Services must be agreed in writing through the change "
        "control process set out in this Agreement, and no verbal instruction "
        "shall oblige either party to vary the Services."
    )),
    ("Fees and Payment", (
        "The Customer shall pay the Fees set out in the fee schedule in "
        "accordance with the invoicing cycle agreed by the parties. All "
        "invoices are payable within thirty days of the date of invoice and "
        "amounts overdue for more than thirty days shall attract interest at "
        "the rate of 1.5% per month or the maximum rate permitted by law, "
        "whichever is lower. The Provider shall issue a tax invoice in "
        "accordance with the applicable Goods and Services Tax requirements, "
        "and the Customer shall be responsible for the payment of TDS under "
        "section 194J of the Income Tax Act, 1961 where applicable. The "
        "Provider may terminate this Agreement where payment is overdue for "
        "more than sixty days despite written notice."
    )),
    # Clause 4 is engineered to start on page 3 and continue on page 4.
    ("Service Levels and Remedies", (
        "The Provider shall achieve the service levels set out in Annexure A "
        "and shall use commercially reasonable efforts to maintain the "
        "infrastructure, tooling and staffing required to meet them. If the "
        "Provider fails to meet a service level in any calendar month, the "
        "Customer shall be entitled to a service credit equal to ten percent "
        "of the Fees payable for that month, calculated against the Fees "
        "actually invoiced rather than the Fees contractually payable, so "
        "that the credit reflects the value of the Services actually "
        "delivered during the affected month. The Customer shall notify the "
        "Provider in writing within ten days of any failure, describing the "
        "failure in reasonable detail, and the Provider shall use "
        "commercially reasonable efforts to remedy the failure as soon as "
        "practicable and in any event within the time limits stated in "
        "Annexure A. Service credits shall be applied against the next "
        "invoice issued after the Customer's notification, or refunded where "
        "no further invoice is due, and the Customer shall not be required to "
        "exhaust the service credit remedy before asserting any other right "
        "that arises from a material breach of this Agreement. Repeated "
        "failure to meet the service levels entitling the Customer to service "
        "credits in three consecutive months shall constitute a material "
        "breach of this Agreement, and the Provider may cure any material "
        "breach within fifteen days of receiving written notice from the "
        "Customer describing the breach in reasonable detail. The Provider "
        "shall provide the Customer with a monthly service level report "
        "covering availability measurements, incident summaries, response "
        "times and any service credits applied, within five business days of "
        "the end of each calendar month. The service credits set out in this "
        "clause are the sole and exclusive remedy of the Customer for a "
        "failure to meet a service level and shall not limit any other right "
        "of the Customer arising out of a material breach of this Agreement, "
        "including the right to terminate this Agreement for persistent "
        "underperformance of the Services. Where a service level failure is "
        "caused by the Customer's own equipment, network or instructions, the "
        "Provider shall not be obliged to grant a service credit for that "
        "failure, provided that the Provider demonstrates the causal link in "
        "the monthly service level report referred to above. The parties "
        "shall review the service levels at least once per quarter and may "
        "amend Annexure A by mutual written agreement where the nature or "
        "scale of the Services materially changes, provided that no amendment "
        "shall reduce the availability target below the level in force at the "
        "date of the original signature. Each party shall keep its service "
        "level monitoring records, including raw availability logs and "
        "incident tickets, for a period of two years from the date of the "
        "relevant month, and shall make them available to the other party "
        "upon reasonable written request for the purposes of verifying a "
        "claimed service credit, resolving a disputed service level "
        "measurement, or supporting a claim that a failure was caused by an "
        "event beyond the Provider's reasonable control."
    )),
    ("Confidentiality", (
        "Each party shall keep the other party's Confidential Information "
        "secret and shall not disclose it to any third party without the "
        "prior written consent of the disclosing party, save where disclosure "
        "is required by law or by a regulator of competent jurisdiction, or "
        "to those professional advisers who are bound by duties of "
        "confidentiality no less strict than those in this clause. The "
        "receiving party shall protect the Confidential Information with at "
        "least the same degree of care that it uses to protect its own "
        "confidential information, and in no event less than reasonable care. "
        "The obligations in this clause survive termination or expiry of this "
        "Agreement for a period of three years. The Customer shall comply "
        "with all applicable data protection laws, including the Information "
        "Technology Act, 2000 and the Information Technology (Reasonable "
        "Security Practices and Procedures and Sensitive Personal Data or "
        "Information) Rules, 2011, when processing any Personal Data provided "
        "by the Provider, and shall notify the Provider without undue delay, "
        "and in any event within forty-eight hours, of any data security "
        "incident affecting such data, with a description of the incident, "
        "its likely impact and the remediation steps already taken."
    )),
    ("Intellectual Property", (
        "All intellectual property rights in the deliverables created under "
        "this Agreement vest in the Customer upon full payment of the Fees, "
        "and the Provider assigns all related rights to the Customer upon "
        "creation. The Provider retains its pre-existing intellectual property "
        "and grants the Customer a limited, non-exclusive, non-transferable "
        "licence to use it solely as incorporated in the deliverables for the "
        "term of this Agreement. Neither party may use the other party's "
        "name, logo or trademarks in any publicity or marketing material "
        "without prior written approval."
    )),
    ("Warranties and Disclaimer", (
        "The Provider warrants that the Services will be performed in a "
        "workmanlike manner consistent with generally accepted professional "
        "standards in India, that the Services will not materially degrade "
        "the performance of the Customer's existing systems, and that the "
        "Provider's personnel will be appropriately qualified for the work. "
        "EXCEPT AS EXPRESSLY SET OUT IN THIS AGREEMENT, EACH PARTY DISCLAIMS "
        "ALL OTHER WARRANTIES, EXPRESS OR IMPLIED, INCLUDING ANY IMPLIED "
        "WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE."
    )),
    ("Limitation of Liability", (
        "NEITHER PARTY SHALL BE LIABLE FOR ANY INDIRECT, INCIDENTAL OR "
        "CONSEQUENTIAL LOSS OR DAMAGE, INCLUDING LOSS OF PROFITS, LOSS OF "
        "BUSINESS OR LOSS OF DATA, ARISING OUT OF OR IN CONNECTION WITH THIS "
        "AGREEMENT, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH LOSS. THE "
        "AGGREGATE LIABILITY OF THE PROVIDER UNDER THIS AGREEMENT SHALL NOT "
        "EXCEED THE FEES PAID OR PAYABLE BY THE CUSTOMER IN THE TWELVE MONTHS "
        "PRECEDING THE EVENT GIVING RISE TO THE CLAIM. NOTHING IN THIS "
        "AGREEMENT LIMITS LIABILITY FOR FRAUD, DEATH OR PERSONAL INJURY "
        "RESULTING FROM NEGLIGENCE."
    )),
    ("Indemnification", (
        "The Provider shall defend the Customer against any claim that the "
        "deliverables infringe a third party's intellectual property rights "
        "and shall indemnify the Customer against the resulting damages, "
        "costs and reasonable legal fees. The Customer shall indemnify the "
        "Provider against claims arising from the Customer's materials or "
        "instructed use of the deliverables. The indemnified party shall "
        "give the indemnifying party prompt written notice of any claim, "
        "provide reasonable cooperation in the defence at the indemnifying "
        "party's expense, and not admit liability or settle the claim without "
        "the indemnifying party's prior written consent, not to be "
        "unreasonably withheld. This clause does not impose any obligation on "
        "the Provider in respect of claims arising from unauthorised "
        "modifications to the deliverables or combination of the deliverables "
        "with materials not supplied by the Provider."
    )),
    ("Term and Termination", (
        "This Agreement is effective from the date first written above and "
        "continues for an initial term of twelve months, renewing "
        "automatically for successive one-year periods unless either party "
        "gives written notice of non-renewal at least sixty days before the "
        "end of the then-current term. Either party may terminate this "
        "Agreement upon sixty days prior written notice, and either party may "
        "terminate with immediate effect where the other party commits a "
        "material breach that remains uncured fifteen days after notice. "
        "Termination does not limit any right or remedy accruing prior to "
        "termination, and sections 3, 5, 8 and 9 survive termination."
    )),
    ("Force Majeure", (
        "Neither party is liable for any failure or delay in performance "
        "caused by events beyond its reasonable control, including natural "
        "disasters, war, terrorism, acts of government, epidemics, and "
        "failures of third-party telecommunications networks, provided that "
        "the affected party gives prompt written notice to the other party "
        "and uses reasonable efforts to mitigate the effects of the event "
        "and to resume performance as soon as practicable."
    )),
    ("Governing Law and Dispute Resolution", (
        "This Agreement is governed by the laws of India. Any dispute arising "
        "out of or in connection with this Agreement shall first be escalated "
        "to the designated executives of the parties, and failing resolution "
        "within thirty days shall be subject to the exclusive jurisdiction "
        "of the courts at Bengaluru, subject to any arbitration procedure "
        "that the parties may agree in writing. Each party irrevocably "
        "consents to such jurisdiction and waives any objection to venue."
    )),
]


def _fee_schedule_block() -> List[str]:
    return [
        "FEE SCHEDULE",
        "Service Type             | Rate (INR per hour)",
        "Standard support         | 4,500",
        "Premium support          | 7,200",
        "Emergency on-site visit  | 12,000",
        "Travel and accommodation at actuals, subject to a monthly cap of INR 15,000.",
    ]


def _annexure_block() -> List[str]:
    return [
        "ANNEXURE A: SERVICE LEVELS",
        "Metric                   | Target",
        "Availability             | 99.5% per calendar month",
        "Incident response        | 4 business hours",
        "Resolution (severity 1)  | 24 hours",
        "Service credits accrue only where the monthly availability target is missed.",
        "Availability is measured excluding scheduled maintenance windows notified "
        "in advance.",
    ]


def build_multi_page_pdf(path: Path) -> None:
    """Build the 6-page PDF; clause 4 breaks across the page 2 -> 3 boundary.

    Layout (A4, 11pt base-14, <= 50 body lines per page between the
    repeating header and footer):
      p1: preamble + cl1 + cl2 + cl3
      p2: cl4 heading + first 30 of 39 cl4 body lines
      p3: last 9 cl4 body lines + cl5 + cl6 + cl7 + cl8
      p4: cl9 + cl10 + cl11 + cl12
      p5: FEE SCHEDULE table + signature block
      p6: ANNEXURE A: SERVICE LEVELS
    Page cuts are computed from the *measured* wrapped line counts, so the
    fixture is reproducible and never depends on font metrics at render time
    (each page gets its assigned chunk of pre-wrapped lines).
    """
    import pymupdf

    PAGE_CAPACITY = 50
    blocks: List[tuple[str, List[str]]] = [("preamble", _wrap(_PREAMBLE))]
    for i, (title, body) in enumerate(_CLAUSES, start=1):
        blocks.append((f"cl{i}", [f"{i}. {title}", *_wrap(body)]))
    fee = _fee_schedule_block()
    signature = [
        "IN WITNESS WHEREOF the parties have executed this Agreement.",
        "For and on behalf of Acme Infra Pvt Ltd (Provider):",
        "Name: R. Krishnan",
        "Designation: Managing Director",
        "Date: 15 March 2024",
        "For and on behalf of Bluepeak Technologies Limited (Customer):",
        "Name: S. Iyer",
        "Designation: Chief Financial Officer",
        "Date: 15 March 2024",
    ]
    annexure = _annexure_block()

    block_lines = {k: lns for k, lns in blocks}
    def size(kind: str) -> int:
        return len(block_lines[kind])

    cl4_lines = _wrap(_CLAUSES[3][1])
    cl4_head = "4. " + _CLAUSES[3][0]

    # Page 2 holds the cl4 heading plus 30 of its body lines; the remaining
    # body lines open page 3 (the mid-clause page break under test).
    fit_p2 = 30
    assert len(cl4_lines) > fit_p2, (
        f"clause 4 must break across pages 2->3; needs >{fit_p2} body lines, "
        f"has {len(cl4_lines)}"
    )
    p2 = 1 + fit_p2
    assert p2 <= PAGE_CAPACITY

    p1 = size("preamble") + size("cl1") + size("cl2") + size("cl3")
    assert p1 <= PAGE_CAPACITY, f"page 1 over capacity: {p1}"
    p3 = (len(cl4_lines) - fit_p2) + size("cl5") + size("cl6") + size("cl7") + size("cl8")
    assert p3 <= PAGE_CAPACITY, f"page 3 over capacity: {p3}"
    p4 = size("cl9") + size("cl10") + size("cl11") + size("cl12")
    assert p4 <= PAGE_CAPACITY, f"page 4 over capacity: {p4}"
    p5 = len(fee) + len(signature)
    assert p5 <= PAGE_CAPACITY, f"page 5 over capacity: {p5}"
    assert len(annexure) <= PAGE_CAPACITY, f"page 6 over capacity: {len(annexure)}"

    page_chunks = [
        block_lines["preamble"] + block_lines["cl1"] + block_lines["cl2"] + block_lines["cl3"],
        [cl4_head] + cl4_lines[:fit_p2],
        cl4_lines[fit_p2:] + block_lines["cl5"] + block_lines["cl6"] + block_lines["cl7"] + block_lines["cl8"],
        block_lines["cl9"] + block_lines["cl10"] + block_lines["cl11"] + block_lines["cl12"],
        fee + signature,
        annexure,
    ]

    doc = pymupdf.open()
    for page_no, chunk in enumerate(page_chunks, start=1):
        page = doc.new_page(width=W, height=H)
        y = BODY_Y0
        for line in chunk:
            page.insert_text((MARGIN, y), line, fontsize=FONT_SIZE)
            y += LEADING
        # Header/footer at fixed y; pdfplumber orders lines by y, so the body
        # (starting at BODY_Y0) follows them and strip_headers_footers removes
        # both from the cleaned text.
        page.insert_text((MARGIN, HEADER_Y),
                         f"Confidential - Page {page_no} of 6", fontsize=10)
        page.insert_text((W - MARGIN - 220, FOOTER_Y), _COMPANY_FOOTER, fontsize=10)
    doc.save(str(path))
    doc.close()


# ---------------------------------------------------------------------------
# Fixture (b): 4-page DOCX
# ---------------------------------------------------------------------------

_DOCX_SECTIONS: List[tuple[str, str]] = [
    ("1. Definitions", "\"Services\" means the managed network support services described in the statement of work."),
    ("2. Term and Renewal", "This Agreement continues for an initial term of twelve months and renews automatically for successive one-year periods unless either party gives sixty days notice of non-renewal."),
    ("3. Payment Terms", "The Customer shall pay all undisputed invoices within thirty days of receipt. Late payments attract interest at 1.5% per month or the maximum permitted by law, whichever is lower."),
    ("4. Confidentiality", "Each party shall protect the other party's Confidential Information and may disclose it only to personnel with a need to know who are bound by equivalent confidentiality obligations."),
    ("5. Service Levels", "The Provider shall maintain the service levels set out in the fee schedule. Monthly availability below the target entitles the Customer to a service credit of ten percent of the monthly Fees."),
    ("6. Data Protection", "The Provider shall comply with the Information Technology Act 2000 and the applicable data protection requirements when processing personal data on behalf of the Customer."),
    ("7. Termination for Convenience", "Either party may terminate this Agreement for convenience upon ninety days prior written notice, in which case the Customer shall pay for all Services performed up to the effective date of termination."),
    ("8. Limitation of Liability", "The Provider's aggregate liability under this Agreement shall not exceed the Fees paid in the twelve months preceding the claim and neither party is liable for indirect or consequential loss."),
]


def build_four_page_docx(path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.add_heading("INFRASTRUCTURE SERVICES AGREEMENT", 0)
    doc.add_paragraph(
        "This Infrastructure Services Agreement is made on 2 April 2024 between "
        "Bluepeak Technologies Limited (the \"Customer\") and Acme Infra Pvt Ltd "
        "(the \"Provider\") for the provision of managed network support services."
    )

    # Heading 1 sections with body; Heading 2 sub-sections mid-document.
    for title, body in _DOCX_SECTIONS[:4]:
        doc.add_heading(title, level=1)
        doc.add_paragraph(body)

    doc.add_heading("3.1 Late Payment Interest", level=2)
    doc.add_paragraph(
        "Interest under section 3 accrues only on undisputed amounts and is "
        "calculated on a monthly compounding basis."
    )

    # 3x3 table mid-document.
    table = doc.add_table(rows=3, cols=3)
    for j, header in enumerate(("Service", "Availability Target", "Credit")):
        table.cell(0, j).text = header
    for i, row in enumerate((
        ("Network monitoring", "99.5%", "10% of monthly Fees"),
        ("Patch management", "99.0%", "5% of monthly Fees"),
    ), start=1):
        for j, val in enumerate(row):
            table.cell(i, j).text = val

    for title, body in _DOCX_SECTIONS[4:]:
        doc.add_heading(title, level=1)
        doc.add_paragraph(body)

    # 2-column signature block at the end.
    doc.add_heading("IN WITNESS WHEREOF", level=1)
    sig = doc.add_table(rows=4, cols=2)
    sig.cell(0, 0).text = "For and on behalf of Bluepeak Technologies Limited (Customer)"
    sig.cell(0, 1).text = "For and on behalf of Acme Infra Pvt Ltd (Provider)"
    sig.cell(1, 0).text = "Name: S. Iyer"
    sig.cell(1, 1).text = "Name: R. Krishnan"
    sig.cell(2, 0).text = "Designation: Chief Financial Officer"
    sig.cell(2, 1).text = "Designation: Managing Director"
    sig.cell(3, 0).text = "Date: 2 April 2024"
    sig.cell(3, 1).text = "Date: 2 April 2024"
    doc.save(str(path))


# ---------------------------------------------------------------------------
# Fixture (c): scanned-style PDF (image only, no text layer)
# ---------------------------------------------------------------------------

_SCANNED_LINES = [
    "MASTER SERVICES AGREEMENT",
    "",
    "1. Definitions",
    "Services means the support services described in this Agreement.",
    "",
    "2. Fees and Payment",
    "The Customer shall pay the Fees within thirty days of the invoice date.",
    "",
    "3. Term",
    "This Agreement continues for twelve months from the effective date.",
    "",
    "4. Termination",
    "Either party may terminate upon sixty days prior written notice.",
    "",
    "5. Governing Law",
    "This Agreement is governed by the laws of India.",
]


def build_scanned_pdf(path: Path) -> None:
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default()
    img = Image.new("RGB", (1190, 1684), "white")  # ~A4 at 150 dpi
    draw = ImageDraw.Draw(img)
    y = 72
    for line in _SCANNED_LINES:
        if line:
            draw.text((72, y), line, fill="black", font=font)
        y += 22
    png = path.with_suffix(".png")
    img.save(str(png))
    doc = pymupdf.open()
    page = doc.new_page(width=W, height=H)
    page.insert_image(pymupdf.Rect(0, 0, W, H), filename=str(png))
    doc.save(str(path))
    doc.close()
    png.unlink()


# ---------------------------------------------------------------------------
# Fixture (d): corrupt PDF
# ---------------------------------------------------------------------------


def build_corrupt_pdf(path: Path) -> None:
    import random

    # Fixed seed: the fixture is reproducible across test runs.
    path.write_bytes(b"%PDF-1.4" + random.Random(20261103).randbytes(50))


# ---------------------------------------------------------------------------
# Fixture (e): large TXT (~1.8M chars)
# ---------------------------------------------------------------------------

_BULK_PARAS = [
    "The Provider shall use reasonable efforts to perform the Services in accordance with the agreed service levels, applicable industry standards, and the detailed requirements set out in the statements of work executed under this Agreement from time to time.",
    "The Customer shall provide the Provider with all reasonable information, access, and cooperation necessary for the proper performance of the Services, provided that such access is given in a manner that does not unreasonably interfere with the Customer's day-to-day operations.",
    "Any amendment to this Agreement must be made in writing and signed by authorised representatives of both parties, and no variation, waiver, or settlement shall be binding unless so reduced to writing and signed.",
    "Each party shall comply with all applicable laws and regulations in the performance of its obligations under this Agreement, and shall maintain all licences and approvals required for the provision or receipt of the Services.",
    "The parties may execute this Agreement in counterparts, each of which is deemed an original and all of which together constitute one and the same instrument, and electronic signatures shall be deemed originals for this purpose.",
]


def _bulky_section(number: int) -> str:
    body = " ".join(_BULK_PARAS) * 6
    return f"{number}. Section {number} of the Agreement\n\n{body}\n\n"


def build_large_txt(path: Path) -> None:
    parts = [
        "LARGE MASTER SERVICES AGREEMENT\n\n"
        + _PREAMBLE
        + "\n\nThis large agreement is generated for parser performance and "
        "truncation-boundary testing.\n\n"
    ]
    n = 1
    while sum(len(p) for p in parts) < 1_800_000:
        parts.append(_bulky_section(n))
        n += 1
    path.write_text("".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

FIXTURES = ("multi_page.pdf", "four_page.docx", "scanned.pdf", "corrupt.pdf", "large.txt")


def build_all(dest_dir: Path) -> dict[str, Path]:
    """Build every fixture into ``dest_dir``; returns name -> path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    return {
        "multi_page.pdf": _build(lambda p: build_multi_page_pdf(p), dest_dir / "multi_page.pdf"),
        "four_page.docx": _build(lambda p: build_four_page_docx(p), dest_dir / "four_page.docx"),
        "scanned.pdf": _build(lambda p: build_scanned_pdf(p), dest_dir / "scanned.pdf"),
        "corrupt.pdf": _build(lambda p: build_corrupt_pdf(p), dest_dir / "corrupt.pdf"),
        "large.txt": _build(lambda p: build_large_txt(p), dest_dir / "large.txt"),
    }


def _build(builder, path: Path) -> Path:
    if not path.exists():  # idempotent: skip regeneration within a run
        builder(path)
    return path


if __name__ == "__main__":  # manual generation for inspection
    import sys

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/fixtures")
    for name, p in build_all(out).items():
        print(f"{name}: {p} ({p.stat().st_size:,} bytes)")
