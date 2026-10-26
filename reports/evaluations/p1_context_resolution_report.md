# P1 — Deterministic Context-Resolution Layer

**Status:** implemented (P1 only). No P2–P7, no dataset/model/artifact change, no commit.
**Date:** 2026-10-26 · **Baseline:** `main` @ `cbd9c29`.

---

## 1. Planned scope reported before editing

| File | Kind | Purpose |
|---|---|---|
| `nlp/context/__init__.py` | **new** | package export |
| `nlp/context/resolver.py` | **new** | the resolver (no dependencies) |
| `tests/test_context_resolution.py` | **new** | 10 general-purpose tests |
| `app/models/schemas.py` | modified | `Clause.context: Optional[dict] = None` (additive) |
| `app/services/analyzer.py` | modified | build the bundle once, attach to each clause |

No rule, severity, trigger, threshold, ML, missing-protection or legal behaviour was touched.

## 2. Interface

```python
from nlp.context import resolve_context
bundle: dict[str, dict] = resolve_context(raw_clauses)   # raw_clauses: segmenter Clause dataclasses
```
Per-clause bundle:
```json
{
  "status": "complete | partial | none",
  "references": [{"raw": "Clause 7.4", "kind": "clause",
                  "target_clause_ids": ["…"], "status": "resolved|missing|ambiguous"}],
  "overrides":  [{"raw": "Notwithstanding Clauses 7.1 and 7.2 …", "marker": "notwithstanding",
                  "target_clause_ids": ["…"], "status": "candidate"}],
  "related_clause_ids": ["…"],
  "unresolved_references": ["…"]
}
```
Reference `kind` ∈ {clause, section, schedule, exhibit, annexure, appendix, definition}.

## 3. Design and data flow

```
parse → segment → [resolve_context(raw_clauses)] → classify → NER → obligations → risk rules → score
                                     │
                     builds: by_section, by_schedule, definitions
                     emits : per-clause references / overrides / related / unresolved
                     attaches: Clause.context   (read-only; rules ignore it in P1)
```
- **References:** regex over clause text for `Clause(s)|Section(s)|Schedule(s)|Exhibit(s)|Annexure(s)|Appendix`, followed by one or more numbers (`7.4`, `7.1 and 7.2`, `2, 3`).
- **Resolution:** exact lookup in `by_section` (normalised, whitespace-stripped) or `by_schedule` (from schedule-like headings). Self-references are excluded.
- **Definitions:** `"Term" means …` indexed document-wide; other clauses that use the term (letter-boundary, case-insensitive) get a `definition` reference to the defining clause.
- **Precedence:** a sentence containing `notwithstanding | prevails | subject to | override` **and** a resolvable reference is recorded as an **override candidate**. It is *never* treated as proof that a conflict is resolved.
- **Statuses:** per-reference `resolved` / `missing` / `ambiguous`; per-bundle `complete` / `partial` (any unresolved) / `none`. Ambiguity = a section number mapping to more than one clause.

## 4. Changed-file inventory

New: `nlp/context/__init__.py`, `nlp/context/resolver.py`, `tests/test_context_resolution.py`, this report.
Modified: `app/models/schemas.py` (one optional field), `app/services/analyzer.py` (one import, one call, one kwarg).

```diff
+    # P1: deterministic cross-reference / context bundle (additive, optional).
+    context: Optional[Dict[str, Any]] = None
-    raw_clauses = segment_clauses(full_text, contract_id=contract_id)
+    raw_clauses = segment_clauses(full_text, contract_id=contract_id)
+    context_bundle = resolve_context(raw_clauses)
-            entities=extraction.entities,
+            entities=extraction.entities,
+            context=context_bundle.get(raw.clause_id),
```

## 5. Resolution statuses and examples (from the tests)

| Case | Observed |
|---|---|
| Clause reference resolves | `Clause 1` → `resolved`, target `t_c001` |
| Defined term across clauses | `Cap` → `kind=definition`, `resolved`, target = definitions clause |
| Schedule reference | `Schedule 2` → `kind=schedule`, `resolved` |
| Explicit precedence | `Notwithstanding Clause 1 …` → `overrides[0].status = "candidate"`, never `"resolved"` |
| Reference present but no resolution of conflict | still `candidate` only; no suppression, no claim |
| Missing target | `Clause 99` → `missing`, `target_clause_ids=[]`, bundle `partial` |
| Ambiguous | two clauses with section `1` → `ambiguous`, both targets listed |
| No cross-references | every bundle `status = "none"`, no references |
| Long document / repeated refs | 30 repeated `Clause 1` → 30 resolved |
| TC-05 (one example, not the criterion) | `Schedule 2` and `Clause 7.4` **detected**; unresolved, because Markdown-prefixed headings (`## 7. LIABILITY`) are not parsed as section numbers |

## 6. Tests and exit codes

| Command | Exit | Result |
|---|---|---|
| `uv run --no-sync ruff check .` | **0** | all checks passed |
| `uv run --no-sync pytest tests/test_context_resolution.py -q` | **0** | **10 passed** |
| `uv run --no-sync pytest -q` (full) | **1** | **71 collected → 64 passed, 7 failed** |

**Before → after:** 61 collected / 54 passed / 7 failed → **71 / 64 / 7**. The same seven provenance failures remain visible and untouched (`T1a`, `T1b`, `T2a`, `T2b`, `T3a`, `T3b`, `T8`); no skips or xfails were added.

Two of my own new tests initially failed for **test-design** reasons and were corrected (not weakened): `"Clause 1"` is a substring of `"Clause 10"` (now exact-match), and duplicate-section ambiguity needed synthetic clause objects rather than relying on segmentation.

## 7. Before/after behaviour and regressions

- **No behavioural change to rules**: `Clause.context` is additive; the rule engine, scorer, ML booster, missing-protection logic and legal pointers were not modified. The existing 7 failures are unchanged; the other tests (including `test_e2e`, `test_api_smoke`, `test_regressions`, `test_risk_model`, `test_rls`, `test_auth`) still pass.
- **Contracts without cross-references** are unaffected (bundle `none`; test 8).
- Persisted job JSON gains an optional `context` object per clause (backward compatible; `null` when absent).

## 8. Known unsupported reference formats (honest limits)

- **Markdown-prefixed headings** (`## 7. LIABILITY`) are not recognised as section numbers by the existing segmenter → references such as `Clause 7.4` are reported **unresolved** (surfaced, not assumed). Fixing this belongs to the segmenter, not P1.
- Lettered/roman sub-items (`Clause 7.4(a)`, `Section IV`) — only numeric keys are indexed.
- Schedule keys beyond `[A-Za-z0-9]+` (`Schedule 2.1`, `Annexure A-1`) partially supported.
- Definitions: only `"Term" means/shall mean/refers to/has the meaning` forms; inline parenthetical definitions are not indexed.
- Precedence: only sentence-level markers; no resolution of *which* clause wins, and no inference from clause order (deliberate).
- References inside tables/OCR-damaged text are not resolved.

## 9. Rollback

Delete `nlp/context/`, `tests/test_context_resolution.py`, this report; revert the two one-line additions in `app/models/schemas.py` and `app/services/analyzer.py` (`git checkout -- app/models/schemas.py app/services/analyzer.py`). No data, model or artifact was touched, so no backup restoration is needed.

## 10. Remaining risks and next stage

- The bundle is **produced but not consumed** — rules cannot yet use it. That is by design for P1; consuming it requires P2 (evidence binding) and P4 (rule precision) with their own approval.
- `related_clause_ids` is a lexical, not semantic, relation; a referenced clause may be irrelevant or conditional (documented).
- Override detection is a **candidate** signal; treating it as authoritative would be wrong.
- **Recommended next:** **P2 evidence binding** (add spans/`search_scope` to `RiskFlag`), then **P3** four-way missing-protection status which can use `related_clause_ids` for schedule lookups.
