"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { useFormatter, useLocale } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

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

export function dateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function startOfLocalMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function addLocalMonths(date: Date, amount: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

export function calendarMonthDays(month: Date): Date[] {
  const first = startOfLocalMonth(month);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - mondayOffset);
  return Array.from(
    { length: 42 },
    (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index),
  );
}

export function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
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
  const locale = useLocale();
  const pickerRef = useRef<HTMLDivElement>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => startOfLocalMonth(selectedDate));
  const monthDays = useMemo(() => calendarMonthDays(calendarMonth), [calendarMonth]);
  const monthFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }),
    [locale],
  );
  const dayFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: "full" }),
    [locale],
  );
  const weekdayLabels = useMemo(() => {
    const monday = new Date(2026, 5, 1);
    const weekdayFormatter = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
    return Array.from({ length: 7 }, (_, index) => {
      const day = new Date(2026, 5, monday.getDate() + index);
      return { key: dateInputValue(day), label: weekdayFormatter.format(day) };
    });
  }, [locale]);

  useEffect(() => {
    if (pickerOpen) setCalendarMonth(startOfLocalMonth(selectedDate));
  }, [pickerOpen, selectedDate]);

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
          <div className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-[292px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[var(--tessera-text)] shadow-[0_20px_60px_rgba(0,0,0,0.38)]">
            <div className="mb-3 flex items-center justify-between border-b border-[var(--tessera-border)] pb-2">
              <button
                type="button"
                aria-label={labels.prevMonth}
                onClick={() => setCalendarMonth((month) => addLocalMonths(month, -1))}
                className="grid h-8 w-8 place-items-center rounded-md border border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <p className="text-sm font-semibold capitalize">
                {monthFormatter.format(calendarMonth)}
              </p>
              <button
                type="button"
                aria-label={labels.nextMonth}
                onClick={() => setCalendarMonth((month) => addLocalMonths(month, 1))}
                className="grid h-8 w-8 place-items-center rounded-md border border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-7 gap-1 text-center text-[0.68rem] font-medium uppercase text-[var(--tessera-text-muted)]">
              {weekdayLabels.map((day) => (
                <span key={day.key}>{day.label}</span>
              ))}
            </div>
            <div className="mt-2 grid grid-cols-7 gap-1">
              {monthDays.map((day) => {
                const inMonth = day.getMonth() === calendarMonth.getMonth();
                const selected = isSameLocalDate(day, selectedDate);
                return (
                  <button
                    key={dateInputValue(day)}
                    type="button"
                    aria-label={dayFormatter.format(day)}
                    onClick={() => {
                      onDate(dateInputValue(day));
                      setPickerOpen(false);
                    }}
                    className={cn(
                      "h-8 rounded-md text-xs font-medium transition-colors",
                      selected
                        ? "bg-[#123e6a] text-[#d8eaff] ring-1 ring-[#2e72d2]"
                        : "text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]",
                      !inMonth && "text-[var(--tessera-text-muted)] opacity-45",
                    )}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
