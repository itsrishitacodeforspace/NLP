# Dataset License / Provenance — 20261103

> **Scope:** what the files *in this repo* say about the two external datasets
> (CUAD, MAUD) — license, source, version, counts, splits — and the exact
> statement of what each legitimately supports and does **not** support.

## 1. What is in the repo

### CUAD — `data/datasets/cuad/`

| File | Contents |
|---|---|
| `CUADv1.json` | 510 documents, `version: aok_v1.0`; the combined dataset (train + test titles, no title overlap) |
| `train_separate_questions.json` | 408 documents, 408 paragraphs, 22,450 QA pairs, 41 categories |
| `test.json` | 102 documents, 102 paragraphs, 4,182 QA pairs, 41 categories |
| `category_descriptions.csv` | 41 CUAD category names + descriptions + answer formats |

Each document: `{title, paragraphs: [{context, qas: [{question, answers, is_impossible}]}]}`.
Document titles are EDGAR-style filing identifiers (e.g.
`LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT`), indicating the source
is **SEC EDGAR filings** (Atticus project's CUAD). One paragraph per document.

**Derived artifacts** (manifest-verified, train-only):
`data/processed/clause_classifier.csv` — 9,278 rows, 408 docs, 14 CUAD-mapped
categories (manifest `source_authentication.upstream_authenticated: false` —
"Hashes computed locally ... No upstream CUAD checksum was consulted").

### MAUD — `data/datasets/maud/data/`

| File | Rows (data) |
|---|---|
| `MAUD_train.csv` | 25,827 rows; 153 distinct `contract_name`s; 7 categories; `data_type` ∈ {main 13,256, rare_answers 2,924, abridged 9,647} |
| `MAUD_dev.csv` | 6,753 rows (main 3,471, rare_answers 756, abridged 2,526) |
| `MAUD_test.csv` | 6,651 rows (main 3,896, abridged 2,755) |
| `raw/main.csv`, `raw/abridged.csv`, `raw/counterfactual.csv` | the raw label sheets (153 / 96 / 153 contract rows) with 148+ QA columns |
| `contracts/contract_N.txt` | 152 contract text files |

Schema: `data_type, contract_name, text, answer, label, question, subquestion,
text_type, id, category`. Categories: Deal Protection and Related Provisions
(9,753 train), Material Adverse Effect (8,548), Conditions to Closing (5,034),
Operating and Efforts Covenant (1,611), Knowledge (442), General Information
(225), Remedies (214).

## 2. License — what the files actually say

**No license file exists anywhere under `data/datasets/`** (searched
`LICENSE*`, `README*`, `*terms*`, case-insensitive `license` in all dataset
files). The CUAD JSON files carry only `version: aok_v1.0`; the MAUD CSVs
carry no license metadata at all.

> **License: unverified in-repo — verify before redistribution.**
>
> The prior `phase_2c_readiness_report.md` claimed "License: CC BY 4.0" for
> both datasets. That claim is **not supported by anything in this repo** —
> the report itself carries a 2026-11-03 correndum admitting the repo ships
> no LICENSE files and the claim "needs final settlement". Treat "CC BY 4.0"
> as an **unverified prior claim**, not a fact established here. (For what it
> is worth, the upstream Atticus project publishes CUAD under CC BY 4.0 and
> MAUD under a similar permissive license on Hugging Face, but that is
> upstream documentation, not a statement verifiable from this checkout.)

## 3. What each dataset legitimately supports / does NOT support

### CUAD
**Supports (legitimately, in-repo):**
- Clause **mention-detection / span extraction** for its 41 US-contract
  categories (the QA "Highlight the parts related to X" task).
- Training/evaluating a **multi-label clause classifier** over the
  14 categories that map into the internal taxonomy (the `cuad` source in
  `data/processed/`).
- **Family/template analysis** of US commercial contracts (EDGAR-derived).

**Does NOT support:**
- **Indian-law compliance** — CUAD is a **US** dataset (US EDGAR filings, US
  contract forms). Nothing about Indian statutes (stamp duty, TDS, ICA,
  DPDP) is represented.
- Legal advice, correctness of any legal conclusion, or generalization to
  non-US / Indian contracts.
- The `train_separate_questions.json` / `test.json` split is **not
  template-family disjoint** (7/102 test docs leak — see
  `cuad_family_leakage_20261103.md`), so the raw test split overstates
  generalization; the 95 family-disjoint docs are the defensible held-out set.

### MAUD
**Supports (legitimately, in-repo):**
- QA over **US merger agreement** provisions (MAE, deal protection, closing
  conditions, efforts covenants, knowledge, remedies, general information).
- Multi-document understanding of M&A contract clauses (the dataset's
  stated purpose).

**Does NOT support:**
- **Indian-law compliance** — MAUD is a **US** dataset (US merger agreements).
- Independent-document statistics: MAUD rows are **not independent documents**
  (multiple rows share one `contract_name`; 25,827 train rows cover only 153
  contracts), so per-row dedup under-counts and row-level "counts" overstate
  effective sample size.
- Legal advice or generalization to non-US M&A.

## 4. Cross-dataset note

Both datasets are **US** corpora. **Neither supports any claim about
Indian-law compliance.** The internal 26-label taxonomy's 12
India-specific / non-CUAD categories (Indemnification, Data Protection,
Dispute Resolution, Force Majeure, Service Levels, Change Control, Notice,
Acceptance, Compliance, Stamp Duty, TDS/GST, Arbitration Seat) have **zero
CUAD-derived rows** and are 100% rule-dependent with no gold labels — their
quality cannot be measured by anything in this repo.

## 5. Provenance verification status (from manifests)

- `data/processed/clause_classifier.csv.manifest.json`:
  `source_authentication.basis = "internal-partition-consistency"`,
  `upstream_authenticated = false`.
- All processed artifacts are **hash-pinned to this checkout only**; the
  provenance check proves lineage/consistency, **never** upstream
  authenticity or model accuracy.
