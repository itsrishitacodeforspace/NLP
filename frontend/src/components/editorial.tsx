import * as React from 'react';
import { cn } from '@/lib/utils';

/* ── Shared editorial primitives ────────────────────────────────────────────
   The visual grammar of the "Redline" interface: serif display headings,
   mono § section marks, and hairline rules instead of floaty cards. */

/** A hairline rule. Purely decorative when aria-hidden. */
export function Rule({ className }: { className?: string }) {
  return <div aria-hidden className={cn('h-px w-full bg-border', className)} />;
}

/** Page title: mono kicker + serif display heading, with an optional right-hand slot. */
export function PageTitle({
  kicker,
  title,
  meta,
  children,
  className,
}: {
  kicker?: React.ReactNode;
  title: React.ReactNode;
  meta?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        'flex flex-col gap-4 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between',
        className
      )}
    >
      <div className="space-y-2">
        {kicker ? (
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            {kicker}
          </p>
        ) : null}
        <h1 className="font-display text-[1.85rem] font-semibold leading-[1.08] tracking-tight sm:text-4xl">
          {title}
        </h1>
        {meta ? <div className="text-sm leading-relaxed text-muted-foreground">{meta}</div> : null}
      </div>
      {children ? <div className="flex shrink-0 flex-wrap items-center gap-3">{children}</div> : null}
    </header>
  );
}

/** Section heading: hanging § NN mark + serif title over a hairline rule. */
export function SectionHeading({
  index,
  title,
  action,
  className,
}: {
  index?: string | number;
  title: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('flex items-baseline justify-between gap-4 border-b border-border pb-2', className)}>
      <h2 className="flex items-baseline gap-3 font-display text-lg font-semibold tracking-tight sm:text-xl">
        {index !== undefined ? (
          <span aria-hidden className="font-mono text-[11px] font-normal tracking-widest text-primary">
            §&nbsp;{index}
          </span>
        ) : null}
        {title}
      </h2>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}
