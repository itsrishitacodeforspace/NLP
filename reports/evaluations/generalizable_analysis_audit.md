# Generalizable Analysis Audit — Stage A (baseline) + Stage B (patch proposal)

**Status:** Stage A complete; Stage B proposal only. **No application code changed.**
**Date:** 2026-10-26 · **Baseline:** `main` @ `cbd9c29` · worktree unchanged (15 modified + 6 untracked-new from the provenance workstream; no staging/commit).
**Fixture used as ONE diagnostic, not a template:** `uploads/c_20261026_134911_fc805c301d8d_TC-05_cross_reference_traps.md` (synthetic; header declares all parties fictional).

---

## 1. Executive summary

The pipeline is a strong **per-clause** analyser with no **whole-contract reasoning**. Every material failure observed below traces to one of four root causes:

1. **No cross-reference resolution** — clauses are scored in isolation, so a qualifier in another clause ("Notwithstanding Clauses 7.1 and 7.2 … shall not exceed the Cap") is invisible. This produces **both** false positives and false negatives on the same document.
2. **No evidence binding for contract-level findings** — stamp-duty/TDS/§124 findings carry `clause_id=None`; there is no passage, no offsets, no recorded search scope.
3. **Keyword-presence proxies** for "is this protection present?" — a heading, a defined term, or a mention anywhere in the corpus counts as presence.
4. **Obligation field extraction is under-specified** — headings and preceding text leak into `subject`, deadlines written in words are missed, and `action` can be `None`.

These are general defects, not fixture quirks. Fixes below are deterministic, offline, and introduce no new dependency.

**Recommendation:** implement the **context-resolution layer (A)** + **finding evidence binding (B)** first; they unlock trustworthy severities and make missing-protection work measurable. Obligation fixes (F) are low-risk and independent.

---

## 2. Current pipeline and source-file map

```
parse            app/services/parser.py
  → segment      app/services/segmenter.py        (Clause dataclass: clause_id, offsets, heading, metadata)
  → classify     nlp/clause_classification/classifier.py
                     classify_clause:207  (rule + TF-IDF hybrid)
                     _rule_classify:383   (keyword bank; Miscellaneous fallback:402)
                     load_cuad_keyword_bank:259, auto-load at import:336
  → NER          nlp/ner/ner.py
  → obligations  nlp/obligation_extraction/extractor.py
                     _analyse_sentence / _extract_subject / _extract_action_object / _extract_deadline
  → risk rules   nlp/risk_scoring/rules.py
                     apply_rules:368 · _contract_level_rules:422 · text_corpus:428
                     mandatory_checks:430 · keyword_present:437 · synthetic clause:470
                     RiskFlag creation sites: 75,92,115,151,170,200,227,258,279,301,322,440,458
  → ML booster   app/services/analyzer.py:213 _augment_with_ml_risks (called at analyser:162)
  → score        nlp/risk_scoring/scorer.py
  → output       app/models/schemas.py (Clause, RiskFlag, AnalysisResult)
```

**The orchestrator never builds a document graph.** `app/services/analyzer.py` `_analyse` iterates `for raw in raw_clauses:` and immediately classifies/extracts per clause; `apply_rules(clauses, summary)` receives a flat list. Nothing resolves "Clause 7.4", "Schedule 2", "Clause 1.3 (Cap)" or precedence rules (`Clause 1.7`).

---

## 3. Baseline test results (actual)

`uv run --no-sync pytest -q` → **exit 1**, **61 collected, 54 passed, 7 failed**.

The 7 failures are the provenance guards on the **unswapped production** artifacts (`T1a`, `T1b`, `T2a`, `T2b`, `T3a`, `T3b`, `T8`) — `manifest missing` / the un-lineaged production corpus. They are pre-existing and unrelated to analysis quality; they must not be "fixed" by this workstream.

`uv run --no-sync ruff check .` → **exit 0**.

---

## 4. Ranked root-cause findings (with evidence)

| # | Finding | Evidence (file:line / observed) | Confidence |
|---|---|---|---|
| **R1** | **No cross-reference or precedence resolution.** Each clause is scored independently; `analyzer._analyse` loops clauses and `rules.apply_rules` only sees the flat list. | `app/services/analyzer.py` `_analyse` loop (~112-135); `nlp/risk_scoring/rules.py:368` | **Confirmed** |
| **R2** | **Liability-cap rule is single-clause and direction-blind.** `rule_uncapped_liability` inspects only `clause.text` for cap language; a cap defined elsewhere is invisible. On TC-05 it emitted **`RISK_LIABILITY_002` "Missing liability cap" (high)** although Clause 7.4 caps liability at "the Cap" (defined in 1.3) — and attached it to `tc05_c003` (the Definitions clause), not the liability clause. | observed output; `rules.py:75,92` (flag sites) | **Confirmed** |
| **R3** | **Contract-level findings have no evidence.** `RISK_STAMP_001`, `RISK_TDS_001`, `RISK_S124_001` all emitted with `clause_id=None`; `RiskFlag` has no `evidence`/`char_start`/`search_scope` field. | observed output; `app/models/schemas.py` `RiskFlag` fields | **Confirmed** |
| **R4** | **Missing-protection is corpus keyword presence.** `_contract_level_rules` builds `text_corpus` (`:428`) and tests `keyword_present = any(k in text_corpus …)` (`:437`); a defined term or an unrelated mention counts as "present". | `rules.py:428,430,437` | **Confirmed** |
| **R5** | **ML booster is unattributed and uncalibrated.** Two `ML_RISK_001` findings (high) on TC-05 with no rule basis, no span, and no exposed confidence; severity is derived from a predicted class, not evidence. | observed output; `analyzer.py:213-…` | **Confirmed** |
| **R6** | **Obligation subjects capture headings/prose; deadlines in words are missed.** Observed subjects: `"TERM AND RENEWAL 3.1 The initial Subscri"`, `"FEES AND PAYMENT 4.1 The Customer"`, `"LIABILITY 7.1 The Provider's liability t"`; one row had `action=None`; `deadline=None` throughout even where "within thirty (30) days" appears. | observed output; `nlp/obligation_extraction/extractor.py` `_extract_subject`, `_extract_deadline`, `DEADLINE_RE` (digit-only) | **Confirmed** |
| **R7** | **Heading/section text inflates clause classification.** The Definitions clause was labelled `['Limitation of Liability','Payment Terms','Definitions','Term and Renewal']` and received the liability finding. | observed output; `classifier._rule_classify:383` (no heading/body separation) | **Confirmed** |
| **R8** | **Legal claims presented without qualification.** Stamp-duty/TDS/"§124 gap" are emitted as critical/medium findings for a SaaS agreement with `clause_id=None`; no source identity, passage, jurisdiction or verification date is attached. | observed output; `nlp/risk_scoring/case_law.py` (citation+summary+jurisdiction only) | **Confirmed** |
| **R9** | **Genuine signal missed on the same document.** Clause 7.1 says liability "shall be unlimited"; the trigger list requires the exact phrase "unlimited liability", so `RISK_LIABILITY_001` did **not** fire — while the *opposite* finding did (R2). | observed output; `rules.py` `rule_uncapped_liability` trigger list | **Confirmed** |

---

## 5. Examples by failure class

**(A) Cross-reference / precedence.** Clause 7.4 (`Notwithstanding Clauses 7.1 and 7.2 … shall not exceed the Cap`) overrides 7.1/7.2 unlimited liability; `Cap` is defined in 1.3 by reference to Schedule 2; Clause 1.7 states body prevails over Schedules **except Fees, where Schedule 2 prevails** — creating a real conflict between Clause 4.1 ("within thirty days") and Schedule 2 ("Net 90 days"). The system resolves none of this. *(Also: 3 similar traps — 1.4 `Excluded Liabilities` → Clauses 8 & 9.1; 10.2 → 10.4; 11.2 carve-out → Schedule 3.)*

**(B) Evidence.** Supported by observation: three contract-level findings with `clause_id=None`; `RiskFlag` has no span field at all; nothing records what was searched.

**(C) Missing protection.** `missing_clauses` was `[]` on TC-05 — correct here, but the mechanism cannot distinguish "present via Schedule" from "present only as a heading/defined term" (R4). The general risk is symmetrical: a Schedule-based protection would be reported missing, and a defined term would suppress a real absence.

**(D) Rule precision.** R2/R9: one rule family produced a *false positive* and *missed a true positive* on adjacent clauses of the same document.

**(E) ML booster.** R5: model-only findings with no evidence and no confidence surfaced at `high`, indistinguishable in the report from evidence-backed rule findings.

**(F) Obligations.** R6: malformed subjects, a null action, and no deadlines.

**(G) Legal grounding.** R8: critical stamp-duty/TDS/§124 findings without sources or qualification.

---

## 6. Proposed generalizable fixes (Stage B) and alternatives

**P1 — Lightweight deterministic context-resolution layer (addresses A, and enables B/C/D).**
- New module `nlp/context/` (no dependency): after segmentation, build an index of `section_number → clause_id`, definitions (`"X" means …`), schedules (`## SCHEDULE n`), and explicit precedence sentences (`Notwithstanding …`, `… prevails`, `subject to …`).
- Resolve references (`Clause 7.4`, `Clauses 7.1 and 7.2`, `Schedule 2`, `Schedule 3`) to `clause_id`s; attach `related_clause_ids`, `resolved_references`, `unresolved_references` to each `Clause`.
- Detect **explicit overrides**: a clause containing `notwithstanding`/`prevails`/`subject to` that names another clause is marked as *overriding* it, so rules can suppress/qualify the overridden finding **and say so**.
- Flag unresolved/circular/ambiguous references rather than guessing.
- *Alternative considered:* LLM-based coreference — rejected (new dependency, non-deterministic, unverifiable).

**P2 — Evidence binding on every finding (B).**
- Add `evidence`, `char_start`, `char_end`, `search_scope`, `related_clause_ids`, `evidence_strength` to `RiskFlag`; populate at all 13 creation sites (`rules.py:75…458`). Contract-level findings must carry `search_scope` (which clauses/keywords were consulted) and never a fabricated span.
- Severity stays separate from `evidence_strength`.

**P3 — Missing-protection: four-way status (C).**
- Replace `keyword_present` (`rules.py:437`) with a clause-aware check: exclude definitional/`means` constructs and negations; credit provisions found in schedules; emit `present | incomplete | not_found_in_scope | undetermined` plus the search scope and synonyms tried. "Not found" never implies illegality.

**P4 — Rule precision pass (D).**
- Audit the 10 registered rules for cross-clause qualifications (consume P1), fix the `"unlimited liability"` phrasing gap (R9), stop attributing findings to a clause that merely *mentions* the topic (R2/R7).

**P5 — ML booster separation (E).**
- Emit `source="model"` findings with confidence exposed and `evidence_strength="model-only"`; never at `critical`; measure incremental value via the existing ablation (artifact removal), no retraining.

**P6 — Obligation fields (F).**
- Strip heading prefixes from `subject`; extend `DEADLINE_RE` to number words (`thirty (30) days`); leave fields `None` + `unresolved_fields` rather than guessing.

**P7 — Legal grounding (G).**
- Attach source metadata / "unverified" status from `case_law.py`; downgrade or abstain when unsupported; stop asserting stamp duty/TDS are universally required.

**Rollback:** each patch is module-local with feature flags defaulting to current behaviour; `git checkout -- <file>` per module (no commits made).

---

## 7. Evaluation design and metrics (defined before thresholds)

**Corpus.** Existing fixtures first (`data/raw/sample_msa.txt`); TC-05 as **one** example; plus a small, hand-built set (~12–20 synthetic docs, provenance recorded as *synthetic*) covering: cross-references that change/don't change meaning; definitions and exceptions; conflicts with and without precedence; schedule-located protections; missing/broken/circular/ambiguous references; synonym-drafted protections; true and false missing-protection cases; ≥2 contract types. **No tuning on the held-out portion.**

**Metrics (report denominators + per-category):**
- Risk: precision/recall per rule, FP/FN counts, severity agreement, evidence-span correctness, supporting-passage completeness.
- Context: reference-resolution accuracy; override-detected correctness; unresolved-reference handling.
- Missing protection: 4-way classification quality vs hand labels.
- Obligations: field-level exact/partial accuracy (actor, action, object, condition, deadline) + span alignment.
- Abstention/uncertainty behaviour; ML-booster incremental delta (same set, artifact on/off).
- **No aggregate "accuracy" score** — labels are too few.

---

## 8. Risks, limitations, unresolved questions

- Hand labels will be **single non-expert reviewer** → technical, not legal, validation.
- Synthetic corpus may over-fit to the author's expectations; results are indicative.
- `CaseLawReference` sources are **unverified** against primary sources → must stay qualified.
- Adding `RiskFlag` fields is backward-compatible JSON but changes persisted job payloads; Neo4j `upsert_risk` will not store them until updated (follow-up).
- Obligation `action` for "shall be unlimited" is semantically ambiguous — field model may need a `predicate` vs `object` split; open question.
- Pre-existing 7 provenance failures remain and are **out of scope** here.

---

## 9. Files inspected / files changed

**Inspected (read-only):** `README.md`, `pyproject.toml`, `AGENTS.md`, `plan.md`, `app/main.py`, `app/services/analyzer.py`, `app/services/segmenter.py`, `app/services/parser.py`, `app/models/schemas.py`, `nlp/clause_classification/classifier.py`, `nlp/clause_classification/tfidf_model.py`, `nlp/obligation_extraction/extractor.py`, `nlp/risk_scoring/rules.py`, `nlp/risk_scoring/scorer.py`, `nlp/risk_scoring/case_law.py`, `nlp/ner/ner.py`, `scripts/eval_classifier.py`, `scripts/verify_provenance.py`, `tests/*`, `uploads/c_20261026_134911_fc805c301d8d_TC-05_cross_reference_traps.md`.

**Changed:** this report only (`reports/evaluations/generalizable_analysis_audit.md`). **No application code, tests, data, artifacts, or models modified.**

---

## 10. Recommendation

Implement in this order, each as a separately approved, test-first change:

1. **P1 context-resolution layer** (unblocks correctness of severity; highest value).
2. **P2 evidence binding** (makes every finding auditable; prerequisite for honest reporting).
3. **P3 four-way missing-protection status** (depends on P1 for schedule lookups).
4. **P6 obligation fields** (independent, low risk).
5. **P4 rule precision**, **P5 ML separation**, **P7 legal grounding** last, each measured against the same examples.

Do not begin until the evaluation corpus and metrics above are approved.
