"use client";

import { CalendarDays } from "lucide-react";
import { useFormatter } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { CalendarPopover } from "@/components/cockpit/calendar-popover";
import { Button } from "@/components/ui/button";
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
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="min-w-16 text-xs font-medium text-[var(--tessera-text-muted)]">
        {labels.window}
      </span>
      <div className="flex h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]">
        {presets.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => onPeriod(preset.value)}
            className={cn(
              "h-7 rounded px-3 text-xs font-medium transition-colors",
              period === preset.value
                ? "bg-[#123e6a] text-[#d8eaff] ring-1 ring-[#2e72d2]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="flex h-9 max-w-[520px] shrink-0 items-center gap-3 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]">
        <CalendarDays className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
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
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={pickerOpen}
          onClick={() => setPickerOpen((open) => !open)}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 font-medium text-[var(--tessera-text-muted)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
        >
          <CalendarDays className="h-4 w-4" />
          {labels.refresh}
        </Button>
        {pickerOpen ? (
          <CalendarPopover
            selectedDate={selectedDate}
            onPick={(value) => {
              onDate(value);
              setPickerOpen(false);
            }}
            labels={{ prevMonth: labels.prevMonth, nextMonth: labels.nextMonth }}
            className="absolute right-0 top-[calc(100%+0.5rem)] z-50"
          />
        ) : null}
      </div>
    </section>
  );
}
