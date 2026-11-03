import * as React from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/components/layout/theme-provider';
import { ToastProvider } from '@/components/layout/toast';
import { AuthProvider } from '@/features/auth/auth-provider';
import { vi } from 'vitest';

/**
 * Render a component wrapped in the app's provider stack
 * (QueryClient + Theme + Toast + Auth), mirroring src/app/layout.tsx.
 *
 * Components that call `useRouter()` (e.g. DropZone) additionally need
 * `vi.mock('next/navigation', ...)` at the top of the test file, because
 * Next's app-router hooks throw outside a Next.js document.
 */
export function renderWithProviders(ui: React.ReactElement, options?: Omit<RenderOptions, 'wrapper'>) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>{ui}</AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>,
    options
  );
}

/**
 * next/navigation is mocked per test file (vi.mock hoists the factory above
 * imports, so the factory must be self-contained and reference no imported
 * bindings). Each test file uses this shape and records `push` calls on
 * globalThis.__BC_TEST_ROUTER_PUSH:
 *
 *   vi.mock('next/navigation', () => ({
 *     useRouter: () => ({
 *       push: (p: string) => globalThis.__BC_TEST_ROUTER_PUSH?.(p),
 *       replace: () => {}, back: () => {}, forward: () => {},
 *       refresh: () => {}, prefetch: () => {},
 *     }),
 *     usePathname: () => '/',
 *     useSearchParams: () => new URLSearchParams(),
 *     useRouterState: () => ({ asPath: '/', pathname: '/' }),
 *   }));
 *
 * Then assert with:  expect(getRouterPushSpy()).toHaveBeenCalledWith('/jobs/x');
 */
declare global {
  // eslint-disable-next-line no-var
  var __BC_TEST_ROUTER_PUSH: ReturnType<typeof vi.fn> | undefined;
}

/** Returns (creating on first use) the shared router push spy. */
export function getRouterPushSpy() {
  if (typeof globalThis.__BC_TEST_ROUTER_PUSH === 'undefined') {
    globalThis.__BC_TEST_ROUTER_PUSH = vi.fn();
  }
  return globalThis.__BC_TEST_ROUTER_PUSH;
}

export { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
