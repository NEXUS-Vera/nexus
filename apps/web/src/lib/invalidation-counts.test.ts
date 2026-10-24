import { describe, expect, it } from 'vitest';
import { countEvidenceInvalidations } from './invalidation-counts';

describe('countEvidenceInvalidations', () => {
  it('counts applicability independently of historical PASS/FAIL and counts each chain row', () => {
    const chains = [
      { applicability: { state: 'STALE' }, assessment: 'PASS', testId: 'T1' },
      { applicability: { state: 'STALE' }, assessment: 'FAIL', testId: 'T1' },
      { applicability: { state: 'RECHECK_REQUIRED' }, assessment: 'PASS' },
      { applicability: { state: 'CURRENT' }, assessment: 'FAIL' },
      { applicability: null }, {}, { applicability: {} },
    ];
    const before = JSON.stringify(chains);
    expect(countEvidenceInvalidations(chains)).toEqual({ staleCount: 2, recheckCount: 1 });
    expect(JSON.stringify(chains)).toBe(before);
  });
  it('handles empty chains and unknown future states', () => {
    expect(countEvidenceInvalidations([])).toEqual({ staleCount: 0, recheckCount: 0 });
    expect(countEvidenceInvalidations([{ applicability: { state: 'UNKNOWN' } }])).toEqual({ staleCount: 0, recheckCount: 0 });
  });
});
