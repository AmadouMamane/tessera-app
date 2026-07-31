"use client";

import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

/**
 * Shared cockpit atoms — the canonical "premium" KPI tile, extracted from the
 * Journal d'audit reference (see docs/ui-style-reference.md). Reuse these on every
 * cockpit page so the look reproduces mechanically instead of being re-implemented.
 */

/** Period-over-period delta badge: "+X.X%", green when good, red when not. */
export function DeltaBadge({
  deltaPct,
  goodIsUp = true,
  noneLabel,
}: {
  deltaPct: number | null;
  /** Whether an upward change is the good direction (false for error rate, cost…). */
  goodIsUp?: boolean;
  /** Text shown when there is no previous period to compare against. */
  noneLabel: string;
}) {
  if (deltaPct == null) {
    return <span className="text-xs text-[var(--tessera-text-muted)]">{noneLabel}</span>;
  }
  const up = deltaPct >= 0;
  const good = up === goodIsUp;
  return (
    <span
      className={cn(
        "text-xs font-medium",
        good ? "text-[var(--tessera-green)]" : "text-[var(--tessera-fg-danger)]",
      )}
    >
      {up ? "+" : ""}
      {deltaPct.toFixed(1)}%
    </span>
  );
}

/**
 * Fixed-height (108px) KPI card with no layout shift: the box owns the heights and
 * skeletons; the caller supplies the content (value, delta badge, trend row). While
 * ``loading`` the value and trend rows show skeletons that mirror the final boxes —
 * so the page never "dances" as data arrives.
 */
export function MetricCard({
  label,
  value,
  delta,
  trend,
  info,
  loading = false,
}: {
  label: string;
  value: ReactNode;
  /** Usually a <DeltaBadge />; sits next to the value. */
  delta?: ReactNode;
  /** The bottom row: a sparkline, a status hint, anything fixed at h-5. */
  trend?: ReactNode;
  /** Optional <MetricInfo/> — a ⓘ explaining what the metric is / how computed. */
  info?: ReactNode;
  loading?: boolean;
}) {
  return (
    <section className="h-[108px] overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 font-medium text-[var(--tessera-text-muted)] text-xs">
        {label}
        {info}
      </p>
      {loading ? (
        <div className="mt-1 flex h-8 items-baseline gap-2">
          <Skeleton className="h-7 w-16" />
          <Skeleton className="h-4 w-12" />
        </div>
      ) : (
        <div className="mt-1 flex h-8 items-baseline gap-2">
          <p className="text-[1.55rem] font-semibold leading-none text-[var(--tessera-text-strong)]">
            {value}
          </p>
          {delta}
        </div>
      )}
      <div className="mt-1.5 h-7 border-t border-[var(--tessera-border)] pt-1.5">
        {loading ? <Skeleton className="h-5 w-full" /> : trend}
      </div>
    </section>
  );
}
