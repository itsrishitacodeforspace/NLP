import { Info } from 'lucide-react';

/**
 * Mandatory product disclaimer. Rendered on every primary surface.
 * Never implies a legal conclusion.
 */
export function Disclaimer() {
  return (
    <p className="flex items-start gap-1.5 rounded-none border-l-2 border-primary/50 bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>
        contract analysis is for informational purposes only and does not
        constitute legal advice. Findings require appropriate human review.
      </span>
    </p>
  );
}
