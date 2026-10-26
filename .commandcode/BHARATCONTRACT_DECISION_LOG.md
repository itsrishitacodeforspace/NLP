# BharatContract AI — Decision Log

Chronological record of decisions, approvals, restrictions and rejected approaches.
Labels: **[REPORTED]** = from project history/earlier in the session chain; **[THIS-SESSION]** = verified during
this export. Dates are session-relative (all 2026-10-26 unless stated).

---

## D0 — Project framing (charter)
- **Decided:** the project is a *college project* prioritising integrity, reproducibility and honest
  limitations over feature breadth.
- **Decided:** neutral bilateral review by default; party-focused review only when the represented party is
  identified.
- **Decided:** no paid datasets, no LLM/keyword-driven legal verdicts, no dashboard expansion, no model
  proliferation unless justified.
- **Rejected:** "make the repo look impressive"; rewriting working components without evidence.

## D1 — Evidence standards for the agent
- **Decided:** every claim labelled VERIFIED / REPORTED / INFERRED / UNKNOWN / CONTRADICTED; no fabricated
  test results, citations, hashes or file paths; a manifest proves lineage only, never accuracy.
- **Decided:** separate **artifact provenance** ≠ **evaluation** ≠ **predictive validity**.

## D2 — Baseline audit values (later stages build on these)
- **Recorded [REPORTED]:** `main` @ `cbd9c29fa3c24b229aa8bc20ee804a2d3985d4f5`; uv-managed Python 3.12.14;
  host Python 3.13.13 (out of the declared range); `uv lock --check` PASS; `ruff` clean; initial suite
  38 passed; `app.main` imports.
- **Recorded [REPORTED]:** Neo4j/Postgres/Redis/Celery/auth not operational; DeBERTa deps + weights absent;
  `tesseract` absent → OCR dead.

## D3 — Scope decision for evaluation
- **Decided:** Option B — commercial services cluster (MSA / Service / Vendor), with NDA as a
  classification-only adjunct; Employment excluded from risk evaluation.
- **Rationale:** the only bundled fixture is an MSA; all 10 risk rules target commercial service clauses;
  15 of 26 internal labels have dataset support; the Indian-statutory labels (Stamp Duty, TDS/GST,
  Arbitration Seat) have **no** dataset support.
- **Rejected:** NDA risk detection (0 rules, no labels); SPA/Lease; all 8 `ContractType` values.

## D4 — Data-lineage correction (Gate A)
- **Decided:** the earlier "407/408 CUAD mismatch" was **my own counting error** (set-cardinality vs
  document-count). There is **no divergent record**; CUADv1 = train ∪ test on distinct normalized texts.
- **Rejected:** any claim that a record differed; any assumption of document-level isolation from filenames.

## D5 — Leakage remediation design (P1 provenance work)
- **Decided:** split identity must be resolved from **file path + SHA-256** against a hash-pinned allowlist,
  never a caller label; fail closed on unknown/drifted sources.
- **Decided:** manifests record source splits/hashes/command/code revision; row-level lineage (`doc_id`,
  `split`) is the real guard against forged manifests.
- **Known accepted risk (documented, not removed):** `--allow-whole-corpus` still permits the mixed corpus.
- **Decided:** manifests are **not** upstream-authenticated (`upstream_authenticated: false`,
  basis = internal partition consistency).

## D6 — A3 staged rebuild (approved, executed, not swapped)
- **Approved:** backup + staged rebuild only.
- **Executed [REPORTED]:** backup to `C:\Users\Ivermectin\Documents\bharatcontract\a3_backup_20261026T011900\`
  (9 files + manifest, 9/9 hash+size OK); rebuild into `data/processed.staging/` from train-only sources.
- **Decided:** **no swap** into `data/processed/`; `CUADv1.json` not used for training.
- **Decided:** `data/processed.staging/` added to `.gitignore` so staged output can never be committed.

## D7 — Pre-replacement verdict
- **Decided:** **NOT READY** for replacement, on two procedural grounds (staged artifacts themselves
  verified): (a) the only backup was in the **ephemeral** scratchpad; (b) the verifier ignored row-level
  lineage.
- **Follow-up approved:** durable backup copy + row-level lineage in `scripts/verify_provenance.py`.
- **Decided:** manifests are unsigned assertions → the verifier must check row lineage, not just hashes.

## D8 — Keyword-bank behavioural comparison
- **Decided:** compare production vs staged bank on a **fixed, reproducible** corpus (12 MSA clauses + 300
  rows sampled with `random.Random(42)`), each bank in a **separate process** with the production bank's
  import-time auto-load suppressed.
- **Result [REPORTED]:** 308/312 identical; 4 changed; provider/staged rule IDs identical on the fixture.
- **Decided:** **no accuracy claim** — the sample is small, unlabelled and partly training-overlapping.

## D9 — P1 approved (context resolution only)
- **Approved scope:** deterministic resolver; no rule/severity/trigger changes; produce but do not consume.
- **Explicitly prohibited:** deciding that every "notwithstanding" overrides; inferring precedence from
  clause order; treating a reference as proof a conflict is resolved; TC-05-specific rules.
- **Implemented [REPORTED]:** `nlp/context/{__init__,resolver}.py`, `tests/test_context_resolution.py`,
  additive `Clause.context`, analyzer integration, report. Suite 71/64/7.

## D10 — P2 approved (evidence binding only)
- **Approved scope:** additive `EvidenceSpan` + five `RiskFlag` fields; bind once in `apply_rules`;
  ML findings marked model-only and unverified.
- **Explicitly prohibited:** changing rule triggers/severity/scoring/legal recommendations; P3;
  inventing spans; attaching an arbitrary nearby clause.
- **Implemented [REPORTED]:** 3 modified + 2 new files. Suite 81/74/7 (same seven failures).
- **Decided:** evidence is clause-granular for now; contract-level findings stay `unverified`.

## D11 — Standing restrictions (as of this export) [THIS-SESSION record, per supplied authorization]
- No production artifact replacement; `data/processed/` and `data/processed.staging/` stay distinct.
- No retraining, archive extraction, dataset regeneration.
- No P3–P7 implementation without explicit approval.
- Do not fix, hide or skip the seven provenance failures.
- No service startup; no Git staging/commit/amend/rebase/reset/push.
- No deletion/moving/overwriting of user files; no replacing existing `.commandcode/` files.

## Rejected approaches (cumulative)
- LLM-based coreference/precedence reasoning (new dependency, non-deterministic, unverifiable).
- Treating keyword presence as proof of a protection (or of its absence).
- Presenting model confidence as a calibrated probability.
- Retraining or swapping artifacts to make the test suite green.
- Blanket `xfail`/skip to obtain green tests.
- Using TC-05 as the sole acceptance criterion.
