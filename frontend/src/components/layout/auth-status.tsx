'use client';

import { useAuth } from '@/features/auth/auth-provider';

export function AuthStatus() {
  const { user, backendAuthEnabled } = useAuth();

  // Backend auth disabled: everyone is an anonymous admin — say so honestly.
  if (!backendAuthEnabled) {
    return (
      <span className="hidden text-xs text-muted-foreground md:inline" title="Authentication is disabled on the backend">
        Auth off
      </span>
    );
  }

  if (!user) {
    return (
      <a
        href="/login"
        className="rounded-md border border-input px-3 py-1.5 text-xs font-medium transition-colors hover:bg-accent"
      >
        Sign in
      </a>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground">
        {user.username} · <span className="capitalize">{user.role}</span>
      </span>
      <LogoutButton />
    </div>
  );
}

import { LogoutButton } from './logout-button';
