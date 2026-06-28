"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeftRight,
  CalendarClock,
  ChevronDown,
  ChevronUp,
  Clock3,
  Crosshair,
  Download,
  FileCheck2,
  History,
  RotateCcw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { type ComponentType, useEffect, useState } from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import {
  GoToDateButton,
  TemporalRail,
  useDataRange,
  type useTemporalState,
} from "@/components/overview/temporal-rail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { fetchFleet } from "@/lib/api/client";
import type { TimelineReport } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { exportSnapshot } from "@/lib/evidence-export";

type Temporal = ReturnType<typeof useTemporalState>;
type Reading = Temporal["reading"];

const READING_ICON: Record<Reading, ComponentType<{ className?: string }>> = {
  live: Activity,
  asof: Crosshair,
  historique: History,
};
const PERIODS = ["h24", "d7", "d30"] as const;

/**
 * SR-01 · Signal Scrubber, rendered as ONE premium command bar — the single
 * temporal focus for every SURVEILLER page (registre §4/§8). Collapsed by default
 * (reading · période · agents · comparer + export + a real micro-status line);
 * "Déplier" reveals the scrubber panel. It READS the global shared window and never
 * replays an execution (signals only). The rail code stays internal — the bar shows
 * the human title "Navigation temporelle des signaux".
 */
export function SignalCommandBar({
  temporal,
  timeline,
  sloTarget,
  liveStatus,
}: {
  temporal: Temporal;
  timeline?: TimelineReport;
  sloTarget?: number;
  liveStatus: string;
}) {
  const t = useTranslations("overview.time");
  const ta = useTranslations("overview.actions");
  const [expanded, setExpanded] = useState(false);
  const [compare, setCompare] = useState("target");
  // Real micro-status: a live clock + the count of observed agents (no hardcode).
  const [clock, setClock] = useState("");
  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString(undefined, {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }),
      );
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);
  const fleet = useQuery({
    queryKey: ["fleet-scope-filter"],
    queryFn: ({ signal }) => fetchFleet(signal),
    staleTime: 60_000,
  });
  const nAgents = fleet.data?.agents?.length ?? 0;
  const dataRange = useDataRange();
  const minPickDate = dataRange.data?.start ? new Date(dataRange.data.start) : undefined;

  const reading = temporal.reading;
  const ReadingIcon = READING_ICON[reading];
  const asOfMs = temporal.windowEnd ?? temporal.committedAt ?? null;
  const asOfLabel = temporal.asOf
    ? new Date(temporal.asOf).toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : t("nowLive");

  return (
    <section className="rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)]/75 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] backdrop-blur-sm">
      {/* Collapsed command row — the single temporal focus. */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        {/* Lecture — Live / As-of / Historique, differentiated by ICON. */}
        <SelectChip
          icon={ReadingIcon}
          label={t("reading")}
          value={reading}
          onChange={(v) => temporal.setReading(v as Reading)}
          options={[
            { value: "live", label: t("modeLive") },
            { value: "asof", label: t("modeAsof") },
            { value: "historique", label: t("modeHistory") },
          ]}
          accent
        />
        {/* Période (Live / Historique) OR "État au : T" (As-of). */}
        {reading === "asof" ? (
          <span className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-gold-500/50 bg-gold-500/10 px-3 text-xs text-gold-200">
            <CalendarClock className="h-3.5 w-3.5 shrink-0 text-gold-400" />
            {t("asofAt")}
            <b className="font-semibold tabular-nums text-[var(--tessera-text)]">{asOfLabel}</b>
            <GoToDateButton
              selectedDate={asOfMs ? new Date(asOfMs) : new Date()}
              onPick={temporal.pickDate}
              minDate={minPickDate}
            />
          </span>
        ) : (
          <SelectChip
            icon={Clock3}
            label={t("period")}
            value={temporal.periodKey}
            onChange={temporal.setPeriodKey}
            options={PERIODS.map((p) => ({ value: p, label: t(p) }))}
          />
        )}
        {/* Agents — global scope filter (URL-driven, self-contained chip). */}
        <AgentScopeFilter />
        {/* Comparer à — the baseline lens (meaningful when reading the past). */}
        {reading !== "live" ? (
          <SelectChip
            icon={ArrowLeftRight}
            label={t("compareTo")}
            value={compare}
            onChange={setCompare}
            options={[
              { value: "target", label: t("baselineTarget") },
              { value: "now", label: t("baselineNow") },
              { value: "none", label: t("noBaseline") },
            ]}
          />
        ) : null}
        {/* Déplier / Replier. */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={expanded}
          className="h-9 gap-1.5"
          onClick={() => setExpanded((e) => !e)}
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          {expanded ? t("collapse") : t("expand")}
        </Button>
        {/* Export — scoped to the current (période, asOf). */}
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 gap-2"
            onClick={() => exportSnapshot("export")}
          >
            <Download className="h-4 w-4" />
            {ta("exportReport")}
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-9 gap-2"
            onClick={() => exportSnapshot("evidence")}
          >
            <FileCheck2 className="h-4 w-4" />
            {ta("generateEvidencePack")}
          </Button>
        </div>
      </div>

      {/* Micro-status line — replaces the old full-width rule; real clock + agents. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-[var(--tessera-border)]/60 px-3 py-1.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
        <span className="flex items-center gap-1.5">
          <ReadingIcon className="h-3 w-3 text-gold-400" />
          <span className="font-medium text-[var(--tessera-text)]">
            {reading === "live"
              ? t("descLive")
              : reading === "asof"
                ? t("descAsof")
                : t("descHistorique")}
          </span>
        </span>
        <span aria-hidden>·</span>
        <span className="tabular-nums">{clock}</span>
        <span aria-hidden>·</span>
        <span className="tabular-nums">{t("agentsObserved", { n: nAgents })}</span>
        {reading === "asof" && temporal.asOf ? (
          <span className="ml-auto flex items-center gap-2">
            <Badge tone="gold" className="shrink-0">
              {t("modeAsof")}
            </Badge>
            <span>{t("asofBanner", { time: asOfLabel })}</span>
            <button
              type="button"
              className="whitespace-nowrap font-medium text-blue-300 hover:underline"
              onClick={() => temporal.setReading("live")}
            >
              {t("exitReplay")} →
            </button>
          </span>
        ) : null}
      </div>

      {/* Expanded — human title, mode legend, the scrubber panel, and the only
          place the as-of jump-to-proofs lives (signals, never an execution replay). */}
      {expanded ? (
        <div className="border-t border-[var(--tessera-border)]/60 px-3 pb-3 pt-2">
          <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
            <h3 className="font-sans text-sm font-semibold text-[var(--tessera-text)]">
              {t("navTitle")}
            </h3>
            <p className="text-[0.68rem] text-[var(--tessera-text-muted)]">
              {t("modeLive")} — {t("descLive")} · {t("modeAsof")} — {t("descAsof")} ·{" "}
              {t("modeHistory")} — {t("descHistorique")}
            </p>
          </div>
          <TemporalRail
            embedded
            mode={temporal.mode}
            liveStatus={liveStatus}
            timeline={timeline}
            sloTarget={sloTarget}
            selectedAt={temporal.selectedAt}
            onSelectedAtChange={temporal.setSelectedAt}
            periodKey={temporal.periodKey}
            windowEnd={temporal.windowEnd}
            onModeChange={temporal.changeMode}
            compare={compare}
            onCompareChange={setCompare}
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <GoToDateButton
              selectedDate={asOfMs ? new Date(asOfMs) : new Date()}
              onPick={temporal.pickDate}
              minDate={minPickDate}
            />
            {reading !== "live" ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 gap-2"
                onClick={() => temporal.setReading("live")}
              >
                <RotateCcw className="h-4 w-4" />
                {t("exitReplay")}
              </Button>
            ) : null}
            {temporal.asOf ? (
              <Link
                href={`/prouver/etat-a-date?asof=${encodeURIComponent(temporal.asOf)}`}
                className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] px-3 text-xs font-medium text-blue-300 hover:bg-[var(--tessera-muted)]"
              >
                <CalendarClock className="h-4 w-4" />
                {t("openInProofs")}
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** A compact labeled select styled to match the command bar. */
function SelectChip({
  icon: Icon,
  label,
  value,
  onChange,
  options,
  accent,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  accent?: boolean;
}) {
  return (
    <label
      className={cn(
        "flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border px-3 text-xs",
        accent
          ? "border-gold-500/50 bg-gold-500/10 text-gold-200"
          : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-gold-400" />
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer rounded bg-transparent font-semibold text-[var(--tessera-text)] outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-[var(--tessera-bg)]">
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
