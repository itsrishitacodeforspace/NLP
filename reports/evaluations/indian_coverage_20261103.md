# Indian Contract Scenario Coverage Inventory

> Generated 2026-11-03 by the Indian-contract workstream subagent.
> Baseline: HEAD `f0bad0a` + this workstream's commits.
> All 5 new samples are synthetic, fictional-party contracts in `data/raw/`.

## 1. Coverage inventory (existing rules + classifier categories)

The charter identifies 15 Indian commercial contract scenarios. This table
records which scenarios are **covered**, **partially covered**, or **not
covered** by the existing rule engine (pre-this-workstream) and the 12
rule-only classifier categories (14 of 26 are ML-supported; the 12
rule-only categories have zero CUAD training rows and are detected by the
rule classifier alone).

| # | Scenario | Existing rules | Rule-only classifier | Status |
|---|----------|---------------|---------------------|--------|
| 1 | **MSA / Services Agreement** | RISK_LIABILITY_001, RISK_INDEMNITY_001, RISK_RENEWAL_001, RISK_TERM_001, RISK_DATA_001, RISK_ARB_001, RISK_STAMP_001, RISK_TDS_001, RISK_S124_001 | Indemnification, Data Protection, Dispute Resolution, Service Levels, Stamp Duty, TDS/GST, Arbitration Seat | **Covered** (all 9 rules fire on sample_msa.txt) |
| 2 | **NDA (one-way)** | RISK_STAMP_001; MISSING_CLAUSE_LIMITATION_OF_LIABILITY | Confidentiality (ML), Dispute Resolution (rule-only) | **Partially covered** — no rule specific to NDA breadth; stamp duty + missing-LoL fire. New: RISK_DISPUTE_001 does NOT fire (NDA has court jurisdiction clause). |
| 3 | **Employment Agreement** | RISK_STAMP_001; RISK_TDS_001 (suppressed when TDS present); MISSING_CLAUSE_GOVERNING_LAW; MISSING_CLAUSE_LIMITATION_OF_LIABILITY | Non-Compete/Non-Solicit (ML), Confidentiality (ML), Payment Terms (ML), TDS/GST (rule-only), Stamp Duty (rule-only) | **Partially covered** — TDS negative test works; no post-employment non-compete rule existed. **New: RISK_NONCOMPETE_001** (this workstream). |
| 4 | **Vendor / Procurement Agreement** | RISK_RENEWAL_001, RISK_TERM_001; RISK_STAMP_001 (suppressed when stamp mentioned); RISK_TDS_001 (suppressed when TDS present) | Service Levels (rule-only), Insurance (ML), Payment Terms (ML), Stamp Duty (rule-only), TDS/GST (rule-only) | **Covered** — all expected rules fire/suppress correctly. |
| 5 | **Data Processing Agreement (DPA)** | RISK_DATA_001 (24h window); RISK_DATA_MISSING (suppressed when DP present) | Data Protection (rule-only) | **Covered** — tight-window rule fires; DP-presence negative works. New: RISK_DISPUTE_001 fires (no dispute clause in DPA). |
| 6 | **Consulting Agreement** | RISK_GOV_001 (foreign law); RISK_S124_001 (indemnity gap); RISK_STAMP_001; RISK_TDS_001 | Indemnification (rule-only), Intellectual Property (ML), Payment Terms (ML) | **Covered** — foreign-law rule fires on Delaware; §124 gap fires; narrow indemnity correctly does NOT fire RISK_INDEMNITY_001. New: RISK_DISPUTE_001 fires. |
| 7 | **License Agreement** | RISK_LIABILITY_001/002; RISK_STAMP_001 | Intellectual Property (ML) | **Partially covered** — LoL rules apply; no IP-licence-specific rule. |
| 8 | **Franchise Agreement** | RISK_LIABILITY_001/002; RISK_TERM_001; RISK_STAMP_001 | Non-Compete/Non-Solicit (ML), Intellectual Property (ML) | **Partially covered** — generic rules apply; no franchise-specific rule. |
| 9 | **Lease / Rental Agreement** | RISK_LIABILITY_001/002; RISK_STAMP_001 | Stamp Duty (rule-only) | **Partially covered** — stamp duty rule applies; no lease-specific rule. |
| 10 | **Loan / Finance Agreement** | RISK_LIABILITY_001/002; RISK_STAMP_001 | — | **Partially covered** — LoL rules apply; no finance-specific rule. |
| 11 | **Share Purchase Agreement (SPA)** | RISK_LIABILITY_001/002; RISK_INDEMNITY_001; RISK_STAMP_001; RISK_S124_001 | Indemnification (rule-only), Assignment (ML) | **Covered** — indemnity + LoL + stamp rules all apply. |
| 12 | **Joint Venture / Partnership** | RISK_LIABILITY_001/002; RISK_STAMP_001 | Assignment (ML) | **Partially covered** — generic rules apply. |
| 13 | **Real Estate / Conveyance** | RISK_LIABILITY_001/002; RISK_STAMP_001 | Stamp Duty (rule-only) | **Partially covered** — stamp duty is the key Indian-specific rule and it applies. |
| 14 | **Revenue Share / Distribution** | RISK_LIABILITY_001/002; RISK_TERM_001; RISK_STAMP_001 | Payment Terms (ML) | **Partially covered** — generic rules apply. |
| 15 | **Government / Public Procurement** | RISK_LIABILITY_001/002; RISK_STAMP_001; RISK_TDS_001 | Compliance (rule-only), Payment Terms (ML) | **Partially covered** — TDS + stamp duty apply; no gov-procurement-specific rule. |

### Summary

- **Fully covered** (existing rules fire on realistic samples): scenarios 1,
  4, 5, 6, 11 — 5 of 15.
- **Partially covered** (generic rules apply but no scenario-specific rule):
  scenarios 2, 3, 7, 8, 9, 10, 12, 13, 14, 15 — 10 of 15.
- **Not covered**: 0 of 15 (every scenario has at least the stamp-duty and
  limitation-of-liability rules applicable).

### Gaps addressed by this workstream

1. **RISK_NONCOMPETE_001** (post-employment non-compete, s. 27 ICA) —
   scenario 3 (employment) and any consulting/contractor agreement with a
   post-termination restraint. Severity MEDIUM (statutory voidness is a
   real risk but the clause may still be partially enforceable or the
   parties may accept the risk).
2. **RISK_DISPUTE_001** (missing dispute resolution mechanism) —
   scenarios 2, 3, 5, 6 (any contract without arbitration or court
   jurisdiction language). Severity MEDIUM (absence of a mechanism is a
   gap but the default statutory forum is a valid fallback).

### Gaps NOT addressed (intentionally)

- No new rules for licence, franchise, lease, loan, JV, real-estate,
  revenue-share, or government-procurement scenarios: the existing
  generic rules (LoL, indemnity, stamp duty, TDS, termination) already
  cover the key risks for these scenarios. Scenario-specific rules would
  be low-precision without a corpus to validate against.
- No new taxonomy labels: the 12 rule-only classifier categories
  (Indemnification, Data Protection, Dispute Resolution, Force Majeure,
  Service Levels, Change Control, Notice, Acceptance, Compliance, Stamp
  Duty, TDS/GST, Arbitration Seat) are sufficient for the scenarios
  covered by the 5 new samples. Adding labels without training data
  would not improve classification (the ML half cannot emit them).

## 2. New samples

| File | Scenario | Key positive findings | Key negative findings |
|------|----------|----------------------|----------------------|
| `sample_nda.txt` | One-way NDA | RISK_STAMP_001; MISSING_CLAUSE_LIMITATION_OF_LIABILITY | RISK_DISPUTE_001 (has court clause); RISK_GOV_001 (Indian law); RISK_NONCOMPETE_001 (no non-compete) |
| `sample_employment.txt` | Employment | RISK_NONCOMPETE_001 (post-employment s.27); RISK_STAMP_001; RISK_DISPUTE_001; MISSING_CLAUSE_GOVERNING_LAW | RISK_TDS_001 (TDS mentioned); RISK_GOV_001 (no foreign law) |
| `sample_vsa.txt` | Vendor/procurement | RISK_RENEWAL_001 (MEDIUM, 60-day notice); RISK_TERM_001 (one-sided); MISSING_CLAUSE_LIMITATION_OF_LIABILITY | RISK_STAMP_001 (stamp mentioned); RISK_TDS_001 (TDS mentioned); RISK_DISPUTE_001 (has arbitration) |
| `sample_data_processing.txt` | DPA annex | RISK_DATA_001 (24h window); RISK_LIABILITY_002 (no cap in breach clause); RISK_DISPUTE_001; RISK_STAMP_001; MISSING_CLAUSE_GOVERNING_LAW | RISK_DATA_MISSING (DP present); RISK_GOV_001 (no foreign law) |
| `sample_consulting.txt` | Consulting | RISK_GOV_001 (Delaware); RISK_S124_001 (indemnity gap); RISK_DISPUTE_001; RISK_STAMP_001; RISK_TDS_001 | RISK_INDEMNITY_001 (narrow, capped); RISK_LIABILITY_001 (cap present) |

## 3. New rules

### RISK_NONCOMPETE_001 — Post-employment non-compete

- **Meaning:** A clause restraining a former employee/consultant from
  competing after the relationship ends is likely void under s. 27 of the
  Indian Contract Act, 1872.
- **Severity:** MEDIUM (score 55.0). Rationale: statutory voidness is a
  real risk, but (a) partial restraints (geographic, client-specific) have
  different enforceability profiles, (b) in-employment restraints are
  outside s. 27 and may be enforceable, and (c) the parties may accept the
  risk knowingly. Not HIGH because the clause is not "defective" in the
  same sense as uncapped liability — it is a common drafting pattern that
  Indian courts routinely strike down.
- **Triggers:** Two independent conditions must both be met:
  1. A **post-relationship window** trigger (e.g. "following the
     termination", "after the end of the employment") in a non-negated
     context.
  2. A **competing action** trigger (e.g. "compete with", "engage in any
     business that competes", "solicit any customer") in a **negated**
     context (the action is prohibited — "shall not compete"). The
     negation check uses a full-sentence window (not the standard 6-token
     window) because non-compete clauses use long adverbial phrases.
- **Negation tests:**
  - In-employment non-solicit → NO fire (no post-relationship window).
  - Confidentiality clause mentioning a competitor → NO fire (no
    competing action trigger).
  - IP assignment clause → NO fire (no post-relationship window +
    competing action).
  - Post-termination clause without competing action (e.g. parking
    restriction) → NO fire.
  - Non-Indian jurisdiction → NO fire.
  - Clause not labelled "Non-Compete / Non-Solicit" → NO fire (gated on
    the classifier label).
- **Jurisdiction:** India only (requires_indian=True).
- **Case law:** s. 27 ICA (statute — safe). No case citation curated
  (verify_note: "statute-only pointer — no case citation curated").

### RISK_DISPUTE_001 — Missing dispute-resolution mechanism

- **Meaning:** The contract has no arbitration clause AND no
  court/jurisdiction clause anywhere in the document. The parties would
  fall back to the default statutory forum.
- **Severity:** MEDIUM (score 50.0). Rationale: absence of a mechanism is
  a gap, but the default statutory forum (CPC 1908) is a valid,
  enforceable fallback — not a defect in law. The risk is practical
  (less predictable, potentially inconvenient forum), not legal.
- **Triggers:** Document-wide phrase search (contract-level rule).
  1. **Arbitration mechanism:** reuses `_has_arbitration_context` from
     NER (context-cue + negation-aware). A negated mention
     ("there is no arbitration clause") does NOT count.
  2. **Court/jurisdiction mechanism:** positive, non-negated mentions of
     "jurisdiction of the courts", "courts at", "subject to the
     jurisdiction", "shall have jurisdiction", etc. Forum-restraint
     clauses ("shall not submit to the jurisdiction") are excluded.
  The rule fires only when BOTH are absent.
- **Evidence:** Contract-level, `evidence_status="unverified"`,
  `search_scope` describes the document-wide phrase search. No span can
  prove an absence.
- **Negation tests:**
  - Contract with arbitration clause → NO fire.
  - Contract with court jurisdiction clause → NO fire.
  - Contract with negated arbitration ("no arbitration clause") → FIRES
    (the negated mention is not a mechanism).
  - Non-Indian jurisdiction → NO fire.
- **Jurisdiction:** India only.
- **Case law:** Plain-law note with statute pointers (Arbitration and
  Conciliation Act 1996 Part I; CPC 1908 ss. 5-6). No case citation
  curated. verify_note honestly states what is verified (statute
  existence) and what is not (no case citation; practical gap is
  fact-specific).

## 4. False positives found and addressed

| # | False positive | Fix |
|---|---------------|-----|
| 1 | "nor" in a negated list ("shall not solicit any employee, nor solicit any customer") was incorrectly treated as negating the SECOND item via the standard 6-token window, causing the non-compete action trigger to be suppressed. | Fixed by using a full-sentence negation window for the non-compete action trigger: if ANY negation cue appears before the action in the same sentence, the action is considered negated (i.e. it IS a non-compete prohibition). This correctly handles both "shall not compete" and "shall not ... nor ... solicit". |
| 2 | The NDA sample was expected to fire RISK_DISPUTE_001, but the NDA actually contains a court jurisdiction clause ("submits to the jurisdiction of the courts at Bengaluru"), so RISK_DISPUTE_001 correctly does NOT fire. | Test updated to assert the CORRECT behavior (negative: RISK_DISPUTE_001 does not fire because a court clause is present). This is a documented accepted limitation: the NDA's court clause is a valid dispute-resolution mechanism. |
| 3 | The employment sample initially failed to detect ≥2 parties because the human party name ("Ms. Ananya Deshmukh") did not satisfy the NER step-2 requirement of ≥2 capitalized words. | Fixed by (a) giving the employee a two-word surname ("Ananya Rao Deshmukh") and (b) fixing the unreachable preamble party-detection code in `analyzer.py` (a `break` statement before the group-extraction loop made the fallback dead code). |

## 5. Accepted limitations

1. **RISK_NONCOMPETE_001 precision:** The rule requires BOTH a
   post-relationship window AND a negated competing action. A clause
   that uses different wording for the post-relationship window
   (e.g. "after the expiry of the Agreement" without "termination")
   or a different competing action (e.g. "provide services to a
   competitor") may not be detected. The trigger lists are deliberately
   conservative to avoid false positives.
2. **RISK_DISPUTE_001 phrase coverage:** The rule uses a fixed list of
   court/jurisdiction phrases. A forum clause expressed in unusual
   wording (e.g. "all disputes shall be heard by the courts of the
   High Court at X") may not match. The `search_scope` and
   `uncertainty_note` fields explicitly state this limitation.
3. **Party detection for individual (non-corporate) parties:** The NER
   step-2 requires ≥2 capitalized words, which works for "Ananya Rao
   Deshmukh" but not for single-name or honorific-prefixed names. This
   is a pre-existing limitation in `analyzer.py` (not introduced by this
   workstream).
4. **DPA sample: RISK_LIABILITY_002 fires on the breach-notification
   clause** because the classifier labels it "Limitation of Liability"
   (the phrase "shall not" in the breach context is not a cap). This is
   a known classifier imprecision, not a rule defect. The finding is
   correctly marked as a review prompt, not a confirmed defect.

## 6. Verification

- `uv run pytest tests/test_indian_contracts.py tests/test_risk_rules.py
  tests/test_no_stale_duplicates.py -q` → **75 passed**
- `uv run ruff check nlp/risk_scoring/ tests/test_indian_contracts.py
  tests/test_risk_rules.py` → **clean**
- `uv run pytest tests/ -q` → **560 passed** (including 35 new tests
  from this workstream: 21 in test_indian_contracts.py, 14 in
  test_risk_rules.py)
- `uv run python scripts/run_demo.py` → **works** (12 clauses, 13
  obligations, risk_score 100 on sample_msa.txt)
- Root duplicates (`risk_scoring/rules.py`, `risk_scoring/case_law.py`)
  are byte-identical to their `nlp/` counterparts (verified by
  `test_no_stale_duplicates.py`).
