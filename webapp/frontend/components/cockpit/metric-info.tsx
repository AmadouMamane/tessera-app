"use client";

import * as Popover from "@radix-ui/react-popover";
import { Info } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * MetricInfo — the canonical "what does this number mean?" affordance.
 *
 * A discreet ⓘ button next to a metric/section title that opens a popover
 * explaining, in plain language: what the metric IS, how it is COMPUTED, and
 * where the data comes FROM. Reuse it on every cockpit card so a first-time
 * operator can read any KPI ("Score qualité", "Contrôles en échec", "Preuves
 * d'audit"…) without guessing.
 *
 * Click/keyboard (not hover) so the richer text stays readable and touch works;
 * `stopPropagation` so opening it never triggers an enclosing card's navigation.
 */
export interface MetricInfoProps {
  /** The metric/section name, shown as the popover heading. */
  title: string;
  /** Plain-language definition: what this number represents. */
  what: ReactNode;
  /** Optional: how it is computed (formula / aggregation / threshold). */
  how?: ReactNode;
  /** Optional: where the underlying data comes from (the real source). */
  source?: ReactNode;
  className?: string;
}

export function MetricInfo({ title, what, how, source, className }: MetricInfoProps) {
  const t = useTranslations("metricInfo");
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={t("about", { name: title })}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            "inline-flex h-4 w-4 shrink-0 cursor-help items-center justify-center rounded-full text-[var(--tessera-text-muted)] outline-none transition-colors hover:text-[var(--tessera-text)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            className,
          )}
        >
          <Info className="h-3.5 w-3.5" aria-hidden />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={6}
          collisionPadding={12}
          onClick={(e) => e.stopPropagation()}
          className={cn(
            "z-50 w-72 rounded-xs border border-[var(--tessera-tooltip-border)] bg-[var(--tessera-tooltip-bg)] p-3 text-left shadow-[0_2px_6px_rgba(0,0,0,0.4)]",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          )}
        >
          <p className="font-semibold text-[var(--tessera-tooltip-fg)] text-xs">{title}</p>
          <p className="mt-1 text-[0.72rem] leading-relaxed text-[var(--tessera-tooltip-fg-muted)]">
            {what}
          </p>
          {how ? (
            <div className="mt-2 border-[var(--tessera-tooltip-border)] border-t pt-2">
              <p className="font-medium text-[0.66rem] text-[var(--tessera-tooltip-fg-muted)] uppercase tracking-wide">
                {t("calcul")}
              </p>
              <p className="mt-0.5 text-[0.72rem] leading-relaxed text-[var(--tessera-tooltip-fg-muted)]">
                {how}
              </p>
            </div>
          ) : null}
          {source ? (
            <div className="mt-2 border-[var(--tessera-tooltip-border)] border-t pt-2">
              <p className="font-medium text-[0.66rem] text-[var(--tessera-tooltip-fg-muted)] uppercase tracking-wide">
                {t("source")}
              </p>
              <p className="mt-0.5 text-[0.72rem] leading-relaxed text-[var(--tessera-tooltip-fg-muted)]">
                {source}
              </p>
            </div>
          ) : null}
          <Popover.Arrow className="fill-[var(--tessera-tooltip-border)]" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
