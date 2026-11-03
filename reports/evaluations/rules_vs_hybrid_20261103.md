# Rules-Only vs Hybrid Clause Classifier — 20261103

> **IN-DISTRIBUTION TRAINING-CORPUS COMPARISON — NOT A GENERALIZATION ESTIMATE. CUAD is a US dataset; template-family separation from the keyword-bank source documents is not guaranteed.**

- Input: `data/processed/clause_classifier.csv` — 9278 rows total, 2000 evaluated (deterministic stratified-by-file sample, seed 20261103)
- Gold: the `category` column of the CSV, which is the taxonomy category the row's snippet was *derived* from (training labels, not human adjudication).
- **Active components:** rule engine (2021 compiled keyword patterns, incl. CUAD bank) | TF-IDF model **ACTIVE (14 labels)** | keyword bank **LOADED (verified)**.
- TF-IDF labels (the only classes the ML half can emit): Assignment, Audit Rights, Confidentiality, Definitions, Governing Law, Insurance, Intellectual Property, Limitation of Liability, Miscellaneous, Non-Compete / Non-Solicit, Payment Terms, Term and Renewal, Termination, Warranty.
- Elapsed: 47.4s.

## Summary (top-1 / top-3)

| Mode | Acc@1 | Acc@3 | Macro-F1@1 | Weighted-F1@1 | Macro-F1@3 | Weighted-F1@3 |
|---|---|---|---|---|---|---|
| rule-only | 0.3370 | 0.4080 | 0.2367 | 0.3818 | 0.2542 | 0.4110 |
| hybrid | 0.9160 | 0.9860 | 0.8560 | 0.9167 | 0.4134 | 0.7951 |

## Rule-only — per-class (top-1 / top-3)

Macro-F1: top-1 = 0.2367, top-3 = 0.2542; weighted-F1: top-1 = 0.3818, top-3 = 0.4110.

### Top-1

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Definitions | 0.455 | 0.038 | 0.070 | 397 |
| Intellectual Property | 0.610 | 0.335 | 0.432 | 248 |
| Assignment | 0.763 | 0.435 | 0.554 | 200 |
| Term and Renewal | 0.354 | 0.655 | 0.460 | 200 |
| Payment Terms | 0.447 | 0.264 | 0.332 | 174 |
| Limitation of Liability | 0.948 | 0.369 | 0.531 | 149 |
| Non-Compete / Non-Solicit | 0.545 | 0.041 | 0.076 | 147 |
| Termination | 0.376 | 0.278 | 0.320 | 126 |
| Audit Rights | 0.944 | 0.451 | 0.611 | 113 |
| Governing Law | 0.922 | 0.807 | 0.861 | 88 |
| Insurance | 0.875 | 0.805 | 0.838 | 87 |
| Warranty | 0.630 | 0.486 | 0.548 | 35 |
| Miscellaneous | 0.009 | 0.200 | 0.018 | 30 |
| Confidentiality | 0.017 | 0.167 | 0.031 | 6 |
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
| Definitions | 0.357 | 0.050 | 0.088 | 397 |
| Intellectual Property | 0.571 | 0.407 | 0.475 | 248 |
| Assignment | 0.646 | 0.520 | 0.576 | 200 |
| Term and Renewal | 0.312 | 0.750 | 0.441 | 200 |
| Payment Terms | 0.317 | 0.333 | 0.325 | 174 |
| Limitation of Liability | 0.900 | 0.423 | 0.575 | 149 |
| Non-Compete / Non-Solicit | 0.500 | 0.068 | 0.120 | 147 |
| Termination | 0.323 | 0.333 | 0.328 | 126 |
| Audit Rights | 0.929 | 0.690 | 0.792 | 113 |
| Governing Law | 0.902 | 0.841 | 0.871 | 88 |
| Insurance | 0.838 | 0.954 | 0.892 | 87 |
| Warranty | 0.481 | 0.714 | 0.575 | 35 |
| Miscellaneous | 0.011 | 0.233 | 0.020 | 30 |
| Confidentiality | 0.012 | 0.167 | 0.022 | 6 |
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

## Hybrid — per-class (top-1 / top-3)

Macro-F1: top-1 = 0.8560, top-3 = 0.4134; weighted-F1: top-1 = 0.9167, top-3 = 0.7951.

### Top-1

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Definitions | 0.929 | 0.889 | 0.909 | 397 |
| Intellectual Property | 0.906 | 0.899 | 0.903 | 248 |
| Assignment | 0.952 | 0.890 | 0.920 | 200 |
| Term and Renewal | 0.783 | 0.850 | 0.815 | 200 |
| Payment Terms | 0.965 | 0.937 | 0.950 | 174 |
| Limitation of Liability | 0.980 | 0.993 | 0.987 | 149 |
| Non-Compete / Non-Solicit | 0.820 | 0.898 | 0.857 | 147 |
| Termination | 0.879 | 0.921 | 0.899 | 126 |
| Audit Rights | 0.991 | 0.982 | 0.987 | 113 |
| Governing Law | 0.989 | 1.000 | 0.994 | 88 |
| Insurance | 0.988 | 0.977 | 0.983 | 87 |
| Warranty | 1.000 | 0.971 | 0.986 | 35 |
| Miscellaneous | 0.897 | 0.867 | 0.881 | 30 |
| Confidentiality | 0.714 | 0.833 | 0.769 | 6 |
| <abstained> | 0.000 | 0.000 | 0.000 | 0 |

### Top-3

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Definitions | 0.800 | 0.987 | 0.884 | 397 |
| Intellectual Property | 0.687 | 0.984 | 0.809 | 248 |
| Assignment | 0.717 | 0.975 | 0.826 | 200 |
| Term and Renewal | 0.352 | 1.000 | 0.521 | 200 |
| Payment Terms | 0.556 | 0.977 | 0.708 | 174 |
| Limitation of Liability | 0.898 | 1.000 | 0.946 | 149 |
| Non-Compete / Non-Solicit | 0.673 | 0.966 | 0.793 | 147 |
| Termination | 0.521 | 1.000 | 0.685 | 126 |
| Audit Rights | 0.942 | 1.000 | 0.970 | 113 |
| Governing Law | 0.917 | 1.000 | 0.957 | 88 |
| Insurance | 0.860 | 0.989 | 0.920 | 87 |
| Warranty | 0.576 | 0.971 | 0.723 | 35 |
| Miscellaneous | 0.041 | 0.933 | 0.078 | 30 |
| Confidentiality | 0.054 | 0.833 | 0.102 | 6 |
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

## Abstention

- **rule-only**: never returns an empty label list — its 'abstention' is the `Miscellaneous` fallback: 642/2000 rows (32.1%).
  - fallback distribution over gold: Definitions=273, Intellectual Property=71, Payment Terms=70, Non-Compete / Non-Solicit=59, Limitation of Liability=38, Term and Renewal=34, Assignment=33, Termination=25
- **hybrid**: empty label list after the 0.15 TF-IDF threshold: 0/2000 rows (0.0%).

What we give up when abstaining = the gold categories above: these are the rows where the mode emits no usable label (hybrid) or only the `Miscellaneous` fallback (rule-only), i.e. the precision cost of staying quiet.

## Mode delta (rule-only → hybrid)

- Top-1 label changed: 1308/2000 (65.4%).
- Rows the rule mode mis-filed as `Miscellaneous` that the hybrid re-labels correctly-or-differently: 638.

## Hybrid confusion matrix (top-1, classes observed)

> Multi-label handling: the hybrid classifier emits a ranked list of up to 5 labels (union of TF-IDF and rule labels). Top-1 metrics use label[0]; the confusion matrix maps each row to its single top-1 prediction, so multi-label agreement is under-represented here — top-3 is the fairer single-number view.

| gold \ pred | Payment Terms | Term and Renewal | Termination | Indemnification | Limitation of Liability | Warranty | Confidentiality | Data Protection | Intellectual Property | Non-Compete / Non-Solicit | Governing Law | Dispute Resolution | Force Majeure | Assignment | Audit Rights | Insurance | Compliance | Service Levels | Notice | Acceptance | Definitions | Miscellaneous | Stamp Duty |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Payment Terms | 163 | 1 | 4 | 0 | 1 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| Term and Renewal | 1 | 170 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 0 | 0 |
| Termination | 0 | 5 | 116 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Indemnification | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Limitation of Liability | 0 | 1 | 0 | 0 | 148 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Warranty | 0 | 0 | 1 | 0 | 0 | 34 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Confidentiality | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Data Protection | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Intellectual Property | 2 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 223 | 16 | 0 | 0 | 0 | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| Non-Compete / Non-Solicit | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 10 | 132 | 0 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Governing Law | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 88 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Dispute Resolution | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Force Majeure | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Assignment | 0 | 1 | 5 | 0 | 1 | 0 | 1 | 0 | 5 | 6 | 1 | 0 | 0 | 178 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 0 |
| Audit Rights | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 111 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Insurance | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 85 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Compliance | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Service Levels | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Notice | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Acceptance | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Definitions | 1 | 38 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 353 | 0 | 0 |
| Miscellaneous | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 0 |
| Stamp Duty | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Non-claims

> IN-DISTRIBUTION TRAINING-CORPUS COMPARISON — NOT A GENERALIZATION ESTIMATE. CUAD is a US dataset; template-family separation from the keyword-bank source documents is not guaranteed.
> - This corpus is the **training corpus** (manifest-verified train-only); every number here is in-distribution.
> - The keyword bank is derived from the same CUAD snippets, so rule-mode accuracy is doubly optimistic.
> - CUAD is a US dataset; nothing here supports a claim about Indian-law contracts or categories.
