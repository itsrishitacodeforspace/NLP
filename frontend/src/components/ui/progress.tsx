'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number; // 0..1
  label?: string;
}

export function Progress({ value, className, label, ...props }: ProgressProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? 'Progress'}
      className={cn('h-2 w-full overflow-hidden bg-muted', className)}
      {...props}
    >
      <div
        className="h-full bg-primary transition-all duration-300"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
