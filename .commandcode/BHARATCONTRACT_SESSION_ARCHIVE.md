# BharatContract AI — Session Archive (reconstructed)

> **This is a reconstructed project/session handoff from supplied conversation context and accessible
> repository records, not a verbatim export of the complete ChatGPT transcript.** It does not contain every
> message, and it does not reproduce exact wording for messages it does not hold. Where a detail could not be
> confirmed from the repository, it is labelled as reported rather than restated as fact.

**Original transcript accessible?** No. No ChatGPT transcript file or external session log was available to
this session. The record below is derived from (a) the project history supplied by the user in-conversation,
(b) files created earlier in this same session chain, and (c) the repository state inspected during this
export.

**What was inspected during this export (this-session evidence):** `.commandcode/` contents
(`settings.json`, `taste/taste.md`, `taste/taste---general-preferences/taste.md`), `git status`
(branch `main`, 17 modified + 17 untracked files), and the existence of the three files under
`reports/evaluations/`.

---

## 1. Chronology (reconstructed)

### Phase 1 — Orientation
The user asked to "complete this project". A full file-map review of the codebase followed (FastAPI backend,
Streamlit UI, rule-first NLP, provenance-free data pipeline). Baseline checks: 38 tests passing, ruff clean,
demo producing a risk report.

### Phase 2 — Runtime verification and hardening
Live FastAPI boot and Streamlit boot were verified; error paths probed (400 bad extension, 400 empty upload,
413 oversize, 404 unknown, 422 non-multipart). Fixes applied: `datetime.utcnow()` → `app/core/time.utcnow()`
(deprecated in 3.12), `use_container_width` → `width="stretch"`, empty uploads rejected at the edge, a 500
handler that no longer leaks the exception class outside development, and a Postgres fallback for contract
lookups after an in-memory job-cache miss. `AGENTS.md` was corrected (it referenced a non-existent
`package.json`).

### Phase 3 — Auth/RBAC, row-level security, case-law, ML risk booster
Optional JWT auth (`AUTH_ENABLED`, default **off**), bcrypt hashing with a PBKDF2 fallback, ranked roles
`viewer < analyst < admin`, `/api/v1/auth/token` + `/me`, owner-scoped reads (404 not 403), case-law pointers
per rule, and a weakly-supervised TF-IDF risk classifier used only as a recall booster (`ML_RISK_001`).
Commits `316aa5e`, `abef0bd`, `cbd9c29` were made and **pushed**, with explicit approval at the time.

### Phase 4 — Research-integrity reset
A charter and an agent master prompt were supplied. Work switched to a staged protocol: read-only audit →
scope → patch proposal → approval → implementation → evaluation. All later work was approval-gated.

### Phase 5 — Data lineage and leakage
CUAD split facts established (510 / 408 / 102; clean partition). The earlier "407/408 mismatch" was
identified as a **counting error by the agent**, corrected and recorded. The key finding: the original
corpus was built from the **whole** CUADv1, so all 102 held-out documents were inside training.

### Phase 6 — Provenance subsystem
Hash-pinned source allowlist, per-artifact manifests, runtime provenance registry (`/healthz` block,
`PROVENANCE_*` tokens in analysis warnings), a fail-closed readiness verifier, and adversarial tests proving a
forged manifest cannot rescue an artifact with held-out rows.

### Phase 7 — A3 backup + staged rebuild
Durable backup created; train-only rebuild into `data/processed.staging/` (9,278 classifier rows from 407
documents, all `train`); verifier passing on staging; **no production swap**.

### Phase 8 — Pre-replacement audit
Verdict: **NOT READY** for replacement on two procedural grounds (ephemeral backup; verifier ignoring row
lineage). Both were then closed: durable backup verified, and row-level lineage added to the verifier.

### Phase 9 — Keyword-bank behavioural comparison
Production vs staged bank, isolated processes, fixed corpus. 308/312 identical; 4 differences; no accuracy
claim.

### Phase 10 — Generalizable analysis audit (Stage A/B)
Root causes R1–R9 identified (no cross-reference resolution; single-clause liability rule; evidence-less
contract-level findings; keyword-presence missing-protection; unattributed ML findings; obligation field
defects; heading inflation; unqualified legal claims). P1→P7 roadmap proposed.

### Phase 11 — P1 implemented (context resolution)
Deterministic resolver added; context attached but **not consumed** by rules. Suite 71/64/7.

### Phase 12 — P2 implemented (evidence binding)
`EvidenceSpan` + five additive `RiskFlag` fields; binding in `apply_rules`; ML findings marked unverified.
Suite 81/74/7 with the same seven provenance failures.

### Phase 13 — This export
Documentation only: five handoff files created in `.commandcode/`. No code, test, data, model or artifact
change.

---

## 2. Recurring failure modes the user pushed back on
- Reporting a result as verified when only a summary had been supplied.
- Comparing a set cardinality to a document count (the 407/408 error) — corrected honestly.
- Losing fail-closed behaviour to obtain a green suite (explicitly forbidden; never done).
- Conflating provenance with accuracy.
- Masking substantive invariants behind a manifest gate (found during review; tests were split, not weakened).

## 3. The seven persistent test failures
`T1a`, `T1b`, `T2a`, `T2b`, `T3a`, `T3b`, `T8` — all rooted in the **unswapped, unlineaged** production
artifacts. They are the guard working, not regressions. They must stay visible until a separately approved
replacement.

## 4. Integrity notes for a future session
- Never fabricate a hash, count, citation, file path or command result.
- Record the exact commands and exit codes actually run.
- Distinguish code correctness from production readiness and from legal validation.
- Preserve negative results (e.g. the ML booster's value remains unmeasured; the behavioural comparison found
  no accuracy improvement).
- Treat TC-05 as one diagnostic, never the acceptance criterion.

## 5. Known gaps in this archive
- No verbatim messages; no timestamps per turn.
- Some intermediate command outputs are summarised rather than quoted.
- The exact HEAD commit is **reported**, not re-read during this export.
- All test counts and artifact hashes in this export are **reported from earlier in the session chain** and
  were **not recomputed here** except where explicitly marked [THIS-SESSION].
