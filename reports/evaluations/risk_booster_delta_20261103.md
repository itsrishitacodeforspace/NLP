# ML Risk-Booster Delta — 20261103

> **IN-DISTRIBUTION TRAINING-CORPUS COMPARISON — NOT A GENERALIZATION ESTIMATE. CUAD is a US dataset; template-family separation from the keyword-bank source documents is not guaranteed.**

Full pipeline (`app.services.analyzer.analyse_bytes`) run **twice** on the same deterministic CUAD TRAIN clause-text sample (n=300 documents, seed 20261103): once with the ML risk artefact **disabled** (`risk_model._CACHED` hidden, so `_augment_with_ml_risks` no-ops — same behaviour as a missing artefact), once with it **active**. Artefact present in this environment: **yes**.

| Measure | Value |
|---|---|
| Rule-only findings (booster off) | 1531 |
| Rule findings (booster on) | 1531 |
| **ML_RISK_001 findings added** | **63** |
| ML findings on clauses already rule-flagged (redundant) | 0 |
| Clauses whose risk_score changed | 63 / 580 |
| Clauses whose risk_level changed | 63 / 580 |
| Documents whose overall score/level changed | 60 / 300 |

Interpretation: the booster only fires on clauses the rules did **not** flag (by construction it skips rule-flagged clauses, so the redundancy column should be 0). Every added ML_RISK_001 is `source="model"`, `evidence_status="unverified"`, a review prompt with an uncalibrated score — not a verified finding.

> IN-DISTRIBUTION TRAINING-CORPUS COMPARISON — NOT A GENERALIZATION ESTIMATE. CUAD is a US dataset; template-family separation from the keyword-bank source documents is not guaranteed.
