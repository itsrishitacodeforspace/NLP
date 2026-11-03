'use client';

import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import * as React from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/state';
import { useAuth } from '@/features/auth/auth-provider';
import { isApiError, errorMessage } from '@/lib/api/errors';

function DisabledNotice() {
  return (
    <Alert variant="info">
      <AlertTitle>Authentication is disabled</AlertTitle>
      <AlertDescription>
        Authentication is disabled on this backend. You are using anonymous access.{' '}
        <Link href="/" className="underline underline-offset-4">
          Back to home
        </Link>
      </AlertDescription>
    </Alert>
  );
}

function LoginForm({ next }: { next: string | null }) {
  const router = useRouter();
  const { login } = useAuth();
  const [username, setUsername] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(username, password);
      router.push(next || '/');
    } catch (err) {
      if (isApiError(err)) {
        if (err.isThrottled) {
          setError('Too many failed attempts — account temporarily locked. Please try again in a short while.');
        } else if (err.isAuth) {
          setError('Incorrect username or password.');
        } else {
          setError(err.detail);
        }
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="login-username">Username</Label>
        <Input
          id="login-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoFocus
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="login-password">Password</Label>
        <Input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full" disabled={submitting || !username || !password}>
        {submitting ? (
          <>
            <Spinner className="h-3.5 w-3.5 border-foreground/30 border-t-foreground" /> Signing in…
          </>
        ) : (
          'Sign in'
        )}
      </Button>
      <p className="text-center text-xs">
        <Link href="/" className="text-muted-foreground underline underline-offset-4">
          Back to home
        </Link>
      </p>
    </form>
  );
}

export default function LoginPage() {
  const { backendAuthEnabled, loading } = useAuth();
  const searchParams = useSearchParams();
  const next = searchParams.get('next');

  if (loading) {
    return (
      <div className="mx-auto max-w-sm space-y-4 pt-10">
        <div className="flex justify-center">
          <Spinner />
        </div>
        <p className="text-center text-sm text-muted-foreground">Checking authentication…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-sm space-y-6 pt-10">
      <Card>
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Access BharatContract AI with your credentials.</CardDescription>
        </CardHeader>
        <CardContent>
          {backendAuthEnabled ? <LoginForm next={next} /> : <DisabledNotice />}
        </CardContent>
      </Card>
    </div>
  );
}
