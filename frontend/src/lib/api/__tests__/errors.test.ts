import { describe, expect, it } from 'vitest';
import { ApiError, errorMessage, isApiError } from '@/lib/api/errors';

describe('api/errors.ts — ApiError', () => {
  it('carries status, detail and a stable name', () => {
    const e = new ApiError(404, 'not found');
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('ApiError');
    expect(e.status).toBe(404);
    expect(e.detail).toBe('not found');
    expect(e.message).toBe('not found');
  });

  it('exposes status predicates', () => {
    const mk = (s: number) => new ApiError(s, 'x');
    expect(mk(401).isAuth).toBe(true);
    expect(mk(403).isForbidden).toBe(true);
    expect(mk(404).isNotFound).toBe(true);
    expect(mk(409).isConflict).toBe(true);
    expect(mk(413).isTooLarge).toBe(true);
    expect(mk(429).isThrottled).toBe(true);
    // Each predicate is exclusive to its own status.
    expect(mk(401).isNotFound).toBe(false);
    expect(mk(404).isAuth).toBe(false);
    expect(mk(200).isAuth).toBe(false);
    expect(mk(200).isThrottled).toBe(false);
  });

  it('isApiError narrows only ApiError instances', () => {
    expect(isApiError(new ApiError(500, 'x'))).toBe(true);
    expect(isApiError(new Error('nope'))).toBe(false);
    expect(isApiError('string')).toBe(false);
    expect(isApiError(null)).toBe(false);
  });

  describe('errorMessage', () => {
    it('prefers ApiError.detail', () => {
      expect(errorMessage(new ApiError(413, 'File too large'))).toBe('File too large');
    });

    it('falls back to Error.message', () => {
      expect(errorMessage(new Error('boom'))).toBe('boom');
    });

    it('stringifies anything else', () => {
      expect(errorMessage('plain')).toBe('plain');
      expect(errorMessage(42)).toBe('42');
      expect(errorMessage(null)).toBe('null');
    });
  });
});
