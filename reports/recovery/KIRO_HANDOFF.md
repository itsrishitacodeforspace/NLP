# Kiro Handoff — BharatContract AI

Durable session handoff. Preserves (does not replace) the CommandCode records
under `.commandcode/` and the earlier `reports/recovery/` documents. Read
`.commandcode/BHARATCONTRACT_PROJECT_MEMORY.md` and `RECOVERY_TRACKER.md` first
for the full prior history.

Last updated: 2026-10-31 (submission-readiness audit).

## 0. 2026-10-31 submission-readiness audit addendum

- Verified code HEAD: `2ca788f`; the audit-docs commit is on top (local only;
  not pushed). `origin/main` is `2ca788f`; working tree clean.
- Re-ran at `2ca788f`: full suite **227 passed**; focused **126 passed**
  (including `tests/test_p4_cap_resolution.py`); evaluation **17/17**;
  `verify_provenance.py` **0 failures**; ruff clean; demo exit 0.
- Corrected the final report’s commit reference, non-test lineage wording
  (CUAD train; MAUD train+dev), evidence-binding/advisory wording, reproduction
  order, and privacy/licensing caveats.
- No code changes, no retraining, and no `data/processed/` rebuild.

## 1. Verified repository state

- Branch: `main`.
- Starting HEAD this session: `8b18f89` (the audit commit).
- Ending HEAD this session: `3db8416` (+ final docs commit on top).
  **Note:** `origin/main` moved externally during the session from `5a03a1b` to
  `90bb769` (the M1 commit was pushed outside this session; nothing was pushed
  from here). Local is 4 commits ahead of `origin/main`.
- Working tree: clean after the commits below (plus repo-local `tmp/` scratch,
  which is gitignored).
- Python: uv-managed 3.12.14; always use `uv run` (host `python` is out of range).

## 2. Commits added this session (audit + remediation)

- `8b18f89` docs(audit): zero-trust integration audit + audit-only tests
- `90bb769` fix(risk): preserve review prompts for negated statutory mentions (D4)
- `e2fdbb9` fix(segmentation): exact source spans; preserve multi-line preamble content (D1/D2/D3)
- `128a835` fix(risk): parse written-number breach notice periods (D5; also swept in
  the D6 `_detect_parties` change via a git-add race — recorded in the tracker)
- `5b64da9` fix(ner): stop party-name walk-back at a second corporate suffix
- `1b13c2d` chore(data): restore verified processed artifacts (manifests only)
- `3db8416` docs(audit): record remediation verification evidence

Earlier 2026-10-30 sessions (same working line): `85011e2` eval harness,
`b35da18` renewal notice parsing, `aaa9fd5`+`a1aaf8b` stamp/TDS detection recall,
`ece750f` merge reconciliation, `8c60ae6` cross-reference cap resolution,
`42b985c` obligation passive/deadline fix.

## 3. Key architectural decisions (unchanged, reaffirmed)

- Rule-first, evidence-bound risk engine; ML is a recall booster only and never
  overrides a rule. Model findings are always `evidence_status="unverified"`.
- Graceful degradation is mandatory: Neo4j/Postgres/OCR/transformers all no-op.
- Single taxonomy source (`nlp/taxonomy.py`). Timestamps via `app.core.time.utcnow()`.
- Provenance ≠ evaluation ≠ predictive validity. A manifest proves lineage only.
- Cross-reference context is advisory; suppression requires an explicit resolved
  reference plus verified applicability — never keyword presence (see
  `tests/test_p4_cap_resolution.py`).
- No production artifact replacement, retraining, archive extraction, service
  startup, or push without explicit approval. The 2026-10-30 data restoration was
  the first authorised replacement; it followed the controlled protocol recorded
  in `reports/audit/remediation_verification_20261030.md`.

## 4. What this session added

**Audit** (`reports/audit/integration_audit_20261030.md`):
- Zero-trust verification of every reported number (all reproduced exactly).
- Six integration defects D1–D6 with evidence; `tests/test_audit_integration.py`
  (14 passing + 7 xfail defect records at audit time).

**Remediation** (evidence: `reports/audit/remediation_verification_20261030.md`):
- `nlp/ner/ner.py` — negation-aware statutory detection (D4): a 6-token
  same-sentence window (`not/no/never/without/neither/nor/exempt`) decides whether
  a stamp/TDS mention is denied; denied mentions no longer suppress the review
  prompts. Positive, boundary, and post-mention controls locked.
- `app/services/segmenter.py` — span-based rewrite (D1/D2/D3): `_paragraph_spans`,
  `_normalise_items`, span-based grouping and `_split_long_clause`. Every
  `Clause.text == cleaned[char_start:char_end]`; multi-line preambles keep every
  line; long-clause sub-offsets are exact. Grouping semantics unchanged (demo and
  eval identical).
- `nlp/risk_scoring/rules.py` — breach-window rule uses shared `NUMBER_TOKEN_RE` /
  `written_number_to_int` (D5); cross-stage consistency test.
- `app/services/analyzer.py` — `_detect_parties` no longer truncates names
  containing "Services"/"Company" (D6); generic-fragment guard; stop-at-second
  corporate suffix (adjacent names never glue).
- `data/processed/` restored under the authorised controlled procedure: backup at
  `tmp/processed-backup-20261030/`, supported builder used, verifier now **0
  failures** (was 5); manifests committed (tracked per `.gitignore`); artifacts
  gitignored. No source datasets modified; no models retrained.
- All 7 audit xfail defect records converted to normal passing regression tests.
- New tests: 4 negation (`test_regressions.py`), 7 segmenter slicing (`test_segmenter.py`),
  5 breach-window (`test_risk_rules.py`), +9 integration (`test_audit_integration.py`).

## 5. Reproducible setup and verification commands

```bash
uv sync --extra dev
uv run ruff check .
uv run pytest --tb=no
uv run pytest tests/test_evaluation_harness.py tests/test_risk_rules.py -q
uv run python scripts/run_demo.py
uv run python scripts/run_evaluation.py
uv run python scripts/verify_provenance.py
```

## 6. Historical results (verified at `5b64da9`, docs at `3db8416`; current re-run in §0)

- `ruff check .` → All checks passed.
- Full suite → **227 collected, 227 passed, 0 failed, 0 errors, 0 skipped**
  (junit-verified). The 7 provenance guards now pass on the restored artifacts;
  no test is xfailed or skipped.
- Focused suite (obligations, regressions, risk model/rules, P4, eval harness)
  → **126 passed**.
- `scripts/run_evaluation.py` → **17/17 cases pass, 0 regressions, 3/3 invariants**,
  exit 0. (`obligation_passive` additionally observes `RISK_DATA_001` — the
  intended D5 effect; case still passes.)
- `scripts/run_demo.py` → exit 0; 12 clauses, 13 obligations, score 100.0/critical;
  both sample parties detected.
- `scripts/verify_provenance.py` → **0 failures, 0 skipped, exit 0**.
- End-to-end adversarial verification (`tmp/remediation_verify.py`) → 16/16 checks.
- Independent two-model semantic review of `8b18f89..HEAD` dispatched via
  workflow `wf_9c01541cb5ee4650`; outcome recorded in the tracker on completion.

## 7. Outstanding defects / known limitations

1. ML risk score remains uncalibrated (presentation only is fixed); models remain
   `provenance-unverified` (training corpus overlaps held-out CUAD).
2. P3 four-way missing-protection status has no explicit enum/consumer
   (see `reports/recovery/P3_STATUS_DESIGN.md`).
3. TDS detection still requires the at-source construction ("tax deducted from
   the invoice" is intentionally not matched) — precision-over-recall by design.
4. Cross-reference cap suppression is intentionally narrow (unknown party scope
   or carve-outs keep the review prompt).
5. Renewal notices in cross-referenced clauses remain advisory-only.
6. Deadline parsing covers hyphenated compounds only ("twenty four days"
   space-separated is missed); the party-role vocabulary is finite.
7. No-comma leading conditions still cannot be split reliably without a parser.
8. Offsets index the cleaned document, not raw file bytes; raw-byte fidelity is
   a documented migration if ever needed by a consumer (none today).
9. Advisory note prints one missing reference twice ("missing" + "unresolved");
   `page_hint` is a dead field; `strip_headers_footers` is dead code; two
   contract-id digest lengths (10 vs 12 chars); rule exceptions are silently
   swallowed (fail-safe but hides bugs); ML booster can flag a clause whose rule
   finding was cleared by verified suppression (stays unverified by contract).

## 8. Next three prioritised actions

1. **Research-readiness evaluation** (audit report §F): pre-registered labelled
   corpus with per-component metrics (classification/NER P-R, obligation slot-F1,
   evidence-span exactness, resolver accuracy), annotation guide + dual
   annotation + agreement reporting; verify and record dataset licence terms in-repo.
2. **Renewal cross-reference notice** under the same fail-closed contract used
   for caps, or **P3 status enum** for machine-readable missing-protection status.
3. **Advisory-hygiene batch**: note deduplication, contract-id digest alignment,
   rule-exception logging, `page_hint`/`strip_headers_footers` decision.
   (ML calibration remains approval-gated; no retraining without instruction.)

## 9. Continuation prompt for a future Kiro session

> Resume BharatContract AI from `reports/recovery/KIRO_HANDOFF.md` at the
> audit-docs state on branch `main` (code verified at `2ca788f`; `origin/main`
> is `2ca788f`). Verify with `uv run ruff check .`,
> `uv run pytest --tb=no` (expect 227 passed, 0 failed, 0 skipped),
> `uv run python scripts/run_evaluation.py` (expect 17/17, 0 regressions), and
> `uv run python scripts/verify_provenance.py` (expect 0 failures). Pick the next
> action from Section 8, work test-first in a verified milestone, keep the
> evaluation lock list honest, do not weaken provenance guards, do not
> rebuild/replace `data/processed/` or push without explicit approval, and do
> not add a co-author trailer.

No secrets, tokens, or credentials are stored in this handoff.
