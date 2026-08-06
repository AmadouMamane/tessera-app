import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

/**
 * ZoneBand — the translucent banded section grouping one cockpit zone.
 *
 * Extracted from the Qualité IA dashboard (where it matched the Sécurité & privacy page) so the
 * observability page can speak the same sectioning language: a labelled band holding real
 * sub-cards, the heading carrying an icon + label. No "A./B." numbering — that read as a
 * worksheet, not a dashboard.
 */
export function ZoneBand({
  label,
  icon: Icon,
  iconClassName = "text-[var(--tessera-green)]",
  info,
  children,
}: {
  label: string;
  icon: LucideIcon;
  /** Per-zone accent so each band's icon reads as its own facet. */
  iconClassName?: string;
  /** Optional ⓘ explainer rendered next to the band label. */
  info?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      data-slot="card"
      className="min-w-0 rounded-xl border border-[var(--tessera-border)]/50 bg-[var(--tessera-surface)]/25 p-2.5"
    >
      <h2 className="mt-0.5 mb-1.5 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        <Icon className={`h-3.5 w-3.5 shrink-0 ${iconClassName}`} />
        {label}
        {info}
      </h2>
      <div className="flex min-w-0 flex-col gap-2.5">{children}</div>
    </section>
  );
}
