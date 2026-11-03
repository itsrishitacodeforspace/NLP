import Link from 'next/link';
import { Scale } from 'lucide-react';
import { ThemeToggle } from './theme-toggle';
import { AuthStatus } from './auth-status';

export function AppHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Scale className="h-5 w-5 text-primary" aria-hidden />
          <span className="hidden sm:inline">BharatContract AI</span>
          <span className="sm:hidden">BharatContract</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm" aria-label="Primary">
          <NavLink href="/contracts" label="Contracts" />
          <NavLink href="/obligations" label="Obligations" />
          <NavLink href="/graph" label="Graph" />
          <NavLink href="/compare" label="Compare" />
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <ThemeToggle />
          <AuthStatus />
        </div>
      </div>
    </header>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="rounded-md px-3 py-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
    >
      {label}
    </Link>
  );
}
