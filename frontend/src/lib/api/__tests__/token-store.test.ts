import { beforeEach, describe, expect, it } from 'vitest';
import { clearToken, getToken, getStoredUser, saveToken } from '@/lib/api/token-store';

// The token store uses process.env.AUTH_STORAGE_KEY (default 'bharatcontract.token').
// In tests we just use whatever KEY the module resolved to — localStorage is mocked.

function mockLocalStorage() {
  let store = new Map<string, string>();
  return {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => void (store = new Map()),
  };
}

beforeEach(() => {
  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage(),
    writable: true,
  });
});

describe('api/token-store.ts', () => {
  it('getToken returns null when nothing is stored', () => {
    expect(getToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
  });

  it('saveToken/getToken round-trips a token', () => {
    saveToken({ token: 'abc123', username: 'alice', role: 'admin', expiresAt: null });
    expect(getToken()).toBe('abc123');
  });

  it('getStoredUser returns username and role but not the token itself', () => {
    saveToken({ token: 'abc123', username: 'bob', role: 'analyst', expiresAt: null });
    expect(getStoredUser()).toEqual({ username: 'bob', role: 'analyst' });
  });

  it('clearToken removes the stored token', () => {
    saveToken({ token: 'abc123', username: 'alice', role: 'admin', expiresAt: null });
    clearToken();
    expect(getToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
  });

  it('treats an expired token as absent and clears it', () => {
    saveToken({ token: 'stale', username: 'carol', role: 'viewer', expiresAt: Date.now() - 1000 });
    expect(getToken()).toBeNull();
    // The expired entry must have been purged.
    expect(window.localStorage.getItem('bharatcontract.token')).toBeNull();
  });

  it('returns null for future expiry', () => {
    saveToken({ token: 'fresh', username: 'carol', role: 'viewer', expiresAt: Date.now() + 60_000 });
    expect(getToken()).toBe('fresh');
  });

  it('is resilient to corrupt JSON in storage', () => {
    window.localStorage.setItem('bharatcontract.token', '{not json');
    expect(getToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
  });
});
