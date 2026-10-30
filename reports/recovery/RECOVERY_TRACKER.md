# Recovery Tracker — BharatContract AI

Last updated: 2026-10-29

## State
- Branch `main`; verification baseline `97f4c21` (14 local commits ahead of
  `origin/main` `a1b4298`). This docs-only update follows that baseline. Nothing pushed.
- Clean verification worktree: repo-local `tmp/bcc-clean-97f4c21` at `97f4c21`.
  Main-tree user WIP remains uncommitted and untouched.
- Historical fresh-checkout validation: `tmp/freshcheckout` at `118e8ae` (superseded by the
  current clean run below).

## Commits this session
- `66684a1` fix(tests): ship TC-05 synthetic fixture for fresh-checkout reproducibility
- `8bbbe47` chore: remove committed .ua scratch and gitignore it
- `ae55c59` docs: document data/processed regeneration for fresh clones
- `c2df667` test(provenance): assert source lineage, not exact-text overlap, in T1b
- `fe75ef2` fix(risk): don't treat indemnification clauses as limitation-of-liability
- `e2468c8` fix(risk): mark stamp-duty and TDS "not found" as review, not confirmed defect
- `3ec86b6` fix(risk): qualify S124 indemnity finding and document scoring heuristic
- `d6e3f69` feat(risk): add advisory cross-reference analysis to findings
- `118e8ae` fix(obligations): populate deadline_date, handle passive voice, written-out deadlines
- `0cf396a` fix(obligations): add source offsets, conditions, beneficiary; clarify ML score
- `975512b` fix(risk): scope S124 check to indemnity clauses
- `f1bf4f4` docs(recovery): record S124 scope fix and current verification
- `be51191` docs: add final project report

## Verified clean workflow — current HEAD (2026-10-29)
Starting HEAD: `97f4c21`. Worktree: repo-local `tmp/bcc-clean-97f4c21`.

1. `uv sync --extra dev` → exit 0 (154 packages, Python 3.12.14)
2. `uv run ruff check .` → "All checks passed!"
3. `uv run python scripts/build_training_data.py` → exit 0; 9,278 rows, 5 manifests
4. `uv run python scripts/verify_provenance.py` → **0 failures, 0 skipped**
5. `$env:BCC_EVAL_MODE='ci'; uv run pytest -q` → **exit 0** (129 tests at HEAD)
6. `uv run python scripts/run_demo.py` → exit 0 (12 clauses, 13 obligations, score 100.0/critical)
7. API smoke: `tests/test_api_smoke.py` passed in the full suite. A direct `uvicorn` launch
   for `/healthz` and `/docs` was blocked by `dcg`; it was not run.

## Provenance diagnosis at current HEAD
- Main tree `data/processed/` has 5 artifacts and **0 manifests**; mtimes are 2026-10-22.
  `clause_classifier.csv` header is `text,category,source` (no `doc_id`/`split` columns).
- `scripts/verify_provenance.py` → 5 failures, 0 skipped.
- `tests/test_no_leakage.py` → 7 failed, 16 passed
  (T1a/T1b/T2a/T2b/T3a/T3b/T8).
- `data/processed.staging/` holds newer artifacts from 2026-10-26 (code revision `cbd9c29`)
  with the correct `doc_id`/`split` header and all 5 manifests. It was **not** swapped.
- Clean rebuild at HEAD produces the correct schema, 5 manifests, 0 verifier failures, and
  129/129 passing tests. Conclusion: **stale main-tree generated artifacts**, not a code
  regression or test-isolation defect. No code/test fix was made; the guards correctly fail closed.
- The main-tree artifacts were not rebuilt or replaced. That remains approval-gated.

## Fixed this session
- D1–D8 (fresh-clone blockers, T1b, liability/stamp/TDS/S124 severity + scoring, cross-reference notes).
- D9 (obligations): calendar-date deadlines now populate `deadline_date`; passive voice uses the by-agent as obligor (or None when no agent) instead of inventing the grammatical object; written-out numbers normalize to digits.

## Fixed this pass (obligations + ML wording)
- D10: obligations carry zero-based half-open source offsets; `Obligation.text` is the exact
  `clause_text[start:end]` slice. Repeated/ambiguous sentences leave both offsets `None` rather
  than guessing.
- D11: leading/mid/trailing conditions and exceptions are preserved in `condition`; the main-clause
  modal is preferred over a protasis modal; deadlines inside a condition are not attributed to the
  duty; passive by-agents are recovered without inventing a subject.
- D12: beneficiary/counterparty extraction is conservative (explicit `to X` / dative patterns only,
  role nouns or corporate/proper names); optional `party_aliases` canonicalises defined names.
  Ambiguous recipients (`to Mumbai`, `comply with the Act`) stay `None`.
- D13: `ML_RISK_001` no longer presents `predict_proba` as calibrated confidence. The flag is named
  "Model-suggested …" and the explanation says "uncalibrated model score … (raw classifier output,
  not a calibrated probability)".
- D14: `RISK_S124_001` was contract-level but scanned the whole contract, so an unrelated
  "breach of contract" mention suppressed it. It now evaluates only indemnification clauses,
  keeps `evidence_status="unverified"`, and reports an indemnity-specific `search_scope`.
  Regression: `test_s124_not_suppressed_by_unrelated_breach_of_contract_language`.
- Regression coverage added in `tests/test_obligation_extraction.py` (18 cases: offsets, duplicates,
  beneficiary, aliases, conditions/exceptions, protasis, passive, condition dates, written-out
  deadlines) and `tests/test_risk_model.py` (wording/no-"confidence" assertion). The deleted tail of
  `test_tfidf_outputs_are_canonicalised` is restored to match HEAD.

Verification: focused suite (obligations, regressions, risk rules, risk model, P4) → 75 passed;
`uv run ruff check .` → clean. Full main-tree `uv run pytest --tb=no` → 137 passed, 7 failed, all
in `tests/test_no_leakage.py` from stale main-tree `data/processed/` artifacts (missing manifests /
old schema without `doc_id`/`split`). The isolated clean rebuild at HEAD passes 129/129.

## Main-tree provenance failures — VERIFIED stale artifacts (not code defects)
Main tree `data/processed/` has 5 artifacts, **0 manifests**, and an old header without
`doc_id`/`split`; `verify_provenance.py` reports 5 "manifest missing" failures (7 test failures
with lineage). The isolated worktree at `97f4c21` regenerates 5 manifests, passes the verifier
with 0 failures, and passes all 129 tests. Resolution is a separately-approved main-tree artifact
rebuild; do not swap staging blindly or weaken the guards.

## Open (documented, not defects)
- ML risk classifier score is still uncalibrated (`ML_RISK_001`); only its presentation is fixed.
- Whole-contract cross-reference reasoning is not consumed by risk rules (P4); prior suppression
  was reverted as unsafe.
- P3 four-way missing-protection status (`present | incomplete | not_found_in_scope | undetermined`)
  is represented only implicitly by existing `RiskFlag` fields; no explicit status enum or consumer.
  Section 124 now has the "Verify" qualifier and an indemnity-only search scope.
- No-comma leading conditions (e.g. "If required by law the Provider shall …") cannot be split
  reliably without a parser; the responsible party is left `None` rather than guessed.
- The uncommitted user P4 work (analyzer `related_clause_texts` enrichment, `app/utils/text.py`
  markdown headings, P4 tests, reports) is preserved in the working tree and complements the
  committed cross-reference analysis.

## Next actions
1. (Approval-gated) rebuild/replace stale main-tree `data/processed/` artifacts with
   `uv run python scripts/build_training_data.py`, then require
   `verify_provenance.py` 0 failures and a full 144-test main-tree run.
2. Calibrate or label the ML risk score (a raw `predict_proba` remains uncalibrated).
3. Whole-contract cross-reference reasoning consumed by rules, with labelled evaluation.
4. Optional: explicit P3 status enum/consumer if the API needs machine-readable status values.

## Blocks
- Main-tree `data/processed/` remains stale, so the 7 provenance tests stay red until an
  approval-gated rebuild. This is a data-state issue, not a code fix.
- Direct `uvicorn` smoke is blocked by `dcg`; `tests/test_api_smoke.py` covers the API roundtrip.
- Do not push without separate instruction.

---

## Kiro session 2026-10-30 (HEAD 42c25b0 -> b35da18)

State: branch `main`; HEAD advanced from `42c25b0` to `b35da18` (2 local commits,
nothing pushed; `origin/main` at `42c25b0`). Working tree clean. The previously
"uncommitted user P4 work" is committed at `42c25b0`.

Commits this session:
- `85011e2` test(eval): add deterministic synthetic evaluation harness and labelled corpus
- `b35da18` fix(risk): parse written/parenthetical renewal notice periods

Verification at `b35da18` (all via `uv run --no-sync`):
- `ruff check .` -> All checks passed.
- `pytest --tb=no` -> 146 passed, 7 failed (153 collected). The 7 failures are the
  same `tests/test_no_leakage.py` provenance guards on the stale main-tree
  `data/processed/` (Oct 22, no manifests). Unchanged data-state issue; guards
  working as designed.
- Focused suite (obligations, regressions, risk model/rules, P4, eval harness) -> 84 passed.
- `scripts/run_evaluation.py` -> 14/17 cases pass, 3 known limitations, 0 regressions;
  3/3 evidence-integrity invariants hold; exit 0.
- `scripts/run_demo.py` -> exit 0; 12 clauses, 13 obligations, score 100.0/critical.

Added: `nlp/evaluation/` (cases + harness), `scripts/run_evaluation.py`,
`tests/test_evaluation_harness.py`, `reports/evaluations/synthetic_eval_results.{md,json}`,
shared number helpers in `app/utils/text.py`, renewal-notice parsing fix in
`nlp/risk_scoring/rules.py`, defect D12, and `reports/recovery/KIRO_HANDOFF.md`.
Final report updated to the current counts and the new harness.

Not done (approval-gated / documented): main-tree `data/processed/` rebuild;
ML calibration; cross-reference suppression; stamp/TDS and passive-voice recall
(documented as eval known limitations). No push; no co-author trailer.

---

## Kiro session 2026-10-30, second pass (HEAD b35da18 -> aaa9fd5)

State: branch `main`; HEAD advanced from `b35da18` to `aaa9fd5` (1 local commit,
nothing pushed). Working tree clean after the commit.

Commits this session:
- `aaa9fd5` fix(ner): detect stamped-paper and deduction-at-source wording for stamp/TDS

Task: resolve the `stamp_tds_present_missed` evaluation known limitation
(`RISK_STAMP_001` / `RISK_TDS_001` false "not found" prompts on present language).

Root cause: `detect_stamp_duty_mention` / `detect_tds_mention` in `nlp/ner/ner.py`
matched only literal keywords ("stamp duty", "e-stamp", "franking",
"indian stamp act") and `\b(?:tax deducted at source|tds|section 19[45])\b`, so
"duly stamped paper" and "deduction of tax at source" were missed. Reproduced with
a direct detector call (both returned False) and via the eval case before the fix.

Fix (minimal, detector-level only):
- `_STAMP_DUTY_RE` adds tight stamped-wording forms: adverb-qualified "stamped"
  ("duly", "non-judicial", "properly", "sufficiently", "adequately",
  "appropriately"), "stamped paper/certificate/document/instrument/agreement/copy",
  "stamp paper(s)", "stamping of this/the/such". Existing keyword list unchanged.
- `_TDS_RE` keeps the old forms verbatim and adds "tax deduction at source",
  "deduct(ed|ing|ion)? (of)? tax at source", and "deduct(ed|ing)? at source".
  Bare "tax" or "deduction" never matches; the at-source construction is required.
- Jurisdiction gating, payment-clause scoping, severity, "not found — verify"
  wording, evidence status, and search scope in `rules.py` are untouched; a
  detected mention suppresses the review prompt, it is not asserted to be a
  confirmed legal compliance fact.

Regression coverage (tests/test_regressions.py, 4 new tests):
- positives: "duly stamped paper", "non-judicial stamp paper", "stamped copies",
  "stamping of this Agreement", "deduction of tax at source", "deduct tax at
  source", "deduct at source", "amounts deducted at source".
- negative controls: "rubber-stamped the decision", "postage stamp", "date stamp",
  "stamp out fraud", "timestamped", "paper copy", "stamp of approval"; "goods and
  services tax", "income tax returns", "sales tax", "deduction of damages",
  "deduction for late delivery", "source code escrow", "tax deducted from the
  invoice" (no "at source" — intentionally not matched).

Verification at `aaa9fd5` (all via `uv run --no-sync`):
- `ruff check .` -> All checks passed.
- `pytest --tb=no -q` -> 157 collected, **150 passed, 7 failed** (junit-verified).
  The 7 failures are the same `tests/test_no_leakage.py` provenance guards on the
  stale main-tree `data/processed/` — unchanged data-state issue, kept separate
  from this task; artifacts not touched.
- Focused suite (obligations, regressions, risk model/rules, P4 adversarial/
  context/cross-reference, eval harness) -> **88 passed** (was 84; +4 new tests).
- `scripts/run_evaluation.py` -> **15/17 pass, 2 known limitations, 0 regressions,
  0 resolved pending**, 3/3 invariants OK, exit 0. Before the fix: 14/17 pass,
  3 known limitations. `stamp_tds_present_missed` now passes; its
  `known_limitation` note was removed and the lock set in
  `tests/test_evaluation_harness.py` updated (otherwise the lock test correctly
  fails on a silently resolved limitation).
- `scripts/run_demo.py` -> exit 0; output identical to the pre-fix baseline
  (12 clauses, 13 obligations, score 100.0/critical; sample MSA still
  stamp_duty_mentioned=false, tds_mentioned=false).

Reports updated: `reports/evaluations/synthetic_eval_results.{md,json}`
(regenerated), final project report (counts + defect D13), `KIRO_HANDOFF.md`.

Not done (approval-gated / documented): main-tree `data/processed/` rebuild;
ML calibration; cross-reference suppression; `obligation_passive` recall. No push;
no co-author trailer.

---

## Kiro session 2026-10-30, third pass (HEAD a1aaf8b -> 8c60ae6 +docs)

State: branch `main`. The session opened with an **in-progress merge** left from
a `git pull`: `MERGE_HEAD=5a03a1b` (the pushed first version of the stamp/TDS
fix, which had since been rewritten locally into `aaa9fd5` + `a1aaf8b`) and 3
conflicted docs. Diffing the sides showed the only differences were the literal
`NEWCOMMIT` hash placeholder in 11 doc lines; code, tests, and eval reports were
identical. The conflicts were resolved by keeping the local side, producing
merge commit `ece750f` whose tree is identical to `a1aaf8b` (verified with
`git diff a1aaf8b HEAD` — empty). Both histories stay reachable, so the branch
fast-forwards on push. Nothing pushed.

Commits this session:
- `ece750f` merge: reconcile origin/main (5a03a1b) with local stamp/TDS commits
- `8c60ae6` fix(risk): suppress missing-cap finding only for resolved, applicable cross-referenced caps

Task: resolve the `liability_cap_in_crossref` evaluation known limitation
(false `RISK_LIABILITY_002` when a cross-referenced clause states the cap).

Root cause: `rule_uncapped_liability` evaluated only the clause's own text and
entities. The resolver already resolved "Clause 7.4" to the cap clause
(status `resolved`, no unresolved references) and the analyzer already attached
the referenced clause text to the context bundle, but the rule never consulted
it — the context fed only the advisory `cross_reference_note`. Reproduced via
the eval harness (`run_case` on `liability_cap_in_crossref` -> fail,
"expected rule RISK_LIABILITY_002 absent, but it fired") with the resolved
context printed and inspected.

Fix (fail-closed verification gate in `nlp/risk_scoring/rules.py`):
- `_cross_reference_states_applicable_cap` requires the resolver's explicit
  `references` entries with `status == "resolved"`; any unresolved, missing, or
  ambiguous reference returns False. `related_clause_texts` without a resolved
  reference is never sufficient — keyword suppression stays reverted (the P4
  adversarial/context suites, which never include resolved references, pass
  unchanged).
- `_cap_text_covers_liability` then checks the referenced text actually covers
  the assessed liability: cap language required; exclusion/override markers
  ("excluding", "except for", "notwithstanding", "unlimited", ...) reject;
  a cap scoped to direct losses does not cover assessed indirect/consequential
  exposure; party scope must be mutual ("each party", ...) or name a party that
  also appears in the assessed clause; unknown scope rejects.
- Genuinely absent cap vs unresolved reference vs ambiguous reference vs
  cap-that-may-not-cover: only the first suppression case is silent; every
  uncertain case keeps `RISK_LIABILITY_002` as the human-review prompt, with
  the advisory `cross_reference_note` surfacing the considered text.
- Evidence/provenance: kept findings still bind the exact owning-clause span
  (role "direct"), and referenced clauses stay traceable via
  `related_clause_ids` + the advisory note; no spans are fabricated for
  related clauses. Jurisdiction gating and the `RISK_LIABILITY_001` uncapped
  path are untouched.

Regression coverage (`tests/test_p4_cap_resolution.py`, 14 tests): valid
mutual cap (suppresses), same-party cap (suppresses), unresolved reference,
missing reference, ambiguous reference, unrelated reference (definitions),
referenced clause without cap, cap with relevant exclusion, direct-losses-only
cap vs indirect assessment, different-party cap, conflicting cap language,
related text without resolved reference (negative control), generic cap with
unknown scope (negative control), and no-context unchanged behaviour.
`tests/test_p4_cross_reference.py`: one test updated to the new contract — its
scenario now uses an excluding cap so the finding stands and every
advisory-note assertion is preserved (comment explains why).

Verification at `8c60ae6` (all via `uv run --no-sync`):
- `ruff check .` -> All checks passed.
- `pytest --tb=no -q` -> 171 collected, **164 passed, 7 failed** (junit-verified).
  The 7 failures are the same `tests/test_no_leakage.py` provenance guards on
  the stale main-tree `data/processed/` — unchanged data-state issue, kept
  separate; artifacts not touched.
- Focused suite (obligations, regressions, risk model/rules, all four P4
  suites, eval harness) -> **102 passed** (was 88; +14 new tests).
- `scripts/run_evaluation.py` -> **16/17 pass, 1 known limitation
  (`obligation_passive`), 0 regressions, 0 resolved pending**, 3/3 invariants
  OK, exit 0. Before the fix: 15/17 pass, 2 known limitations. The case's
  `known_limitation` note was removed and the lock set in
  `tests/test_evaluation_harness.py` updated.
- `scripts/run_demo.py` -> exit 0; output identical to the pre-fix baseline
  (12 clauses, 13 obligations, score 100.0/critical).

Reports updated: `reports/evaluations/synthetic_eval_results.{md,json}`
(regenerated), final project report (counts, defect D14, §6.2/§7.3 whole-contract
reasoning now partially addressed), `KIRO_HANDOFF.md`.

Not done (approval-gated / documented): main-tree `data/processed/` rebuild;
ML calibration; `obligation_passive` recall; renewal cross-reference notices
remain advisory-only; P3 status enum. No push; no co-author trailer.

---

## Kiro session 2026-10-30, fourth pass (HEAD 58d279d -> 42b985c +docs)

State: branch `main`; HEAD advanced from `58d279d` to `42b985c` + a docs commit
(6 local commits ahead of `origin/main` at `5a03a1b`, nothing pushed). Working
tree clean.

Commits this session:
- `42b985c` fix(obligations): recover passive by-agents and compound written deadlines

Task: resolve the `obligation_passive` evaluation known limitation (the last
one): "Personal data shall be encrypted by the Processor within twenty-four
(24) hours of a security incident" produced subject=None, deadline=None.

Root cause (two independent gaps, reproduced with a direct extractor call):
1. The passive-agent path actually worked (`be encrypted` matched, `by the
   Processor` was located), but `_party_after` returned None because
   `_PARTY_ROLE` has no data-protection role nouns — "Processor" (and
   "Controller") were missing from the party vocabulary.
2. The extractor's local `_NUMBER_WORDS`/`_NUM_ALT` matched single tokens only
   (and lacked "seventy"/"eighty"), so the hyphenated compound "twenty-four"
   never matched `DEADLINE_RE`.

Fix (in `nlp/obligation_extraction/extractor.py` only):
- Deadlines now use the shared `NUMBER_TOKEN_RE` / `written_number_to_int`
  from `app.utils.text` (the vocabulary the renewal rule already uses):
  "twenty-four (24) hours" -> "24 hours", "sixty-five days" -> "65 days",
  "seventy days" -> "70 days". Parenthetical-digit and single-word behaviour
  unchanged.
- `Processor`/`Controller` added to `_PARTY_ROLE`.
- Passive detection recognises common irregular participles
  (sent/made/paid/done/taken/met/held) alongside -ed/-en forms.

Conservative semantics preserved and locked by tests: passive without an agent
leaves the subject unknown; a non-party agent phrase ("by Friday") stays
unknown; no uploader role is inferred; conditions, exceptions, counterparties,
exact source offsets (zero-based half-open slices), and active-voice behaviour
are unchanged ("available" is not treated as a participle); one obligation per
sentence, no duplicates; extraction stays clause-local — cross-references
remain advisory-only in the risk layer.

Regression coverage (`tests/test_obligation_extraction.py`, 15 new tests):
Processor/Controller by-agents, irregular participles (paid/sent), non-party
agent phrase, agentless passive with compound deadline, compound deadlines with
and without parenthetical digits (24/65/70), passive with leading condition
(condition + deadline both preserved), passive with exception, adjective
negative control, active-voice unchanged, clause-local cross-reference
sentence, exact offsets on a passive sentence.

Verification at `42b985c` (all via `uv run --no-sync`):
- `ruff check .` -> All checks passed.
- `pytest --tb=no -q` -> 186 collected, **179 passed, 7 failed** (junit-verified).
  The 7 failures are the same `tests/test_no_leakage.py` provenance guards on
  the stale main-tree `data/processed/` — unchanged data-state issue; artifacts
  not touched.
- Focused suite (obligations, regressions, risk model/rules, all four P4
  suites, eval harness) -> **117 passed** (was 102; +15 new tests).
- `scripts/run_evaluation.py` -> **17/17 pass, 0 known limitations, 0
  regressions, 0 resolved pending**, 3/3 invariants OK, exit 0. Before the fix:
  16/17 pass, 1 known limitation. The case's `known_limitation` note was
  removed; the lock set in `tests/test_evaluation_harness.py` is now an
  explicit empty set with a comment.
- `scripts/run_demo.py` -> exit 0; output identical to the pre-fix baseline
  (12 clauses, 13 obligations, score 100.0/critical).

Reports updated: `reports/evaluations/synthetic_eval_results.{md,json}`
(regenerated), final project report (counts, defect D15, all-limitations-resolved
note), `KIRO_HANDOFF.md`.

Not done (approval-gated / documented): main-tree `data/processed/` rebuild;
ML calibration; renewal cross-reference notices; P3 status enum. Space-separated
written compounds ("twenty four days") and unusual role nouns in by-agent
phrases remain conservative misses. No push; no co-author trailer.

---

## Kiro session 2026-10-30, fifth pass — zero-trust integration audit (no production code changed)

Audit-only pass at HEAD `c3a6468`. Full report:
`reports/audit/integration_audit_20261030.md`. No production code, tests, or
`data/processed/` content was modified; one audit-only test file was added.

Verified baseline (all executed): ruff clean; full suite 186 collected / 179
passed / 7 failed (the same provenance guards); eval harness 17/17 exit 0;
demo exit 0 identical output; provenance verifier 5 failures exit 1. Doc
staleness found: handoff said "ahead 6" (actual 7, merge commit counts); final
report's "~70 s" suite timing measured at ~89 s. All substantive reported
numbers reproduced exactly.

Added: `tests/test_audit_integration.py` — 14 passing integration tests
(offsets, cross-reference caps incl. indemnity-exclusion + different-party at
pipeline level, obligations, dedupe, fail-safety, taxonomy-sync guard, ML
invariants, stamp/TDS positive controls) + 7 `xfail(strict=True)` defect
records. Suite after addition: **207 collected, 193 passed, 7 failed
(provenance), 7 xfailed**; ruff clean; eval unchanged 17/17.

Confirmed integration defects (evidence in report §C):
- D2 (high): segmentation silently drops lines 2+ of a non-heading multi-line
  preamble paragraph.
- D4 (high): negated stamp/TDS mentions ("was not executed on duly stamped
  paper", "without deduction of tax at source") suppress the review prompts.
- D1 (medium): clause offsets don't slice the source for single-newline
  heading+body layout (dominant layout; API/graph offsets wrong).
- D3 (medium): long-clause sub-offsets drift (heading length + separator
  assumptions).
- D5 (medium): breach-window rule parses digit-only notice periods; written
  "twenty-four (24) hours" invisible to it (obligation layer sees "24 hours").
- D6 (low-medium): `_detect_parties` drops names containing the noise word
  "services" ("ABC Services Pvt Ltd" lost).

Provenance: isolated rebuild at HEAD in `tmp/audit-rebuild/` (gitignored) →
5 artifacts + 5 manifests, verifier exit 0, byte-identical to
`data/processed.staging/`; staging itself verifies 0 failures. Diagnosis
confirmed: stale main-tree data, not code/env; approval-gated rebuild/swap
remains pending (report §H).

Not done (boundaries): no production code changes; no test weakening; no
`data/processed/` modification; no push; no model retraining.

---

## Kiro session 2026-10-30, sixth pass — integration defect remediation D1–D6 + data restoration

State: branch `main`. Started at audit commit `8b18f89`. All six audit defects
fixed and verified; stale `data/processed/` restored under the authorised
controlled procedure. Working tree clean at `3db8416` (docs). NOTE: `origin/main`
moved externally during this session from `5a03a1b` to `90bb769` (the M1 commit
was pushed outside this session; nothing was pushed from here). Local is 4
commits ahead of `origin/main`.

Commits this session (in order):
- `90bb769` fix(risk): preserve review prompts for negated statutory mentions (D4)
- `e2fdbb9` fix(segmentation): exact source spans; preserve multi-line preamble content (D1/D2/D3)
- `128a835` fix(risk): parse written-number breach notice periods (D5) — ALSO
  contains the D6 `_detect_parties` production change: two parallel `git add`
  calls raced and swept `app/services/analyzer.py` into this commit. Content is
  correct and the tree is green at this commit; recorded here for honesty
  instead of rewriting history.
- `5b64da9` fix(ner): stop party-name walk-back at a second corporate suffix
  (adjacent-name gluing regression found by the adversarial verification)
- `1b13c2d` chore(data): restore verified processed artifacts (manifests only;
  artifacts gitignored)
- `3db8416` docs(audit): record remediation verification evidence

Root causes and fixes (full evidence: `reports/audit/remediation_verification_20261030.md`):
- D4: presence-only statutory detection. Fix: 6-token same-sentence negation
  window (`not/no/never/without/neither/nor/exempt`) in `nlp/ner/ner.py`;
  sentence punctuation bounds scope; positive/boundary/post-mention controls.
- D1/D3: offsets reconstructed with synthetic separators. Fix: span-based
  segmentation (`_paragraph_spans`, `_normalise_items`, span-based grouping and
  `_split_long_clause`); every `Clause.text == cleaned[char_start:char_end]`.
  Consumers traced first: offsets feed only Neo4j persistence, API output, and
  `length`; all `Clause.text` consumers re-tokenize, so the change is
  representation-compatible. Offsets index the cleaned document (the pipeline's
  documented frame); raw-file-byte fidelity is a separate documented migration.
- D2: multi-line preamble lines dropped. Fixed by the same span-based grouping
  (every line survives inside the exact span; >200-char first lines become body).
- D5: digit-only breach-window regex. Fix: shared `NUMBER_TOKEN_RE` /
  `written_number_to_int`; cross-stage consistency test added.
- D6: `_detect_parties` noise-word truncation ("services"/"company"). Fix:
  removed from walk-back noise set; generic-fragment guard; stop-at-second
  suffix after adversarial verification caught adjacent-name gluing
  ("Acme Consulting Services Pvt Ltd and Zenith Technologies Pvt Ltd" previously
  merged into one string).

Data restoration (authorised; full evidence trail in the verification record):
pre-checks (isolated rebuild verified 0 failures, byte-identical to staging,
stale inventory hashed, no active processes), hash-verified backup at
`tmp/processed-backup-20261030/`, replacement via the supported builder
(`--out-dir data/processed`), post-checks (hashes match isolated build;
`verify_provenance.py` → 0 failures, exit 0; row lineage 9,278 / 22,450 /
32,580 / 55,030; the 7 previously failing provenance tests pass). No source
datasets modified; no models retrained.

Verification at `5b64da9` (+ docs at `3db8416`):
- `ruff check .` → All checks passed.
- Full suite → **227 collected, 0 failed, 0 errors, 0 skipped** (junit-verified).
  Before: 207 collected, 193 passed, 7 failed (provenance), 7 xfailed.
- Focused suite (obligations, regressions, risk model/rules, P4, eval harness)
  → **126 passed**.
- `scripts/run_evaluation.py` → 17/17, 0 regressions, 3/3 invariants, exit 0
  (`obligation_passive` additionally observes RISK_DATA_001 — intended D5 effect).
- `scripts/run_demo.py` → exit 0; output identical to baseline.
- End-to-end adversarial verification (`tmp/remediation_verify.py`) → 16/16 checks.
- Independent two-model semantic review of `8b18f89..HEAD` dispatched via
  workflow `wf_9c01541cb5ee4650`; outcome recorded below when complete.

Remaining (documented, not defects from this milestone): raw-byte offset
fidelity migration; advisory-note duplicate wording for one missing reference;
`page_hint` dead field; `strip_headers_footers` dead code; two contract-id
digest lengths; rule exceptions silently swallowed (fail-safe, hides bugs);
ML-vs-verified-suppression presentation tension (findings stay unverified);
P3 status enum; renewal cross-reference notices; ML calibration (approval-gated).
