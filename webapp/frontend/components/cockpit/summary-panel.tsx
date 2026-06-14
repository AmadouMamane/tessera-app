"use client";

import type { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

/**
 * Shared cockpit atoms (see docs/ui-style-reference.md): the fixed-height bottom
 * summary card and the ranked count list, lifted from the audit reference so every
 * page reuses them instead of re-implementing.
 */

/** Fixed-height (142px) summary card with a title and a scroll-clipped body. */
export function SummaryPanel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex h-[142px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h2 className="shrink-0 font-sans text-sm font-semibold text-[var(--tessera-text)]">
        {title}
      </h2>
      <div className="mt-2 min-h-0 flex-1 overflow-hidden pb-1">{children}</div>
    </section>
  );
}

/** Top-N ranked list with a proportional bar per row (skeleton while loading). */
export function CountList({
  items,
  loading,
  danger,
}: {
  items: { key: string; count: number }[];
  loading: boolean;
  danger?: boolean;
}) {
  if (loading) return <Skeleton className="h-24 w-full" />;
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <ol className="space-y-1 pb-1">
      {items.slice(0, 3).map((item, index) => (
        <li
          key={`${item.key}-${index}`}
          className="grid grid-cols-[1rem_minmax(0,1fr)_auto] items-center gap-2 text-[0.72rem] leading-tight"
        >
          <span className="font-mono text-[var(--tessera-text-muted)]">{index + 1}</span>
          <div className="min-w-0">
            <p className="truncate text-[var(--tessera-text)]">{item.key}</p>
            <div className="mt-0.5 h-1.5 rounded-full bg-[var(--tessera-bg)]">
              <div
                className={cn("h-full rounded-full", danger ? "bg-red-400" : "bg-[#2e72d2]")}
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
          </div>
          <span className="font-mono text-[var(--tessera-text-muted)]">{item.count}</span>
        </li>
      ))}
    </ol>
  );
}
