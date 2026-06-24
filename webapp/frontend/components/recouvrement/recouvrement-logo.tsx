import { Banknote } from "lucide-react";

import { cn } from "@/lib/cn";

/**
 * The recouvrement console's OWN logo — a distinct product identity, not the
 * Tessera control-plane lockup. A rounded badge carrying the agent's glyph
 * (Banknote, from the shared agent-icon system) + the wordmark and an "interne"
 * tagline. The label/tagline are passed in so they stay localized.
 */
export function RecouvrementLogo({
  label,
  tagline,
  className,
}: {
  label: string;
  tagline?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 items-center gap-2.5", className)}>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-400">
        <Banknote className="h-5 w-5" aria-hidden="true" />
      </span>
      <span className="flex min-w-0 flex-col leading-tight">
        <span className="truncate font-semibold text-sm tracking-tight text-[var(--tessera-text)]">
          {label}
        </span>
        {tagline ? (
          <span className="truncate text-[0.6rem] font-medium uppercase tracking-wider text-[var(--tessera-text-muted)]">
            {tagline}
          </span>
        ) : null}
      </span>
    </div>
  );
}
