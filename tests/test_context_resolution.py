"""P1: deterministic cross-reference / context resolution (general-purpose)."""
from __future__ import annotations

from pathlib import Path

from app.services.segmenter import segment_clauses
from nlp.context import resolve_context
from nlp.context.resolver import BUNDLE_NONE, BUNDLE_PARTIAL, STATUS_CANDIDATE, STATUS_MISSING

TC05 = Path(__file__).resolve().parent / "fixtures" / "TC-05_cross_reference_traps.md"


def _ctx(text: str) -> dict:
    return resolve_context(segment_clauses(text, contract_id="t"))


def _first_ref(bundle: dict, raw_fragment: str) -> dict:
    for _pid, b in bundle.items():
        for ref in b["references"]:
            if raw_fragment.lower() in ref["raw"].lower():
                return ref
    raise AssertionError(f"reference containing {raw_fragment!r} not found")


def test_clause_reference_resolves():
    doc = "1. Liability\n\nLiability is capped.\n\n2. Override\n\nNotwithstanding Clause 1, liability is unlimited.\n"
    b = _ctx(doc)
    ref = _first_ref(b, "Clause 1")
    assert ref["status"] == "resolved"
    assert ref["target_clause_ids"] == ["t_c001"]


def test_defined_term_resolves_across_clauses():
    doc = '1. Definitions\n\n"Cap" means the amount in the schedule.\n\n2. Liability\n\nLiability shall not exceed the Cap.\n'
    b = _ctx(doc)
    ref = _first_ref(b, "Cap")
    assert ref["kind"] == "definition" and ref["status"] == "resolved"
    assert ref["target_clause_ids"] == ["t_c001"]


def test_schedule_reference_resolves():
    doc = "1. Fees\n\nFees are payable per Schedule 2.\n\nSCHEDULE 2 - FEES\n\nAmount payable annually.\n"
    b = _ctx(doc)
    ref = _first_ref(b, "Schedule 2")
    assert ref["kind"] == "schedule" and ref["status"] == "resolved"
    assert ref["target_clause_ids"]


def test_explicit_precedence_is_recorded_as_candidate_only():
    doc = "1. Liability\n\nLiability is capped.\n\n2. Override\n\nNotwithstanding Clause 1, liability is unlimited.\n"
    b = _ctx(doc)
    overrides = [o for x in b.values() for o in x["overrides"] if "Notwithstanding" in o["raw"]]
    assert overrides, "precedence sentence with a resolvable reference should be recorded"
    assert all(o["status"] == STATUS_CANDIDATE for o in overrides)
    # A candidate is NOT proof that a conflict is resolved.
    assert all(o["status"] != "resolved" for o in overrides)


def test_reference_that_exists_but_does_not_resolve_conflict():
    # The override points at a clause that does not contain a conflicting term.
    doc = "1. Payments\n\nInvoice monthly.\n\n2. Override\n\nNotwithstanding Clause 1, the parties may vary.\n"
    b = _ctx(doc)
    overrides = [o for x in b.values() for o in x["overrides"]]
    assert overrides and all(o["status"] == STATUS_CANDIDATE for o in overrides)
    assert any(o["target_clause_ids"] == ["t_c001"] for o in overrides)


def test_missing_target_clause_is_reported_not_assumed():
    doc = "1. Scope\n\nThe parties refer to Clause 99 for details.\n"
    b = _ctx(doc)
    ref = _first_ref(b, "Clause 99")
    assert ref["status"] == STATUS_MISSING
    assert ref["target_clause_ids"] == []
    assert any(bundle["status"] == BUNDLE_PARTIAL for bundle in b.values())


def test_ambiguous_reference_when_section_repeats():
    from types import SimpleNamespace

    clauses = [
        SimpleNamespace(clause_id="a", section_number="1", heading="Liability", text="Text A."),
        SimpleNamespace(clause_id="b", section_number="1", heading="Liability", text="Text B."),
        SimpleNamespace(clause_id="c", section_number="3", heading="Scope", text="See Clause 1 for the cap."),
    ]
    b = resolve_context(clauses)
    ref = next(r for r in b["c"]["references"] if r["raw"].lower() == "clause 1")
    assert ref["status"] == "ambiguous"
    assert sorted(ref["target_clause_ids"]) == ["a", "b"]


def test_document_without_cross_references_is_clean():
    doc = "1. Payments\n\nInvoice monthly within 30 days.\n\n2. Term\n\nThe term is two years.\n"
    b = _ctx(doc)
    assert b and all(x["status"] == BUNDLE_NONE for x in b.values())
    assert all(not x["references"] for x in b.values())


def test_long_document_with_repeated_references():
    body = "".join(
        f"{i}. Clause {i}\n\nNotwithstanding Clause 1, obligation {i} applies.\n\n" for i in range(2, 32)
    )
    b = _ctx("1. Base\n\nBase obligation applies.\n\n" + body)
    refs = [r for x in b.values() for r in x["references"] if r["raw"].strip().lower() == "clause 1"]
    assert len(refs) == 30, f"expected 30 repeated references, got {len(refs)}"
    assert all(r["status"] == "resolved" for r in refs)


def test_tc05_references_are_detected_and_unresolved_by_markdown_headings():
    """TC-05 is one example, not the acceptance criterion.

    Its headings are Markdown-prefixed ('## 7. LIABILITY'), which the segmenter
    does not treat as section numbers, so references must be reported as
    UNRESOLVED rather than silently assumed.
    """
    text = TC05.read_text(encoding="utf-8")
    b = _ctx(text)
    raws = [r["raw"] for x in b.values() for r in x["references"]]
    assert any("Schedule 2" in r for r in raws), raws[:10]
    assert any("Clause 7.4" in r or "Clauses 7.1" in r for r in raws), raws[:10]
    # Nothing resolves to a fabricated target; unresolved is explicit.
    assert any(x["unresolved_references"] for x in b.values())
