# BharatContract AI — Artifact Index

Paths, hashes and verification status. **Hashes marked [REPORTED] were recorded earlier in the session
chain and were NOT recomputed during this export.** [THIS-SESSION] = verified here.

---

## A. Reports (all under `reports/evaluations/`) — [THIS-SESSION: files exist]

| File | Status | SHA-256 |
|---|---|---|
| `generalizable_analysis_audit.md` | exists; hash **not computed in this export** | `3cad28c7d673cb9ae43e1a4b3c548beaadf9d7f03b3f2fa9f12443dc37e0060b` [REPORTED] |
| `p1_context_resolution_report.md` | exists; hash **not recomputed** | `91621e56be31669a0f285522a949681f6ea8b80ad2dd786b6fbf097a239dc374` [REPORTED] |
| `p2_evidence_binding_report.md` | exists; hash **not recomputed** | `b2dc50a49d6be11a060b8c9e62d9457d604c93954d4ac6a966ed1daf77cb8160` [REPORTED] |

Sizes reported earlier: audit 14,835 B / 169 lines; P1 report 7,837 B; P2 report 5,993 B.

---

## B. Source datasets (tracked) — `data/datasets/`

| Path | SHA-256 [REPORTED] |
|---|---|
| `data/datasets/cuad/CUADv1.json` | `ed0b77d85bdf4014d7495800e8e4a70565b48ee6f8a2e5dca9cf8655dbf10eae` |
| `data/datasets/cuad/train_separate_questions.json` | `7de21d2bb741ac939e2a839ef9640634a5e0f9f40ea2b82c6833baf7db33dab4` |
| `data/datasets/cuad/test.json` | `007b6a40b0c65247f881627375c3d2e9b6aeeb5dfa89957494feed0765a1a073` |
| `data/datasets/maud/data/MAUD_train.csv` | `43b0989a68a774c8a43cd83de22a238902eb633f72395e15980215d3ae71a95d` |
| `data/datasets/maud/data/MAUD_dev.csv` | `b183f9685ceb4f8cc67e09c2dd00a8bb2608ee7cbf77b6a889d22eb4a186155f` |
| `data/datasets/maud/data/MAUD_test.csv` | `6360b510059619c1d7aeea9ac1e7794080862dfd73ae24a8cebb2d7d45af741a` |

Also present: `data/datasets/cuad/{test.json, train_separate_questions.json, category_descriptions.csv}`,
`data/datasets/maud/data/contracts/` (contract text files). **Never modify these.**

Fixture: `data/raw/sample_msa.txt` (tracked). Uploaded diagnostic: `uploads/…TC-05_cross_reference_traps.md`
(gitignored; do not delete).

---

## C. Production processed artifacts — `data/processed/` (untracked; **UNVERIFIED**)

| File | SHA-256 [REPORTED] | Status |
|---|---|---|
| `clause_classifier.csv` | `9acc4d415d5bb5ca96f9413795362f649f9fb217cd0bb02bf01747a3b29529c6` | 11,508 rows; **no manifest**; carries exact overlap with held-out text (1,706 rows) |
| `cuad_keyword_bank.json` | `de13af504042aca21b58ed276a9729f1e8583b15817019020155429354755463` | 536,894 B; **no manifest**; runtime consumer |
| `cuad_examples.jsonl` | `81a21443b65b50cb3f71988059001a56944ba3c361e5ca1caac329b8e351a079` | 48,153,160 B; no manifest; no consumer |
| `maud_examples.jsonl` | `4aef6e038b1d96ac166dfa5b581291d2041cd6b694c490c569385617ddbeba59` | 64,548,476 B; no manifest; no consumer |
| `unified_examples.jsonl` | `436be074f80a8b483652a2514c165a6ee5dc2f3eb4283d9e664e4ebd2e5d22d6` | 112,701,636 B; no manifest; no consumer |

**No `*.manifest.json` exists in `data/processed/`.** These artifacts have **not** been replaced.

---

## D. Staged artifacts — `data/processed.staging/` (untracked, gitignored; **VERIFIED**, not swapped)

| File | SHA-256 [REPORTED] | Rows |
|---|---|---|
| `clause_classifier.csv` | `03241d80becff51ec441bd531b8ece1b04101f3900283a57506cef11e14bdcb9` | 9,278 (407 doc IDs, all `train`) |
| `cuad_examples.jsonl` | `3520fa8a6555216ae09874a3bd8dc03c02ec01fef7e751b96112db0e19f06701` | 22,450 (train) |
| `cuad_keyword_bank.json` | `2c6b6999906fde1be8db94cc30482712374cd64a99d0ec3dc4f4f6fb1d9b7c77` | 453,770 B (train only) |
| `maud_examples.jsonl` | `e733cca55d874a14d29bbf0a433d641867b358a11962916b13349bf9b3e7bb0d` | 32,580 (25,827 train / 6,753 dev) |
| `unified_examples.jsonl` | `5a97f008f551d551fa4dcc22ac41105e8a52e8e500ce147328ee794ed128a926` | 55,030 (48,277 train / 6,753 dev) |

Plus **5** `*.manifest.json` (one per artifact). Verifier on this directory: **0 failures, 0 skipped**
[REPORTED]. Keyword bank is `lineage=none` (aggregate; manifest-only).

---

## E. Models — `models/` (tracked archives; **provenance-unverified**)

| File | SHA-256 [REPORTED] | Git | Status |
|---|---|---|---|
| `tfidf_classifier.7z` | `6bf3840cdc19aca2cae6510a3f6335719e31c816f2e394108699374ee8cafcda` | tracked | `provenance-unverified` — trained on full CUADv1 (train ∪ test) |
| `risk_classifier.7z` | `e03616822cd767af871d7a424c6b5ba3fd66fd2fea0166c4fb00ceb39bc5cb3a` | tracked | `provenance-unverified` — same corpus overlap + rule-derived weak labels |
| `tfidf_classifier.joblib` | `87c60eebca94b40f25c5d4403b3d6991b6467bc85e91422c252cddd0141003ae` | ignored cache | `cache_sha256` declared in `PROVENANCE_STATUS.json` |
| `risk_classifier.joblib` | `b40ed2b20d2eb8e8ea423e63ce2fe9f062897641aeafa916dbfa3add4447b4ce` | ignored cache | same |
| `models/hf/` | — | ignored | partial DeBERTa config/tokenizer **only**; **no weights** |
| `models/PROVENANCE_STATUS.json` | — | **untracked (new)** | machine-readable provenance declaration |

**Do not extract, delete, overwrite or regenerate either archive or either cache.**

---

## F. Backups

| Location | Contents | Status |
|---|---|---|
| `C:\Users\Ivermectin\Documents\bharatcontract\a3_backup_20261026T011900\` | 9 payload files + `backup_manifest.json` | **DURABLE**; 9/9 hash+size OK [REPORTED] |
| `…\Temp\commandcode\…\scratchpad\a3_backup_20261026T011900\` | same | **EPHEMERAL** (session scratchpad); retained |

Backed-up hashes equal the §C and §E values above (production state at backup time).

---

## G. Code modules added by the provenance / P1 / P2 work (untracked, new)

`nlp/context/{__init__,resolver}.py` · `nlp/datasets/{splits,manifest}.py` · `nlp/provenance.py` ·
`scripts/verify_provenance.py` · `tests/test_no_leakage.py` · `tests/test_context_resolution.py` ·
`tests/test_evidence_binding.py` · `models/PROVENANCE_STATUS.json` · `reports/` (three reports).

---

## H. How to verify (read-only)
```bash
# hashes of any artifact
uv run --no-sync python -c "import hashlib,pathlib; p=pathlib.Path('data/processed/clause_classifier.csv'); print(hashlib.sha256(p.read_bytes()).hexdigest())"

# staged provenance + row lineage (exit 0 only when everything verifies)
uv run --no-sync python scripts/verify_provenance.py --out-dir data/processed.staging

# production readiness (EXPECTED to exit 1 until a swap is approved)
uv run --no-sync python scripts/verify_provenance.py
```
