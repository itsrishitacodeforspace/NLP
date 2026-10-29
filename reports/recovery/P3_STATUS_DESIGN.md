# P3 Contract-Level Finding Status — Design

The four-way status is represented by existing `RiskFlag` fields plus whether a finding is emitted. No new schema field is required; the mapping below is the contract.

## Status semantics and mapping

| Status | Representation | Example |
|---|---|---|
| 1. Confirmed issue | rule fires; `evidence_status="direct"`; a `clause_id` + `EvidenceSpan` is attached | `RISK_LIABILITY_001` ("unlimited liability" in a real clause) |
| 2. Relevant protection found | rule returns `None` (no `RiskFlag` emitted) | a liability clause with a stated cap |
| 3. Not found; requires verification | rule fires; `evidence_status="unverified"`; explanation says "not found" | `RISK_STAMP_001`, `RISK_TDS_001` |
| 4. Applicability/evidence unresolved | rule fires; `evidence_status="unverified"`; explanation says "may"/"verify" | `RISK_S124_001` |

Status 2 is the *absence of an emitted finding*, not a field. Statuses 3 and 4 share `evidence_status="unverified"` and are distinguished by the explanation wording (and `search_scope`).

## Per-rule applicability and evidence requirements

- `RISK_STAMP_001` (status 3): fires only for Indian jurisdiction when no stamp-duty language is detected. Establishes "not found", never "unstamped".
- `RISK_TDS_001` (status 3): fires only for Indian jurisdiction and a Payment Terms clause without TDS language. Establishes "not found", never "non-compliant" (applicability is fact-dependent).
- `RISK_S124_001` (status 4): fires only for Indian jurisdiction when an indemnity clause exists but does not expressly cover direct losses / breach of contract. Establishes "may be insufficient", never "defective". Absence of an indemnity clause emits no S124 finding. Since `975512b` the check reads only indemnification clause text; `search_scope` says so explicitly.
- `RISK_LIABILITY_001` (status 1): fires when a Limitation-of-Liability clause explicitly states unlimited/no-limitation language, with a clause-level span.

## Scoring contract

`score_contract` is an **ordinal risk heuristic** (0–100), not a calibrated probability. 100 means "top of the critical band", not "100% likely to be a problem". One critical finding lands in the critical band (~86) but does not by itself reach 100; volume and severity mass add up to the 100 cap.
