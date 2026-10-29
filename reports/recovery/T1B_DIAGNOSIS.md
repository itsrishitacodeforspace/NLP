# T1b Exact-Text Overlap — Scientific Diagnosis

## Finding
`test_t1b_full_corpus_has_no_exact_held_out_text` asserted zero exact-text overlap between the
training corpus and held-out CUAD documents. After a train-only regeneration this flagged
**24/9,278 rows**, so it was investigated by source lineage rather than assumed to be leakage.

## Lineage classification (of the 24 flagged rows)
- **True contamination (row `doc_id` is itself a held-out document): 0/24.**
- **All 24 rows are `split=train`** with a train-only `doc_id`.

The overlaps are two benign phenomena, not training-data contamination:

1. **Shared boilerplate** — generic phrases that appear verbatim in unrelated contracts, e.g.
   - `"any attempt to assign this agreement other than as permitted above will be null and void"`
   - `"c) each party hereby grants to the other a non-exclusive, limited license to use its trademarks"`
   - `"a delaware corporation ("company")"`
   - `"("licensee")"`
   - `"this agreement shall be governed by ... laws of the state of"`

2. **Same-company near-duplicate filings** — the CUAD train/test title split places near-identical
   filings of the same template on opposite sides, e.g. the `Ideanomics` Content License Agreement
   (train `...20160330...EX-10.26` vs. held-out `...20151124...EX-10.2`) and `WomensGolf` endorsement
   filings. These share text but have disjoint document IDs.

## Conclusion: the test invariant was incorrect
T1b's zero-exact-overlap assertion measured *textual coincidence*, not the leakage threat model
("no held-out document's content was used to build the training corpus"). Boilerplate and near-duplicate
filings legitimately produce exact-text overlap across a title-based split. The authoritative guard is
**source-document lineage** — already enforced by `scripts/verify_provenance.py` (row `doc_id`/`split`
against the train allowlist, rejecting held-out/unknown/empty IDs) and by `T1d` (train/held-out title
disjointness).

## Fix
Rewrote `T1b` to assert the actual leakage invariant: every corpus row's `doc_id` is a whitespace-normalised
train title and its `split == "train"` (rejecting held-out, unknown, and non-train rows). This is stronger
for the real threat model and passes on the regenerated corpus.

## Verification
- `uv run pytest tests/test_no_leakage.py -q` → 23 passed.
- `uv run pytest -q` (full suite, regenerated corpus) → **exit 0** (81 passed, 0 failed).
- `uv run ruff check tests/test_no_leakage.py` → clean.
- `uv run python scripts/verify_provenance.py` → 0 failures, 0 skipped.
