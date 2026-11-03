'use client';

import * as React from 'react';
import { CalendarClock, CalendarX2 } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { deriveObligationStatus, OBLIGATION_STATUS_STYLE } from '@/features/obligations';
import { cn } from '@/lib/utils';
import type { Obligation } from '@/types';

const TYPE_LABEL: Record<Obligation['obligation_type'], string> = {
  obligation: 'Obligation',
  right: 'Right',
  prohibition: 'Prohibition',
  condition: 'Condition',
};

/**
 * Vertical timeline of obligations that HAVE a definite deadline_date,
 * sorted by date, with a "today" marker. Obligations without a definite
 * date are listed separately below — never plotted on the timeline.
 */
export function ObligationsTimeline({ obligations }: { obligations: Obligation[] }) {
  const now = React.useMemo(() => new Date(), []);
  const dated = React.useMemo(
    () =>
      obligations
        .map((o) => ({ o, d: deriveObligationStatus(o, now) }))
        .filter((x) => x.d.date !== null)
        .sort((a, b) => (a.d.date as Date).getTime() - (b.d.date as Date).getTime()),
    [obligations, now]
  );
  const undated = obligations.filter((o) => !o.deadline_date);
  const today = new Date(now);
  today.setHours(12, 0, 0, 0);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4" aria-hidden />
            Dated obligations
          </CardTitle>
          <CardDescription>
            Only obligations with a definite, machine-parsed deadline date are plotted.
            Conditional or expression-only dates are not shown here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {dated.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No obligations have a definite deadline date. See “No fixed date” below.
            </p>
          ) : (
            <ol className="relative ml-3 border-l-2 border-border">
              <li aria-hidden className="absolute -left-[9px] top-0 h-0 w-0">
                {/* today marker */}
                <TodayMarker today={today} min={dated[0].d.date as Date} max={dated[dated.length - 1].d.date as Date} />
              </li>
              {dated.map(({ o, d }) => (
                <li key={o.obligation_id} className="relative pb-6 pl-6 last:pb-0">
                  <span
                    aria-hidden
                    className={cn(
                      'absolute -left-[7px] top-1 h-3 w-3 rounded-full border-2 border-background',
                      d.status === 'Overdue'
                        ? 'bg-risk-critical'
                        : d.status === 'Upcoming'
                          ? 'bg-risk-high'
                          : 'bg-muted-foreground/50'
                    )}
                  />
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-sm font-medium tabular-nums">{(d.date as Date).toLocaleDateString()}</span>
                    <span
                      className={cn(
                        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium',
                        OBLIGATION_STATUS_STYLE[d.status]
                      )}
                    >
                      {d.status}
                    </span>
                    <Badge variant="secondary" className="text-xs">
                      {TYPE_LABEL[o.obligation_type] ?? o.obligation_type}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm">
                    {[o.action, o.object].filter(Boolean).join(' ') || o.text}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {o.subject ?? 'Unattributed'}
                    {o.counterparty ? ` → ${o.counterparty}` : ''}
                    {o.frequency ? ` · ${o.frequency}` : ''} · clause {o.clause_id}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarX2 className="h-4 w-4" aria-hidden />
            No fixed date
          </CardTitle>
          <CardDescription>
            Obligations without a definite deadline date. Some carry an expression
            (e.g. “30 days”) that depends on a trigger event — they are not plotted
            on the timeline.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {undated.length === 0 ? (
            <p className="text-sm text-muted-foreground">All obligations have a fixed date.</p>
          ) : (
            <ul className="divide-y">
              {undated.map((o) => {
                const d = deriveObligationStatus(o, now);
                return (
                  <li key={o.obligation_id} className="flex items-start gap-3 py-2.5">
                    <span
                      className={cn(
                        'mt-0.5 inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
                        OBLIGATION_STATUS_STYLE[d.status]
                      )}
                    >
                      {d.status}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm">{[o.action, o.object].filter(Boolean).join(' ') || o.text}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {o.subject ?? 'Unattributed'}
                        {o.counterparty ? ` → ${o.counterparty}` : ''}
                        {o.deadline_expression ? ` · “${o.deadline_expression}”` : ''}
                        {o.frequency ? ` · ${o.frequency}` : ''} · clause {o.clause_id}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TodayMarker({ today, min, max }: { today: Date; min: Date; max: Date }) {
  const span = max.getTime() - min.getTime();
  if (span <= 0) return null;
  const t = (today.getTime() - min.getTime()) / span;
  if (t < 0 || t > 1) return null;
  return (
    <span
      className="absolute -left-[16px] flex items-center text-[10px] font-medium text-risk-critical"
      style={{ top: `${t * 100}%` }}
    >
      <span className="h-px w-4 bg-risk-critical/70" aria-hidden />
      today
    </span>
  );
}
