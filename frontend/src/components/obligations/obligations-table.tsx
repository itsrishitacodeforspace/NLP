'use client';

import * as React from 'react';
import Link from 'next/link';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  OBLIGATION_STATUS_STYLE,
  anyObligationHasDate,
  buildObligationsIcs,
  deriveObligationStatus,
  matchesDeadlineFilter,
  type DeadlineFilter,
  type DerivedStatus,
} from '@/features/obligations';
import { cn } from '@/lib/utils';
import type { Obligation, ObligationType } from '@/types';

const PAGE_SIZE = 25;

type SortKey = 'party' | 'deadline' | 'type' | 'confidence';
type SortDir = 'asc' | 'desc';

const TYPE_LABEL: Record<ObligationType, string> = {
  obligation: 'Obligation',
  right: 'Right',
  prohibition: 'Prohibition',
  condition: 'Condition',
};

interface Filters {
  subject: string; // 'all' or a subject value
  deadline: DeadlineFilter;
  frequency: string; // 'all' or a frequency value
  type: string; // 'all' or ObligationType
  search: string;
}

function useNow(): Date {
  // Stable "today" for the session; re-computed only on mount.
  return React.useMemo(() => new Date(), []);
}

export function ObligationsTable({
  obligations,
  contractId,
}: {
  obligations: Obligation[];
  contractId: string;
}) {
  const now = useNow();
  const [filters, setFilters] = React.useState<Filters>({
    subject: 'all',
    deadline: 'all',
    frequency: 'all',
    type: 'all',
    search: '',
  });
  const [sortKey, setSortKey] = React.useState<SortKey>('deadline');
  const [sortDir, setSortDir] = React.useState<SortDir>('asc');
  const [page, setPage] = React.useState(1);

  const subjects = React.useMemo(
    () =>
      [...new Set(obligations.map((o) => o.subject).filter((s): s is string => Boolean(s)))].sort(),
    [obligations]
  );
  const frequencies = React.useMemo(
    () =>
      [...new Set(obligations.map((o) => o.frequency).filter((f): f is string => Boolean(f)))].sort(),
    [obligations]
  );

  const derived = React.useMemo(
    () => obligations.map((o) => ({ o, d: deriveObligationStatus(o, now) })),
    [obligations, now]
  );

  const filtered = React.useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return derived.filter(({ o }) => {
      if (filters.subject !== 'all' && o.subject !== filters.subject) return false;
      if (!matchesDeadlineFilter(o, filters.deadline, now)) return false;
      if (filters.frequency !== 'all' && o.frequency !== filters.frequency) return false;
      if (filters.type !== 'all' && o.obligation_type !== filters.type) return false;
      if (q) {
        const hay = [o.text, o.action, o.object, o.condition, o.subject, o.counterparty, o.clause_id]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [derived, filters, now]);

  const sorted = React.useMemo(() => {
    const arr = [...filtered];
    const dir = sortDir === 'asc' ? 1 : -1;
    arr.sort((a, b) => {
      switch (sortKey) {
        case 'party':
          return (a.o.subject ?? '∞').localeCompare(b.o.subject ?? '∞') * dir;
        case 'type':
          return a.o.obligation_type.localeCompare(b.o.obligation_type) * dir;
        case 'confidence':
          return (a.o.confidence - b.o.confidence) * dir;
        case 'deadline': {
          const da = a.d.date?.getTime() ?? Number.POSITIVE_INFINITY;
          const db = b.d.date?.getTime() ?? Number.POSITIVE_INFINITY;
          return (da - db) * dir;
        }
      }
    });
    return arr;
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = sorted.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const exportIcs = () => {
    const blob = buildObligationsIcs(obligations);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `contractual-deadlines-${contractId}.ics`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const canExport = anyObligationHasDate(obligations);
  const selectCls =
    'h-9 border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search obligations…"
          value={filters.search}
          onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          className="w-56"
          aria-label="Search obligations"
        />
        <select
          className={selectCls}
          value={filters.subject}
          onChange={(e) => setFilters((f) => ({ ...f, subject: e.target.value }))}
          aria-label="Filter by responsible party"
        >
          <option value="all">Party: all</option>
          {subjects.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select
          className={selectCls}
          value={filters.deadline}
          onChange={(e) => setFilters((f) => ({ ...f, deadline: e.target.value as DeadlineFilter }))}
          aria-label="Filter by deadline"
        >
          <option value="all">Deadline: all</option>
          <option value="has-date">Has date</option>
          <option value="no-date">No date</option>
          <option value="overdue">Overdue</option>
          <option value="upcoming">Upcoming</option>
        </select>
        <select
          className={selectCls}
          value={filters.frequency}
          onChange={(e) => setFilters((f) => ({ ...f, frequency: e.target.value }))}
          aria-label="Filter by frequency"
        >
          <option value="all">Frequency: all</option>
          {frequencies.map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <select
          className={selectCls}
          value={filters.type}
          onChange={(e) => setFilters((f) => ({ ...f, type: e.target.value }))}
          aria-label="Filter by type"
        >
          <option value="all">Type: all</option>
          {(Object.keys(TYPE_LABEL) as ObligationType[]).map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </select>
        <div className="ml-auto">
          {canExport ? (
            <Button variant="outline" size="sm" onClick={exportIcs}>
              Contractual deadlines (ICS)
            </Button>
          ) : (
            <span title="No obligations have definite dates" className="inline-block">
              <Button variant="outline" size="sm" disabled>
                Contractual deadlines (ICS)
              </Button>
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto border border-border">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="bg-muted/40">
            <tr className="text-left font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              <th className="px-3 py-2 font-medium">Obligation</th>
              <SortHeader label="Responsible party" active={sortKey === 'party'} dir={sortDir} onClick={() => toggleSort('party')} />
              <th className="px-3 py-2 font-medium">Beneficiary</th>
              <th className="px-3 py-2 font-medium">Trigger</th>
              <SortHeader label="Deadline" active={sortKey === 'deadline'} dir={sortDir} onClick={() => toggleSort('deadline')} />
              <th className="px-3 py-2 font-medium">Frequency</th>
              <SortHeader label="Type" active={sortKey === 'type'} dir={sortDir} onClick={() => toggleSort('type')} />
              <th className="px-3 py-2 font-medium">Source clause</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <SortHeader label="Confidence" active={sortKey === 'confidence'} dir={sortDir} onClick={() => toggleSort('confidence')} />
            </tr>
          </thead>
          <tbody className="divide-y">
            {pageItems.map(({ o, d }) => (
              <ObligationRow key={o.obligation_id} o={o} d={d} contractId={contractId} />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {sorted.length} of {obligations.length} obligations
          {sorted.length !== obligations.length ? ' (filtered)' : ''}
        </span>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>
            Prev
          </Button>
          <span className="tabular-nums">
            Page {safePage} / {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

function SortHeader({
  label,
  active,
  dir,
  onClick,
}: {
  label: string;
  active: boolean;
  dir: SortDir;
  onClick: () => void;
}) {
  return (
    <th className="px-3 py-2 font-medium">
      <button type="button" onClick={onClick} className="inline-flex items-center gap-1 hover:text-foreground">
        {label}
        {active ? (
          dir === 'asc' ? (
            <ArrowUp className="h-3 w-3" aria-hidden />
          ) : (
            <ArrowDown className="h-3 w-3" aria-hidden />
          )
        ) : (
          <ChevronsUpDown className="h-3 w-3 opacity-50" aria-hidden />
        )}
      </button>
    </th>
  );
}

function ObligationRow({
  o,
  d,
  contractId,
}: {
  o: Obligation;
  d: DerivedStatus;
  contractId: string;
}) {
  const heading = [o.action, o.object].filter(Boolean).join(' ') || o.text;
  return (
    <tr className="align-top hover:bg-muted/20">
      <td className="max-w-[320px] px-3 py-2.5">
        <span className="line-clamp-2" title={o.text}>
          {heading}
        </span>
      </td>
      <td className="px-3 py-2.5">{o.subject ?? '—'}</td>
      <td className="px-3 py-2.5">{o.counterparty ?? '—'}</td>
      <td className="max-w-[220px] px-3 py-2.5">
        <span className="line-clamp-2 text-muted-foreground" title={o.condition ?? undefined}>
          {o.condition ?? '—'}
        </span>
      </td>
      <td className="whitespace-nowrap px-3 py-2.5">
        {d.date ? (
          <span>{o.deadline_date?.slice(0, 10)}</span>
        ) : o.deadline_expression ? (
          <span className="text-muted-foreground">{o.deadline_expression}</span>
        ) : (
          '—'
        )}
      </td>
      <td className="px-3 py-2.5">{o.frequency ?? '—'}</td>
      <td className="px-3 py-2.5">
        <Badge variant="secondary" className={cn('capitalize', typeTint(o.obligation_type))}>
          {TYPE_LABEL[o.obligation_type] ?? o.obligation_type}
        </Badge>
      </td>
      <td className="px-3 py-2.5">
        <Link
          href={`/contracts/${contractId}/review#clause-${o.clause_id}`}
          className="break-all text-xs text-primary underline-offset-2 hover:underline"
          title={o.clause_id}
        >
          {shortClause(o.clause_id)}
        </Link>
      </td>
      <td className="px-3 py-2.5">
        <span
          className={cn(
            'inline-flex items-center rounded-none border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide whitespace-nowrap',
            OBLIGATION_STATUS_STYLE[d.status]
          )}
        >
          {d.status}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-12 overflow-hidden bg-muted">
            <div
              className="h-full bg-primary/70"
              style={{ width: `${Math.round(Math.max(0, Math.min(1, o.confidence)) * 100)}%` }}
            />
          </div>
          <span className="tabular-nums text-xs text-muted-foreground">
            {Math.round(o.confidence * 100)}%
          </span>
        </div>
      </td>
    </tr>
  );
}

function typeTint(t: ObligationType): string {
  switch (t) {
    case 'prohibition':
      return 'border-risk-high/40 bg-risk-high/10 text-risk-high';
    case 'right':
      return 'border-primary/30 bg-primary/10 text-primary';
    case 'condition':
      return 'border-risk-medium/40 bg-risk-medium/10 text-risk-medium';
    default:
      return 'border-border bg-muted/40';
  }
}

function shortClause(clauseId: string): string {
  const m = clauseId.match(/c(\d+)$/);
  return m ? `clause ${m[1]}` : clauseId;
}
