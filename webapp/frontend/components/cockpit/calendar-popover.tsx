"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import { cn } from "@/lib/cn";

/**
 * The bare calendar panel — month header + weekday row + day grid — lifted out of
 * the Journal d'audit ``WindowControl`` atom so the same picker can be reused by
 * any caller that owns its own popover shell (open/close, anchoring). The atom and
 * the SR-01 signal scrubber both render this single implementation, so the calendar
 * never drifts between surfaces.
 *
 * The caller positions/opens it; this component owns only the visible month and
 * emits a ``YYYY-MM-DD`` string when a day is picked.
 */

/** Format a ``Date`` as a ``YYYY-MM-DD`` local-day string. */
export function dateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfLocalMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addLocalMonths(date: Date, amount: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function calendarMonthDays(month: Date): Date[] {
  const first = startOfLocalMonth(month);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - mondayOffset);
  return Array.from(
    { length: 42 },
    (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index),
  );
}

function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

export interface CalendarPopoverLabels {
  prevMonth: string;
  nextMonth: string;
}

/** Local-day ordinal (ignores time) for inclusive min/max bound comparisons. */
function dayOrdinal(date: Date): number {
  return date.getFullYear() * 10000 + date.getMonth() * 100 + date.getDate();
}

export function CalendarPopover({
  selectedDate,
  onPick,
  labels,
  className,
  minDate,
  maxDate,
}: {
  /** The day the calendar highlights and opens on. */
  selectedDate: Date;
  /** Receives a ``YYYY-MM-DD`` string when a day is picked. */
  onPick: (value: string) => void;
  labels: CalendarPopoverLabels;
  className?: string;
  /** Earliest selectable day (inclusive); earlier days render disabled. */
  minDate?: Date;
  /** Latest selectable day (inclusive); later days render disabled. */
  maxDate?: Date;
}) {
  const minOrd = minDate ? dayOrdinal(minDate) : null;
  const maxOrd = maxDate ? dayOrdinal(maxDate) : null;
  const locale = useLocale();
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

  return (
    <div
      className={cn(
        "w-[292px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[var(--tessera-text)] shadow-[0_20px_60px_rgba(0,0,0,0.38)]",
        className,
      )}
    >
      <div className="mb-3 flex items-center justify-between border-b border-[var(--tessera-border)] pb-2">
        <button
          type="button"
          aria-label={labels.prevMonth}
          onClick={() => setCalendarMonth((month) => addLocalMonths(month, -1))}
          className="grid h-8 w-8 place-items-center rounded-md border border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <p className="text-sm font-semibold capitalize">{monthFormatter.format(calendarMonth)}</p>
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
          const ord = dayOrdinal(day);
          const outOfRange = (minOrd != null && ord < minOrd) || (maxOrd != null && ord > maxOrd);
          return (
            <button
              key={dateInputValue(day)}
              type="button"
              disabled={outOfRange}
              aria-label={dayFormatter.format(day)}
              onClick={() => onPick(dateInputValue(day))}
              className={cn(
                "h-8 rounded-md text-xs font-medium transition-colors",
                selected
                  ? "bg-[#123e6a] text-[#d8eaff] ring-1 ring-[#2e72d2]"
                  : "text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]",
                !inMonth && "text-[var(--tessera-text-muted)] opacity-45",
                outOfRange && "cursor-not-allowed opacity-25 hover:bg-transparent",
              )}
            >
              {day.getDate()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
