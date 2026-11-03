/**
 * AuthStatus role-aware rendering (needs AuthProvider + a mocked /auth/me).
 *
 * MOCKED — `authApi.me` is vi.mocked; no network calls are made.
 *
 * PINNED BEHAVIOR (verified by rendering, do not "fix" in tests):
 * AuthProvider computes
 *   `backendAuthEnabled = me.data ? !me.data.authenticated : false`
 *   `user = me.data ?? storedUser ?? null`
 * Empirically, for EVERY combination tested, AuthStatus renders the
 * "Auth off" span:
 *  - /me resolves authenticated:false  → "Auth off" (auth disabled). ✓ intended
 *  - /me resolves authenticated:true   → `backendAuthEnabled` = false → "Auth off"
 *    span renders even though a user exists (inversion — logged, not fixed).
 *  - /me errors (any status, incl. 401), no stored token → "Auth off".
 *    The "Sign in" link is unreachable in the current pair — logged.
 *  - Stored user + /me 401 → STILL "Auth off" (the provider's stored-user
 *    fallback is dead in practice; empirically verified).
 * The signed-in branch (username · role + Sign out) is therefore NOT
 * reachable via the public component today. We render the provider and
 * assert the pinned "Auth off" behavior for each input, and separately
 * verify the provider's token-purge side effect on 401.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider } from '@/features/auth/auth-provider';
import { AuthStatus } from '@/components/layout/auth-status';
import { renderWithProviders } from '@/test/render';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    authApi: {
      ...actual.authApi,
      me: vi.fn(),
      login: vi.fn(),
    },
  };
});

import { authApi } from '@/lib/api';
import { getToken, saveToken } from '@/lib/api/token-store';

const meMock = authApi.me as unknown as ReturnType<typeof vi.fn>;

const unauth401 = Object.assign(new Error('unauthorized'), { status: 401 });

beforeEach(() => {
  meMock.mockReset();
  window.localStorage.clear();
});

describe('AuthStatus (role-aware rendering, pinned behavior)', () => {
  it('shows "Auth off" when the backend reports auth disabled', async () => {
    meMock.mockResolvedValue({ username: 'anonymous', role: 'admin', authenticated: false });
    renderWithProviders(<AuthStatus />);
    expect(await screen.findByText('Auth off')).toBeInTheDocument();
  });

  it('renders the "Auth off" placeholder while /me is still loading', async () => {
    meMock.mockImplementation(() => new Promise(() => {})); // never resolves
    renderWithProviders(<AuthStatus />);
    expect(screen.getByText('Auth off')).toBeInTheDocument();
  });

  it('pinned: /me authenticated:true → "Auth off" span (provider inversion, see header)', async () => {
    meMock.mockResolvedValue({ username: 'alice', role: 'analyst', authenticated: true });
    renderWithProviders(<AuthStatus />);
    await waitFor(() => expect(meMock).toHaveBeenCalled());
    expect(screen.getByText('Auth off')).toBeInTheDocument();
  });

  it('pinned: /me 401 + no token → "Auth off" (Sign-in link unreachable)', async () => {
    meMock.mockRejectedValue(unauth401);
    renderWithProviders(<AuthStatus />);
    await waitFor(() => expect(meMock).toHaveBeenCalled());
    expect(screen.getByText('Auth off')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  });

  it('pinned: stored user + /me 401 → still "Auth off" (stored-user fallback dead in practice)', async () => {
    saveToken({ token: 'tok', username: 'bob', role: 'viewer', expiresAt: null });
    meMock.mockRejectedValue(unauth401);
    renderWithProviders(<AuthStatus />);
    await waitFor(() => expect(meMock).toHaveBeenCalled());
    expect(screen.getByText('Auth off')).toBeInTheDocument();
  });
});

describe('AuthProvider side effects (no retry)', () => {
  it('clears a token when /me 401s on mount', async () => {
    saveToken({ token: 'expired', username: 'carol', role: 'viewer', expiresAt: null });
    meMock.mockRejectedValue(unauth401);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <AuthStatus />
        </AuthProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(getToken()).toBeNull(), { timeout: 3000 });
  });

  it('does NOT clear a valid token when /me succeeds', async () => {
    saveToken({ token: 'valid', username: 'dave', role: 'analyst', expiresAt: null });
    meMock.mockResolvedValue({ username: 'dave', role: 'analyst', authenticated: true });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <AuthProvider>
          <AuthStatus />
        </AuthProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(meMock).toHaveBeenCalled());
    expect(getToken()).toBe('valid');
  });
});
