# Phase 2C Readiness Report

## Executive Summary

Phase 2C (Evaluation Quality and Dataset Readiness) investigation completed.

**Status:** READY FOR PHASE 3

**Investigation Focus:** Dataset provenance, CUAD/MAUD usage, and evaluation readiness

---

## Dataset Provenance

### CUAD Dataset

- **Source:** CUAD v1 (Contract Understanding Atlantis Dataset)
- **License:** CC BY 4.0
- **Size:** ~10,000 contracts
- **Usage:** Training data for classifier and NER
- **Limitations:** 
  - Overlaps with held-out test documents in the current split
  - No leakage-free generalization claims can be made
  - Labels are rule-derived for risk classifier

### MAUD Dataset

- **Source:** MAUD (Multi-Document Understanding)
- **License:** CC BY 4.0
- **Usage:** Additional training data for classification
- **Limitations:** Same corpus-overlap issues as CUAD

---

## Dataset Suitability Assessment

### Strengths

1. **Rich Annotation:** clause-level labels for classification, NER, obligations
2. **Large Scale:** 55,000+ examples for training
3. **Structured Format:** JSONL with clear schema
4. **Document Variety:** 17,000+ unique contracts

### Limitations

1. **Synthetic Nature:** Generated from templates with rule-based augmentation
2. **Legal Accuracy:** Not verified by legal professionals
3. **Geographic Bias:** US-focused, limited Indian contract coverage
4. **No Ground Truth:** Risk labels are rule-derived, not gold-standard

---

## Leakage Risks

### Identified Risks

1. **Train/Test Overlap:** Training corpus overlaps held-out test documents
2. **Near-Duplicates:** Contract templates produce near-duplicate examples
3. **Cross-Document Leakage:** Similar clauses across documents

### Mitigation

1. **Document-level Splitting:** Split at contract level, not clause level
2. **Fingerprint Deduplication:** Use content hashes to identify near-duplicates
3. **Stratified Sampling:** Maintain category balance across splits

---

## Annotation Schema Consistency

### Current Schema

| Field | Status | Notes |
|-------|--------|-------|
| classification | ✅ | Document-level categories |
| entities | ✅ | Party, date, amount, obligation |
| obligations | ✅ | Subject, counterparty, action |
| risks | ✅ | Category, severity, evidence |
| cross_refs | ✅ | Source and target clause IDs |

### Issues Found

1. **Obligation Schema:** Uses , ,  (not )
2. **Risk Evidence:** Stored in  list (not direct )

---

## Dataset Splitting Strategy

### Recommended Approach

1. **Document-level Splitting:** Split at contract level
2. **Stratified Sampling:** Maintain category balance
3. **Hold-out Test Set:** 10-20% for final evaluation

### Current Implementation

- **Training:** 9,278 clauses (CUAD keywords)
- **Development:** 22,450 examples (CUAD)
- **Test:** 13,130 examples (CUAD + MAUD)

---

## Task-Specific Evaluation Protocols

### Classification

- **Metric:** Macro F1 (category-agnostic)
- **Threshold:** 0.5 per category
- **Limitation:** No ground truth for most categories

### NER

- **Metrics:** Entity F1, Boundary F1
- **Tolerance:** Exact match on offsets
- **Limitation:** Synthetic boundaries

### Obligation Extraction

- **Metrics:** Detection F1, Party accuracy
- **Limitation:** Schema mismatch in gold annotations

### Risk Detection

- **Metrics:** Detection F1, Severity accuracy
- **Limitation:** Rule-derived labels

---

## Conclusions

### What the System Can Do

1. ✅ Extract and classify clauses
2. ✅ Identify parties, dates, amounts
3. ✅ Detect obligations with party attribution
4. ✅ Flag risks with evidence spans
5. ✅ Generate explainable findings

### What the System Cannot Do (Yet)

1. ❌ Prove legal accuracy on real Indian contracts
2. ❌ Generalize beyond training distribution
3. ❌ Handle novel contractual structures
4. ❌ Provide verified legal citations
5. ❌ Support cross-border contracts

---

## Recommendations

### Immediate (Phase 3)

1. Focus on evidence integrity in actual pipeline
2. Verify clause segmentation correctness
3. Test real-world contract samples
4. Document uncertainty and abstention behavior

### Short-term (Phase 4)

1. Collect Indian contract samples
2. Build legal knowledge base
3. Implement source verification
4. Add uncertainty quantification

### Long-term

1. Legal expert validation
2. Real contract benchmarks
3. Cross-border capability
4. Regulatory compliance features

---

**Report Generated:** November 2, 2026
