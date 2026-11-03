import { describe, expect, it } from 'vitest';
import { ruleIdToCategory } from '@/features/risks';

describe('features/risks — ruleIdToCategory (frontend display grouping)', () => {
  it('maps Indian-statutory and per-clause rule prefixes', () => {
    expect(ruleIdToCategory('RISK_LIABILITY_001')).toBe('Liability');
    expect(ruleIdToCategory('RISK_LIABILITY_002')).toBe('Liability');
    expect(ruleIdToCategory('RISK_TDS_001')).toBe('TDS');
    expect(ruleIdToCategory('RISK_STAMP_001')).toBe('Stamp duty');
    expect(ruleIdToCategory('RISK_INDEMNITY_001')).toBe('Indemnity');
    expect(ruleIdToCategory('RISK_DATA_001')).toBe('Data protection');
    expect(ruleIdToCategory('RISK_TERM_001')).toBe('Termination');
    expect(ruleIdToCategory('RISK_ARB_001')).toBe('Arbitration');
    expect(ruleIdToCategory('RISK_GOV_001')).toBe('Governing law');
    expect(ruleIdToCategory('RISK_RENEWAL_001')).toBe('Renewal');
    expect(ruleIdToCategory('RISK_NONCOMPETE_001')).toBe('Non-compete');
    expect(ruleIdToCategory('RISK_DISPUTE_001')).toBe('Dispute');
    expect(ruleIdToCategory('RISK_S124_001')).toBe('Indemnity (s.124)');
  });

  it('maps ML-recall-boost findings to "Model"', () => {
    expect(ruleIdToCategory('ML_RISK_001')).toBe('Model');
  });

  it('maps unknown/missing rule ids to "Other"', () => {
    expect(ruleIdToCategory('RISK_FOO_999')).toBe('Other');
    expect(ruleIdToCategory('MISSING_CLAUSE_LIMITATION_OF_LIABILITY')).toBe('Other');
    expect(ruleIdToCategory('RISK_DATA_MISSING')).toBe('Other');
    expect(ruleIdToCategory('')).toBe('Other');
    expect(ruleIdToCategory(null)).toBe('Other');
    expect(ruleIdToCategory(undefined)).toBe('Other');
  });
});
