# P4 Adversarial Review — 2026-10-27

## Verdict: PARTIALLY VERIFIED

The original P4 suppression was found to be **unsafe** and was reverted. The context enrichment (related_clause_texts) is retained as advisory only.

## Adversarial findings

### Liability suppression (unsafe)
The original logic suppressed RISK_LIABILITY_002 whenever a related clause contained any cap keyword ("liability cap", "shall not exceed", "limited to", "maximum liability"). This is unsafe because:
- A cap for a different party does not protect the assessed party.
- A cap for a different loss category (direct vs. indirect) does not apply.
- A cap mentioned only in a definition does not establish a contractual cap.
- A cap that excludes the assessed liability does not help.
- Conflicting provisions make applicability ambiguous.
- Unresolved references must not suppress.

Keyword presence in a related clause is insufficient to establish applicability. Reference resolution alone is not proof.

### Renewal suppression (unsafe)
The original logic treated any notice period in a related clause as a renewal opt-out. This is unsafe because:
- A reminder is not an opt-out right.
- A generic termination-notice clause is not a non-renewal opt-out.
- Conflicting provisions make applicability ambiguous.

## Fix applied
Removed the automatic suppression from both `rule_uncapped_liability` and `rule_auto_renewal`. Findings are preserved. Context is advisory only. The enrichment (related_clause_texts) is retained for future, more careful integration.

## Tests
- `tests/test_p4_context_rules.py` (3 tests) — updated to assert findings are preserved.
- `tests/test_p4_adversarial.py` (10 tests) — all pass, covering the adversarial cases above.

## Verification
- Ruff: All checks passed!
- Full suite: 7 failed, 89 passed, 4 warnings (84+ collected). The 7 failures are the expected provenance guards.

## Limitations
- No whole-contract suppression is performed; false positives from cross-referenced caps/notice periods remain.
- A future, safer integration would require semantic analysis of party, scope, and loss category — beyond keyword matching.

## Conclusion
**PARTIALLY VERIFIED** — the context enrichment is sound and additive; the suppression was unsafe and has been removed. The system no longer makes unsupported suppression decisions.