# Family-Disjoint Held-Out Evaluation — 20261103

> **CUAD test split, family-disjoint by title+shingle proxy; US contracts; category set differs from the internal 26-label taxonomy (mapped via nlp/taxonomy.py); results indicate in-dataset generalization within CUAD only.**

## Family leakage (the realistic held-out set)

- Train docs: 408 across 375 families; test docs: 102 across 99 families (shingle threshold 0.5).
- Test docs whose family ALSO appears in train: **7** (excluded from evaluation).
- **Test docs family-disjoint from train: 95** (evaluated set).
- Reverse: train docs whose family appears in test: 14.

Evaluated 5039 CUAD-annotated examples from those 95 disjoint documents.

## Summary (top-1 / top-3)

| Mode | Acc@1 | Acc@3 | Macro-F1@1 | Weighted-F1@1 | Macro-F1@3 | Weighted-F1@3 |
|---|---|---|---|---|---|---|
| rule-only | 0.1840 | 0.2526 | 0.1314 | 0.1978 | 0.1373 | 0.2164 |
| hybrid | 0.4009 | 0.5324 | 0.4034 | 0.4133 | 0.2046 | 0.3680 |

## Rule-only

Abstention: 0/5039 (0.0%); Miscellaneous fallback: 1233.

### Top-1

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Intellectual Property | 0.416 | 0.152 | 0.223 | 1037 |
| Payment Terms | 0.212 | 0.198 | 0.205 | 580 |
| Definitions | 0.020 | 0.012 | 0.015 | 573 |
| Non-Compete / Non-Solicit | 0.857 | 0.011 | 0.021 | 562 |
| Assignment | 0.839 | 0.260 | 0.396 | 420 |
| Term and Renewal | 0.169 | 0.416 | 0.241 | 406 |
| Limitation of Liability | 0.870 | 0.109 | 0.194 | 366 |
| Termination | 0.224 | 0.140 | 0.172 | 243 |
| Miscellaneous | 0.039 | 0.249 | 0.067 | 213 |
| Insurance | 0.634 | 0.542 | 0.584 | 179 |
| Audit Rights | 0.683 | 0.344 | 0.458 | 157 |
| Warranty | 0.135 | 0.125 | 0.130 | 104 |
| Governing Law | 0.294 | 0.574 | 0.389 | 101 |
| Confidentiality | 0.037 | 0.143 | 0.058 | 98 |
| <abstained> | 0.000 | 0.000 | 0.000 | 0 |
| Acceptance | 0.000 | 0.000 | 0.000 | 0 |
| Compliance | 0.000 | 0.000 | 0.000 | 0 |
| Data Protection | 0.000 | 0.000 | 0.000 | 0 |
| Dispute Resolution | 0.000 | 0.000 | 0.000 | 0 |
| Force Majeure | 0.000 | 0.000 | 0.000 | 0 |
| Indemnification | 0.000 | 0.000 | 0.000 | 0 |
| Notice | 0.000 | 0.000 | 0.000 | 0 |
| Service Levels | 0.000 | 0.000 | 0.000 | 0 |
| Stamp Duty | 0.000 | 0.000 | 0.000 | 0 |

### Top-3

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Intellectual Property | 0.350 | 0.212 | 0.264 | 1037 |
| Payment Terms | 0.177 | 0.419 | 0.249 | 580 |
| Definitions | 0.010 | 0.014 | 0.012 | 573 |
| Non-Compete / Non-Solicit | 0.393 | 0.020 | 0.037 | 562 |
| Assignment | 0.743 | 0.309 | 0.437 | 420 |
| Term and Renewal | 0.133 | 0.564 | 0.215 | 406 |
| Limitation of Liability | 0.605 | 0.134 | 0.219 | 366 |
| Termination | 0.169 | 0.185 | 0.176 | 243 |
| Miscellaneous | 0.039 | 0.282 | 0.069 | 213 |
| Insurance | 0.502 | 0.648 | 0.566 | 179 |
| Audit Rights | 0.606 | 0.420 | 0.496 | 157 |
| Warranty | 0.100 | 0.164 | 0.124 | 104 |
| Governing Law | 0.266 | 0.604 | 0.370 | 101 |
| Confidentiality | 0.035 | 0.184 | 0.059 | 98 |
| <abstained> | 0.000 | 0.000 | 0.000 | 0 |
| Acceptance | 0.000 | 0.000 | 0.000 | 0 |
| Compliance | 0.000 | 0.000 | 0.000 | 0 |
| Data Protection | 0.000 | 0.000 | 0.000 | 0 |
| Dispute Resolution | 0.000 | 0.000 | 0.000 | 0 |
| Force Majeure | 0.000 | 0.000 | 0.000 | 0 |
| Indemnification | 0.000 | 0.000 | 0.000 | 0 |
| Notice | 0.000 | 0.000 | 0.000 | 0 |
| Service Levels | 0.000 | 0.000 | 0.000 | 0 |
| Stamp Duty | 0.000 | 0.000 | 0.000 | 0 |

## Hybrid

Abstention: 0/5039 (0.0%); Miscellaneous fallback: 13.

### Top-1

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Intellectual Property | 0.589 | 0.290 | 0.389 | 1037 |
| Payment Terms | 0.508 | 0.317 | 0.391 | 580 |
| Definitions | 0.202 | 0.808 | 0.323 | 573 |
| Non-Compete / Non-Solicit | 0.470 | 0.247 | 0.324 | 562 |
| Assignment | 0.863 | 0.479 | 0.616 | 420 |
| Term and Renewal | 0.321 | 0.453 | 0.376 | 406 |
| Limitation of Liability | 0.797 | 0.344 | 0.481 | 366 |
| Termination | 0.554 | 0.317 | 0.403 | 243 |
| Miscellaneous | 0.529 | 0.211 | 0.302 | 213 |
| Insurance | 0.709 | 0.626 | 0.665 | 179 |
| Audit Rights | 0.738 | 0.592 | 0.657 | 157 |
| Warranty | 0.812 | 0.125 | 0.217 | 104 |
| Governing Law | 0.964 | 0.792 | 0.870 | 101 |
| Confidentiality | 0.667 | 0.020 | 0.040 | 98 |
| <abstained> | 0.000 | 0.000 | 0.000 | 0 |

### Top-3

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Intellectual Property | 0.413 | 0.410 | 0.411 | 1037 |
| Payment Terms | 0.225 | 0.576 | 0.323 | 580 |
| Definitions | 0.195 | 0.951 | 0.323 | 573 |
| Non-Compete / Non-Solicit | 0.270 | 0.384 | 0.317 | 562 |
| Assignment | 0.685 | 0.533 | 0.600 | 420 |
| Term and Renewal | 0.147 | 0.685 | 0.241 | 406 |
| Limitation of Liability | 0.612 | 0.380 | 0.469 | 366 |
| Termination | 0.247 | 0.428 | 0.313 | 243 |
| Miscellaneous | 0.057 | 0.404 | 0.099 | 213 |
| Insurance | 0.507 | 0.648 | 0.569 | 179 |
| Audit Rights | 0.483 | 0.618 | 0.542 | 157 |
| Warranty | 0.171 | 0.173 | 0.172 | 104 |
| Governing Law | 0.324 | 0.812 | 0.463 | 101 |
| Confidentiality | 0.041 | 0.194 | 0.068 | 98 |
| <abstained> | 0.000 | 0.000 | 0.000 | 0 |
| Acceptance | 0.000 | 0.000 | 0.000 | 0 |
| Compliance | 0.000 | 0.000 | 0.000 | 0 |
| Data Protection | 0.000 | 0.000 | 0.000 | 0 |
| Dispute Resolution | 0.000 | 0.000 | 0.000 | 0 |
| Force Majeure | 0.000 | 0.000 | 0.000 | 0 |
| Indemnification | 0.000 | 0.000 | 0.000 | 0 |
| Notice | 0.000 | 0.000 | 0.000 | 0 |
| Service Levels | 0.000 | 0.000 | 0.000 | 0 |
| Stamp Duty | 0.000 | 0.000 | 0.000 | 0 |

## Gold category distribution (disjoint set)

| Category | Count |
|---|---|
| Intellectual Property | 1037 |
| Payment Terms | 580 |
| Definitions | 573 |
| Non-Compete / Non-Solicit | 562 |
| Assignment | 420 |
| Term and Renewal | 406 |
| Limitation of Liability | 366 |
| Termination | 243 |
| Miscellaneous | 213 |
| Insurance | 179 |
| Audit Rights | 157 |
| Warranty | 104 |
| Governing Law | 101 |
| Confidentiality | 98 |

## Non-claims

> CUAD test split, family-disjoint by title+shingle proxy; US contracts; category set differs from the internal 26-label taxonomy (mapped via nlp/taxonomy.py); results indicate in-dataset generalization within CUAD only.
> Family separation is a template proxy (title + 8-gram shingle), NOT legal independence — disjoint families can still share boilerplate/jurisdiction.
> This is an in-dataset generalization estimate within CUAD only; it does not support any claim about Indian-law contracts or out-of-CUAD generalization.
> Gold labels come from CUAD's QA annotations (mapped via nlp/taxonomy.py), not independent human adjudication of clause category.
