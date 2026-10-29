# Synthetic Evaluation Results

Deterministic run of the synthetic corpus in `nlp/evaluation/cases.py` through the full `analyse_bytes` pipeline. All contracts are synthetic; expectations encode desired behaviour. This is a software-behaviour check, **not** a measure of legal accuracy or real-world reliability.

## Summary

- Cases: 17
- Passing: 13
- Known limitations (declared, still failing): 4
- Unexpected regressions: 0
- Resolved limitations (declared but now passing): 0

## Evidence-integrity invariants

- [OK] model_findings_are_unverified
- [OK] clause_rule_findings_have_direct_span
- [OK] contract_level_findings_are_scoped_unverified

## Cases

### uncapped_liability_tp — PASS
- Category: `risk_true_positive`
- Expected: Explicit unlimited liability must be flagged as uncapped liability.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_TERMINATION, RISK_LIABILITY_001, RISK_STAMP_001

### auto_renewal_no_notice — PASS
- Category: `risk_true_positive`
- Expected: Auto-renewal with no notice period is a high-severity lock-in risk.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_RENEWAL_001, RISK_STAMP_001

### auto_renewal_with_notice — KNOWN LIMITATION
- Category: `risk_severity_calibration`
- Expected: Auto-renewal WITH a clearly stated 60-day non-renewal notice in the same clause should be medium severity, not high (the lock-in risk is reduced).
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_RENEWAL_001, RISK_STAMP_001
- Deviations from expected:
    - expected RISK_RENEWAL_001@medium, observed ['high']
- Known limitation: rule_auto_renewal parses the notice period with a digit-only regex, so a 'sixty (60) days' (parenthetical/written-out) notice is not recognised and the finding stays high instead of being reduced to medium.

### foreign_gov_law — PASS
- Category: `risk_true_positive`
- Expected: Foreign governing law in an Indian-jurisdiction contract is flagged.
- Observed rule findings: MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_GOV_001, RISK_STAMP_001

### one_sided_termination — PASS
- Category: `risk_true_positive`
- Expected: Termination for convenience in sole discretion is flagged.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, ML_RISK_001, RISK_STAMP_001, RISK_TERM_001

### broad_indemnity_tp — PASS
- Category: `risk_true_positive`
- Expected: Indemnity covering 'any and all claims from any cause whatsoever' is broad.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_TERMINATION, ML_RISK_001, RISK_INDEMNITY_001, RISK_S124_001, RISK_STAMP_001

### data_breach_tight — PASS
- Category: `risk_true_positive`
- Expected: A <=24h breach-notification window is flagged as operationally tight.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_DATA_001, RISK_STAMP_001, RISK_TDS_001

### capped_liability_tn — PASS
- Category: `risk_true_negative`
- Expected: A stated liability cap must NOT raise an uncapped/missing-cap finding.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_TERMINATION, ML_RISK_001, RISK_STAMP_001

### indemnity_direct_losses — PASS
- Category: `risk_true_negative`
- Expected: Indemnity expressly covering direct losses/breach must not raise S124.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_TERMINATION, ML_RISK_001, RISK_INDEMNITY_001, RISK_STAMP_001

### complete_contract — PASS
- Category: `risk_true_negative`
- Expected: A contract with governing law, termination and a liability cap must not raise the keyword-based missing-clause or liability findings.
- Observed rule findings: ML_RISK_001, RISK_STAMP_001, RISK_TDS_001

### stamp_tds_absent — PASS
- Category: `uncertain_legal_conclusion`
- Expected: Absent stamp-duty/TDS language must surface as 'not found - verify' review prompts (unverified), never as a confirmed violation.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_STAMP_001, RISK_TDS_001

### indemnity_narrow — PASS
- Category: `uncertain_legal_conclusion`
- Expected: A narrow indemnity (no direct-loss wording) must raise S124 as a qualified 'may be insufficient - verify' prompt, not a defect.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_TERMINATION, ML_RISK_001, RISK_S124_001, RISK_STAMP_001

### obligation_conditional — PASS
- Category: `conditions_and_exceptions`
- Expected: A conditional payment duty must capture both its condition and its exception.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_STAMP_001, RISK_TDS_001

### ambiguous_recipient — PASS
- Category: `party_beneficiary_ambiguity`
- Expected: A statute reference is not a party; the recipient must stay None, not fabricated.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_STAMP_001

### liability_cap_in_crossref — KNOWN LIMITATION
- Category: `cross_reference_resolution`
- Expected: A liability cap stated in a cross-referenced clause (7.4) should prevent a 'missing cap' finding on clause 7.1.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_TERMINATION, ML_RISK_001, RISK_LIABILITY_002, RISK_STAMP_001
- Deviations from expected:
    - expected rule RISK_LIABILITY_002 absent, but it fired (false positive)
- Known limitation: Rules evaluate a single clause; the cap in cross-referenced clause 7.4 is not consumed, so RISK_LIABILITY_002 is a false positive on 7.1. Automatic cross-clause suppression was deliberately reverted as unsafe (a keyword match in a related clause does not establish an applicable cap).

### obligation_passive — KNOWN LIMITATION
- Category: `passive_voice`
- Expected: A passive duty ('shall be encrypted by the Processor within twenty-four (24) hours') should recover the by-agent as obligor and the 24h deadline.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_STAMP_001, RISK_TDS_001
- Deviations from expected:
    - obligation['encrypted']: subject is None (expected a responsible party)
    - obligation['encrypted']: deadline=None (expected '24 hours')
- Known limitation: Hyphenated written compounds ('twenty-four') are not normalised by the deadline parser, and the passive by-agent is not recovered here, so the subject and 24h deadline are both missed.

### stamp_tds_present_missed — KNOWN LIMITATION
- Category: `detection_recall_gap`
- Expected: 'duly stamped paper' and 'deduction of tax at source' are present, so the stamp/TDS 'not found' prompts should NOT fire.
- Observed rule findings: MISSING_CLAUSE_GOVERNING_LAW, MISSING_CLAUSE_LIMITATION_OF_LIABILITY, MISSING_CLAUSE_TERMINATION, RISK_STAMP_001, RISK_TDS_001
- Deviations from expected:
    - expected rule RISK_STAMP_001 absent, but it fired (false positive)
    - expected rule RISK_TDS_001 absent, but it fired (false positive)
- Known limitation: detect_stamp_duty_mention / detect_tds_mention use narrow keyword lists and miss 'duly stamped paper' and 'deduction of tax at source', so the review prompts fire on a contract that already addresses both.
