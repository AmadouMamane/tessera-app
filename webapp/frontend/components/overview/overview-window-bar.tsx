"use client";

import { useTranslations } from "next-intl";
import { useMemo } from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { WindowControl, endOfLocalDay } from "@/components/cockpit/window-control";
import { useWindowStore } from "@/lib/stores/window-store";

/** Window DURATION presets (ms), spanning backwards from the window end. */
const PRESET_MS: Record<string, number> = {
  h24: 24 * 3_600_000,
  d7: 7 * 24 * 3_600_000,
  d30: 30 * 24 * 3_600_000,
  d90: 90 * 24 * 3_600_000,
};

/**
 * The overview's single window owner (CONTRAT RAIL): the proven `WindowControl`
 * atom (presets + "Aller à une date" calendar) bound to the shared `useWindowStore`,
 * plus the agent filter — the two view filters in one top bar. The rail READS this
 * window (period + anchorEnd) and only navigates within it (scrub) — it owns nothing.
 *
 * Model: the calendar picks the window END (absolute day → end-of-day, or "now"
 * when today/future); the preset is the DURATION. So "7 j ending 3 March". This
 * lets the window travel over a long production history; the rail follows.
 */
export function OverviewWindowBar() {
  const t = useTranslations("overview");
  const period = useWindowStore((s) => s.period);
  const setPeriod = useWindowStore((s) => s.setPeriod);
  const anchorEnd = useWindowStore((s) => s.anchorEnd);
  const setAnchorEnd = useWindowStore((s) => s.setAnchorEnd);

  const presets = useMemo(
    () => [
      { value: "h24", label: t("context.lifecycle24h") },
      { value: "d7", label: t("context.lifecycleValue") },
      { value: "d30", label: t("context.lifecycle30d") },
      { value: "d90", label: t("context.lifecycle90d") },
    ],
    [t],
  );

  const windowEnd = anchorEnd ? new Date(anchorEnd) : new Date();
  const spanMs = PRESET_MS[period] ?? 7 * 24 * 3_600_000;
  const windowStart = new Date(windowEnd.getTime() - spanMs);

  function onDate(value: string) {
    const eod = endOfLocalDay(value);
    if (!eod) return;
    // A day at/after today means "now" → keep the page live (anchor cleared).
    setAnchorEnd(eod.getTime() >= Date.now() ? null : eod.toISOString());
  }

  return (
    <div className="mb-3 flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1">
        <WindowControl
          presets={presets}
          period={period}
          onPeriod={setPeriod}
          windowStart={windowStart}
          windowEnd={windowEnd}
          selectedDate={windowEnd}
          onDate={onDate}
          loading={false}
          labels={{
            window: t("context.lifecycle"),
            refresh: t("window.goToDate"),
            prevMonth: t("window.prevMonth"),
            nextMonth: t("window.nextMonth"),
          }}
        />
      </div>
      <AgentScopeFilter />
    </div>
  );
}
