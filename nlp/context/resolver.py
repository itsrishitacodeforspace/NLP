"""Deterministic cross-reference / context resolution for contract clauses.

Scope (deliberately narrow):
  * find references to clauses/sections/schedules/exhibits/annexures/appendices;
  * resolve them against the *current document's* parsed structure;
  * resolve defined terms (``"Term" means ...``) across clauses;
  * record explicit precedence/override language as a **candidate**, never as proof
    that a conflict is resolved;
  * report unresolved / ambiguous / missing references.

Nothing here decides legal meaning. The existing risk rules are untouched: this
module only produces a traceable context bundle for each clause.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List

STATUS_RESOLVED = "resolved"
STATUS_MISSING = "missing"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_CANDIDATE = "candidate"  # precedence language that references something
BUNDLE_COMPLETE = "complete"
BUNDLE_PARTIAL = "partial"
BUNDLE_NONE = "none"

_REF_RE = re.compile(
    r"\b(?P<kind>clauses?|sections?|schedules?|exhibits?|annexures?|appendices|appendix)"
    r"\s+(?P<nums>\d+(?:\.\d+)*(?:\s*(?:,|and|or|&|to)\s*\d+(?:\.\d+)*)*)",
    re.IGNORECASE,
)
_DEF_RE = re.compile(
    r"[\"\u201c](?P<term>[A-Z][A-Za-z0-9 ,/&'\-]{1,60}?)[\"\u201d]\s*(?:means|shall mean|refers to|has the meaning)",
    re.IGNORECASE,
)
_PRECEDENCE_RE = re.compile(
    r"\b(notwithstanding|prevails?|shall prevail|subject to|overrid(?:e|es|ing|den))\b",
    re.IGNORECASE,
)
_SCHEDULE_HEAD_RE = re.compile(
    r"^\s*#*\s*(?P<kind>schedule|exhibit|annexure|appendix)\s+(?P<key>[A-Za-z0-9]+)", re.IGNORECASE
)
_NUM_RE = re.compile(r"\d+(?:\.\d+)*")
_SENTENCE_RE = re.compile(r"(?<=[.;:])\s+|\n+")


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().lower())


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text or "") if s and s.strip()]


def _build_indexes(clauses: Iterable) -> dict:
    by_section: Dict[str, List[str]] = {}
    by_sched: Dict[str, List[str]] = {}
    definitions: Dict[str, dict] = {}
    for cl in clauses:
        cid = getattr(cl, "clause_id", None)
        if not cid:
            continue
        sec = getattr(cl, "section_number", None)
        if sec:
            by_section.setdefault(_norm_key(sec), []).append(cid)
        head = getattr(cl, "heading", None) or ""
        m = _SCHEDULE_HEAD_RE.match(head)
        if m:
            by_sched.setdefault(_norm_key(m.group("key")), []).append(cid)
        for dm in _DEF_RE.finditer(getattr(cl, "text", "") or ""):
            term = _norm_key(dm.group("term"))
            if term and term not in definitions:
                definitions[term] = {"term": dm.group("term").strip(), "clause_id": cid}
    return {"by_section": by_section, "by_sched": by_sched, "definitions": definitions}


def _targets(kind: str, nums: str, idx: dict) -> tuple[list[str], str]:
    """Resolve one reference group; returns (clause_ids, status)."""
    kind = kind.lower()
    keys = [_norm_key(n) for n in _NUM_RE.findall(nums or "")]
    if not keys:
        return [], STATUS_MISSING
    resolved: List[str] = []
    status = STATUS_RESOLVED
    for key in keys:
        if kind.startswith(("schedule", "exhibit", "annex", "appendix")):
            found = idx["by_sched"].get(key, [])
        else:
            found = idx["by_section"].get(key, [])
        if not found:
            status = STATUS_MISSING
            continue
        if len(found) > 1:
            status = STATUS_AMBIGUOUS
            resolved.extend(found)
            continue
        resolved.extend(found)
    return sorted(set(resolved)), status


def resolve_context(clauses: Iterable) -> Dict[str, dict]:
    """Return ``{clause_id: context_bundle}`` for every clause in the document."""
    clauses = list(clauses)
    idx = _build_indexes(clauses)
    bundles: Dict[str, dict] = {}

    for cl in clauses:
        cid = getattr(cl, "clause_id", None)
        if not cid:
            continue
        text = getattr(cl, "text", "") or ""
        references: List[dict] = []
        overrides: List[dict] = []
        unresolved: List[str] = []
        related: set[str] = set()

        for m in _REF_RE.finditer(text):
            raw = " ".join(m.group(0).split())
            targets, status = _targets(m.group("kind"), m.group("nums"), idx)
            targets = [t for t in targets if t != cid]
            references.append(
                {
                    "raw": raw,
                    "kind": m.group("kind").lower().rstrip("s"),
                    "target_clause_ids": targets,
                    "status": status,
                }
            )
            if status == STATUS_RESOLVED and targets:
                related.update(targets)
            else:
                unresolved.append(raw)

        # Defined terms used in this clause (whole-term match, case-insensitive).
        for _term, meta in idx["definitions"].items():
            if meta["clause_id"] == cid:
                continue
            if re.search(r"(?<![a-z0-9])" + re.escape(meta["term"]).lower() + r"(?![a-z0-9])", text.lower()):
                references.append(
                    {
                        "raw": meta["term"],
                        "kind": "definition",
                        "target_clause_ids": [meta["clause_id"]],
                        "status": STATUS_RESOLVED,
                    }
                )
                related.add(meta["clause_id"])

        # Precedence language is recorded as a CANDIDATE only - never as proof.
        for sentence in _sentences(text):
            if not _PRECEDENCE_RE.search(sentence):
                continue
            for ref in [r for r in references if r["target_clause_ids"]]:
                if ref["raw"] in sentence:
                    overrides.append(
                        {
                            "raw": " ".join(sentence.split())[:240],
                            "marker": _PRECEDENCE_RE.search(sentence).group(0).lower(),
                            "target_clause_ids": ref["target_clause_ids"],
                            "status": STATUS_CANDIDATE,
                        }
                    )

        if references or overrides:
            status = BUNDLE_PARTIAL if unresolved else BUNDLE_COMPLETE
        else:
            status = BUNDLE_NONE

        bundles[cid] = {
            "status": status,
            "references": references,
            "overrides": overrides,
            "related_clause_ids": sorted(related),
            "unresolved_references": unresolved,
        }
    return bundles
