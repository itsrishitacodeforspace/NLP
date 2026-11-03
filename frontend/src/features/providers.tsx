'use client';

import * as React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/components/layout/theme-provider';
import { ToastProvider } from '@/components/layout/toast';
import { AuthProvider } from '@/features/auth/auth-provider';

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Only safe, idempotent GETs retry. Mutations are handled per-call.
            retry: (failureCount, error) => {
              const status = (error as { status?: number })?.status;
              if (status && status >= 400 && status < 500 && status !== 408 && status !== 429) return false;
              return failureCount < 2;
            },
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <AuthProvider>{children}</AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
