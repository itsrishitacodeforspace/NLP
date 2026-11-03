import { Info } from 'lucide-react';

/**
 * Mandatory product disclaimer. Rendered on every primary surface.
 * Never implies a legal conclusion.
 */
export function Disclaimer() {
  return (
    <p className="flex items-start gap-1.5 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>
        AI-generated contract analysis is for informational purposes only and does not
        constitute legal advice. Findings require appropriate human review.
      </span>
    </p>
  );
}
