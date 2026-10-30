# BharatContract AI — Zero-Trust Integration Audit

**Audit date:** 30 October 2026
**Audited tree:** commit `c3a6468` on branch `main` (audit artifacts added on top, uncommitted at audit time)
**Mode:** audit-only. No production code was modified. All behavioral claims below were
reproduced by direct execution on the audited tree; nothing is taken from documentation
on trust. Audit-only tests live in `tests/test_audit_integration.py` (14 passing
integration tests + 7 `xfail(strict=True)` defect records). Isolated provenance
investigation was confined to `tmp/audit-rebuild/` (repo-local, gitignored);
`data/processed/` was not read-modified, rebuilt, or deleted.

**Evidence hierarchy used throughout:** (1) direct execution output > (2) source-code
reading with file:line citations > (3) project documentation. Where documents conflict
with execution, execution wins and the conflict is listed in §A.3.

---

## A. Verified repository baseline

### A.1 Git state (executed)

- Branch `main`; HEAD `c3a646831087ee20d376328eb680339a69e613a3`; working tree clean.
- `main` is **ahead of `origin/main` (`5a03a1b`) by 7 commits**, nothing behind.
  Recent history: `c3a6468` docs (obligation fix) → `42b985c` obligation passive/deadline
  fix → `58d279d` docs → `8c60ae6` cross-reference cap fix → `ece750f` merge
  reconciliation → `a1aaf8b`/`aaa9fd5` stamp/TDS fix + docs.
- No stash, no in-progress merge/rebase at audit time; no non-sample git hooks.

### A.2 Reported results vs executed results

| Claim (handoff / final report) | Executed at audit | Verdict |
|---|---|---|
| `ruff check .` clean | "All checks passed!" | Confirmed |
| Full suite: 186 collected, **179 passed, 7 failed** | 186 tests, 7 failures, 0 errors, 0 skipped (junit), ~89 s | Confirmed; the 7 failures are exactly the documented `test_no_leakage.py` set (T1a/T1b/T2a/T2b/T3a/T3b/T8) |
| Eval harness: **17/17, 0 known limitations, 0 regressions**, exit 0 | `cases=17 passing=17 known_limitations=0 regressions=0 resolved=0`, exit 0, 3/3 invariants OK | Confirmed |
| Demo: exit 0, 12 clauses, 13 obligations, 100.0/critical | identical | Confirmed |
| Provenance verifier: 5 failures, 0 skipped | `5 failure(s), 0 skipped`, exit 1 | Confirmed |
| Python 3.12.14 via uv | 3.12.14 | Confirmed |

After adding the audit test file (21 tests): **207 collected, 193 passed, 7 failed
(same provenance set), 7 xfailed**. No existing test was modified, weakened, or deleted.

### A.3 Stale / conflicting documentation found

1. `KIRO_HANDOFF.md` §1 says "6 local commits ahead of `origin/main`"; the actual
   count is **7** (the merge commit `ece750f` is countable). Cosmetic.
2. `KIRO_HANDOFF.md` §6 quotes results "verified at `42b985c`"; the docs commit
   `c3a6468` sits on top. This is the repo's established two-commit convention
   (code commit, then docs commit citing it), noted so future readers do not mistake
   it for drift.
3. Final report §5.2 says the suite runs "in ~70 s"; measured 89 s on this machine.
   Timing only; no content impact.
4. No other conflicts: every substantive number in the handoff, tracker, and final
   report reproduced exactly (§A.2). The documentation discipline is unusually good;
   the audit found no inflated claims.

---

## B. End-to-end architecture and data-flow findings

Traced path (executed with a crafted 5-clause contract through `analyse_bytes`,
plus direct unit-level probes; trace script preserved at `tmp/audit_trace.py`):

```
parse_bytes → parse_document (clean per page/whole text)
  → segment_clauses (cleaned text; positional clause ids; offsets vs cleaned text)
  → resolve_context (references/definitions/precedence candidates)
  → classify_clause (hybrid: letter-boundary keyword rules + heading hints + TF-IDF)
  → extract_entities (regex-first NER)
  → extract_obligations_from_clause (clause-local; conservative)
  → related_clause_texts enrichment (analyzer)
  → apply_rules (clause-gated rules + contract-level rules + dedupe
                 + case-law + evidence binding + advisory cross-ref notes)
  → _augment_with_ml_risks (recall-only, source="model", unverified)
  → score_contract (ordinal heuristic)
```

### B.1 What works and is verified

- **Offsets within the pipeline frame are self-consistent.** All offsets index the
  *cleaned* text; `clean_text` is length-changing (NFKC, smart quotes, line endings)
  but idempotent, so parse→segment sees identical bytes. Obligation spans and rule
  evidence spans are clause-text-relative (`locator="clause_text"`) — three offset
  frames coexist (cleaned-document, clause-text, and raw-bytes-unused) and are
  consistently labelled. The final report documents this accurately.
- **Clause IDs** are positional (`{contract_id}_cNNN`, `_sNN` for splits),
  deterministic, and unique per run. Verified: no collisions within runs.
- **Reference metadata reaches consumers.** The resolver's `references` (with
  `resolved/missing/ambiguous` status) and the analyzer's `related_clause_texts`
  feed both the advisory notes and the fail-closed cap-verification gate. Verified
  end-to-end: a resolved mutual cap suppresses `RISK_LIABILITY_002`; exclusion,
  different-party, missing, and unresolved variants all keep the finding.
- **Obligations** retain conditions ("If a security incident occurs"), exceptions
  ("unless the Customer waives it"), parties ("Processor" via by-agent), beneficiaries
  ("Controller" via recipient verb), and compound deadlines ("24 hours") — verified
  at pipeline level. Agentless passives and non-party agent phrases ("by the data
  processing team") correctly leave the subject `None`. Extraction is clause-local;
  referenced clauses' duties are never imported.
- **State distinction is real, not cosmetic.** Unknown (`subject=None`), ambiguous
  (reference status), unresolved (missing reference → advisory note + finding kept),
  absent ("not found — verify" prompts with `search_scope`, `evidence_status=
  "unverified"`), and confirmed (clause-level findings with `direct` evidence spans)
  are distinguishable in output and enforced by the 3 harness invariants.
- **No rule-layer duplication**: dedupe by `rule_id` holds even with two
  cap-less liability clauses (verified: exactly one `RISK_LIABILITY_002`).
- **No present-vs-missing contradiction**: a classified-but-cap-less LoL clause
  yields `RISK_LIABILITY_002` and never `MISSING_CLAUSE_LIMITATION_OF_LIABILITY`
  (the missing-check is classifier-OR-keyword fail-open, rules are classifier-gated
  fail-closed; the directions interlock for LoL). Guarded by a new audit test.
- **Fail-safety**: per-rule `try/except` in `apply_rules` (a raising rule is skipped,
  other findings survive — tested); full model fallback chain (missing archive →
  pure rule classification); typed parser errors; empty document →
  `DocumentParseError`.

### B.2 Structural observations (not defects, recorded for completeness)

- **Asymmetric detection channels**: mandatory-clause checks use unanchored
  substrings over the corpus ("termination" matches "pre-termination"), while the
  classifier uses letter-boundary regexes, and per-clause rules gate on classifier
  labels. The design errs conservative in both directions (missing-check toward
  "present", rules toward "not evaluated"), so no direct contradiction is produced,
  but a misclassified clause can be invisible to its dedicated rules while counting
  as "present" for the missing-check. Blind-spot surface, not a live contradiction.
- **ML booster vs verified suppression**: when cross-reference verification clears
  `RISK_LIABILITY_002`, the clause counts as "no rule hit" and the ML booster may
  flag it — and may also flag the cap clause itself (observed in the trace: two
  `ML_RISK_001`, high severity). Findings stay `source="model"` + `unverified`
  (invariant holds), so this is a presentation-level tension, not a correctness
  violation — but a reviewer sees the system "clear" and "flag" the same clause.
- **Advisory note duplication**: one missing reference produces both "missing
  reference to 'Section 99'" and "unresolved reference to 'Section 99'" in the same
  note (both lists contain it). Cosmetic.
- **Noise obligations**: "neither party shall be liable for indirect damages"
  extracts an obligation with `subject="neither party", action="liable"` — a
  liability allocation read as a duty. Conservative noise, not a wrong party.
- **Dead fields/code**: `Clause.page_hint` is always `None` (page data dropped at
  the parse→segment boundary); `strip_headers_footers` is never called in the
  pipeline; `_TFIDF_MODEL_LOADED` caches a transient model-load failure for the
  process lifetime.
- **Two contract-id schemes**: the upload route uses a 10-char SHA-256 prefix with
  second-resolution timestamp; `save_upload` derives a 12-char digest. Identical
  bytes uploaded twice in the same second collide on contract_id, hence on every
  clause_id. Low practical impact (ids are caller-scoped), worth aligning.
- **Rule exceptions are swallowed silently** (`try/except: continue`). Fail-safe
  but can hide a rule bug indefinitely; consider logging.

---

## C. Integration defects (severity-ordered, evidence-backed)

Each has an `xfail(strict=True)` record in `tests/test_audit_integration.py`; the
suite goes red the day a fix lands, forcing the record to be updated.

### D2 — Silent text loss in segmentation (HIGH)
A multi-line paragraph whose first line is **not** a heading loses every line after
the first when it leads a clause group: `_trim_heading` keeps only line 1 and
`body = "\n\n".join(buffer[1:])` skips the rest of `buffer[0]`.
Evidence (executed): `"This Agreement is made today.\nIt is between A and B.\n\n1. PAYMENT\n…"`
→ no clause contains "between A and B". Real contracts whose preamble/intro spans
two physical lines silently lose content from all downstream analysis.
Test: `test_d2_segmentation_does_not_lose_preamble_lines`.

### D4 — Negated statutory mentions suppress stamp/TDS review prompts (HIGH for the Indian-law value proposition)
`detect_stamp_duty_mention` / `detect_tds_mention` are pure presence checks. Verified
executed results: "Payments shall be made **without** deduction of tax at source" →
`tds_mentioned=True`; "The Provider is **not** responsible for deducting tax at
source" → `True`; "This Agreement **was not** executed on duly stamped paper" →
`stamp_duty_mentioned=True`. Each suppresses `RISK_TDS_001`/`RISK_STAMP_001` — the
review prompt disappears exactly when the text actively disclaims the protection.
Positive controls verified: genuinely protective mentions still suppress (locked by
`test_applicable_stamp_and_tds_mentions_still_suppress_prompts`). Note the existing
negative controls ("postage stamp", "rubber-stamped") cover *unrelated* senses but
not *negated applicable* senses.
Tests: `test_d4_negated_tds_mention_still_prompts_review`,
`test_d4_negated_stamp_mention_still_prompts_review`.

### D1 — Clause offsets do not slice the source for the most common layout (MEDIUM)
When a heading and its body are separated by a **single** newline (the dominant
real-world layout), the segmenter rebuilds `Clause.text` with a synthetic `\n\n`,
so `cleaned.find(...)` fails and offsets fall back to a cursor that drifts by one
char per such clause. Verified: `text[char_start:char_end] != clause.text` for every
headed clause in the pipeline trace (5/5). In-pipeline findings are unaffected
(evidence spans are clause-relative), but `Clause.char_start/char_end` exposed via
API/graph are wrong for typical documents, and existing tests assert only
monotonicity (`tests/test_long_clauses.py`), never exactness.
Test: `test_d1_clause_offsets_slice_source_for_single_newline_headings`.

### D3 — Long-clause sub-offsets drift systematically (MEDIUM)
Split-clause offset arithmetic assumes `\n\n` separators everywhere and starts from
the heading's offset: sub-clauses of a headed long clause are shifted left by
`len(heading)+2`, with further drift after sentence/fixed splits. Verified: all 3
sub-clauses of a split clause fail the slice test.
Test: `test_d3_long_clause_sub_offsets_slice_source`.

### D5 — Breach-window rule parses digit-only notice periods (MEDIUM)
`rule_data_breach_window` uses `(\d+)\s+(hour|day…)`, so "within twenty-four (24)
hours" is invisible to it — while the obligation layer (now using the shared
`NUMBER_TOKEN_RE`) reports a "24 hours" deadline for the same sentence. Verified:
the crafted contract yields no `RISK_DATA_001` while its obligation carries the
24h deadline. Cross-stage inconsistency; the renewal rule was fixed for the same
pattern (`b35da18`) but this rule was missed.
Test: `test_d5_written_number_breach_window_is_flagged`.

### D6 — Party detection drops legal names containing noise words (LOW-MEDIUM)
`_detect_parties` walks tokens back from the corporate suffix and stops at noise
words, which include **"services"**. "ABC Services Pvt Ltd" is silently discarded
while "ABC Technologies Pvt Ltd" is kept (verified in trace: `parties == ['ABC
Technologies Pvt Ltd']`). Metadata completeness issue (findings unaffected), but
"Services" is among the most common words in Indian company names.
Test: `test_d6_similar_party_names_are_both_detected`.

---

## D. Adversarial test coverage and remaining gaps

Required scenarios → coverage (E = pre-existing unit tests, A = new audit tests):

| Scenario | Coverage | Result |
|---|---|---|
| Cap referenced from indemnity clause with exclusions | A `test_crossref_cap_in_indemnity_clause_with_exclusion_keeps_finding` (pipeline-level; unit-level E in `test_p4_cap_resolution.py`) | finding kept, advisory note present |
| Cap exists but wrong party/loss category | E (unit) + A `test_crossref_cap_for_different_party_keeps_finding` (pipeline) | finding kept |
| Cross-referenced obligation with conditions | A `test_cross_referenced_obligations_stay_clause_local` | clause-local; condition/deadline preserved; nothing imported |
| Passive voice, ambiguous responsible party | A `test_passive_with_non_party_agent_phrase_stays_unknown` + E | subject `None`, never guessed |
| Compound deadline + conditions | A `test_compound_deadline_with_condition_and_beneficiary_preserved` | all fields preserved |
| Stamp/TDS mentions not actually applicable (negation) | A defect records D4 (xfail) | **defect confirmed** |
| Missing-clause evidence / unresolved references | A `test_missing_reference_is_advisory_and_finding_kept` + E | finding kept; note advisory; contract-level findings scoped+unverified |
| Multiple parties with similar defined names | A defect record D6 (xfail) | **defect confirmed** |

**Remaining coverage gaps (honest list):** the 17-case harness has no negation
cases, no written-number breach-window case, no party-noise case, no offset-fidelity
case, no long-document case (>2500 chars), no PDF/DOCX ingestion case (all cases are
TXT via `analyse_bytes`), no auth/RLS interaction case, and no case asserting
*absence* of obligations. Offset exactness has no pipeline-level assertion anywhere
(D1/D3 records are the first). Classifier accuracy has no labelled evaluation at all.

---

## E. Provenance failure diagnosis

**State (executed):** main `data/processed/` holds 5 artifacts dated 2026-10-22 with
the old header `text,category,source` (no `doc_id`/`split` lineage columns) and
**zero** manifests; `clause_classifier.csv` has 11,508 rows. The verifier
(`scripts/verify_provenance.py`) requires two layers per artifact: (1) a
`<artifact>.manifest.json` with source hashes + split identity, and (2) row-level
lineage (`doc_id`/`split` per row against hash-pinned approved sources in
`nlp/datasets/splits.py`). The 7 failing tests decompose as: 5× manifest-missing
(T1a/T2a/T3a×2/T8), 1× manifest-content (T2b), 1× lineage (T1b — all 11,508 rows
have empty `doc_id`/`split`, i.e. "non-train split" by construction).

**Isolated investigation (no production data touched):** an isolated rebuild at the
audited HEAD into `tmp/audit-rebuild/` (gitignored) via
`uv run python scripts/build_training_data.py --out-dir tmp/audit-rebuild` produced
5 artifacts + 5 manifests; the verifier reports **0 failures** on it (9,278 CSV rows
with valid train lineage; 22,450/32,580/55,030 JSONL rows). The isolated build is
**byte-identical** to the existing `data/processed.staging/` (SHA-256 compared, all
5 artifacts), and `data/processed.staging/` itself verifies with 0 failures.

**Conclusion:** stale generated data, fully consistent with the tracker's prior
diagnosis. Not an environment problem (the build reproduces deterministically on
this machine), not a code defect (current code produces compliant artifacts), not a
genuine provenance breach (no evidence of held-out contamination — the old artifacts
simply predate the lineage machinery; their *unverifiability* is the issue, and the
guards correctly fail closed). A clean isolated build reproduces the expected
artifact+manifest structure exactly. Remediation is an approval-gated rebuild or
staging swap (§H); the guards were not weakened, and `data/processed/` was not
modified in any way during this audit.

---

## F. Evaluation and research-readiness assessment

### F.1 What is measured today
The 17-case synthetic harness measures **behavioral conformance**: per-case expected
rule IDs present/absent, severity calibration on one axis (renewal notice),
obligation slot checks (subject/counterparty/condition/deadline on 4 cases), and 3
global evidence-integrity invariants. It is deterministic, fail-closed (lock test
prevents silent regressions and silent "fixes"), and honest about its limits in its
own header. The 186-test suite adds component-level regression locking. This is a
good *engineering* verification posture.

### F.2 What is not measured (gap vs the report's claims)
The final report is careful not to claim accuracy — and the audit confirms no such
claim appears. For research readiness, the following are currently **unmeasured**:
clause-classification precision/recall per label; NER precision/recall; obligation
slot-level F1 (subject/action/condition/deadline/beneficiary); evidence-span
exactness (the invariants check span *presence*, not correctness — and §C/D1 shows
document-level offsets are wrong for the dominant layout); cross-reference resolver
accuracy (resolution recall/precision vs a gold reference set); severity calibration
against human judgment; abstention quality (how often "unverified/verify" is the
right call); end-to-end robustness on PDF/DOCX/scanned inputs.

### F.3 What a research-grade evaluation needs
- **Metrics per component**: per-label P/R/F1 (classification, NER), slot-F1
  (obligations), span-exact match rate (evidence/offsets), resolver
  precision/recall, severity agreement (weighted kappa), and calibration error if
  any score is ever presented numerically. Rule-level confusion reporting, never a
  single aggregate "accuracy".
- **Dataset**: a pre-registered, versioned corpus mixing (a) licensed public
  contracts (CUAD is bundled; MAUD is bundled — **neither carries a LICENSE file in
  this repo**, so upstream licence terms must be verified and recorded before any
  redistribution or publication), and (b) Indian-law-specific contracts (stamp
  duty/TDS/S124/seat-venue phenomena are absent from CUAD's taxonomy).
- **Annotation**: a written annotation guide; dual annotation by legally qualified
  annotators; adjudication; retention of per-annotator labels (not just gold) so
  disagreement is measurable.
- **Leakage control**: keep the current document-level (title) split with
  hash-pinned lineage manifests — the machinery is good (T1d proves train/held-out
  document disjointness). Extend it: near-duplicate analysis must stay report-only
  (T1c correctly does not assert); any future benchmark must use group-by-document
  splitting and never the bundled models' training corpus (already flagged
  `provenance-unverified` — the audit confirms no generalization claim is made).
- **Human legal review**: report inter-annotator agreement (Cohen's kappa pairwise,
  Fleiss' for >2), publish disagreement classes (legal-interpretation vs
  language-ambiguity vs annotator error), and evaluate the system against the
  *adjudicated* gold with abstention-aware scoring.
- **Uncertainty representation**: the system's current vocabulary (unverified,
  search_scope, "may — verify", known limitations, `None` parties) is the right
  substrate; a research evaluation should score whether uncertainty is *calibrated*
  (does "verify" correlate with actual ambiguity?), per the P3 status-design note.

**Bottom line:** 17 synthetic single-author cases with engineered expectations are
necessary and sufficient for *regression control* — and the audit verified they all
pass — but they evidence nothing about accuracy, recall, or legal correctness. The
report already says this; the audit independently confirms the claim is accurate and
that no document overstates it.

---

## G. Prioritised remediation plan

1. **D4 — negation-aware statutory detection** (protects the core Indian-law value
   proposition): add a narrow negation window ("not", "without", "no … shall be
   responsible for") around matched stamp/TDS phrases, with the existing positive
   controls locked. Moderate care needed to avoid suppressing genuine mentions.
2. **D2 — preamble text loss**: in `_group_paragraphs_into_clauses.flush`, join
   remaining lines of a group-leading multi-line item into the body instead of
   dropping them. Small, well-scoped; flip `test_d2`.
3. **D1 + D3 — offset fidelity**: stop reconstructing clause text synthetically for
   offset lookup (locate heading and body spans independently, or record spans
   during grouping); make long-clause splitting span-based. Add slice-exactness
   tests (the D1/D3 records flip red→green).
4. **D5 — breach-window written numbers**: use the shared `NUMBER_TOKEN_RE` in
   `rule_data_breach_window` (mirrors the renewal fix pattern); add digit/written
   parity tests.
5. **D6 — party noise-word over-truncation**: only treat "services" (etc.) as noise
   when removing it still leaves a valid name, or whitelist noise-stripping to
   heading contexts.
6. **Low priority**: de-duplicate advisory-note reference wording; align the two
   contract-id digest lengths; log (not silently swallow) rule exceptions; decide
   the ML-vs-verified-suppression presentation policy; populate or remove
   `page_hint`; remove or wire `strip_headers_footers`.
7. **Approval-gated**: rebuild/swap `data/processed/` (reproducibility proven in §E;
   staging is byte-identical to a fresh isolated build).
8. **Research track**: pre-registered labelled corpus + per-component metrics per §F.3.

## H. Items explicitly requiring your approval

1. **Rebuild or swap `data/processed/`** (from `scripts/build_training_data.py` or
   the byte-identical `data/processed.staging/`). Not done. Evidence for the
   decision is in §E; the isolated build directory `tmp/audit-rebuild/` is retained
   for inspection (gitignored).
2. **Whether to schedule the D1–D6 fixes** as the next milestone(s). The defect
   records are in place; fixing flips them to XPASS(strict)→red, which is the
   intended signal to update them to permanent tests.
3. **Model retraining / artifact replacement** remains gated as before; nothing in
   this audit touched models.
4. **Push to remote**: not performed; the branch is 7 local commits ahead plus this
   audit's documentation commit.

---

## Audit scope and limitations (for honesty)

- PDF/DOCX/OCR ingestion paths were read but not exercised with binary fixtures;
  the trace and probes use the TXT path (`analyse_bytes`), which is what the
  evaluation harness uses.
- Neo4j/PostgreSQL were not exercised live (graceful-degradation design makes them
  no-ops locally); API behavior was assessed via existing smoke tests and code reading.
- The audit ran on a single Windows machine; path/line-ending behavior elsewhere
  was not verified.
- The two context-gathering sub-investigations (parser/segmenter internals,
  classifier internals) were used for orientation; every load-bearing claim in this
  report was independently re-verified by direct execution before inclusion.
