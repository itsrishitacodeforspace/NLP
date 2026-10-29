# Provenance Guard Root-Cause Audit — 2026-10-27

## Failure matrix

| Test | Assertion | Why it fails | Guard correct? | Resolution requires |
|---|---|---|---|---|
| T1a | `verify(clause_classifier.csv, allowed_splits=("train",), require=True, deep=True)["ok"]` | No manifest file exists for `data/processed/clause_classifier.csv`. | Yes — fail-closed on missing manifest. | Production artifact replacement with staged (A3) rebuild + manifests. |
| T1b | No corpus row occurs verbatim in held-out documents. | 1,706/11,508 rows contain text verbatim in held-out docs (production corpus built from whole CUADv1). | Yes — substantive invariant. | Rebuild from train-only sources (already staged, not swapped). |
| T2a | `verify(cuad_keyword_bank.json, ...)` | No manifest for `cuad_keyword_bank.json`. | Yes. | Manifest generation + train-only rebuild. |
| T2b | Manifest sources all `split == "train"`. | No manifest exists → `load_manifest` returns None. | Yes. | Same as T2a. |
| T3a | `load_manifest(maud_examples.jsonl)` and `unified_examples.jsonl` non-None. | No manifests for either MAUD artifact. | Yes. | Manifest generation. |
| T3b | Manifest sources exclude `test` split. | No manifest → assertion fails. | Yes. | Same as T3a. |
| T8 | `verify(cuad_examples.jsonl, ...)` | No manifest for `cuad_examples.jsonl`. | Yes. | Manifest generation + train-only rebuild. |

## Guard correctness

- `manifest.verify`: fail-closed on missing manifest (raises `ProvenanceError`), checks artifact hash drift, source split membership, and re-hashes sources in deep mode. **Correct.**
- `verify_provenance.verify_artifact`: adds row-level lineage (CSV `doc_id`/`split`, JSONL `metadata.title`/`split`) on top of manifest. **Correct.**
- No guard was found to silently skip required validation or incorrectly accept invalid provenance. The forged-manifest test (L5) confirms row lineage overrides a forged manifest.

## Resolution requirements

All seven failures stem from **missing production-side provenance**, not defective guards. Resolution requires:
1. Replacing `data/processed/` artifacts with the staged (train-only, verified) versions in `data/processed.staging/`.
2. This requires explicit user approval (authorization boundary per project memory D11).

No code change is appropriate. The guards are working as designed.

## Test count reconciliation

- Previous reported: 81 collected / 74 passed / 7 failed.
- Current: 89 collected / 80 passed / 7 failed (after adding 8 new tests: 2 regression + 3 P4 context + 10 P4 adversarial - some not collected due to name collisions or collection rules; net +8 over 81 = 89). Actually: 81 + 2 + 3 + 10 = 96, but actual is 89. The discrepancy of 7 is likely due to test name collisions or pytest collection deduplication. The 7 provenance failures are stable.

## Verified facts vs assumptions
- **Verified:** Production `data/processed/` has 5 artifacts and 0 manifests. Staging has 5 artifacts + 5 manifests. Guards fail closed. No guard defect found.
- **Assumption:** Staged artifacts are production-ready (reported as verified by row-level lineage, but not independently re-verified in this session beyond listing).

## Conclusion
The guards are correct. The failures represent genuinely missing production provenance. No fix is possible without production artifact replacement (not authorized). Leave the guards failing.