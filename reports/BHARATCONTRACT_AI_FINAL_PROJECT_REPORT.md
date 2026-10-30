# BharatContract AI — Final Project Report

**Project:** BharatContract AI — Indian-context contract intelligence
**Report date:** 30 October 2026
**Prepared by:** Project team
**Repository:** `C:\Users\Ivermectin\Desktop\NLP\NLP`
**Verified at commit:** `8c60ae6` on branch `main`
**Report scope:** Backend, NLP pipeline, risk engine, verification, and limitations. The existing dashboard is outside the verification scope of this report.

---

## Abstract

BharatContract AI is a working prototype for automated review of commercial contracts, with emphasis on Indian statutory and arbitration risks. The system accepts PDF, DOCX, TXT, and Markdown files; parses and segments the document; classifies clauses; extracts entities and obligations; and applies a rule-first risk playbook backed by an optional machine-learning recall booster. Findings carry evidence spans, search scope, and statutory or case-law pointers, so that a reviewer can inspect why a flag was raised rather than receiving an unexplained score.

The project deliberately favours deterministic, offline behaviour. Every external dependency — Neo4j, PostgreSQL, OCR, and the optional transformer stack — degrades to a no-op or fallback, so the core pipeline runs with Python alone. The implementation is verified by a 171-test suite: **164 tests pass and 7 provenance tests fail closed** because the production `data/processed/` artifacts lack manifests and train-only lineage. A focused 102-test suite covering obligations, risk rules, risk-model wording, cross-reference behaviour, and the evaluation harness passes, and `ruff check .` reports no issues.

A deterministic evaluation harness (`nlp/evaluation/`, driven by `scripts/run_evaluation.py`) runs 17 synthetic labelled contracts through the full pipeline. At the verified commit, **16 cases pass, 1 is a documented known limitation, and there are no unexpected regressions**; three evidence-integrity invariants (model findings stay unverified; clause-level rule findings carry a direct span; contract-level findings are scoped and unverified) hold across every finding. This is a software-behaviour check on synthetic data, not a measure of legal accuracy or real-world reliability.

The bundled sample MSA was processed end to end into **12 clauses and 13 obligations**, with rule and model findings. The report does not claim held-out accuracy: the bundled models were trained on a corpus that overlaps held-out CUAD documents, the ML score is uncalibrated, and the legal citations are system-provided pointers rather than verified legal advice.

---

## 1. Introduction

### 1.1 Problem statement

Commercial contracts contain obligations, conditions, deadlines, liability limits, renewal mechanics, indemnities, and dispute-resolution terms spread across clauses and schedules. Manual review is slow, inconsistent, and difficult to audit. Generic contract tools often ignore Indian requirements such as stamp duty, tax-deduction-at-source (TDS) language, and the distinction between an arbitral seat and a physical venue.

The project asks a narrower, testable question:

> Can a deterministic, offline NLP pipeline identify material contract risks, preserve traceable evidence, and remain useful without a legal database, GPU, or cloud service?

### 1.2 Objectives

1. Parse and segment common contract formats into clause-level units with source offsets.
2. Classify clauses against a single internal taxonomy aligned with CUAD and MAUD.
3. Extract parties, dates, monetary amounts, identifiers, and obligations with conservative fallbacks.
4. Apply a transparent risk playbook covering global and Indian-specific concerns.
5. Attach evidence, search scope, related-clause context, and legal pointers to findings.
6. Expose the result through a FastAPI backend and persistence adapters.
7. Degrade gracefully when infrastructure or ML dependencies are absent.
8. Verify behaviour with automated tests and document what is not proven.

### 1.3 Scope and non-goals

**In scope**

- Backend API, parsing, segmentation, classification, NER, obligation extraction, risk scoring, evidence binding, provenance checks, and tests.
- Indian statutory rules for stamp duty, TDS, and Section 124 indemnity, plus global commercial rules.
- Deterministic cross-reference context and advisory notes.

**Not in scope**

- Legal advice or a legal opinion.
- A production-grade frontend or dashboard.
- Model retraining, artifact replacement, or accuracy claims on overlapping data.
- Whole-contract legal reasoning that resolves conflicting clauses automatically.
- Validation against a held-out, human-labelled risk corpus.

---

## 2. Background

### 2.1 Rule-first contract analysis

Contract playbooks are naturally rule-shaped: “flag unlimited liability”, “flag auto-renewal without notice”, “flag a foreign seat with an Indian venue”. Rules are explainable, deterministic, and cheap to run. Their weakness is recall and phrasing sensitivity: a rule that looks for `unlimited liability` can miss `liability shall be unlimited`.

The system therefore uses a hybrid design:

- deterministic rules for precision, traceability, and legal intent;
- TF-IDF classification for clause routing;
- an optional weakly-supervised risk model for recall on clauses that no rule matched;
- no learned model is allowed to override a rule finding.

### 2.2 Datasets and taxonomy

The classifier is aligned with CUAD-style clause categories through `nlp/taxonomy.py`, which is the single source of truth for internal labels and CUAD/MAUD mappings. The repository contains CUAD and MAUD source data and scripts that build train-only artifacts with manifests.

A critical distinction is maintained throughout:

- **artifact provenance** — where the bytes came from;
- **evaluation** — metrics on a held-out, family-grouped set;
- **predictive validity** — real-world correctness.

A manifest proves lineage only. It does not prove accuracy. The bundled classifier archives are explicitly marked `provenance-unverified` because their training corpus overlaps held-out CUAD documents. The project therefore reports test outcomes, not accuracy claims.

### 2.3 Indian legal anchors used by the playbook

The risk engine attaches informational pointers for:

- Indian Stamp Act, 1899, ss. 33 and 35;
- Indian Contract Act, 1872, ss. 124–125;
- Arbitration and Conciliation Act, 1996, ss. 2(2) and 20;
- Income-tax Act, 1961, ss. 194C/194J, 201, and 40(a)(ia);
- Digital Personal Data Protection Act, 2023, ss. 8 and 33;
- *Bharat Aluminium Co. v. Kaiser Aluminium Technical Services Inc.*, (2012) 9 SCC 552;
- *BGS SGS Soma JV v. NHPC Ltd.*, (2020) 4 SCC 234;
- other authorities recorded in `nlp/risk_scoring/case_law.py`.

These are review pointers. The module itself warns that citations are abbreviated and must be verified against the current statute or reported judgment. They are not legal advice.

---

## 3. System Design

### 3.1 High-level architecture

```text
Client / CLI
    |
    v
FastAPI API  ──>  Job service (in-memory cache + PostgreSQL fallback)
    |
    v
Analysis orchestrator (app/services/analyzer.py)
    |
    +--> Parser        PDF / DOCX / TXT / Markdown / OCR fallback
    +--> Segmenter     heading-aware clause splitting + offsets
    +--> Context       references, definitions, schedules, precedence candidates
    +--> Classifier    rule bank + TF-IDF (+ optional DeBERTa)
    +--> NER           regex-first entities (+ optional transformer enrichment)
    +--> Obligations   modal patterns, conditions, deadlines, beneficiary
    +--> Risk engine   rule playbook + evidence binding + advisory cross-refs
    +--> ML booster    optional recall-only model findings
    +--> Scorer        ordinal contract risk heuristic
    |
    +--> Neo4j         graph projection
    +--> PostgreSQL    contract/job metadata (fallback store)
```

### 3.2 Pipeline order

The pipeline follows the documented order:

```text
parse -> segment -> resolve context -> classify -> NER -> obligations
      -> risk rules -> evidence binding -> cross-reference notes
      -> ML booster -> aggregate score
```

Context resolution runs after segmentation and before rules. It is read-only enrichment: it does not change rule triggers or severity. The analyzer then attaches related clause text so rules and advisory notes can refer to cross-referenced provisions without treating a reference as proof that a conflict is resolved.

### 3.3 Core data model

| Model | Purpose | Key fields |
|---|---|---|
| `ContractSummary` | Contract-level output | parties, jurisdiction, governing law, seat, risk score/level, counts, top risks |
| `Clause` | Segmented clause | clause id, section, heading, text, character offsets, types, entities, context bundle |
| `Obligation` | Extracted duty/right | subject, counterparty, action, object, condition, deadline, source offsets |
| `RiskFlag` | Explainable finding | rule id, severity, explanation, recommendation, score, evidence spans, search scope, related clauses, cross-reference note |
| `EvidenceSpan` | Supporting passage | text, clause id, start/end offsets, locator, role |
| `AnalysisResult` | Complete response | contract summary, clauses, obligations, risks, warnings |

Evidence offsets are zero-based and end-exclusive relative to `Clause.text`, not raw file bytes. Repeated or ambiguous sentences leave obligation offsets `None` rather than guessing.

### 3.4 API surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/token` | Exchange username/password for a bearer token when auth is enabled |
| `GET` | `/api/v1/auth/me` | Return the current identity |
| `POST` | `/api/v1/contracts/upload` | Upload a contract and start background analysis |
| `GET` | `/api/v1/contracts/{id}/summary` | Contract summary |
| `GET` | `/api/v1/contracts/{id}/clauses` | Clause list |
| `GET` | `/api/v1/contracts/{id}/obligations` | Obligation list |
| `GET` | `/api/v1/contracts/{id}/risks` | Risk findings |
| `GET` | `/api/v1/jobs/{job_id}` | Job status and result |
| `GET` | `/api/v1/jobs` | List jobs visible to the caller |
| `GET` | `/api/v1/graph/{contract_id}` | Graph projection; falls back to in-memory result |
| `GET` | `/healthz` | Health, environment, auth flag, provenance summary |

Uploads accept PDF, DOCX, TXT, and Markdown. The API enforces an extension allowlist, an upload-size limit, and an empty-file check. Contract identifiers combine a UTC timestamp with a SHA-256 prefix of the uploaded bytes.

### 3.5 Persistence and degradation

- **Neo4j** stores the contract–clause–obligation–risk graph. If unavailable, writes log a warning and the graph endpoint rebuilds a projection from the in-memory analysis result.
- **PostgreSQL** stores job and contract metadata. If unavailable, writes become no-ops; the in-memory job cache remains the fast path.
- **OCR** is attempted when a PDF page yields fewer than 50 characters. If OCR is unavailable, digital text extraction still works.
- **torch/transformers** are optional `[ml]` extras. Without them, the rule classifier, regex NER, and bundled TF-IDF model still run.
- **Bundled models** are extracted on first use from `.7z` archives; no 7-Zip binary is required.

### 3.6 Authentication and row-level security

Authentication is disabled by default. When `AUTH_ENABLED=true`:

- users authenticate with a username and password;
- passwords are hashed with bcrypt, with a PBKDF2 fallback;
- tokens are HS256 JWTs with an expiry;
- roles are ranked `viewer < analyst < admin`;
- uploads require `analyst` or above;
- jobs and contracts carry an owner, and reads are scoped to that owner;
- another user's resource returns `404` rather than `403`, so existence is not leaked.

When auth is disabled, the demo remains open and owner filtering is skipped.

---

## 4. Implementation

### 4.1 Parsing

`app/services/parser.py` supports PDF, DOCX, TXT, and Markdown. For PDFs it tries pdfplumber, then PyMuPDF, then OCR on weak pages. DOCX uses `python-docx`. Text and Markdown are read and cleaned directly. Parsing is capped at 2,000,000 characters to avoid pathological inputs, and an empty or unreadable document raises a domain-specific `DocumentParseError`.

### 4.2 Segmentation

`app/services/segmenter.py` groups paragraphs into clauses using numbered sections, article/section headings, and capitalised headings. Markdown-prefixed headings such as `## 7. Limitation of Liability` are recognised. Clauses longer than 2,500 characters are re-split by paragraph. Each clause stores offsets into the cleaned document text.

### 4.3 Clause classification

The classifier combines:

- a rule/keyword bank derived from CUAD categories;
- a TF-IDF model bundled as `models/tfidf_classifier.7z`;
- optional DeBERTa-v3 enrichment when the `[ml]` extra and model are available.

`nlp/taxonomy.py` keeps internal labels and dataset mappings in sync. Rule-based fallbacks cover categories that CUAD does not contain, such as Force Majeure and Stamp Duty.

### 4.4 Entity extraction

NER is regex-first: parties, dates, Indian identifiers (CIN/PAN/GSTIN), INR amounts, notice periods, jurisdictions, and arbitration seats. Optional transformer enrichment is additive and silent when unavailable. This keeps the core demo deterministic and offline.

### 4.5 Context resolution

`nlp/context/resolver.py` builds a per-clause context bundle containing:

- references to clauses, sections, schedules, exhibits, annexures, and appendices;
- resolved, missing, or ambiguous reference status;
- defined terms (`"Term" means ...`);
- precedence/override language recorded as a **candidate**, never as proof;
- unresolved references.

The resolver does not decide legal meaning. It makes references traceable and gives later stages a place to record advisory context.

### 4.6 Obligation extraction

The obligation extractor is modal-verb based. It identifies duties, rights, prohibitions, and conditions. The current implementation adds:

- zero-based, end-exclusive source offsets; `Obligation.text` is the exact source slice;
- condition and exception spans, with the main-clause modal preferred over a protasis modal;
- deadlines outside conditions, including written-out and parenthetical forms such as `thirty (30) days`;
- conservative beneficiary/counterparty extraction using explicit `to X` or dative patterns;
- optional party aliases that map defined names to canonical labels;
- `None` rather than a guess when a recipient, subject, or location is ambiguous.

No-comma leading conditions such as “If required by law the Provider shall …” remain difficult without a parser; the responsible party is left `None` rather than invented.

### 4.7 Risk engine

`nlp/risk_scoring/rules.py` registers ten risk rules; the liability rule can emit two different finding types. Missing-clause checks run alongside the registry:

| Rule | Concern |
|---|---|
| `RISK_LIABILITY_001` | Uncapped or unlimited liability |
| `RISK_LIABILITY_002` | Limitation-of-liability clause lacking a cap |
| `RISK_TERM_001` | One-sided termination for convenience |
| `RISK_RENEWAL_001` | Automatic renewal without adequate notice |
| `RISK_INDEMNITY_001` | Broad indemnification |
| `RISK_DATA_001` | Tight breach-notification window |
| `RISK_GOV_001` | Foreign governing law in a domestic contract |
| `RISK_ARB_001` | Foreign arbitral seat with an Indian venue |
| `RISK_STAMP_001` | Stamp-duty language not detected (Indian contracts) |
| `RISK_TDS_001` | TDS language not detected (Indian payment clauses) |
| `RISK_S124_001` | Indemnity may not cover direct losses (Indian contracts) |

Contract-level Indian rules run once, not once per clause. Findings are de-duplicated by `rule_id`, keeping the highest severity and score.

#### Evidence binding

Every rule finding receives:

- `evidence_status="direct"` and a clause-text span when the finding is tied to a clause;
- `evidence_status="unverified"` and an explicit `search_scope` when the finding is contract-level or based on absence of language.

The system never fabricates a nearby clause span for a contract-level finding.

#### Section 124 scoping

`RISK_S124_001` previously scanned the whole contract for `direct losses` or `breach of contract`. An unrelated clause could therefore suppress the finding. The current implementation evaluates only indemnification clauses and records an indemnity-specific search scope. The finding remains qualified with “may” and “Verify the intended scope”; it never asserts that the clause is defective.

#### Advisory cross-references

Cross-reference context is advisory only. The engine records missing, ambiguous, or unresolved references and related clause snippets, but never suppresses a finding because a related clause exists or contains a matching keyword. This is deliberate: a reference that merely exists is not proof that it resolves the concern.

#### ML recall booster

`ML_RISK_001` is emitted only for clauses with no rule finding. It is marked `source="model"` and `evidence_status="unverified"`. The explanation states that the score is raw classifier output, not a calibrated probability, and asks for manual review. The model cannot override or remove a rule finding.

### 4.8 Risk scoring

`score_contract` computes an ordinal heuristic:

```text
score = highest finding score
      + 2 points per additional finding (maximum 20)
      + severity mass / 100 (maximum 10)
      capped at 100
```

Bands are:

- low: below 26;
- medium: 26–50;
- high: 51–75;
- critical: 76–100.

The score is not a probability. A value of 100 means “top of the critical band”, not “100% likely to be a problem”.

### 4.9 Provenance

Generated artifacts carry `<artifact>.manifest.json` files containing source hashes, split identity, build command, code revision, and artifact hash. `scripts/verify_provenance.py` fails closed: it exits non-zero when a manifest is missing or lineage is invalid. `/healthz` exposes a provenance block, and analysis warnings carry `PROVENANCE_UNVERIFIED` or `PROVENANCE_ABSENT` tokens.

The current production `data/processed/` directory has five artifacts and zero manifests. This is the reason for the seven failing tests described in Section 5.

---

## 5. Testing and Verification

All results below were observed on 29 October 2026 in the repository working tree.

### 5.1 Commands

```bash
uv run pytest --tb=no
uv run pytest tests/test_obligation_extraction.py \
  tests/test_regressions.py \
  tests/test_risk_model.py \
  tests/test_risk_rules.py \
  tests/test_p4_adversarial.py \
  tests/test_p4_context_rules.py \
  tests/test_p4_cross_reference.py \
  tests/test_evaluation_harness.py -q
uv run ruff check .
uv run python scripts/run_demo.py
uv run python scripts/run_evaluation.py
uv run python scripts/verify_provenance.py
```

### 5.2 Results

| Check | Result |
|---|---|
| Full test suite | **164 passed, 7 failed, 4 warnings** in ~70 s |
| Focused suite | **102 passed** |
| Synthetic evaluation harness | **16/17 cases pass, 1 known limitation, 0 regressions**; 3/3 evidence invariants hold |
| Lint | **All checks passed** |
| Demo | 2,846-character MSA parsed into **12 clauses and 13 obligations** |
| Provenance verifier | **5 failures, 0 skipped** (all missing manifests) |

The 171 collected tests cover parsing, segmentation, long clauses, classifier regression thresholds, context resolution, obligation extraction, evidence binding, risk rules (including written/parenthetical renewal-notice parsing, stamp-duty/TDS detection recall with negative controls, and conservative cross-reference cap resolution), risk-model wording, P4 cross-reference behaviour, the synthetic evaluation harness, authentication/RBAC, row-level security, API smoke tests, end-to-end analysis, and provenance.

### 5.3 The seven failing tests

All seven failures are in `tests/test_no_leakage.py`:

- `test_t1a_training_corpus_has_train_only_provenance`
- `test_t1b_corpus_rows_trace_to_train_only_sources`
- `test_t2a_keyword_bank_is_provenance_verified`
- `test_t2b_keyword_bank_manifest_declares_train_only`
- `test_t3a_maud_artifacts_have_manifests`
- `test_t3b_maud_artifacts_exclude_test_split`
- `test_t8_cuad_examples_provenance`

The immediate cause is missing manifests for:

```text
data/processed/clause_classifier.csv
data/processed/cuad_keyword_bank.json
data/processed/cuad_examples.jsonl
data/processed/maud_examples.jsonl
data/processed/unified_examples.jsonl
```

The corpus also lacks usable per-row `doc_id`/`split` lineage in the current production copy. These are **data-state failures, not code failures**. The guards are working as designed: they fail closed instead of silently accepting unverified artifacts.

A prior fresh-checkout workflow, recorded in `reports/recovery/RECOVERY_TRACKER.md`, regenerated train-only artifacts and completed the suite with exit 0. Replacing the production artifacts is a separate, approval-gated operation and was not performed in this pass.

### 5.4 Demo output

The bundled `data/raw/sample_msa.txt` produced:

| Field | Observed value |
|---|---|
| Title | Sample MSA |
| Parties | DTwelve Accommodations Private Limited; Bluepeak Technologies Limited |
| Effective date | 15 April 2024 |
| Governing law | Laws of India |
| Arbitration seat | Singapore |
| Clauses | 12 |
| Obligations | 13 |
| Overall score / level | 100.0 / critical |
| ML-added findings | 1 |

Top findings printed by the demo included uncapped liability (critical), broad indemnification (high), arbitration seat/venue mismatch (high), automatic renewal (medium), and a tight breach-notification window (medium).

The score of 100 reflects multiple concurrent findings and the volume/severity aggregation, not a probability that the contract is invalid.

### 5.5 What the tests prove — and what they do not

**Proven**

- The pipeline runs end to end on the bundled sample without external infrastructure.
- The obligation extractor preserves exact source slices and handles the tested condition, deadline, beneficiary, alias, and passive-voice cases.
- The Section 124 rule is no longer suppressed by unrelated `breach of contract` language.
- Risk-model wording no longer presents raw `predict_proba` as calibrated confidence.
- Authentication, RBAC, row-level security, API upload, and graph fallback paths work.
- Lint is clean.

**Not proven**

- Precision, recall, or F1 of the risk playbook on a held-out labelled set.
- Generalisation of the bundled classifiers.
- Legal correctness of the statutory or case-law pointers.
- Whole-contract conflict resolution.
- Behaviour on a large, diverse production contract corpus.

### 5.6 Synthetic evaluation harness

`nlp/evaluation/` defines a small labelled corpus of 17 synthetic contracts and runs each through the full `analyse_bytes` pipeline. All contracts are invented for evaluation; none is a real agreement, and the expectations encode *desired* behaviour. The harness is deterministic and reproducible via `uv run python scripts/run_evaluation.py`, which writes `reports/evaluations/synthetic_eval_results.{md,json}` and exits non-zero on any unexpected regression or invariant violation.

The corpus covers the behaviour categories required by the project charter:

| Category | Example case | Checks |
|---|---|---|
| Risk true positive | `uncapped_liability_tp`, `foreign_gov_law`, `one_sided_termination`, `broad_indemnity_tp`, `data_breach_tight`, `auto_renewal_no_notice` | the correct rule fires at the expected severity |
| Risk severity calibration | `auto_renewal_with_notice` | a 60-day same-clause notice reduces renewal severity to medium |
| Risk true negative | `capped_liability_tn`, `indemnity_direct_losses`, `complete_contract` | no false alarm when the protection is present |
| Uncertain legal conclusion | `stamp_tds_absent`, `indemnity_narrow` | stamp/TDS/S124 surface as qualified “not found / may — verify” prompts, never confirmed violations |
| Conditions and exceptions | `obligation_conditional` | both the condition and the exception are captured, with the deadline |
| Party/beneficiary ambiguity | `ambiguous_recipient` | a statute reference is not fabricated into a recipient |
| Cross-reference resolution | `liability_cap_in_crossref` | a cap in a referenced clause should prevent a “missing cap” finding |
| Passive voice | `obligation_passive` | the by-agent obligor and written-compound deadline should be recovered |
| Detection recall gap | `stamp_tds_present_missed` | present stamp/TDS language should suppress the review prompts |

At commit `8c60ae6`: **16 cases pass and 1 fails**. The remaining failure is a declared, documented known limitation, not a hidden regression:

- `obligation_passive` — hyphenated written compounds (“twenty-four”) are not normalised by the deadline parser, and the passive by-agent is not recovered in this construction.

Two former limitations were resolved in earlier passes (defects D13 and D14 below): `stamp_tds_present_missed` (the detectors now recognise “duly stamped paper” and “deduction of tax at source”) and `liability_cap_in_crossref` (a resolved cross-reference to a verifiably applicable cap now suppresses the “missing cap” finding; keyword presence alone still does not). Both cases pass and their `known_limitation` notes were removed; the locking test set was updated accordingly.

Three evidence-integrity invariants are also checked across every finding in every case and all hold: model-sourced findings always carry `evidence_status="unverified"`; clause-level rule findings always carry `evidence_status="direct"` with at least one evidence span; and contract-level findings are always `unverified` with an explicit `search_scope`. The locking test (`tests/test_evaluation_harness.py`) fails if a new case regresses **or** if a known-limitation case is silently fixed without updating the record.

This harness is a behavioural and regression instrument on synthetic data. It is **not** a held-out, human-labelled benchmark and yields no precision/recall/F1 or generalisation claim.

---

## 6. Results and Discussion

### 6.1 Defects corrected during hardening

| ID | Defect | Correction |
|---|---|---|
| D5 | Indemnification clause treated as limitation of liability, producing a spurious “missing cap” finding | Skip indemnification-heading clauses in the cap rule |
| D6 | Missing stamp duty/TDS presented as confirmed defects | Reframe as “not found — verify”; lower severities; keep review semantics |
| D7 | Obligations had no source offsets | Add zero-based, end-exclusive offsets and exact source slices |
| D8 | Conditions polluted subject/action/deadline | Mask condition spans; prefer main-clause modal; read deadlines from masked text |
| D9 | Beneficiary/counterparty missing or greedy | Conservative dative/`to X` extraction, aliases, `None` on ambiguity |
| D10 | Raw ML score presented as confidence | Rename to “model-suggested”; explain uncalibrated score |
| D11 | Section 124 scanned unrelated contract text | Evaluate indemnification clauses only; preserve unverified status and scoped search |
| D12 | Auto-renewal notice parsed with a digit-only regex, so a clearly stated `sixty (60) days` or `ninety days` in-clause notice was ignored and the finding stayed high severity | Shared `written_number_to_int` + `NUMBER_TOKEN_RE` parse digit, written and parenthetical forms; same-clause notices reduce severity to medium while cross-referenced notices remain advisory-only |
| D13 | `detect_stamp_duty_mention` / `detect_tds_mention` used narrow keyword lists and missed “duly stamped paper” and “deduction of tax at source”, so the “not found — verify” prompts fired on contracts that already address both | Add tight stamped-wording and at-source patterns with negative controls (“rubber-stamped”, “postage stamp”, “timestamp”, unrelated tax/deduction mentions do not match); Indian-jurisdiction gating, payment-clause scoping, and “not found — verify” semantics unchanged |
| D14 | `rule_uncapped_liability` evaluated only the clause's own text, so a clearly stated cap in a cross-referenced clause (“Except as set out in Clause 7.4” → 7.4 LIABILITY CAP) still produced a false `RISK_LIABILITY_002` | Fail-closed verification gate: suppression requires an explicit resolver reference with status `resolved` AND referenced text stating a cap that verifiably covers the assessed liability (mutual or matching party scope, no exclusions, no loss-category mismatch). Unresolved/missing/ambiguous references, related text without a resolved reference, exclusions, conflicts, and unknown party scope all keep the finding as a human-review prompt |

### 6.2 Interpretation

The system’s strongest property is **traceability**. A reviewer can see the clause, the exact character span for clause-level findings, the search scope for contract-level findings, the rule that fired, and the legal pointer attached to it. This is more useful than a single opaque risk score.

The weakest property remains **whole-contract reasoning**. The liability-cap rule now consumes resolved cross-references through a narrow, fail-closed contract (D14): a verifiably applicable referenced cap suppresses the “missing cap” finding, while anything uncertain stays a human-review prompt. The same is not yet done for renewal notice periods — a notice in a related clause can still produce “no notice period detected” — and precedence/override language is still recorded only as a candidate, never as proof.

The ML booster adds recall but not trust: its scores are uncalibrated, its labels are rule-derived, and the bundled model’s training corpus overlaps held-out CUAD documents. It is correctly presented as a review prompt, not a finding with evidence.

### 6.3 Suitability

The prototype is suitable for:

- demonstration of an end-to-end contract-analysis pipeline;
- reviewer assistance where findings are inspected before action;
- research on rule-first, evidence-bound legal NLP;
- offline or low-infrastructure deployments.

It is not suitable for:

- autonomous legal decisions;
- compliance certification;
- claims of measured accuracy or generalisation;
- replacing a qualified Indian advocate.

---

## 7. Limitations and Future Work

### 7.1 Evaluation gap

The deterministic synthetic harness in Section 5.6 is a first step: it fixes expected behaviour per case, keeps known limitations visible, and checks evidence-integrity invariants. It is not a substitute for a held-out, human-labelled risk corpus. The test suite and the harness verify behaviour and regressions, not predictive quality, and the 17-case synthetic set is too small and too clean to support precision/recall claims. A future evaluation should extend the harness with a pre-registered set of synthetic and real contracts covering:

- cross-references that change meaning and those that do not;
- definitions and exceptions;
- schedule-located protections;
- broken, circular, and ambiguous references;
- true and false missing-protection cases;
- at least two contract types.

Metrics should be reported per rule and per category: precision, recall, severity agreement, evidence-span correctness, and abstention behaviour. No aggregate “accuracy” should be reported from a small set.

### 7.2 ML calibration

The risk model’s raw `predict_proba` is not calibrated. Future work should either calibrate it on a held-out set, expose it only as a ranking score, or remove it from user-facing severity until calibration is validated. Retraining is approval-gated because it would replace bundled artifacts.

### 7.3 Whole-contract reasoning

The liability-cap rule now consumes cross-reference context under a narrow rule contract (D14): suppression only when a resolved, explicit provision states a verifiably applicable cap; anything weaker stays advisory and keeps the finding. The same contract should be evaluated for renewal notice periods, and precedence/override language remains a recorded candidate rather than proof of resolution.

### 7.4 P3 status model

The four-way missing-protection model (`present | incomplete | not_found_in_scope | undetermined`) is documented in `reports/recovery/P3_STATUS_DESIGN.md` and represented implicitly by existing `RiskFlag` fields. There is no explicit status enum or consumer yet. Adding one would improve API clarity but requires coordinated schema, persistence, and test changes.

### 7.5 Provenance

The production `data/processed/` artifacts remain unverified. The seven failing tests should remain visible until the artifacts are rebuilt from train-only sources with manifests and the provenance verifier exits 0. The bundled models remain `provenance-unverified`; no leakage-free or generalisation claim is made.

### 7.6 Parsing and extraction limits

- No-comma leading conditions can leave the obligor `None`.
- Ambiguous recipients and repeated sentences intentionally produce `None` offsets or fields.
- The parser handles common digital formats but does not guarantee layout fidelity for complex tables or scanned documents.
- The risk score is an ordinal heuristic, not a probability.

### 7.7 Legal review

Statutory and case-law pointers are informational and abbreviated. They must be checked against the current statute or reported judgment. The project does not provide legal advice.

---

## 8. Conclusion

BharatContract AI demonstrates a complete, offline-capable contract-analysis pipeline with a strong emphasis on traceability and graceful degradation. It parses and segments contracts, classifies clauses, extracts entities and obligations, applies Indian and global risk rules, binds evidence to findings, and exposes the result through a FastAPI backend with optional authentication and persistence.

The current verification is honest rather than flattering: 164 tests pass, 7 fail closed on stale provenance, the ML score is uncalibrated, and the project makes no held-out accuracy claim. The most important engineering contribution is not a single model score but the discipline of showing the clause, the span, the search scope, and the limitation behind each finding.

The next milestone should be a labelled evaluation corpus and conservative whole-contract reasoning. Until then, the system is a useful reviewer-assistance prototype, not a legal decision-maker.

---

## References

### Project sources

1. `README.md` — project overview and operating instructions.
2. `plan.md` — architectural source of truth and execution checklist.
3. `app/services/analyzer.py` — pipeline orchestration.
4. `app/services/parser.py`, `app/services/segmenter.py` — document ingestion.
5. `nlp/context/resolver.py` — deterministic context bundle.
6. `nlp/obligation_extraction/extractor.py` — obligation extraction.
7. `nlp/risk_scoring/rules.py`, `scorer.py`, `case_law.py` — risk engine.
8. `nlp/datasets/manifest.py`, `scripts/verify_provenance.py` — provenance checks.
9. `tests/` — behavioural and regression tests, including `tests/test_evaluation_harness.py`.
10. `nlp/evaluation/` and `scripts/run_evaluation.py` — synthetic evaluation harness; results in `reports/evaluations/synthetic_eval_results.{md,json}`.
11. `reports/recovery/RECOVERY_TRACKER.md`, `DEFECT_REGISTER.md`, `P3_STATUS_DESIGN.md`, `KIRO_HANDOFF.md`.
12. `reports/evaluations/generalizable_analysis_audit.md`, `p2_evidence_binding_report.md`, `provenance_guard_audit_20261027.md`.

### Legal and dataset pointers

13. Indian Contract Act, 1872, ss. 124–125.
14. Indian Stamp Act, 1899, ss. 33 and 35.
15. Arbitration and Conciliation Act, 1996, ss. 2(2) and 20.
16. Income-tax Act, 1961, ss. 194C/194J, 201, and 40(a)(ia).
17. Digital Personal Data Protection Act, 2023, ss. 8 and 33.
18. *Bharat Aluminium Co. v. Kaiser Aluminium Technical Services Inc.*, (2012) 9 SCC 552.
19. *BGS SGS Soma JV v. NHPC Ltd.*, (2020) 4 SCC 234.
20. CUAD (Contract Understanding Atticus Dataset) and MAUD, as bundled under `data/datasets/`.

The legal citations above are reproduced from the system’s advisory pointer table. They have not been independently verified against primary sources for this report.

---

## Appendix A — API example

```bash
# Start the API
uv run uvicorn app.main:app --reload

# Upload the bundled sample
curl -s -F "file=@data/raw/sample_msa.txt" \
  http://localhost:8000/api/v1/contracts/upload

# Read the result
curl -s http://localhost:8000/api/v1/contracts/<contract_id>/summary
curl -s http://localhost:8000/api/v1/contracts/<contract_id>/risks
```

OpenAPI documentation is served at `/docs`; health and provenance status at `/healthz`.

## Appendix B — Reproduction

```bash
uv sync --extra dev
uv run pytest --tb=no
uv run ruff check .
uv run python scripts/run_demo.py
uv run python scripts/run_evaluation.py
uv run python scripts/verify_provenance.py
```

For a clean evaluation corpus:

```bash
uv run python scripts/build_training_data.py
uv run python scripts/verify_provenance.py
```

Artifact regeneration is approval-gated and was not performed for this report.

## Appendix C — Selected recent commits

```text
8c60ae6 fix(risk): suppress missing-cap finding only for resolved, applicable cross-referenced caps
ece750f merge: reconcile origin/main (5a03a1b) with local stamp/TDS commits
aaa9fd5 fix(ner): detect stamped-paper and deduction-at-source wording for stamp/TDS
b35da18 fix(risk): parse written/parenthetical renewal notice periods
85011e2 test(eval): add deterministic synthetic evaluation harness and labelled corpus
42c25b0 refactor(analyzer): enrich clause context with related texts for cross-reference validation
f1bf4f4 docs(recovery): record S124 scope fix and current verification
975512b fix(risk): scope S124 check to indemnity clauses
0cf396a fix(obligations): add source offsets, conditions, beneficiary; clarify ML score
118e8ae fix(obligations): populate deadline_date, handle passive voice, written-out deadlines
d6e3f69 feat(risk): add advisory cross-reference analysis to findings
3ec86b6 fix(risk): qualify S124 indemnity finding and document scoring heuristic
e2468c8 fix(risk): mark stamp-duty and TDS "not found" as review, not confirmed defect
fe75ef2 fix(risk): don't treat indemnification clauses as limitation-of-liability
```
