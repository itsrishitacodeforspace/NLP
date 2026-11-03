# Risk Quality Workstream — 2026-11-03

> Subagent session: BharatContract AI NLP risk-quality improvements (charter §5.A/§5.B/§5.C).
> Branch: `main`, base HEAD `f0bad0a`. All commits local-only (never pushed).

## Summary of changes

### 1. Finding Explanation Enrichment (charter §5.A)

**Schema additions** (all additive, `Optional` with `None` default — old payloads deserialize):

`RiskFlag`:
- `impact_summary: Optional[str]` — one sentence on the practical consequence.
- `affected_parties: Optional[List[str]]` — party names from `ContractSummary.parties` or role nouns.
- `review_action: Optional[str]` — concrete suggested next review step.
- `uncertainty_note: Optional[str]` — what remains uncertain after the automated check.
- `related_clause_ids` was already present; now populated from the context resolver.

**Population logic per rule** (`nlp/risk_scoring/rules.py`):

| Rule | affected_parties logic | uncertainty_note |
|---|---|---|
| RISK_LIABILITY_001 | Role noun in the trigger sentence; falls back to "both parties" | "Negation and scoping in other clauses were not analysed" |
| RISK_LIABILITY_002 | "both parties" (mutual) | Phrase-based search note + "cap may be in different wording" |
| RISK_TERM_001 | Role noun in trigger sentence | "Other sub-clauses may balance this right" |
| RISK_RENEWAL_001 | "both parties" | "Notice period read from this clause only" |
| RISK_INDEMNITY_001 | Role noun in trigger sentence | "Cap or exclusion clauses may narrow this indemnity" |
| RISK_DATA_001 | Role noun in trigger sentence | "Related data-protection terms may set different procedure" |
| RISK_GOV_001 | "both parties" | "Jurisdiction reading based on extracted phrase" |
| RISK_ARB_001 | "both parties" | "Seat/venue detected by keyword heuristics" |
| RISK_STAMP_001 | "both parties" | Phrase-based + "stamping is handled at execution" |
| RISK_TDS_001 | Role noun in clause text | Phrase-based + "applicability depends on payment type" |
| RISK_S124_001 | Role noun in clause text | "Other clauses may allocate these losses differently" |
| MISSING_CLAUSE_* | "both parties" | Phrase-based + "protection may be expressed differently or in an annex" |
| RISK_DATA_MISSING | "both parties" | Phrase-based + "may be in an annexure (e.g. policy attached as annex)" |
| RISK_CONFLICT_001 | "both parties" | "Amounts may cover different scopes the detector could not distinguish" |

**Contract-level rules** use the existing `evidence_status="unverified"` + `search_scope` pattern; `uncertainty_note` always states that the check is phrase-based and the protection may be expressed differently or located in an annex.

**Not populated** (by design, never fabricated): ML booster findings (`source="model"`) — they are recall suggestions, not rule findings.

### 2. Obligation Field Completeness (charter §5.B)

**Schema addition**: `Obligation.frequency: Optional[str] = None`.

**Extractor changes** (`nlp/obligation_extraction/extractor.py`):

- **Frequency**: tight regex `_FREQUENCY_RE` matches monthly/quarterly/annually/weekly/biannually/bi-annually/semiannually/semi-annually/daily/yearly + `per|every` + (month|quarter|year|week|day|annum). Normalised via `_FREQUENCY_NORMALISE`. Vague cadences ("periodically", "as needed") → `None`.
- **Beneficiary fix**: when `_DOUBLE_OBJECT_RE` finds the action verb but the first dative party is the *subject* (self-reference), the extractor now checks whether the rest of the tail contains a `for|against|of <subject>` pattern. If so, the self-referential party is returned (it is still the beneficiary). This fixes "indemnify the Customer against the Customer's losses".
- **Known limitation documented**: "indemnify and hold harmless the Customer" — the compound verb form does not extract the counterparty (the dative party follows "hold harmless", not the action verb). Locked by `test_compound_indemnity_compound_verb_is_known_limitation`.
- **Dedup**: `extract_obligations_from_clause` now tracks `(subject, action, object, condition)` per clause and silently drops exact duplicates (boilerplate restatements). Distinct obligations are both kept.
- **Deadline vs duration**: verified — no deontic modal → no obligation emitted, no deadline fabricated. "The initial term of this Agreement is 90 days." → `[]`.

**Tests added** (`tests/test_obligation_extraction.py`):
- `test_beneficiary_is_recipient_when_self_reference_follows`
- `test_beneficiary_recipient_in_compound_indemnity` (single-verb form)
- `test_compound_indemnity_compound_verb_is_known_limitation`
- `test_beneficiary_none_when_no_explicit_recipient`
- `test_condition_captured_on_material_breach_trigger`
- `test_condition_captured_on_if_fails_to_pay`
- `test_frequency_monthly/quarterly/annually/biannually/per_month/per_annum/weekly`
- `test_no_frequency_when_none_present`
- `test_no_frequency_for_vague_cadence`
- `test_passive_agent_in_prepositional_phrase_is_subject`
- `test_exact_duplicate_obligations_within_clause_are_deduped`
- `test_distinct_obligations_in_same_clause_are_both_kept`
- `test_deadline_not_extracted_from_bare_duration_without_modal`
- `test_deadline_only_from_deontic_sentence`
- `test_repeated_sentences_leave_offsets_unknown` (adapted: exact duplicates are deduped)
- `test_repeated_distinct_sentences_with_ambiguous_offsets`

### 3. Missing-Protection False Positives (charter: "not found" ≠ "absent")

**Findings**:
- `RISK_DATA_MISSING` was **unreachable**: `"personal data"` was in the `has_dp` phrase list, so any contract mentioning personal data was treated as having a data-protection clause. **Fixed**: removed `"personal data"` from `has_dp`; it remains in the *trigger* condition (`mentions_personal_data`). A genuine data-protection clause must say something about *protecting* the data.
- The segmenter **does** include annexure/schedule headings as clauses (ALL-CAPS headings like "SCHEDULE 1: FEES" or "ANNEXURE 2: DATA PROTECTION POLICY" are detected as clause headings). The search scope is therefore genuinely document-wide.
- Known limitation documented by `test_data_missing_fires_when_only_guarantee_phrase_present`: a clause phrased as "guarantee the security of Personal Data" (no searched phrase, no classifier label) still triggers `RISK_DATA_MISSING`. The `uncertainty_note` explicitly says the protection "may be expressed differently or located in an annexure".

**Changes to `_contract_level_rules`**:
- `search_scope` now states "document-wide phrase-based search across N clause(s), including M annexure/schedule clause(s)".
- All `MISSING_CLAUSE_*` and `RISK_DATA_MISSING` findings now carry `impact_summary`, `affected_parties`, `review_action`, and `uncertainty_note` with the phrase-based/annexure honesty note.

### 4. Cross-Reference Contradiction Detector (charter §5.C)

**Rule**: `RISK_CONFLICT_001` (HIGH, contract-level, `evidence_status="direct"` with both clauses' spans).

**Detection logic** (`rule_contradictory_liability_caps`):
- Scans each clause for sentences matching `_LIABILITY_CAP_CONTEXT_RE` (liability + cap/limit/maximum/shall not exceed/in aggregate).
- Extracts money amounts via `_MONEY_RE` (INR/USD/EUR/GBP + lakh/crore units).
- Normalises: `INR 5 lakh` → 500,000; `INR 50 lakh` → 5,000,000.
- **Abstains** on: same clause, different currencies, equal values, scope words (per incident/per claim/per year/per annum) in either sentence.
- Fires once per contract on the first conflicting pair found.

**Precision evidence**:
- Ran on all 6 `data/raw/*.txt` samples: **0 false positives**.
- Synthetic positive: two clauses with `INR 5,00,000` vs `INR 10,00,000` in cap contexts → fires.
- Synthetic negatives (all pass):
  - Equal amounts → abstains.
  - Fee (not cap) + cap → abstains.
  - Per-incident scope + aggregate → abstains.
  - Different currencies (USD vs INR) → abstains.
  - Single cap (only one clause with cap language) → abstains.

**Settings flag**: the detector is gated **ON by default** (no settings flag added) because the zero-false-positive result on all bundled samples meets the charter's precision bar. The rule is registered in `_contract_level_rules` unconditionally; it is inherently conservative (abstains on any ambiguity).

### 5. Score Explainability

**Schema additions** (`ContractSummary`):
- `risk_score_breakdown: Optional[Dict[str, Any]] = None`
- `score_caveat: Optional[str] = None`

**`score_contract` signature change**: returns `(score, level, breakdown)` instead of `(score, level)`. The breakdown dict contains:
- `"top"`, `"volume"`, `"severity_mass"`, `"cap_adjustment"` (floats; sum == score)
- `"findings_by_severity"` (dict of severity label → count, int values)

**Call sites updated**:
- `app/services/analyzer.py`: unpacks 3-tuple, populates `summary_draft.risk_score_breakdown` and `summary_draft.score_caveat = SCORE_CAVEAT`.
- `tests/test_risk_rules.py`: 3 existing tests updated to unpack 3-tuple.

`SCORE_CAVEAT` constant in `scorer.py`: "Score is a prioritization aid derived from rule findings and their severities, not a probability and not a legal assessment." Always set by the analyzer.

## Files changed

| File | Change |
|---|---|
| `app/models/schemas.py` | Additive: `Obligation.frequency`, `RiskFlag.impact_summary/affected_parties/review_action/uncertainty_note`, `ContractSummary.risk_score_breakdown/score_caveat` |
| `nlp/risk_scoring/rules.py` | Enrichment population on all rules; `RISK_CONFLICT_001` detector; `RISK_DATA_MISSING` fix (personal data removed from has_dp); missing-clause honesty notes |
| `nlp/risk_scoring/scorer.py` | `score_contract` returns 3-tuple; `SCORE_CAVEAT` constant |
| `nlp/obligation_extraction/extractor.py` | `frequency` extraction; beneficiary self-reference fix; exact-dedup within clause |
| `app/services/analyzer.py` | Unpack 3-tuple; populate `risk_score_breakdown` + `score_caveat` |
| `tests/test_risk_quality.py` | **New**: enrichment, contradiction, score explainability, missing-clause honesty tests |
| `tests/test_obligation_extraction.py` | 16 new tests (frequency, beneficiary, dedup, deadline-vs-duration) |
| `tests/test_risk_rules.py` | 3 existing scoring tests updated for 3-tuple return |
| `obligation_extraction/extractor.py` | `cp` from `nlp/` (byte-identical) |
| `risk_scoring/rules.py` | `cp` from `nlp/` (byte-identical) |
| `risk_scoring/scorer.py` | `cp` from `nlp/` (byte-identical) |

## Deliberately NOT done

1. **Streamlit risk card** (`streamlit_app/components/risk_card.py`): another agent's file. The new fields are additive and simply not displayed until a later UI pass — by design.
2. **Settings flag for RISK_CONFLICT_001**: the detector is conservative enough (abstains on any ambiguity) that a flag would add configuration surface without a precision benefit. Zero false positives on all bundled samples was the bar, and it was met.
3. **ML booster enrichment**: ML findings (`source="model"`) are recall suggestions, not rule findings. Enriching them would imply a precision the model does not have.
4. **Compound "indemnify and hold harmless" counterparty**: the regex does not scan after "hold harmless" for the dative party. Documented as a known limitation; fixing it requires adding "hold harmless" to the dative-verb vocabulary, which is a broader change than this workstream's scope.
5. **Per-clause evidence span refinement** (audit §2.1: "evidence spans bind the whole clause, not the trigger"): `_tight_span` already binds the trigger *sentence* when `evidence_text` is set. The remaining gap (sub-sentence precision) is a separate improvement.

## Verification

```
uv run pytest tests/test_risk_quality.py tests/test_obligation_extraction.py \
  tests/test_context_resolution.py tests/test_no_stale_duplicates.py \
  tests/test_risk_rules.py tests/test_evidence_binding.py -q
→ 144 passed

uv run pytest tests/ -q
→ all passed (0 failures)

uv run ruff check nlp/obligation_extraction/ nlp/risk_scoring/ \
  app/models/schemas.py app/services/analyzer.py \
  tests/test_risk_quality.py tests/test_obligation_extraction.py
→ All checks passed

uv run python scripts/run_demo.py
→ runs successfully
```
