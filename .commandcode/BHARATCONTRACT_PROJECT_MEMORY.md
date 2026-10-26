# BharatContract AI — Canonical Project Memory

> **READ THIS FIRST.** Self-contained handoff so a new agent can resume with minimal context.
> Export created 2026-10-26 by a documentation-only session. **No application code, tests, datasets,
> models, processed artifacts or existing files were modified.**
>
> **Evidence labels used throughout**
> - **[THIS-SESSION]** — inspected/executed during this export session.
> - **[REPORTED]** — supplied in project history or produced earlier in this session chain; **not**
>   re-executed here. Do not treat as freshly verified.
> - **[INFERENCE]** — plausible explanation needing confirmation.
> - **[UNRESOLVED]** — insufficient evidence.

---

## 1. What the project is

BharatContract AI — a college project for practical contract understanding and **evidence-grounded**
analysis, tuned for the Indian legal context where claims can actually be verified. Intended users:
legal professionals and businesses. The tool is an aid to review, **not** a substitute for legal advice.

**Product principles (binding):** evidence-first and traceable; cautious claims; reproducibility;
anti-hallucination. Review the *whole* contract (definitions, exceptions, schedules, precedence,
cross-references). Separate legal risk from commercial disadvantage and from drafting ambiguity. Neutral
bilateral review by default; party-focused review only when the represented party is identified. Separate
contract facts / legal authority / applicability / system inference. **A missing keyword is not proof of
absence; "not found" is not proof; a missing protection is not automatically illegal.** Keep serious but
uncertain concerns visible and qualified. Separate **severity** from **evidence strength**. Prefer primary
legal sources with identity, jurisdiction, effective/amendment status, relevant passage and verification
date; abstain when sources conflict or cannot be verified. Preserve negative results; use leakage-aware
evaluation. Avoid paid datasets, unnecessary infra, retraining, model proliferation and dashboard
expansion unless separately justified.

**Working style required:** read-only audit → reproducible baseline → root-cause analysis → small approved
changes → general-purpose regression tests → before/after evaluation → documentation + rollback. Never tune
to a single example contract.

---

## 2. Repository state at export time [THIS-SESSION]

- Branch **`main`**, in sync with `origin/main`. HEAD was reported earlier as
  **`cbd9c29fa3c24b229aa8bc20ee804a2d3985d4f5`** [REPORTED]; **HEAD was NOT re-read during this export**.
- **No commit, no push, no staging** for the entire session chain.
- Working tree (**verified in this export**):
  - **17 modified tracked files**: `.gitignore`, `AGENTS.md`, `README.md`, `app/main.py`,
    `app/models/schemas.py`, `app/services/analyzer.py`, `nlp/clause_classification/classifier.py`,
    `nlp/clause_classification/tfidf_model.py`, `nlp/datasets/cuad.py`, `nlp/datasets/maud.py`,
    `nlp/risk_scoring/risk_model.py`, `nlp/risk_scoring/rules.py`, `plan.md`, `pyproject.toml`,
    `scripts/build_training_data.py`, `scripts/eval_classifier.py`, `tests/test_classifier_accuracy.py`.
  - **Untracked**: `.commandcode/settings.json`, `.commandcode/taste/taste.md`,
    `.commandcode/taste/taste---general-preferences/taste.md`,
    `BharatContract_AI_Agent_Master_Prompt.md`, `BharatContract_AI_Project_Charter.md`,
    `models/PROVENANCE_STATUS.json`, `nlp/context/__init__.py`, `nlp/context/resolver.py`,
    `nlp/datasets/manifest.py`, `nlp/datasets/splits.py`, `nlp/provenance.py`,
    `reports/evaluations/generalizable_analysis_audit.md`,
    `reports/evaluations/p1_context_resolution_report.md`,
    `reports/evaluations/p2_evidence_binding_report.md`, `scripts/verify_provenance.py`,
    `tests/test_context_resolution.py`, `tests/test_evidence_binding.py`, `tests/test_no_leakage.py`.

**All of the above must be preserved.** They contain the entire hardening, provenance, P1 and P2 work.

---

## 3. Pre-existing `.commandcode/` content [THIS-SESSION]

| Path | Purpose |
|---|---|
| `.commandcode/settings.json` | permission allow-list (`Shell(uv:*)`, `Shell(kill:*)`) |
| `.commandcode/taste/taste.md` | learned coding-preference index |
| `.commandcode/taste/taste---general-preferences/taste.md` | general preferences |

**Preserved untouched.** All five handoff files below are *new*; no existing file was replaced.

---

## 4. How to run it [REPORTED — verified earlier in the session chain, not re-run here]

```bash
uv sync --extra dev                                # install
uv run pytest -q                                   # tests
uv run ruff check .                                # lint
uv run python scripts/run_demo.py                  # CLI demo, no infra
uv run uvicorn app.main:app --reload               # API  -> http://127.0.0.1:8000/docs
uv run streamlit run streamlit_app/Home.py         # UI   -> http://localhost:8501
docker compose -f docker/docker-compose.yml up --build
```
For the dashboard alone, `uv run streamlit run streamlit_app/Home.py` is sufficient — the UI falls back to
in-process analysis when the API on `:8000` is absent. No `.env` is required (defaults are dev-friendly).
Auth is off by default (`AUTH_ENABLED=false`).

**Environment:** uv-managed; the project env resolves **Python 3.12.14**; host `python` was reported as
**3.13.13**, outside `requires-python = ">=3.10,<3.13"` → always use `uv run`, never bare `python`.
`uv lock --check` PASS [REPORTED]. `ruff` clean [REPORTED].

**Not operational in the inspected environment [REPORTED]:** Neo4j, PostgreSQL, Redis, Celery,
authentication (disabled), DeBERTa (deps + weights absent), OCR (`tesseract` not on PATH).

---

## 5. Architecture and pipeline

```
parse → segment → [P1 resolve_context] → classify → NER → obligations → risk rules → [P2 _bind_evidence] → ML booster → score → API/UI
```

| Layer | Files |
|---|---|
| FastAPI | `app/main.py`, `app/api/routes_{auth,contracts,jobs,graph}.py`, `app/api/deps.py` |
| Core | `app/core/{config,logging,exceptions,security,time}.py` |
| Persistence | `app/db/{neo4j,postgres,queries}.py` |
| Services | `app/services/{parser,segmenter,analyzer,jobs}.py` |
| Schemas | `app/models/schemas.py` |
| Classification | `nlp/clause_classification/{classifier,tfidf_model,classifier_ml}.py` |
| NER | `nlp/ner/{ner,ner_ml}.py` |
| Obligations | `nlp/obligation_extraction/extractor.py` |
| Risk | `nlp/risk_scoring/{rules,scorer,case_law,risk_model}.py` |
| **P1 context** | `nlp/context/{__init__,resolver}.py` |
| Taxonomy | `nlp/taxonomy.py` (26 internal labels; CUAD/MAUD maps) |
| Datasets | `nlp/datasets/{unified,cuad,maud,splits,manifest}.py` |
| Provenance | `nlp/provenance.py`, `scripts/verify_provenance.py`, `models/PROVENANCE_STATUS.json` |
| UI | `streamlit_app/Home.py`, `pages/1..5`, `components/risk_card.py`, `api_client.py` |
| Scripts | `run_demo`, `build_training_data`, `train_tfidf_classifier`, `train_risk_classifier`, `eval_classifier`, `inspect_*`, `debug_*` |

Graceful degradation is a hard requirement: missing Neo4j/Postgres/torch/OCR/ML artifacts must no-op.

---

## 6. Baseline and test-count history (chronological — do not overwrite)

| Point | Collected | Passed | Failed | Source |
|---|---|---|---|---|
| Initial audit | 38 | 38 | 0 | [REPORTED] |
| After hardening + auth/RLS + case-law | 38 | 38 | 0 | [REPORTED] |
| After RLS + ML risk classifier | 46 | 43 | 3 | [REPORTED] |
| After provenance P1 (lineage verifier) | 61 | 54 | 7 | [REPORTED] |
| After **P1 context layer** | 71 | 64 | 7 | [REPORTED] |
| After **P2 evidence binding** | **81** | **74** | **7** | [REPORTED — not re-run in this export] |

**The seven failures are the same provenance guards and remain expected while production artifacts are
unswapped:** `T1a` (classifier CSV manifest missing), `T1b` (exact text overlap in the *unlineaged*
production CSV), `T2a`/`T2b` (keyword-bank manifest missing / no sources), `T3a`/`T3b` (MAUD example
manifests), `T8` (CUAD example manifest). **Never** describe them as fixed, and never suppress them.

---

## 7. Dataset / leakage / provenance history

**CUAD split facts [REPORTED, verified earlier in the chain]:** CUADv1 = 510 docs; `train_separate_questions.json`
= 408; `test.json` = 102; title-disjoint; **exact normalized-text intersection train×test = 0**; CUADv1 =
train ∪ test on distinct normalized texts (509 distinct). One duplicate-hash pair inside v1/train
(`ADUROBIOTECH…CONSULTING AGREEMENT(1)` vs `…AGREEMENT`). Custom normalization: join paragraph contexts with
spaces → collapse whitespace → lowercase → SHA-256 (not an official identity method).

**The original builder used the whole `CUADv1.json`**, so held-out documents entered training. On the
original corpus, **1,706 / 11,508 rows contain text that also occurs verbatim in held-out documents** — an
**overlap statistic, not a proven leakage rate** (no per-row lineage existed; boilerplate explains part).

**Source file hashes [REPORTED]:**
```
CUADv1.json                        ed0b77d85bdf4014d7495800e8e4a70565b48ee6f8a2e5dca9cf8655dbf10eae
train_separate_questions.json      7de21d2bb741ac939e2a839ef9640634a5e0f9f40ea2b82c6833baf7db33dab4
test.json                          007b6a40b0c65247f881627375c3d2e9b6aeeb5dfa89957494feed0765a1a073
MAUD_train.csv                     43b0989a68a774c8a43cd83de22a238902eb633f72395e15980215d3ae71a95d
MAUD_dev.csv                       b183f9685ceb4f8cc67e09c2dd00a8bb2608ee7cbf77b6a889d22eb4a186155f
MAUD_test.csv                      6360b510059619c1d7aeea9ac1e7794080862dfd73ae24a8cebb2d7d45af741a
```

**A3 staged, train-only rebuild [REPORTED]** — output `data/processed.staging/`, inputs
`train_separate_questions.json` + `MAUD_train/dev`; `CUADv1.json` **not** used; no retrain; **no swap**.
Row counts: `clause_classifier.csv` **9,278** (407 distinct doc IDs, all `split=train`); `cuad_examples.jsonl`
22,450 (train); `maud_examples.jsonl` 32,580 (25,827 train / 6,753 dev); `unified_examples.jsonl` 55,030
(48,277 train / 6,753 dev); `cuad_keyword_bank.json` train-only.

Staged hashes [REPORTED]:
```
clause_classifier.csv    03241d80becff51ec441bd531b8ece1b04101f3900283a57506cef11e14bdcb9
cuad_examples.jsonl      3520fa8a6555216ae09874a3bd8dc03c02ec01fef7e751b96112db0e19f06701
cuad_keyword_bank.json   2c6b6999906fde1be8db94cc30482712374cd64a99d0ec3dc4f4f6fb1d9b7c77
maud_examples.jsonl      e733cca55d874a14d29bbf0a433d641867b358a11962916b13349bf9b3e7bb0d
unified_examples.jsonl   5a97f008f551d551fa4dcc22ac41105e8a52e8e500ce147328ee794ed128a926
```
Staging verifier: **0 failures, 0 skipped** [REPORTED] after row-level lineage checks were added.

**Durable backup [REPORTED]** (exist on disk; not re-verified here):
`C:\Users\Ivermectin\Documents\bharatcontract\a3_backup_20261026T011900\` — 9 payload files +
`backup_manifest.json`; 9/9 hash+size match. Scratchpad copy retained at
`…\Temp\commandcode\…\scratchpad\a3_backup_20261026T011900\` (ephemeral).

**Keyword-bank behavioural comparison [REPORTED]:** production 2,045 phrases vs staged 1,895;
**308/312 identical** (98.7 %), 4 changed; identical 9 rule IDs on the MSA fixture; the sample is small and
unlabelled → **neither bank demonstrated more accurate**.

---

## 8. Provenance subsystem (implemented, verified earlier)

- `nlp/datasets/splits.py` — hash-pinned `SOURCE_ALLOWLIST`; `ALLOWLIST_AUTHENTICATION`
  (`upstream_authenticated: false`, basis `internal-partition-consistency`). **Not authenticated against
  upstream CUAD.** `resolve_source`/`resolve_split` fail closed on unknown or drifted files;
  `validate_training_sources` rejects `test`/`mixed` unless `--allow-whole-corpus` (**documented risk**).
- `nlp/datasets/manifest.py` — per-artifact `<artifact>.manifest.json` (artifact sha256, sources with
  sha256+split, code revision, command, row/label counts). `verify(deep=True)` re-hashes sources.
  **Manifests are unsigned assertions**; only row lineage prevents a forged manifest.
- `nlp/provenance.py` — runtime registry; `record_loaded_model` ties status to the **exact `.joblib` bytes**
  with `cache_sha256` drift detection; tokens `PROVENANCE_VERIFIED|UNVERIFIED|ABSENT`.
- `scripts/verify_provenance.py` — fail-closed readiness check = manifest **+ row-level lineage**
  (CSV `doc_id`/`split`; JSONL `metadata.title`/`split`). `cuad_keyword_bank.json` is `lineage=none`
  (manifest-only, aggregate structure). Exit 0 only when all pass.
- `tests/test_no_leakage.py` — T1a–T8 + L1–L5 adversarial (forged manifest cannot rescue an invalid artifact).
- `models/PROVENANCE_STATUS.json` — both `.7z` marked **`provenance-unverified`** (trained on the
  full-CUAD corpus), with `cache_sha256` for each extracted `.joblib`.

---

## 9. Stages P1 and P2 (implemented, not yet reviewed upstream)

### P1 — deterministic context resolution
`resolve_context(raw_clauses) -> {clause_id: {status, references[], overrides[], related_clause_ids[],
unresolved_references[]}}`; reference status `resolved|missing|ambiguous`; precedence recorded as
**`candidate` only**. Attached as additive `Clause.context`. **Not consumed by any rule yet.**
Known limits: Markdown-prefixed headings (`## 7. LIABILITY`) are not parsed as section numbers, so TC-05
references are detected but **unresolved**; `Clause 7.4(a)`, `Section IV`, inline parenthetical
definitions unsupported; no inference of precedence from clause order.

### P2 — evidence binding
`EvidenceSpan{text, char_start, char_end, clause_id, role: direct|contextual, locator: "clause_text"}`
and five additive `RiskFlag` fields (`source`, `evidence_status`, `evidence_spans`, `search_scope`,
`related_clause_ids`). Bound once in `apply_rules` via `_bind_evidence` — **no rule function edited**.
- Clause-level → owning clause span, `status="direct"` (**owning-clause association, not proof**).
- Contract-level (`clause_id=None`) → **no span**, `status="unverified"`, explicit `search_scope`.
- ML → `source="model"`, `status="unverified"`, `role="contextual"`; **confidence is uncalibrated**.
- Offsets index cleaned/segmented `Clause.text`, **not** raw file bytes.
- Evidence is clause-granular (rules do not expose the matched phrase).

---

## 10. Known defects / outstanding risks (ranked)

1. **No whole-contract reasoning consumed yet** — context bundle exists but rules ignore it; liability-cap
   and renewal rules still evaluate single clauses (`RISK_LIABILITY_002` false positive on TC-05).
2. **Contract-level findings remain unverified** — stamp duty/TDS/§124 have no span (only `search_scope`).
3. **Missing-protection = whole-corpus keyword presence** (`rules.py:~428/437`) — headings/defined terms
   count as presence; "not found" not distinguished from absence.
4. **ML booster** — model-only suggestions, uncalibrated confidence, no measured incremental value.
5. **Obligation extraction** — headings leak into `subject`, missing `action/object`, written-out deadlines
   (`thirty (30) days`) missed because the regex is digit-only.
6. **Legal grounding** — case-law pointers lack source identity/passage/verification date; stamp-duty/TDS
   presented as findings without qualification.
7. **Segmenter** does not parse Markdown-prefixed headings → section numbers missing for such documents.
8. **Provenance** — production artifacts unverified; both model archives `provenance-unverified`;
   `--allow-whole-corpus` escape hatch remains.
9. **`classifier_ml.py` is dead code** (never imported). **`user_role` is accepted but unused.**
   Dead config: `use_rule_based_classifier`, `enable_background_jobs`, `default_jurisdiction`;
   `playbook_id` accepted and unused.

---

## 11. TC-05 diagnostic (one example, never the acceptance criterion)

`uploads/c_20261026_134911_fc805c301d8d_TC-05_cross_reference_traps.md` — synthetic SaaS agreement
(fictional parties). Ground truth requires contextual reading: 7.1/7.2 read with 7.4 + definitions
1.3–1.4; 10.2 fee defined in 1.5; 3.2 renewal opt-out + reminder; 11.1 qualified by 11.2 + Schedule 3;
**4.1 (Net 30) vs Schedule 2 (Net 90) with 1.7 precedence for Fees**; 5.2 credits vs 10.3 termination;
9.1 one-way IP indemnity is not automatically a defect; DIAC is a neutral appointing authority;
2.1/1.1 Affiliate breadth benign; stamp duty/TDS/GST must not be violations merely because a keyword is absent.

**Previously reported actual output:** 18 clauses, 13 obligations, 7 risks, score 100/critical;
`RISK_LIABILITY_002` false positive (cap exists in 7.4); `RISK_RENEWAL_001` false positive (30-day notice
exists); no Net 30/Net 90 precedence finding; two ML-only high-risk suggestions (`local_c009` ~98 %,
`local_c011` ~56 % — **not calibrated probabilities**); stamp/TDS/§124 with no clause ID; governing law
blank; obligation headings/missing fields; no cross-reference resolution.

**Do not assume P1/P2 fixed these. They have not been shown to improve risk accuracy.**

---

## 12. Linked artifacts (do not duplicate large files here)

- `BharatContract_AI_Project_Charter.md` — product vision, research methodology, acceptance criteria.
- `BharatContract_AI_Agent_Master_Prompt.md` — operating protocol (stages, integrity rules, approval gates).
- `AGENTS.md` — agent memory: stack, pipeline, uv workflows, provenance notes.
- `README.md` — user-facing docs, including a `## Provenance (data lineage)` section.
- `plan.md` — living plan/checklist (⚠️ still contains an older "phases complete" framing alongside the
  new unchecked provenance limitation; a documentation cleanup is outstanding).
- `reports/evaluations/generalizable_analysis_audit.md` — Stage A/B audit (ranked root causes R1–R9).
- `reports/evaluations/p1_context_resolution_report.md`
- `reports/evaluations/p2_evidence_binding_report.md`
- `models/PROVENANCE_STATUS.json`; `models/{tfidf,risk}_classifier.7z`; `models/*.joblib` (cache);
  `models/hf/` (partial DeBERTa config/tokenizer only — **no weights**).
- `data/datasets/{cuad,maud}` (tracked); `data/processed/` (untracked, **unverified**);
  `data/processed.staging/` (untracked, verified; **never swapped**).

See `.commandcode/BHARATCONTRACT_ARTIFACT_INDEX.md` for hashes and paths.

---

## 13. Hard authorization boundary (current)

**Not authorized:** production artifact replacement (`data/processed/` ← staging), model retraining or
archive extraction, P3–P7 implementation, fixing/hiding the seven provenance failures, service startup,
Git staging/commit/amend/rebase/reset/push, deleting/moving/overwriting user files, replacing existing
`.commandcode/` files without permission.

**Authorized next:** read the P1/P2 reports, inspect the current diff, then **ask for approval** before any
new implementation stage.
