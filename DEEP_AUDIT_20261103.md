# BharatContract AI — Deep Audit Report (2026-11-03)

> Deep-audit of the whole repository, run per the Project Charter (Phase 1/2):
> six parallel reviewer subagents + direct empirical verification by the
> orchestrator. Every **CONFIRMED** finding below was re-verified by running the
> actual code in this environment; items marked **REPORTED** come from a
> subagent's static reading and still need empirical confirmation before any
> fix is trusted.
>
> **Git state at audit time:** branch `main`, HEAD `8d1a8c8`, working tree
> clean, 10 commits ahead of `origin/main` (NOT pushed — local only, per user
> instruction).
> **Environment:** Linux container; `.venv` was rebuilt this session (it had
> been created on Windows and was unusable). `uv run pytest` → **262 passed,
> 3 third-party warnings**. `uv run ruff check .` → 3 pre-existing B008
> warnings in `scripts/check_evaluation_regression.py`.
> `uv run python scripts/verify_provenance.py` → **0 failures, 0 skipped**.
> `uv run python scripts/run_demo.py` → runs: 12 clauses, 13 obligations,
> risk_score 100 (critical) on the bundled sample MSA.

## 0. Executive verdict

The codebase is structurally sound and more careful about evidence discipline
than most projects of its size: graceful degradation genuinely works, evidence
binding never fabricates spans, contract-level findings are marked
`unverified` by construction, ML findings are kept separate from rule
findings, RLS uses 404-not-403, and provenance verification is fail-closed.

However, the audit found **three clusters of serious problems**:

1. **The evaluation layer is not trustworthy** — the "gold" annotations are
   partially fabricated (party names and rule IDs that don't exist in the case
   texts or engine), the regression gate compares a baseline to itself with
   zero minimums, the classifier "regression floors" run on the training
   corpus, and no rules-only/ML-only/hybrid comparison exists anywhere.
2. **The bundled models are leaky** (train∪test CUAD corpus) while
   `data/processed/` is train-only — the models were never retrained from the
   clean data. No accuracy number in the repo is a generalization estimate.
3. **A set of concrete logic defects** in the risk rules, NER, and job
   persistence that produce user-visible false positives, false negatives,
   and lost/stale results (details below; the highest-priority ones were
   empirically confirmed).

Plus a large tail of documentation drift and repo hygiene issues (stale
numbers, wrong dataset facts, 6.6 MB of committed agent-session dumps,
dead duplicate packages at repo root).

---

## 1. CONFIRMED findings (empirically re-verified in this session)

Each item: what was run, what was observed.

### C1. `cases_gold.json` is partially fabricated (evaluation ground truth)

Files: `nlp/evaluation/gold_annotations/cases_gold.json` vs `nlp/evaluation/cases.py`

- `uncapped_liability_tp` case text (cases.py:51-56) names the parties
  **Provider** and **Customer**, but the gold `ner_gold` labels entities
  **"Vendor"** (start 10) and **"Client"** (start 45) — neither string is in
  the text.
- `broad_indemnity_tp` case text says **Supplier/Customer**; gold says
  **"Manufacturer"** / **"Distributor"** — not in the text.
- `one_sided_termination` gold `risk_gold` uses **`RISK_TERMINATION_001`**;
  the engine's rule ID is **`RISK_TERM_001`** (rules.py:229; cases.py itself
  expects `RISK_TERM_001`).
- `foreign_gov_law` gold uses **`RISK_GOVERNING_LAW_001`**; the engine ID is
  **`RISK_GOV_001`**.
- Gold also references **`RISK_PARTY_001`** and **`RISK_OBLIGATION_001`**,
  which exist **nowhere** in the engine (grep confirms).
- `evidence_gold` offsets (e.g. start 150, end 200) are not anchored to real
  offsets in the case texts — consistent with the measured `mean_iou` of 0.018.
- `metrics_integration.py:98` matches the string `"RISK_TERMINATION_001"` in
  its termination metric — so that metric can **never** match a real finding.

Consequence: `integrated_synthetic_baseline.json` (classification macro_f1
0.0, NER F1 0.0, obligation F1 0.412, risk F1 0.169) measures conformance to
invented labels. The obligation F1 0.412 value is also not reproducible from
the current `metrics_integration.py` code (arithmetic gives pooled F1 0.9412
for tp=17, fp=2 — the stored 0.4118 matches neither), so the baseline JSON is
not tied to a reproducible run (its own `git_revision` field says "unknown").

**Fix:** regenerate gold annotations by (a) running the pipeline, (b) having a
qualified reviewer adjudicate each case, and (c) anchoring every span/rule-ID
to the actual text and engine IDs. Until then, the integrated metrics must be
labelled "not a valid measurement".

### C2. The regression gate is a tautology

Files: `scripts/check_evaluation_regression.py`, `nlp/evaluation/regression_detector.py`

- Default `--*-min` thresholds are **0.0**, and the degradation check is
  skipped when `baseline_val == 0` (regression_detector.py:91).
- `run_regression_check` **silently creates the baseline from the new results
  if the baseline is absent** (regression_detector.py:192-204) — first run
  always passes.
- The committed `regression_report.md` ("NO REGRESSIONS DETECTED") compares
  the pipeline to its own first-run output. It carries no information.
- `tests/test_regression_detector.py` never calls `check_regression` (only
  checks the baseline file's shape).

**Fix:** require explicit non-zero minimums (or a reviewed baseline with
provenance), fail when baseline == new results, and unit-test the detector
(same-file pass, zero-baseline, degradation edges).

### C3. `NOTICE_PERIOD_RE` matches bare durations — confirmed false positives

File: `nlp/ner/ner.py:86-90` (the deontic prefix group is optional).

Ran:
```
extract_entities("The initial term of this Agreement is 90 days. The warranty period is 12 months.")
→ [('NOTICE_PERIOD', ' 90 days'), ('NOTICE_PERIOD', ' 12 months')]
```
Term durations and warranty periods are labelled `NOTICE_PERIOD`. Downstream,
`rule_renewal` uses the **first** "N days" it finds for its severity tier
(rules.py:256-267), so a warranty period can set the renewal-notice severity.
Also note the captured text keeps a **leading space** (`' 90 days'`), which
pollutes entity chips and any text matching.

**Fix:** make the deontic prefix mandatory for the `NOTICE_PERIOD` label;
emit a separate `DURATION` label for bare "N days"; strip the match.

### C4. `detect_arbitration_seat` returns ANY city mention — confirmed false positive

File: `nlp/ner/ner.py:214-224` (steps 3-4 scan the whole document for
FOREIGN_SEATS / INDIAN_SEATS with no context requirement).

Ran:
```
detect_arbitration_seat("All payments shall be made to our bank account in Mumbai, India. There is no arbitration clause in this agreement.")
→ 'Mumbai'
detect_arbitration_seat("The data shall be hosted in Singapore. Notices shall be sent to the addresses listed in Annex A.")
→ 'Singapore'
```
A payment address or data-center location becomes the "arbitration seat",
which feeds `RISK_ARB_001` (seat≠venue, HIGH) — a false positive on ordinary
commercial contracts.

**Fix:** steps 3-4 should only fire when the city appears in an
arbitration/dispute-resolution sentence, or in a clause classified as
Dispute Resolution / Arbitration.

### C5. Risk rules: negation handling confirmed broken / missing

Files: `nlp/risk_scoring/rules.py`

Ran (clause labels set explicitly):
```
"…neither party shall be unlimited or uncapped; all claims are capped at fees paid."
→ RISK_LIABILITY_002 (missing-cap) fires on a clause that explicitly caps liability
"…indemnity does not extend to any and all claims; it covers only third-party IP claims."
→ RISK_INDEMNITY_001 (broad indemnity) fires on a clause that narrows the indemnity
```
- `rule_uncapped_liability`: substring triggers (`rules.py:182`) fire even when
  the sentence is negated ("shall **not** be unlimited"). The NER module has a
  working `_is_negated_mention` (ner.py:275-288) — the risk rules don't use it.
- `RISK_LIABILITY_002` ("missing cap") is the inverse failure: a clause that
  **does** cap liability gets flagged as missing a cap when the specific
  keyword list doesn't recognize the cap phrasing. Both directions are wrong.

**Fix:** sentence-level negation guard (reuse NER's cue list) before any
trigger fires; and make the cap-detection list symmetric with the
uncapped-detection list (cap present ⇒ suppress RISK_LIABILITY_002).

### C6. `rule_governing_law_mismatch` misses most real foreign-law phrasings

File: `nlp/risk_scoring/rules.py:345-348` (5 hard-coded phrases).

Ran:
```
"governed by the laws of the Republic of Singapore" → None   (missed)
"governed by the laws of the State of New York"        → RISK_GOV_001 (caught)
"governed by the laws of Delaware"                     → None   (missed)
```
The false-negative gap is large: "the Republic of Singapore", "England and
Wales", "Delaware", "the State of New York" variants, etc.

**Fix:** extract the governing-law phrase with `detect_governing_law`
(ner.py:246-261) and compare the jurisdiction against a known-Indian check,
instead of matching 5 literal strings.

### C7. Obligation `risk_level` is dominated by deadline urgency

File: `nlp/obligation_extraction/extractor.py:615-644`

Ran:
```
"…notify the Client within one hour of discovering a typo in the invoice." → risk_level=critical
"…indemnify the Client within 30 days of a data breach."                   → risk_level=medium
```
A 1-hour typo notification is **CRITICAL**; a 30-day indemnity (usually the
consequential one) is MEDIUM. Charter §7.5: "Severity and evidence strength
are separate dimensions" — deadline urgency is neither severity nor evidence.

**Fix:** keep the deadline as metadata (it already is:
`deadline_expression`); derive severity from obligation type/content
(indemnity > termination > notice), with at most a bounded urgency modifier.

### C8. Job persistence: `created_at`/`finished_at` never written to Postgres

File: `app/services/jobs.py:163-172` (`_persist` payload omits both fields).

`JobRecord.created_at` therefore falls back to the DB column default
(`utcnow()` at upsert time), so `list_job_ids_for_contract` ordering by
`created_at DESC` (postgres.py:250) orders by **persistence time**, not job
creation time. With staggered worker completions, `_latest_job_for` can serve
an older/failed result while a newer succeeded result exists. (Subagent
REPORTED; mechanism confirmed by reading the payload — the omission is
unambiguous.)

**Fix:** persist `created_at`/`finished_at` in `_persist`, and order by
`finished_at DESC NULLS LAST, created_at DESC`.

### C9. `list_jobs` never merges in-memory and Postgres

File: `app/services/jobs.py:108-118` — DB is consulted **only when the
in-memory dict is completely empty**. Consequences (confirmed by code read):

- With ≥1 in-memory job, historical Postgres-only jobs (post-restart) are
  invisible from `GET /api/v1/jobs`.
- `_latest_job_for` (routes_contracts.py:182-187) filters
  `list_jobs(owner=...)` by contract_id — so an **evicted** job (200-cap) for
  contract X is not found while 200 *other* jobs are in memory, and the
  Postgres fallback (`list_job_ids_for_contract`) is only reached if
  `postgres_available()` is true. The documented "survives eviction" fallback
  does not survive eviction in this combination.

**Fix:** `_latest_job_for` should query `list_job_ids_for_contract` directly
(independent of in-memory state); `list_jobs` should merge both sources and
dedup by `job_id`.

### C10. Root-level duplicate packages are dead weight and break the Docker build contract

`git ls-files` confirms **25 tracked files** under root-level
`clause_classification/`, `ner/`, `obligation_extraction/`,
`risk_scoring/`, `context/`, `datasets/`, `evaluation/`, plus root
`taxonomy.py` and `provenance.py` (byte-identical to `nlp/taxonomy.py` and
`nlp/provenance.py` — `diff -q` reports no difference). They were added in
commit `93cedd9`. All app/nlp code imports `nlp.*`, so the duplicates are dead
— **except** the Dockerfile's `pip install .` only ships
`packages = ["app", "nlp", "streamlit_app"]`, so the image works only because
of `COPY . .` + `PYTHONPATH`. Deleting the duplicates without fixing the
Dockerfile would break the container; deleting the Dockerfile reliance without
deleting the duplicates leaves a second `taxonomy.py` violating the
single-taxonomy invariant.

**Fix:** delete the root duplicates AND verify the image still builds
(imports must all be `nlp.*`/`app.*`); add a test that no top-level module
imports exist.

### C11. Committed junk: 6.6 MB of agent-session transcripts + a .bak test

`command-code-session-242f357f.html` (2.4 MB), `-242f357f.txt` (2.0 MB),
`-8f622c4f.html` (1.2 MB), `-8f622c4f.txt` (0.97 MB) are **tracked in git**
(agent session dumps, one 70k lines). `tests/test_metrics_integration.py.bak`
(88 lines, stale version that pytest doesn't collect) is also tracked.

**Fix:** remove all five from the tree (`git rm`), add patterns to
`.gitignore` (`command-code-session-*`, `*.bak`). History rewrite only if the
user approves (per charter §15.4, no destructive history ops without
approval).

### C12. Documentation facts are wrong in the newest reports

Verified against the repo:

| Claim | Location | Reality |
|---|---|---|
| "66,514 unified rows (11,508 classifier rows)" | plan.md §6 | Current manifests: **55,030** / **9,278** (restored artifacts) |
| "current artefacts are not verified" | README.md:233 | `verify_provenance.py` → 0 failures (verified this session) |
| CUAD "MIT-like license", MAUD "Apache 2.0" | nlp/evaluation/README.md | CC BY 4.0 per phase_2c report + autonomous_execution report (needs final settlement) |
| CUAD "Contract Understanding **Atlantis** Dataset"; MAUD "Multi-Document Understanding" | phase_2c_readiness_report.md | Atticus / Merger Agreement Understanding (plan.md §6 is correct) |
| "Integration Tests: 228 passing" | nlp/evaluation/README.md | 262 (this session); 228 matches no point in history |
| "Synthetic Nature: Generated from templates" (of CUAD/MAUD) | phase_2c_readiness_report.md | Both are real-atticus/EDGAR datasets |
| Split "Train 9,278 / Dev 22,450 / Test 13,130" | phase_2c_readiness_report.md | Mislabels artifacts; no 13,130-row test artifact exists |
| plan.md §8 "Known limitation: provenance exits 1" | plan.md | Closed by `1b13c2d`; checkbox still open |

**Fix:** correct plan.md §6/§8, README:233, nlp/evaluation/README.md, and
supersede or correct phase_2c_readiness_report.md; stamp every "N tests pass"
claim with commit SHA + date.

### C13. `strip_headers_footers` is dead code; `page_hint` is never set

`app/services/parser.py:345-351` is defined and unit-tested but has **no
production call site** (grep-confirmed) — PDF headers/footers ("Page 1 of 12",
"Confidential") stay in the text and pollute segmentation/NER.
`Clause.page_hint` (schemas.py:85) is always `None` — page-level provenance
is discarded at the parse→segment boundary despite the charter's
"preserve source locations".

**Fix:** call `strip_headers_footers` per page before `clean_text`; build a
char-offset→page map from `parsed.pages` and stamp `page_hint` (or drop the
field and document it).

### C14. DOCX table content is lost

`app/services/parser.py:236-243` iterates `doc.paragraphs` only —
`python-docx` does not include `w:tbl` content. Fee schedules, signature
blocks, and tabular annexes in DOCX contracts are silently dropped from
`full_text`, and the parse still "succeeds".

**Fix:** walk `doc.element.body` in document order (or paragraphs + tables
with position tracking); at minimum, warn when tables exist but are not
extracted.

### C15. Scanned-PDF garbage can pass as a successful analysis

`app/services/parser.py:97-100` only fails when `full_text` is entirely
empty. If pdfplumber extracts a stray glyph on some pages (page numbers,
ligatures) and OCR is unavailable (tesseract not installed in this container —
check with `which tesseract`), a 40-page scan can produce a few characters of
noise → non-empty `full_text` → `status=SUCCEEDED` with a 1-clause "analysis"
and **no warning**. OCR failure is only logged, never surfaced in
`parsed.warnings` (parser.py:191, 205-207).

**Fix:** (a) append warnings when OCR was attempted on any page or was
unavailable; (b) add a minimum-meaningful-content threshold (e.g. <200 chars
or <50% of pages with text ⇒ `DocumentParseError` with the specific reason);
(c) surface per-page method in `AnalysisResult.metadata`.

### C16. `_detect_parties` window + cap miss real parties

`app/services/analyzer.py:407-413` — scans only the **first 3 clauses**,
caps at 4 parties. Parties that appear only in later clauses (guarantor,
parent) or only in the **signature block** are missed. The NER fallback
(step 2) requires `PARTY`/`ORG` entities, which the regex NER **never emits**
(only DeBERTa enrichment does, and that's optional) — so on the default
install step 2 adds nothing. Zero parties found ⇒ silent `parties=[]`, no
warning.

**Fix:** scan the last 3 clauses too; warn when zero parties are detected;
document the no-ML limitation of step 2.

### C17. `_first_date` picks the first DATE entity, not the effective date

`app/services/analyzer.py:479-496` — "This Agreement dated 1 January 2020 was
amended on 15 April 2024" yields effective_date = **1 January 2020** (the
original instrument's date), not the operative date of the current
agreement. `effective_date` is a headline API/UI field.

**Fix:** score DATE entities by sentence context ("effective date", "made
on", "entered into", "commence"); fall back to first only with a warning.

### C18. `case_law.py` citation issues (verified by the subagent via websearch; treat as REPORTED until re-verified)

- `RISK_GOV_001` cites **s. 28 ICA** (restraint of legal proceedings) for a
  *governing-law* finding — misapplied authority; a foreign governing-law
  clause is generally enforceable in India unless against public policy.
  Either re-scope the rule to forum selection or replace the citation.
- `RISK_DATA_001`/`RISK_DATA_MISSING` cite "DPDP ss. 8 & 33" as if both were
  the notification duty — s. 33 is the **penalty** section.
- Missing entries for `RISK_TERM_001`, `RISK_RENEWAL_001`,
  `RISK_INDEMNITY_001`, `RISK_LIABILITY_002` — four HIGH-severity findings
  carry no legal grounding at all in the UI.
- Typo in the user-facing disclaimer: "abreviated" (case_law.py:9).
- `CaseLawReference` has no verification-date / retrieval metadata (charter
  §9.2 requires it).

**Fix:** per-citation metadata (verified_on, source_url), re-verify each
citation against primary sources, add the four missing entries or explicitly
mark them "no verified authority — review required", and fix the typo.

### C19. Classifier floors evaluate the training corpus

`tests/test_classifier_accuracy.py:105-127` computes top-1/top-3 accuracy on
`data/processed/clause_classifier.csv` — the same document pool that built
the keyword bank (`build_training_data.py:58`) and that overlaps the bundled
TF-IDF model's (leaky) training corpus. The repo's own `eval_classifier.py`
banner says such a metric "cannot be reported as generalization performance",
yet the pytest floors (≥30%/≥55%) are enforced on it. The "top-3" test
actually checks membership in the full label list, not top-3.

**Fix:** reframe the floors as "in-distribution regression floors" explicitly,
or (better) evaluate on a family-disjoint held-out set (see R2).

### C20. `evaluate_against_csv` docstring lies

`nlp/clause_classification/classifier.py:471,495` — docstring says
"rule-based classifier" but the call uses the **hybrid** (no
`rule_based_only=True`). Metrics silently change depending on whether the
model artefact is present.

**Fix:** pass `rule_based_only=True` or rename to hybrid; add both paths.

---

## 2. REPORTED findings (subagent static analysis — not yet empirically confirmed)

These are credible and cited, but per charter §15.1 they must be reproduced
before a fix is trusted. Grouped by area.

### 2.1 NLP / risk engine (subagent 1)

- **DeBERTa classifier loads an untrained base model**
  (`classifier_ml.py:35-39`, default `clause_model =
  microsoft/deberta-v3-base` in config.py:59) with
  `ignore_mismatched_sizes=True` → a random head; if `[ml]` is ever
  installed, garbage labels enter the hybrid merge with softmax "confidence".
  In the current env (no torch/transformers) the path is inert.
- **Evidence spans bind the whole clause, not the trigger**
  (rules.py:626-635) — reviewer can't see which sentence fired.
- **`RISK_TERMINATION_001` vs `RISK_TERM_001`** in
  `metrics_integration.py:98` (also confirmed by orchestrator, see C1).
- **`_TYPE_BASELINE` severity priors** in risk_model.py:186-215 teach the ML
  booster that *every* LoL/Indemnity clause is HIGH risk.
- **Keyword bank built from last 4-6 tokens** of CUAD spans
  (classifier.py:330-340) — generic tails over-match.
- **No abstention in the rule classifier** — unmatched text becomes
  `Miscellaneous @ 0.3` (classifier.py:429-430) instead of an empty label
  list.
- **`rule_missing_data_protection` dead code** (rules.py:335-337, always
  returns None, not registered); `RiskRule.clause_type` field is never
  consulted by `apply_rules` (drift risk); `score_contract` ignores its
  `clauses` param (scorer.py).
- **`ner_ml.py` dedup drops offset** (same entity text at two positions →
  only first kept); date regex matches "3/4/2"-style noise (ner.py:78-79).
- **`severity_order.get(..., 0)`** silently ranks unknown severities below
  LOW (rules.py:531).
- **zip-by-index fragility** between analyzer's filtered related-ids and
  the resolver's index-based text mapping (analyzer.py:175-182,
  resolver.py:189-195) — potential mis-attribution of cross-reference texts.
- **TDS rule is contract-level but keyed to "any Payment Terms clause
  exists"** (rules.py:417-437) — broader than intended.

### 2.2 Backend (subagent 2)

- **`contract_id` collision**: same content uploaded twice in the same second
  → identical `contract_id` (sha256[:10] + `%Y%m%d_%H%M%S`) → Neo4j MERGE
  merges two analyses into one node; Postgres upsert overwrites. (routes_contracts.py:156-161)
- **Postgres `_AVAILABLE_CACHE` once-down = forever-down** (postgres.py:137-146) —
  a transient failure at first use permanently disables metadata persistence
  for the process lifetime.
- **`get_engine()` not thread-safe** (postgres.py:84-107) — double-init race
  under uvicorn's threadpool.
- **JWT `sub`/`role` claims trusted without re-checking `user_store`**
  (deps.py:29-51) — demoted/deleted users keep valid tokens for up to 60 min;
  no warning when `AUTH_SECRET_KEY` is the shipped dev default.
  (Orchestrator note: bcrypt 5.x hash/verify was tested directly and WORKS —
  the subagent's C3 "bcrypt broken" hypothesis is disproven; the passlib
  incompatibility is irrelevant because passlib is bypassed.)
- **Upload read cap**: `file.size` pre-check is dead code (attribute doesn't
  exist); the `read(max_bytes+1)` cap works but truncates silently instead of
  413 on a >25 MB stream. (routes_contracts.py:56-62)
- **No rate limiting on `/api/v1/auth/token`** (routes_auth.py:15-37).
- **Corrupt job result JSON → `result=None` → 404 "not found"** (jobs.py:92,
  routes_contracts.py:116) — a succeeded job appears not to exist.
- **Contract read routes conflate processing/failed/missing as 404**
  (routes_contracts.py:113-142) — users can't see job errors.
- **`fetch_graph` is O(all edges) per call** and owner-unaware (queries.py:216-260).
- **Daemon job threads unbounded** (one per upload, no pool/semaphore,
  jobs.py:126-154); no `finally` guarantee against stuck-RUNNING jobs.
- **`AUTH_USERS` parse failure silently falls back to seeded admin/admin**
  (security.py:145-155) — a "silent fallback that makes a failed stage look
  successful" in charter terms.
- **`role_allows` asymmetric unknown-role default** (security.py:208-214).
- **`playbook_id` form field accepted but never used** (routes_contracts.py:39-42).
- **uploads/ never cleaned up** (fs.py / config.py) — unbounded growth.
- **`/healthz` triggers Neo4j connect attempts** (main.py:93-110, neo4j.py:73-76).
- **`connect_args={"connect_timeout": 3}`** is psycopg2-specific (postgres.py:95).

### 2.3 Pipeline (subagent 4)

- **2M-char truncation** warns but cuts mid-sentence with no indication of
  what was lost (parser.py:102-106); risk findings on a truncated document
  are partly meaningless (missing-clause checks).
- **`_split_long_clause` fixed-char stage can cut mid-word**
  (segmenter.py:391-394) for whitespace-less stretches.
- **Offsets are into *cleaned* text, not the original file** — `clean_text`
  (NFKC + whitespace collapse) makes a document→cleaned offset map
  necessary for any original-document highlighting; the API exposes
  `char_start/char_end` without that caveat beyond the EvidenceSpan
  docstring. (By design, but under-documented for the charter's
  "exact offsets into the original text" requirement.)
- **Numbered list items on their own lines can be misread as headings**
  (segmenter false positive): "(a) ₹10,000;" as a line matches the
  `(a)` section pattern → clause fragmentation.
- **Headings with trailing periods rejected** ("2. Definitions." loses its
  section number → cross-reference resolver and HEADING_HINTS lose it).
- **Per-page OCR/pdfplumber degradation never surfaced** (mixed-quality
  pages without warning).
- **Binary garbage .txt "parses successfully"** (latin-1 never fails).
- **Job exception capture IS correct** (jobs.py:143-151) — verified good.

### 2.4 Data & models (subagent 3)

- **Model ≠ data**: `data/processed/` is train-only (post-restore) but
  `models/tfidf_classifier.joblib` + `risk_classifier.joblib` were trained
  on the full CUADv1 (train∪test) corpus and were **never retrained** from
  the clean data. Repo-documented overlap figure: **1,706 of 11,508**
  production rows verbatim in held-out docs (pre-restore).
- **`test_no_leakage.py` proves lineage, not text-dedup**: T1c
  (near-duplicate 8-gram) is report-only; the keyword bank is
  `LINEAGE_EXEMPT` (no per-row lineage); the "no leakage" name overstates
  the guarantee.
- **Class imbalance**: Definitions 1,760 (19%) vs Confidentiality 48 (0.5%);
  12 of 26 taxonomy categories have **zero** CUAD-derived rows
  (Indemnification, Data Protection, Dispute Resolution, Force Majeure,
  Service Levels, Change Control, Notice, Acceptance, Compliance, Stamp
  Duty, TDS/GST, Arbitration Seat) — the ML half of the hybrid can only
  emit the 14 CUAD-mapped classes; every Indian-specific category is 100%
  rule-dependent with no gold labels.
- **`unified_examples.jsonl` skew**: Definitions 28.7% + Non-Compete 23.7%.
- **`sample_msa.txt` is synthetic with fictional parties** (CIN
  `...123456` / `...098765` tells) — all demo/harness metrics are
  behaviour checks on hand-crafted boilerplate, not generalization.
- **MAUD rows are not independent documents** (multi-page concatenation,
  same contract across rows) — per-row dedup under-counts.
- **Honest capability statement (adopt this verbatim in reports):**
  > The only non-synthetic numbers in `reports/` are provenance/lineage
  > checks (pass) and near-zero baseline F1s on synthetic cases. No metric
  > in this repository supports a claim that any model generalizes to
  > unseen contracts, and no metric supports a claim about Indian-law
  > correctness. The bundled models are leaky and weakly-supervised; the
  > data artifacts are lineage-clean but the models were not retrained from
  > them.

### 2.5 Tests & evaluation (subagent 5)

- **262 tests: ~3-4 tautological, 1 vacuous**
  (`test_evaluation_harness.py::test_case_known_limitation_notes_are_present`
  has `EXPECTED_KNOWN_LIMITATIONS = set()`), **14 artifact-gated** (skip in
  exploratory mode / hard-fail in `BCC_EVAL_MODE=ci`), 2 trivially-passing
  "regression" existence checks.
- **`metrics_integration.py` reimplements P/R/F1 inline** while
  `metrics.py`'s real `compute_obligation_metrics`/`compute_risk_metrics`
  are exported but never called; `slot_level_metrics` hard-coded `{}`.
- **No rules-only vs ML-only vs hybrid comparison exists anywhere** (charter
  §11.2) — `rule_based_only=True` exists and is trivially usable.
- **Abstention/uncertainty evaluated nowhere** (charter §11.7).
- **Legal grounding evaluated as citation *presence* only**
  (test_regressions.py:52-63) — charter §11.6 unmet.
- **e2e/api tests have no content assertions** (any RISK_ id passes,
  test_e2e.py:27-28; graph nodes truthy only).
- **RLS tested only at HTTP layer** — persistence layer (Neo4j direct reads,
  Postgres fallback path) untested.
- **Auth gaps**: no token-expiry, tampered-JWT, admin-via-HTTP, or
  seeded-admin-fallback tests.
- **Parser coverage is 3 tests** (one a constant assert); OCR path, PyMuPDF
  fallback, DOCX, 2M cap, 413 all untested.
- **Job eviction at cap 200 untested**; `_persist` untested beyond datetime.
- **`test_classifier_accuracy.py` loads the keyword bank at import time** —
  order-dependent global mutation.
- **No clean-clone composition test** (whole pipeline with no
  `data/processed/` + no `models/`).
- **`nlp/evaluation/README.md` references nonexistent `reporter.py` /
  `baseline.py`** and stale counts.

### 2.6 Docker/infra (subagent 6)

- **`.dockerignore` excludes `data/processed/`** → the container runs with a
  **degraded classifier** (no CUAD keyword bank), undocumented.
- **`pip install .` ignores `uv.lock`** → image can drift from the tested
  lockfile; three dependency sources (pyproject / requirements.txt /
  uv.lock) are a maintenance hazard.
- **`API_HOST=0.0.0.0` + ports exposed + auth off by default** = world-
  readable demo on any port-forwarded host; README doesn't state the
  exposure caveat.
- **uploads/ volume bind writes real contract bytes to the host** —
  confidentiality consideration, no cleanup.
- **Docker build coupled to the root duplicate packages** (see C10).
- **Compose service names/healthchecks are correct** — verified good.

---

## 3. Verified-good (what the audit confirmed is right)

- **Graceful degradation is real**: every external dep (Neo4j, Postgres,
  torch, OCR, model artefacts) has an explicit no-op path; the zero-infra
  demo genuinely works (re-run this session).
- **bcrypt 5.x works** with the direct-`bcrypt` code path (tested:
  hash/verify round-trip OK, wrong password rejected). The passlib
  incompatibility is bypassed by design.
- **Evidence binding never fabricates**: clause-level spans are exact
  slices; contract-level findings are `evidence_status="unverified"` with
  explicit `search_scope`; ML findings are `source="model"` and never
  "direct". Repeated-sentence obligation offsets abstain to `None`.
- **Cross-reference cap suppression is fail-closed** (rules.py:115-156) and
  locked by strong adversarial tests (test_p4_*).
- **Provenance verification is fail-closed** and passed (0/0 this session);
  `test_no_leakage.py` L1-L5 forged-manifest negative controls are genuinely
  adversarial.
- **RLS 404-not-403** is implemented consistently at the HTTP layer,
  including the graph route checking ownership before touching Neo4j.
- **500 handler** leaks exception type only in development.
- **Offset architecture is layer-consistent**: segmenter
  `cleaned[char_start:char_end] == clause.text` is locked by
  `_assert_all_slice_exact` tests; entity/obligation/evidence offsets are
  clause-relative and documented as such.
- **Negation-aware stamp/TDS detection** in NER (ner.py:275-338) with
  thorough positive/negative/negation test matrices.
- **UI**: no XSS paths found (user strings escaped or markdown-only);
  `analyse_locally` fallback runs the FULL pipeline (not truncated).
- **Charter-aligned wording**: "not legal advice", "not a calibrated
  probability", "review prompt" — no "is illegal" / "violates section X"
  language anywhere in user-facing text.
- **Master prompt and charter are mutually consistent** (no conflicts).

---

## 4. Prioritized fix plan (for Phase 3 approval)

Ordered by (charter impact × confidence / cost). **Nothing here has been
implemented yet** — this is the plan, per the charter's "do not start by
adding features" rule.

### P0 — Correctness of what the product claims (do first)
1. **Fix the evaluation ground truth** (C1, C2): regenerate
   `cases_gold.json` with real party names / real rule IDs / anchored spans;
   fix `RISK_TERMINATION_001`→`RISK_TERM_001` in
   `metrics_integration.py:98`; make the regression gate non-tautological.
   *(Highest charter value: without this, no future improvement is
   measurable.)*
2. **Negation guard in risk rules** (C5): reuse NER's `_is_negated_mention`;
   suppress RISK_LIABILITY_002 when a cap is present; kill the confirmed
   false positives.
3. **Fix `NOTICE_PERIOD_RE`** (C3) — mandatory deontic prefix, separate
   DURATION label.
4. **Fix `detect_arbitration_seat` steps 3-4** (C4) — arbitration-context
   requirement.
5. **Fix `rule_governing_law_mismatch`** (C6) — use
   `detect_governing_law` + jurisdiction check.
6. **Persist `created_at`/`finished_at`** and fix `_latest_job_for` /
   `list_jobs` merging (C8, C9) — results currently lost/stale.
7. **Obligation severity** (C7): deadline urgency out of the primary
   severity determination.

### P1 — Data/model integrity
8. **Retrain both bundled models from the train-only
   `data/processed/`** (or drop them and go rule-only) — closes the
   model≠data gap; re-stamp `PROVENANCE_STATUS.json`.
9. **Build a family-disjoint held-out evaluation set** (split CUAD by
   template family) and re-run classifier floors on it; add the
   rules-only vs hybrid comparison (trivial with `rule_based_only`).
10. **DOCX tables** (C14), **scanned-PDF garbage threshold + OCR warnings**
    (C15), **`strip_headers_footers` wiring** (C13), **party-detection
    window/signature block + zero-party warning** (C16), **`_first_date`
    context scoring** (C17).

### P2 — Security hardening (report-only until approved)
11. `contract_id` uniqueness (uuid component); Postgres re-probe instead of
    once-down cache; `get_engine` lock; token re-validation against
    `user_store`; rate-limit `/token`; 413 on true oversize; surface job
    errors (failed ≠ 404); `AUTH_USERS` parse failure must not silently
    fall back to admin/admin.

### P3 — Docs & hygiene (cheap, high trust value)
12. Fix all C12 doc claims (plan.md §6/§8, README:233, evaluation README,
    phase_2c report); stamp "as of <sha>" on every count.
13. Delete root duplicate packages + fix Dockerfile coupling (C10); delete
    session dumps + .bak (C11); gitignore patterns.
14. `case_law.py`: re-verify citations, add missing entries, add
    verification-date metadata, fix typo, add per-citation "unverified" flag
    (C18).
15. Add missing tests (P0 fixes each get regression tests; plus parser
    paths, 413, eviction, clean-clone composition, rules-only/hybrid
    comparison, abstention measure).

### Explicit non-actions (charter §24)
- No frontend expansion.
- No LLM/redline/Indic-language work.
- No Neo4j/Postgres infra changes beyond the persistence-bug fixes above.
- No history rewrite without approval.
- No pushing to origin (local only, per user).

---

## 5. Subagent session IDs (for follow-up questions)

| Area | Session |
|---|---|
| NLP core | `ses_e5f46592cffeTJ91l0gNOqhz7f` |
| Backend | `ses_e5f46592affeAdpY9tKL9rC1Dg` |
| Data/models/leakage | `ses_e5f465929ffeMasC3ggDDxffiO` |
| Pipeline/parser | `ses_e5f465928ffehe4T0OggxB1m0Z` |
| Tests/evaluation | `ses_e5f465926ffeIuTY3q7umGJBxb` |
| Docs/UI/infra/legal | `ses_e5f46591dffepTn3howkEJoOku` |

## 6. Method notes (charter §15)

- Baseline recorded before any change: 262 passed / ruff 3×B008 /
  provenance 0-0 / demo runs (HEAD `8d1a8c8`).
- Subagents ran read-only; four of six lost shell access mid-session and
  fell back to static analysis — hence the CONFIRMED vs REPORTED split in
  this document. The orchestrator re-ran the highest-stakes claims
  (C1-C10, C15 partial) directly.
- No files were modified, no commits made, nothing pushed, during the audit
  itself (this report is the only new file; the venv rebuild in `.venv/` is
  gitignored and environment-local).
