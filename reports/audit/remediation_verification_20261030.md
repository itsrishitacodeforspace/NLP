# Remediation Milestone — Verification Record

**Date:** 30 October 2026
**Scope:** fixes for audit defects D1–D6 (`integration_audit_20261030.md`) plus the
authorised processed-data restoration.
**Method:** each fix landed after its audit reproduction was confirmed failing and
its defect record converted to a normal passing regression test. This document is
the evidence record; it claims functional regression correctness only — not legal
accuracy, benchmark performance, or production readiness.

## 1. Defect outcomes

| Defect | Fix | Verification |
|---|---|---|
| D4 negated statutory mentions suppress stamp/TDS prompts | 6-token same-sentence negation window in `nlp/ner/ner.py`; cues `not/no/never/without/neither/nor/exempt`; sentence punctuation bounds scope | audit D4 records now pass as normal tests; 4 new detector tests (negated / boundary / post-mention / valid-mention controls) |
| D2 multi-line preamble lines silently dropped | span-based grouping in `app/services/segmenter.py`; every preamble line survives inside the exact clause span | audit D2 record passes; 3 new preamble tests (one-line, multi-line, blank lines, no-heading document) |
| D1 clause offsets don't slice the source | `_paragraph_spans` + `_normalise_items` + span-based `segment_clauses`: every `Clause.text == cleaned[char_start:char_end]` | audit D1 record passes; exact-slicing tests for all heading layouts (single-newline, blank-line, inline) |
| D3 long-clause sub-offsets drift | span-based `_split_long_clause` (paragraph → sentence → fixed-char stages carry document-relative spans) | audit D3 record passes; headed/headless and sentence-split long clauses all slice exactly |
| D5 breach window digit-only parsing | shared `NUMBER_TOKEN_RE` / `written_number_to_int` in `rule_data_breach_window` (mirrors renewal-rule fix) | audit D5 record passes; 5 rule tests incl. loose-period and boundary controls; cross-stage consistency test (obligation deadline and `RISK_DATA_001` co-occur) |
| D6 `_detect_parties` drops names containing "Services"/"Company" | removed those tokens from the walk-back noise set; added generic-fragment guard; added stop-at-second-suffix for adjacent names | audit D6 record passes; multiword-suffix, false-positive, and adjacent-name tests; adversarial end-to-end run caught and fixed the adjacent-name gluing before commit |

## 2. Source-integrity contract status

1. Every source-backed span has valid bounds — `char_end >= char_start` (existing) and slice-exactness tests (new).
2. Every source-backed span slices the original document exactly — verified per clause and per long-clause sub-segment against `clean_text(document)`; the pipeline's offset frame is the cleaned document (`parsed.full_text`), which is what every downstream consumer sees. Raw-file-byte fidelity is a separate, documented migration (not required by any current consumer: offsets feed Neo4j persistence, API output, and the `length` property only).
3. Clause text is not reconstructed with synthetic separators — removed entirely.
4. Sub-clause offsets are document-relative from real spans, not assumed `\n\n` arithmetic.
5. Preamble text is never silently lost.
6. Evidence quotes are clause-relative (`locator="clause_text"`) and correspond to the owning clause's exact span.
7. Cross-reference resolution fabricates no source text (resolver unchanged; cap gate still fail-closed).
8. Empty/malformed inputs fail safely (existing parser tests unchanged).

## 3. Processed-data restoration (authorised)

- Pre-checks: isolated rebuild (`tmp/audit-rebuild/`) verified **0 failures**; byte-identical to `data/processed.staging/` (SHA-256, all 5 artifacts); stale inventory hashed (recorded in recovery tracker); backup created at `tmp/processed-backup-20261030/` (hash-verified, recoverable); directory contained only the 5 expected artifacts; no active process held the files.
- Replacement: `uv run python scripts/build_training_data.py --out-dir data/processed` (supported project procedure; overwrites only its 5 named outputs + manifests; no deletions).
- Post-checks: all 5 artifact hashes match the verified isolated build; `verify_provenance.py` on `data/processed` → **0 failures, 0 skipped, exit 0** (was 5 failures); row lineage 9,278 (CSV) / 22,450 (CUAD) / 32,580 (MAUD) / 55,030 (unified); the 7 previously failing `test_no_leakage.py` tests pass. Manifests committed (tracked per `.gitignore` policy); artifacts remain gitignored. No source datasets modified; no models retrained.

## 4. Results (exact)

- Full suite: **226 → 227 collected, 0 failed, 0 errors, 0 skipped** (junit-verified). The pre-existing 7 provenance failures are resolved by the data restoration; the audit's 7 xfail defect records were each fixed and converted to normal passing tests (none remain xfailed).
- Ruff: All checks passed.
- Evaluation harness: **17/17 cases pass, 0 regressions, 3/3 invariants OK, exit 0**. Case expectations unchanged; `obligation_passive` additionally observes `RISK_DATA_001` (intended D5 effect).
- Demo: exit 0; output identical to the recorded baseline (12 clauses, 13 obligations, score 100.0/critical; both sample parties detected).
- End-to-end adversarial verification (script preserved at `tmp/remediation_verify.py`; frozen output below): **16/16 checks pass**.

## 5. Frozen adversarial-verification output (2026-10-30)

```
PASS preamble line 2 survives
PASS preamble line 3 survives
PASS all clause offsets slice exactly
PASS 'Services' party preserved
PASS second party preserved
PASS negated stamp mention still prompts review
PASS valid TDS mention suppresses prompt
PASS obligation sees 24 hours
PASS risk layer flags written 24h window
PASS excluded cap keeps finding
PASS referenced clause in provenance
PASS advisory note present
PASS clause-level findings have direct clause evidence
PASS contract-level findings scoped+unverified
PASS no fabricated parties in obligations
PASS no duplicate rule findings
RESULT: ALL CHECKS PASS
```

## 6. Commit map

| Commit | Content |
|---|---|
| `90bb769` | D4 negation handling + tests (later pushed to origin externally) |
| `e2fdbb9` | D2/D1/D3 span-based segmentation + tests |
| `128a835` | D5 written-number breach windows (+D6 production change swept in by a git-add race; recorded honestly in the tracker) |
| `5b64da9` | D6 adjacent-name gluing fix (found by adversarial verification) |
| `1b13c2d` | chore(data): restored provenance manifests |
| docs (this file + tracker/handoff/report) | final recording commit |

## 7. What this does not establish

Functional regression correctness on synthetic and crafted inputs only. Not legal
accuracy, not held-out benchmark performance, not real-contract performance, not
production readiness. The 17/17 synthetic pass is a behavioural check, unchanged in
meaning. Model artifacts remain `provenance-unverified` and uncalibrated.
