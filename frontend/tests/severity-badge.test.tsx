/**
 * SeverityBadge / SourceBadge / RiskGauge rendering.
 * NOTE: these are presentational — rendered without providers.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge, SourceBadge, RiskGauge } from '@/components/risks/badges';

describe('SeverityBadge', () => {
  it.each([
    ['critical', 'Critical'],
    ['high', 'High'],
    ['medium', 'Medium'],
    ['low', 'Low'],
  ] as const)('renders the label for %s', (severity, label) => {
    render(<SeverityBadge severity={severity} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('renders "Informational" for unknown severities', () => {
    render(<SeverityBadge severity="wat" />);
    expect(screen.getByText('Informational')).toBeInTheDocument();
  });
});

describe('SourceBadge', () => {
  it('shows "Rule" for rule-based findings', () => {
    render(<SourceBadge source="rule" evidenceStatus="direct" />);
    expect(screen.getByText('Rule')).toBeInTheDocument();
    expect(screen.queryByText(/unverified/)).not.toBeInTheDocument();
  });

  it('shows "ML" for model-supported findings', () => {
    render(<SourceBadge source="model" evidenceStatus="direct" />);
    expect(screen.getByText('ML')).toBeInTheDocument();
    expect(screen.queryByText('Rule')).not.toBeInTheDocument();
  });

  it.each(['unverified', 'unavailable', 'contextual'] as const)(
    'shows the unverified cue when evidence_status=%s',
    (status) => {
      render(<SourceBadge source="rule" evidenceStatus={status} />);
      expect(screen.getByText(/unverified/)).toBeInTheDocument();
    }
  );

  it('does not show the unverified cue for direct evidence', () => {
    render(<SourceBadge source="model" evidenceStatus="direct" />);
    expect(screen.queryByText(/unverified/)).not.toBeInTheDocument();
  });
});

describe('RiskGauge', () => {
  it('exposes an accessible label with score and level on the svg', () => {
    render(<RiskGauge score={42} level="medium" />);
    const svg = screen.getByRole('img', { name: /Risk score 42 of 100, Medium/i });
    expect(svg).toBeInTheDocument();
  });

  it('renders the score number', () => {
    render(<RiskGauge score={87} level="high" />);
    expect(screen.getByText('87')).toBeInTheDocument();
  });
});
