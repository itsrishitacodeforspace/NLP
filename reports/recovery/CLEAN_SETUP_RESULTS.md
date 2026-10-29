# Clean-Checkout Reproduction — 2026-10-28

Verified on a fresh git worktree at HEAD `ae55c59` (Python 3.12.14, uv-managed).

## Setup
```bash
git clone <repo> bharatcontract && cd bharatcontract
uv sync --extra dev                     # exit 0, 154 packages
```

## Lint
```bash
uv run ruff check .                     # "All checks passed!"
```

## Regenerate the evaluation corpus (train-only, with manifests)
```bash
uv run python scripts/build_training_data.py   # exit 0
uv run python scripts/verify_provenance.py     # 0 failures, 0 skipped
```

## Tests
```bash
uv run pytest -q                        # 1 failure: test_no_leakage.py::test_t1b_...
                                        #   (24 boilerplate overlaps, not leakage); rest pass/skip
```

## Run
```bash
uv run python scripts/run_demo.py       # end-to-end demo (no infra)
uv run uvicorn app.main:app             # serves /docs and /healthz (HTTP 200)
```

## Notes
- Without the `build_training_data.py` step, the demo still runs via the bundled TF-IDF model, but the rule-based classifier loses its CUAD keyword bank and the accuracy/provenance tests SKIP (documented in README).
- The 7 provenance failures seen on a developer machine with stale `data/processed/` resolve to 0 after regeneration; the single remaining T1b failure is a boilerplate-overlap test limitation, not a leakage defect.
