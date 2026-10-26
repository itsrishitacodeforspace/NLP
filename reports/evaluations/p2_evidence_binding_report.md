# P2 — Evidence Binding for Risk Findings

**Status:** implemented (P2 only). P3–P7 untouched. No data/model/artifact change, no commit.
**Date:** 2026-10-26 · **Baseline:** HEAD `cbd9c29`; suite **71 collected / 64 passed / 7 failed** (same seven provenance guards, preserved).

---

## 1. Design (smallest compatible representation)

Additive schema, bound once in `apply_rules` — **no individual rule function was edited**, so triggers,
severity, scoring and recommendations are untouched.

```python
class EvidenceSpan(BaseModel):
    text: str
    char_start: int
    char_end: int
    clause_id: Optional[str] = None
    role: str = "direct"        # direct | contextual
    locator: str = "clause_text"

class RiskFlag(BaseModel):
    ...                                  # unchanged fields
    source: str = "rule"                 # rule | model
    evidence_status: str = "unavailable" # direct | contextual | unverified | unavailable
    evidence_spans: List[EvidenceSpan] = []
    search_scope: Optional[str] = None
    related_clause_ids: List[str] = []
```

**Offset semantics (important):** `locator="clause_text"` means `char_start`/`char_end` index the
**clause text as stored in `Clause.text`** — i.e. the cleaned/segmented text produced by
`parser.clean_text` + `segmenter`, **not** raw file bytes and not a normalised copy. Offsets are only
meaningful together with `clause_id`. This distinction is documented in the model docstring.

### Binding rules (`nlp/risk_scoring/rules.py::_bind_evidence`)
| Finding kind | Evidence | `evidence_status` |
|---|---|---|
| clause-level, owning clause found | that clause's full text, `[0, len(text)]`, `role="direct"` | `direct` |
| clause-level, `clause_id` not in the clause list | none | `unverified` |
| contract-level (`clause_id is None`) | none; `search_scope = "document-wide scan across N clause(s); keyword-presence rule - no single supporting span"` | `unverified` |
| ML (`source="model"`) | the scored clause as `role="contextual"` | `unverified` (never elevated) |

No span is invented and no nearby clause is attached: the binding either uses the clause the rule
actually matched, or declares the evidence unverified.

## 2. Changed-file inventory

**Modified:** `app/models/schemas.py` (+`EvidenceSpan`, +5 `RiskFlag` fields with defaults),
`nlp/risk_scoring/rules.py` (+`_bind_evidence`, called at the end of `apply_rules`),
`app/services/analyzer.py` (ML flags marked `source="model"`, `evidence_status="unverified"`,
contextual span).
**New:** `tests/test_evidence_binding.py` (10 tests), this report.
**Unchanged:** all rule triggers/severities/thresholds, P1 resolver, missing-protection logic, ML model,
datasets, `data/processed/`, models, dashboard.

## 3. Tests (all pass)

| # | Test | Asserts |
|---|---|---|
| 1 | single span | `clause.text[start:end] == span.text == clause.text`, `status=direct` |
| 2 | multiple passages | schema round-trips 2 spans with `direct`/`contextual` roles |
| 3 | contract-level | `evidence_spans == []`, `status=unverified`, `search_scope` mentions "document-wide" |
| 4 | missing clause | no span invented, `unverified` |
| 5 | referenced-clause evidence | `related_clause_ids` carried alongside a direct span |
| 6 | Unicode/punctuation | exact slice on `"Cap" means ₹10,00,000 — … ;` |
| 7 | document-wide negative search | scope names N clauses, **no proof-of-absence claim**, no span |
| 8 | backward compatibility | legacy dict validates; defaults `rule`/`unavailable`/`[]` |
| 9 | serialization | `model_dump_json` carries all evidence fields |
| 10 | TC-05 regression | both clause-level and contract-level findings verified against source text |

`uv run --no-sync pytest tests/test_evidence_binding.py -q` → **exit 0, 10 passed**.

## 4. Before/after

| | Baseline | After P2 |
|---|---|---|
| ruff | 0 errors | **0 errors** |
| collected | 71 | **81** (+10) |
| passed | 64 | **74** |
| failed | 7 | **7 — identical set** (`T1a`, `T1b`, `T2a`, `T2b`, `T3a`, `T3b`, `T8`) |

No skips or xfails added; the seven provenance failures remain visible.

## 5. TC-05 observations

- Contract-level findings (`RISK_STAMP_001`, `RISK_TDS_001`, `RISK_S124_001`) now carry an explicit
  `search_scope` and `evidence_status="unverified"` instead of a bare `clause_id=None`.
- Clause-level findings carry the matched clause text with verifiable offsets.
- ML findings on TC-05 are `source="model"`, `evidence_status="unverified"`, `role="contextual"` — they
  cannot be mistaken for evidence-backed rule findings.
- The P1 context bundle is present on clauses but **not consumed** by binding (P2 does not resolve
  cross-references into evidence; that is P3/P4 work).

## 6. Limitations

- Evidence is **clause-granular**, not sentence-granular: the span is the whole clause because the rules
  do not expose which sub-phrase matched. Narrowing it would require changing rule internals (out of scope).
- `evidence_status="direct"` means "the finding's owning clause", **not** "the clause proves the legal
  proposition".
- Contract-level findings are `unverified` by construction; P2 cannot make them traceable without a
  per-rule scope/search-log change.
- Offsets are clause-relative; mapping them back to raw file offsets needs the segmenter's
  `char_start/char_end` (available on `Clause`, not yet joined into `EvidenceSpan`).
- Model confidence remains **uncalibrated**; it is not surfaced as evidence strength.

## 7. Rollback

Delete `tests/test_evidence_binding.py` and this report; revert the three modified files
(`git checkout -- app/models/schemas.py nlp/risk_scoring/rules.py app/services/analyzer.py`). The new
fields are additive with defaults, so reverting the schema alone leaves stored payloads valid.

## 8. Next

P3 (four-way missing-protection status) can now consume `search_scope` + `related_clause_ids`; P4 should
narrow `evidence_spans` to the triggering sentence once rules expose a matched phrase. **P3–P7 remain
untouched.**
