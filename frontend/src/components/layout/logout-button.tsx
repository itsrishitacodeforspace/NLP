'use client';

import { useAuth } from '@/features/auth/auth-provider';
import { Button } from '@/components/ui/button';

export function LogoutButton() {
  const { logout } = useAuth();
  return (
    <Button variant="ghost" size="sm" onClick={logout} className="h-7 px-2 text-xs">
      Sign out
    </Button>
  );
}
