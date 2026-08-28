"use client";

import { CalendarClock, ChevronDown, Clock3 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { CalendarPopover, dateInputValue } from "@/components/cockpit/calendar-popover";
import { CHIP_ACTIVE, CHIP_BASE, CHIP_NEUTRAL } from "@/components/cockpit/rail-chip";
import { cn } from "@/lib/cn";

/**
 * "Voir à date / État au" — the premium point-in-time picker chip shared by the
 * AGIR (§6) and AT-01 rails. A `datetime-local` input pops the OS-drawn calendar,
 * a foreign white panel that can't be themed to the lacquered strip — so date
 * picking goes through the SAME CalendarPopover as SR-01 (the calendar never
 * drifts between surfaces), with a compact time field in the same popover. The
 * chip is champagne while an instant is active, neutral glass in live.
 */
export function AsOfPickerChip({
  value,
  onChange,
  minDate,
}: {
  /** The active instant (UTC ISO) — null in live. */
  value: string | null;
  /** Receives the new instant (UTC ISO), or null to return to live. */
  onChange: (iso: string | null) => void;
  /** Earliest day with real data; earlier days render disabled. */
  minDate?: Date;
}) {
  const t = useTranslations("overview.time");
  const ta = useTranslations("agirRail");
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  // Time-of-day (HH:MM local) applied to picked days. Seeded end-of-day — an
  // as-of reading covers the whole chosen day until refined — and re-synced from
  // the active instant so reopening always shows the true T.
  const [time, setTime] = useState("23:59");
  useEffect(() => {
    if (!value) return;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return;
    const pad = (n: number) => String(n).padStart(2, "0");
    setTime(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
  }, [value]);

  useEffect(() => {
    if (!open) return;
    function closeOnOutsidePointer(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const active = value ? new Date(value) : null;

  /** Combine a local day + HH:MM into the instant; the future clamps to now. */
  const apply = (day: string, hm: string) => {
    const [h = 23, m = 59] = hm.split(":").map((p) => Number.parseInt(p, 10));
    const [y = 1970, mo = 1, d = 1] = day.split("-").map((p) => Number.parseInt(p, 10));
    let instant = new Date(y, mo - 1, d, h, m, 0, 0);
    if (Number.isNaN(instant.getTime())) return;
    if (instant.getTime() > Date.now()) instant = new Date();
    onChange(instant.toISOString());
  };

  const chipText = active
    ? active.toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : null;

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ta("pickLabel")}
        title={active ? t("changeInstant") : t("goToInstant")}
        className={cn(CHIP_BASE, active ? CHIP_ACTIVE : CHIP_NEUTRAL)}
      >
        <CalendarClock className="h-3.5 w-3.5 shrink-0 text-gold-600 dark:text-gold-400" />
        {active ? t("asofAt") : ta("pickLabel")}
        {chipText ? (
          <b className="font-semibold tabular-nums text-[var(--tessera-text)]">{chipText}</b>
        ) : null}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gold-600/70 dark:text-gold-400/70" />
      </button>
      {open ? (
        // biome-ignore lint/a11y/useSemanticElements: anchored rail popover (same shell as GoToDateButton), not a native <dialog> — no modal backdrop semantics
        <div
          role="dialog"
          aria-label={ta("pickLabel")}
          className="sr01-menu absolute left-0 top-[calc(100%+0.5rem)] z-50 w-[292px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] shadow-[0_20px_60px_rgba(0,0,0,0.38)]"
        >
          <CalendarPopover
            selectedDate={active ?? new Date()}
            minDate={minDate}
            // An as-of reading of the future is meaningless — later days disabled.
            maxDate={new Date()}
            onPick={(day) => {
              // Same grammar as SR-01's GoToDateButton: picking the day is the
              // main gesture and closes the popover; retiming reopens it.
              apply(day, time);
              setOpen(false);
            }}
            labels={{ prevMonth: t("prevMonth"), nextMonth: t("nextMonth") }}
            className="w-full border-0 bg-transparent shadow-none"
          />
          <div className="flex items-center justify-between gap-2 border-t border-[var(--tessera-border)] px-3 pb-3 pt-2.5">
            <label className="flex items-center gap-2 text-xs text-[var(--tessera-text-muted)]">
              <Clock3 className="h-3.5 w-3.5" />
              {ta("pickTime")}
              <input
                type="time"
                value={time}
                aria-label={ta("pickTime")}
                onChange={(e) => {
                  const hm = e.target.value;
                  if (!hm) return;
                  setTime(hm);
                  // With an instant active, retiming applies immediately (same day).
                  if (active) apply(dateInputValue(active), hm);
                }}
                className="h-8 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 text-xs text-[var(--tessera-text)] outline-none [color-scheme:dark] focus-visible:ring-2 focus-visible:ring-[rgba(96,194,242,0.35)]"
              />
            </label>
          </div>
        </div>
      ) : null}
    </div>
  );
}
