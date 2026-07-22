"use client";

import { CalendarDays } from "lucide-react";
import { useFormatter } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { CalendarPopover } from "@/components/cockpit/calendar-popover";
import { CHIP_BASE, CHIP_NEUTRAL } from "@/components/cockpit/rail-chip";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";

/**
 * Shared cockpit atom — the canonical top-of-page window picker, lifted verbatim
 * from the Journal d'audit reference (see docs/ui-style-reference.md §3). It reads
 * left → right: label → segmented presets → compact date-range readout → "Aller à
 * une date" with a home-made calendar popover anchored to the right.
 *
 * Generic by design: the caller owns the window state (presets, active period,
 * window bounds, the anchored day) and supplies localized ``labels``; the control
 * only emits ``onPeriod`` / ``onDate`` and renders the calendar.
 *
 * Naming note: this is the *horizontal* picker. The unrelated vertical period
 * selector lives at ``components/observability/period-rail.tsx`` — don't confuse
 * the two.
 */

/** Resolve a ``YYYY-MM-DD`` input to local end-of-day, or null if malformed. */
export function endOfLocalDay(value: string): Date | null {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 23, 59, 59, 999);
}

/** A single segmented-preset option (e.g. ``{ value: "7d", label: "7 jours" }``). */
export interface WindowPreset {
  value: string;
  label: string;
}

/** Localized strings the control needs but cannot derive from Intl. */
export interface WindowControlLabels {
  window: string;
  refresh: string;
  prevMonth: string;
  nextMonth: string;
}

export function WindowControl({
  presets,
  period,
  onPeriod,
  windowStart,
  windowEnd,
  selectedDate,
  onDate,
  loading,
  labels,
  variant = "card",
}: {
  presets: WindowPreset[];
  /** The active preset's ``value``. */
  period: string;
  onPeriod: (value: string) => void;
  /** Window bounds for the compact range readout (null while loading). */
  windowStart: Date | null;
  windowEnd: Date | null;
  /** The day the calendar highlights / opens on — keep this memoized in the caller. */
  selectedDate: Date;
  /** Receives a ``YYYY-MM-DD`` string when a calendar day is picked. */
  onDate: (value: string) => void;
  loading: boolean;
  labels: WindowControlLabels;
  /**
   * "instrument" wears the sr01-strip lacquer (registre §5 v1.8: a temporal rail
   * is visually distinct from content cards). Default "card" keeps the neutral
   * surface for embedded uses (e.g. the app header).
   */
  variant?: "card" | "instrument";
}) {
  const formatter = useFormatter();
  const pickerRef = useRef<HTMLDivElement>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (!pickerOpen) return;

    function closeOnOutsidePointer(event: MouseEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) setPickerOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setPickerOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [pickerOpen]);

  return (
    <section
      className={cn(
        "flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 px-4 py-2",
        variant === "instrument"
          ? "sr01-strip rounded-2xl backdrop-blur-md"
          : "rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]",
      )}
    >
      <span className="min-w-16 text-xs font-medium text-[var(--tessera-text-muted)]">
        {labels.window}
      </span>
      {/* Rail grammar (rail-chip): glass surfaces, the ACTIVE preset in champagne
          — the chosen window is a chosen reading, never a status colour. No
          heartbeat here: this window is anchored at mint (a frozen `until`), so
          a beating "live" dot would claim a present the page does not follow. */}
      <div className="flex h-9 rounded-lg border border-[rgba(96,194,242,0.26)] bg-[rgba(96,194,242,0.05)] p-1 shadow-[inset_0_1px_0_rgba(160,220,250,0.09)]">
        {presets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => onPeriod(preset.value)}
            className={cn(
              "h-7 rounded-md px-3 text-xs font-medium transition-colors",
              period === preset.value
                ? "bg-gold-500/[0.15] text-gold-700 ring-1 ring-gold-500/40 dark:text-gold-200"
                : "text-[var(--tessera-text-muted)] hover:bg-[rgba(96,194,242,0.12)] hover:text-[var(--tessera-text)]",
            )}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="flex h-9 max-w-[520px] shrink-0 items-center gap-3 rounded-lg border border-[rgba(96,194,242,0.26)] bg-[rgba(96,194,242,0.05)] px-3 text-xs text-[var(--tessera-text)] shadow-[inset_0_1px_0_rgba(160,220,250,0.09)]">
        <CalendarDays className="h-4 w-4 shrink-0 text-gold-600 dark:text-gold-400" />
        {loading || !windowStart || !windowEnd ? (
          <Skeleton className="h-4 w-64" />
        ) : (
          <span className="truncate whitespace-nowrap">
            {formatter.dateTime(windowStart, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
            <span className="px-3 text-[var(--tessera-text-muted)]">→</span>
            {formatter.dateTime(windowEnd, {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </span>
        )}
      </div>
      <div ref={pickerRef} className="relative">
        <button
          type="button"
          aria-expanded={pickerOpen}
          onClick={() => setPickerOpen((open) => !open)}
          className={cn(CHIP_BASE, CHIP_NEUTRAL, "cursor-pointer rounded-lg font-medium")}
        >
          <CalendarDays className="h-4 w-4 shrink-0 text-gold-600 dark:text-gold-400" />
          {labels.refresh}
        </button>
        {pickerOpen ? (
          <CalendarPopover
            selectedDate={selectedDate}
            onPick={(value) => {
              onDate(value);
              setPickerOpen(false);
            }}
            labels={{ prevMonth: labels.prevMonth, nextMonth: labels.nextMonth }}
            className="sr01-menu absolute right-0 top-[calc(100%+0.5rem)] z-50"
          />
        ) : null}
      </div>
    </section>
  );
}
