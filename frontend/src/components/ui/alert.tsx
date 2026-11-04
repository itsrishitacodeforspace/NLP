'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export function Alert({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  variant?: 'default' | 'warning' | 'danger' | 'info';
}) {
  return (
    <div
      role="alert"
      className={cn(
        'relative w-full rounded-none border p-4 text-sm',
        {
          default: 'bg-card',
          warning: 'border-risk-medium/40 bg-risk-medium/10 text-foreground',
          danger: 'border-destructive/40 bg-destructive/10 text-foreground',
          info: 'bg-muted/40 text-foreground',
        }[variant],
        className
      )}
      {...props}
    />
  );
}

export function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn('mb-1 font-medium leading-none tracking-tight', className)} {...props} />;
}

export function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('text-sm opacity-90', className)} {...props} />;
}
