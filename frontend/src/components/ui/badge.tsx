import * as React from 'react';
import { cn } from '@/lib/utils';

/* A stamped label — sharp corners, no pill shape. */
export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'secondary' | 'outline' | 'destructive';
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-none border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-[0.08em] transition-colors',
        {
          default: 'border-transparent bg-primary text-primary-foreground',
          secondary: 'border-border bg-secondary text-secondary-foreground',
          destructive: 'border-transparent bg-destructive text-destructive-foreground',
          outline: 'border-border text-foreground',
        }[variant],
        className
      )}
      {...props}
    />
  );
}
