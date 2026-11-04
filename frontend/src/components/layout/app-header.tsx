'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ThemeToggle } from './theme-toggle';
import { AuthStatus } from './auth-status';

const NAV = [
  { href: '/contracts', label: 'Contracts' },
  { href: '/obligations', label: 'Obligations' },
  { href: '/graph', label: 'Graph' },
  { href: '/compare', label: 'Compare' },
] as const;

export function AppHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background">
      <div className="mx-auto flex h-14 max-w-[1440px] items-center gap-4 px-5 sm:gap-6 sm:px-8 lg:px-12">
        <Link
          href="/"
          className="flex shrink-0 items-baseline gap-1.5"
          aria-label="BharatContract AI — home"
        >
          <span aria-hidden className="font-mono text-sm leading-none text-primary">
            §
          </span>
          <span className="font-display text-[17px] font-semibold tracking-tight text-foreground">
            BharatContract
          </span>
          <span className="hidden font-mono text-[10px] uppercase tracking-[0.22em] text-muted-foreground sm:inline">
            AI
          </span>
        </Link>

        <nav className="flex items-center gap-3.5 overflow-x-auto sm:gap-5" aria-label="Primary">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={`shrink-0 border-b-2 pb-0.5 pt-1 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors ${
                  active
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-3">
          <ThemeToggle />
          <AuthStatus />
        </div>
      </div>
    </header>
  );
}
