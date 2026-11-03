/**
 * EmptyState / ErrorState / LoadingState — presentational state components.
 */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/state';

describe('EmptyState', () => {
  it('renders title and description', () => {
    render(<EmptyState title="No results" description="Try a different filter." />);
    expect(screen.getByRole('heading', { name: 'No results' })).toBeInTheDocument();
    expect(screen.getByText('Try a different filter.')).toBeInTheDocument();
  });

  it('renders an optional action slot', () => {
    render(<EmptyState title="Empty" action={<button type="button">Load sample</button>} />);
    expect(screen.getByRole('button', { name: 'Load sample' })).toBeInTheDocument();
  });
});

describe('ErrorState', () => {
  it('renders a default title and the description', () => {
    render(<ErrorState description="The backend is unreachable." />);
    expect(screen.getByRole('heading', { name: 'Something went wrong' })).toBeInTheDocument();
    expect(screen.getByText('The backend is unreachable.')).toBeInTheDocument();
  });

  it('accepts a custom title', () => {
    render(<ErrorState title="Upload failed" description="File too large (413)." />);
    expect(screen.getByRole('heading', { name: 'Upload failed' })).toBeInTheDocument();
  });
});

describe('LoadingState', () => {
  it('renders the label with a status role for screen readers', () => {
    render(<LoadingState label="Loading recent contracts…" />);
    expect(screen.getByText('Loading recent contracts…')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
