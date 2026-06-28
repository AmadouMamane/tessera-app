"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeftRight,
  CalendarClock,
  Check,
  ChevronDown,
  ChevronUp,
  Clock3,
  Crosshair,
  History,
  RotateCcw,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { type ComponentType, type ReactNode, Suspense, useEffect, useRef, useState } from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import {
  GoToDateButton,
  TemporalRail,
  useDataRange,
  type useTemporalState,
} from "@/components/overview/temporal-rail";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, isScopedToAgent, parseAgentScope } from "@/lib/agent-scope";
import { fetchFleet } from "@/lib/api/client";
import type { TimelineReport } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Temporal = ReturnType<typeof useTemporalState>;
type Reading = Temporal["reading"];
type Translate = ReturnType<typeof useTranslations>;

const READING_ICON: Record<Reading, ComponentType<{ className?: string }>> = {
  live: Activity,
  asof: Crosshair,
  historique: History,
};
const PERIODS = ["h24", "d7", "d30"] as const;
const PERIOD_MS: Record<string, number> = {
  h24: 24 * 3600_000,
  d7: 7 * 24 * 3600_000,
  d30: 30 * 24 * 3600_000,
};

// "Comparer à" — visible options per reading (registre §5). Order is defaults-first;
// the omitted ones are hidden because they make no sense for that reading ("now" vs
// now, or a previous-period frame on a single instant). Internal values stay stable.
const COMPARE_ORDER: Record<Reading, string[]> = {
  live: ["target", "previous_period", "baseline", "previous_release", "none"],
  asof: ["now", "target", "baseline", "previous_release", "none"],
  historique: ["previous_period", "target", "baseline", "previous_release", "none"],
};

/** Whether a comparison reference is REALLY computable in the current reading/scope. */
function compareEnabled(reading: Reading, value: string, avail: { target: boolean; now: boolean }) {
  if (value === "none") return true;
  if (value === "target") return avail.target;
  if (value === "now") return reading === "asof" && avail.now;
  // previous_period / baseline / previous_release have no real data source here →
  // never computable (real-or-honest-empty; shown disabled with a reason, never faked).
  return false;
}

/** The reading's preferred default, falling back to the first computable reference. */
function defaultCompare(reading: Reading, avail: { target: boolean; now: boolean }) {
  const pref = reading === "live" ? "target" : reading === "asof" ? "now" : "previous_period";
  if (compareEnabled(reading, pref, avail)) return pref;
  // "À un instant": the whole point of the view is the state at T vs now, so
  // "Maintenant" stays the natural default EVEN when it is not currently computable —
  // it is then shown disabled with a reason, never silently downgraded to "Aucun".
  if (reading === "asof") return "now";
  if (avail.target) return "target";
  return "none";
}

function compareLabel(value: string, t: Translate): string {
  switch (value) {
    case "target":
      return t("cmpTarget");
    case "previous_period":
      return t("cmpPrevPeriod");
    case "baseline":
      return t("cmpBaseline");
    case "previous_release":
      return t("cmpPrevRelease");
    case "now":
      return t("cmpNow");
    default:
      return t("cmpNone");
  }
}

function compareReason(value: string, t: Translate): string {
  switch (value) {
    case "target":
      return t("reasonNoTarget");
    case "now":
      return t("reasonNotComparable");
    case "previous_period":
      return t("reasonNoPrevPeriod");
    case "baseline":
      return t("reasonNoBaseline");
    case "previous_release":
      return t("reasonNoPrevRelease");
    default:
      return "";
  }
}

/** Build the "Comparer à" options: computable ones plain, the rest disabled + reason. */
function buildCompareOptions(
  reading: Reading,
  avail: { target: boolean; now: boolean },
  t: Translate,
): { value: string; label: string; disabled?: boolean }[] {
  return COMPARE_ORDER[reading].map((value) => {
    if (compareEnabled(reading, value, avail)) return { value, label: compareLabel(value, t) };
    return {
      value,
      label: `${compareLabel(value, t)} — ${compareReason(value, t)}`,
      disabled: true,
    };
  });
}

/**
 * SR-01 · Signal Scrubber, rendered as ONE premium command bar — the single
 * temporal focus for every SURVEILLER page (registre §4/§8). Collapsed by default
 * (Lecture · Période/État au · Agents · Comparer à + export + a contextual micro-
 * status line); "Déplier" reveals the scrubber panel. It READS the global shared
 * window and never replays an execution (signals only). The reading labels are
 * human — Maintenant / À un instant / Historique — never the internal "asOf".
 */
export function SignalCommandBar({
  temporal,
  timeline,
  sloTarget,
  hasPresentScore = false,
  liveStatus,
}: {
  temporal: Temporal;
  timeline?: TimelineReport;
  sloTarget?: number;
  /** True when a present quality score exists, so the "Maintenant" baseline is real. */
  hasPresentScore?: boolean;
  liveStatus: string;
}) {
  const t = useTranslations("overview.time");
  // Reading, panel-open and the comparison lens all live in the shared temporal
  // state (URL-backed source of truth) — not private to the bar.
  const { reading, compare, setCompare, expanded, setExpanded } = temporal;
  // The panel clips with overflow-hidden while it animates (height transition),
  // then switches to overflow-visible once open so the "Aller à une date" calendar
  // popover is NOT clipped. Reset to clipped the moment it starts collapsing.
  const [panelOverflow, setPanelOverflow] = useState(false);
  useEffect(() => {
    if (!expanded) setPanelOverflow(false);
  }, [expanded]);

  const targetAvail = sloTarget != null;
  const nowAvail = hasPresentScore;
  // "À un instant" needs a chosen day before any comparison is meaningful — there
  // is no instant to compare against the present yet (registre §12). Until then the
  // "Comparer à" control is shown disabled with a reason, never a phantom default.
  const hasInstant = reading === "asof" ? temporal.asOf != null : true;
  const compareOptions = buildCompareOptions(reading, { target: targetAvail, now: nowAvail }, t);
  // Keep the active comparison honest: if it is hidden for this reading or not
  // computable, fall back to the reading's default (never a phantom comparison).
  // Skipped while awaiting an instant (the control is disabled, value irrelevant).
  useEffect(() => {
    if (reading === "asof" && !hasInstant) return;
    const visible = COMPARE_ORDER[reading].includes(compare);
    if (!visible || !compareEnabled(reading, compare, { target: targetAvail, now: nowAvail })) {
      setCompare(defaultCompare(reading, { target: targetAvail, now: nowAvail }));
    }
  }, [reading, hasInstant, targetAvail, nowAvail, compare, setCompare]);

  const fleet = useQuery({
    queryKey: ["fleet-scope-filter"],
    queryFn: ({ signal }) => fetchFleet(signal),
    staleTime: 60_000,
  });
  const fleetCount = fleet.data?.agents?.length ?? 0;
  const dataRange = useDataRange();
  const minPickDate = dataRange.data?.start ? new Date(dataRange.data.start) : undefined;

  // Switching to À un instant / Historique auto-opens the scrubber (registre §4);
  // returning to Maintenant leaves the panel as the user left it (no forced close).
  const prevReading = useRef(reading);
  useEffect(() => {
    if (prevReading.current === "live" && reading !== "live") setExpanded(true);
    prevReading.current = reading;
  }, [reading, setExpanded]);

  const asOfMs = temporal.windowEnd ?? temporal.committedAt ?? null;
  // The chosen instant T, formatted (date + time) — used by the chip, the micro-line
  // and the Vue badge. Empty in "À un instant" before a date is picked.
  const asOfText = temporal.asOf
    ? new Date(temporal.asOf).toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : null;

  // Real "last update" for the live micro-line: the most recent data instant
  // (timeline window end), not a wall clock. null on SSR / before data → omitted.
  const lastUpdate =
    reading === "live" && timeline?.window_end
      ? new Date(timeline.window_end).toLocaleTimeString(undefined, {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        })
      : null;

  // History window bounds (real, derived from the timeline end + period). null on
  // SSR / before data (so no Date.now() in render → no hydration mismatch).
  const histEndMs = timeline?.window_end ? new Date(timeline.window_end).getTime() : null;
  const histStartMs =
    histEndMs != null ? histEndMs - (PERIOD_MS[temporal.periodKey] ?? 7 * 24 * 3600_000) : null;
  const fromText = histStartMs != null ? fmtDay(histStartMs) : null;
  const toText = histEndMs != null ? fmtDay(histEndMs) : null;

  // Mode-specific "Vue" badge — never duplicates "Lecture", never a single instant
  // in Historique (registre §D).
  const viewLabel =
    reading === "live"
      ? t("vueNow")
      : reading === "asof"
        ? asOfText
          ? t("microStateAt", { time: asOfText })
          : t("vueNoInstant")
        : fromText && toText
          ? t("vuePeriod", { from: fromText, to: toText })
          : t("modeHistory");

  // Contextual micro-line — describes ONLY the active state (registre §3).
  const agents = (
    <Suspense
      key="agents"
      fallback={<span className="tabular-nums">{t("agentsObserved", { n: fleetCount })}</span>}
    >
      <ObservedAgentsLabel fleetCount={fleetCount} />
    </Suspense>
  );
  let microSegments: { key: string; node: ReactNode }[];
  if (reading === "live") {
    microSegments = [
      { key: "data", node: <span>{t("realtime")}</span> },
      ...(lastUpdate
        ? [
            {
              key: "upd",
              node: (
                <span className="tabular-nums">{t("microLastUpdate", { time: lastUpdate })}</span>
              ),
            },
          ]
        : []),
      { key: "agents", node: agents },
    ];
  } else if (reading === "asof") {
    microSegments = asOfText
      ? [
          // "État au {T} · {n} agents observés" — the ambiguous "actions appliquées
          // au présent" is removed from the micro-line (and the rail).
          { key: "state", node: <span>{t("microStateAt", { time: asOfText })}</span> },
          { key: "agents", node: agents },
        ]
      : [{ key: "pick", node: <span>{t("microPickInstant")}</span> }];
  } else {
    microSegments = [
      {
        key: "period",
        node:
          fromText && toText ? (
            <span>{t("microPeriodFromTo", { from: fromText, to: toText })}</span>
          ) : (
            <span>{t("modeHistory")}</span>
          ),
      },
      { key: "agents", node: agents },
      {
        key: "compare",
        node: <span>{t("microComparison", { compare: compareLabel(compare, t) })}</span>,
      },
    ];
  }

  return (
    <section className="rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      {/* Collapsed command row — the single temporal focus. */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        {/* Lecture — Maintenant / À un instant / Historique, with per-mode
            definitions IN the menu (not a permanent line), differentiated by icon. */}
        <LectureMenu reading={reading} onChange={(v) => temporal.setReading(v)} t={t} />
        {/* "État au" (À un instant) — the SINGLE point-in-time picker: the chip IS
            the trigger, opening the calendar directly (no duplicate bottom button).
            Otherwise the Période selector (Maintenant / Historique). */}
        {reading === "asof" ? (
          <GoToDateButton
            selectedDate={asOfMs ? new Date(asOfMs) : new Date()}
            onPick={temporal.pickDate}
            minDate={minPickDate}
            renderTrigger={({ open, toggle }) => (
              <button
                type="button"
                onClick={toggle}
                aria-haspopup="dialog"
                aria-expanded={open}
                aria-label={`${t("asofAt")} ${asOfText ?? t("pickDatePrompt")}`}
                title={asOfText ? t("changeInstant") : t("goToInstant")}
                className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-gold-500/50 bg-gold-500/10 px-3 text-xs text-gold-200 transition-colors hover:bg-gold-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500/50"
              >
                <CalendarClock className="h-3.5 w-3.5 shrink-0 text-gold-400" />
                {t("asofAt")}
                <b className="font-semibold tabular-nums text-[var(--tessera-text)]">
                  {asOfText ?? t("pickDatePrompt")}
                </b>
                <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gold-400/70" />
              </button>
            )}
          />
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
        {/* Comparer à — same level as Lecture/Période/Agents, in ALL readings; only
            computable references are selectable, the rest are disabled with a reason.
            "À un instant" before a day is picked: nothing to compare yet, so the
            control is disabled with a reason — never a phantom default (registre §12). */}
        {reading === "asof" && !hasInstant ? (
          <DisabledChip
            icon={ArrowLeftRight}
            label={t("compareTo")}
            value={t("cmpNow")}
            title={t("reasonSelectInstant")}
          />
        ) : (
          <SelectChip
            icon={ArrowLeftRight}
            label={t("compareTo")}
            value={compare}
            onChange={setCompare}
            options={compareOptions}
          />
        )}
        {/* Déplier / Replier — pushed to the right; the page-level Export / Preuves
            actions now live in the page header (registre §2), not in this temporal
            focus, so the bar holds ONLY temporal controls. */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={expanded}
          className="ml-auto h-9 gap-1.5"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          {expanded ? t("collapse") : t("expand")}
        </Button>
      </div>

      {/* Contextual micro-line — describes ONLY the active reading (no permanent
          documentation of all modes; those live in the Lecture menu). It carries
          NO icon: the leading status icon is the Lecture control's job (one row
          above), and repeating the SAME reading glyph here stacked two identical
          icons vertically and read as a second control. The line is a state
          summary, so its bold first segment carries the meaning. */}
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 border-t border-[var(--tessera-border)]/60 px-3 py-1.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
        {microSegments.map((seg, i) => (
          <span key={seg.key} className="flex items-center gap-1.5">
            {i > 0 ? <span aria-hidden>·</span> : null}
            <span className={i === 0 ? "font-medium text-[var(--tessera-text)]" : undefined}>
              {seg.node}
            </span>
          </span>
        ))}
        {/* The SINGLE "Revenir au direct" (registre §11) — a discreet secondary
            BUTTON (not a link), here in the bar, never duplicated in the rail.
            Absent in Maintenant, and absent in "À un instant" until a day is picked. */}
        {reading === "historique" || (reading === "asof" && hasInstant) ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto h-7 gap-1.5 px-2.5 text-xs"
            onClick={() => temporal.setReading("live")}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {t("exitReplay")}
          </Button>
        ) : null}
      </div>

      {/* Expanded — human title, the scrubber panel, and the only place the as-of
          jump-to-proofs lives (signals, never an execution replay). Animated
          open/close (grid-rows 0fr->1fr) so the KPI cards below never jump. */}
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
        onTransitionEnd={(e) => {
          if (e.propertyName === "grid-template-rows") setPanelOverflow(expanded);
        }}
      >
        <div className={cn(panelOverflow ? "overflow-visible" : "overflow-hidden")}>
          {/* Mount the panel only when open: an always-mounted rail re-ran its
              Date/locale formatting during SSR while collapsed -> a hydration
              mismatch. Gating on `expanded` keeps the grid-rows reveal AND a clean SSR. */}
          {expanded ? (
            <div className="border-t border-[var(--tessera-border)]/60 px-3 pb-3 pt-2">
              {/* No descriptive rail header: the reading lives in the command-bar
                  Lecture chip and the synthetic state in the micro-line above, so the
                  rail goes STRAIGHT to the visualisation (timeline · legend · the
                  selected-event detail when one is picked) — never repeating
                  "Données en temps réel" / "Signaux observés sur la période active". */}
              <TemporalRail
                embedded
                mode={temporal.mode}
                reading={reading}
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
                viewLabel={viewLabel}
              />
              {/* The rail focuses on visualisation + markers + the PROUVER link.
                  Date selection lives ONLY in the "État au" chip above — no
                  duplicate bottom picker (one entry per action). Transition to
                  PROUVER · État à date shows only with an instant chosen (a
                  point-in-time reconstruction, not a replay). */}
              {temporal.asOf ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Link
                    href={`/prouver/etat-a-date?asof=${encodeURIComponent(temporal.asOf)}`}
                    className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] px-3 text-xs font-medium text-blue-300 hover:bg-[var(--tessera-muted)]"
                  >
                    <CalendarClock className="h-4 w-4" />
                    {t("openInProofs")}
                  </Link>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}

/** Date-only formatter for the history window bounds (stable width via tabular-nums). */
function fmtDay(ms: number): string {
  return new Date(ms).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

/**
 * Lecture control — a premium dropdown that carries the per-reading DEFINITIONS
 * (so they no longer need a permanent explanatory line in the rail). Human labels
 * only: Maintenant / À un instant / Historique; never "As-of".
 */
function LectureMenu({
  reading,
  onChange,
  t,
}: {
  reading: Reading;
  onChange: (value: Reading) => void;
  t: Translate;
}) {
  const items: { value: Reading; labelKey: string; descKey: string }[] = [
    { value: "live", labelKey: "modeLive", descKey: "readingDescLive" },
    { value: "asof", labelKey: "modeAsof", descKey: "readingDescAsof" },
    { value: "historique", labelKey: "modeHistory", descKey: "readingDescHistory" },
  ];
  const labelKeyFor: Record<Reading, string> = {
    live: "modeLive",
    asof: "modeAsof",
    historique: "modeHistory",
  };
  const CurrentIcon = READING_ICON[reading];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-gold-500/50 bg-gold-500/10 px-3 text-xs text-gold-200 transition-colors hover:bg-gold-500/20"
        >
          <CurrentIcon className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("reading")}
          <span className="font-semibold text-[var(--tessera-text)]">
            {t(labelKeyFor[reading])}
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gold-400/70" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[20rem]">
        {items.map((r) => {
          const Icon = READING_ICON[r.value];
          return (
            <DropdownMenuItem
              key={r.value}
              onSelect={() => onChange(r.value)}
              className="flex items-start gap-2.5 py-2"
            >
              <Icon className="mt-0.5 h-4 w-4 shrink-0 text-gold-400" />
              <span className="flex min-w-0 flex-col">
                <span className="flex items-center gap-2 text-sm font-medium text-[var(--tessera-text)]">
                  {t(r.labelKey)}
                  {r.value === reading ? <Check className="h-3.5 w-3.5 text-gold-400" /> : null}
                </span>
                <span className="text-[0.7rem] text-[var(--tessera-text-muted)]">
                  {t(r.descKey)}
                </span>
              </span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
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
  options: { value: string; label: string; disabled?: boolean }[];
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
          <option
            key={o.value}
            value={o.value}
            disabled={o.disabled}
            className="bg-[var(--tessera-bg)]"
          >
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/**
 * A non-interactive chip mirroring SelectChip's shape, for a control that is
 * disabled with an honest reason (e.g. "Comparer à" before an instant is chosen).
 * The reason is exposed via the title so the value stays a plain "—".
 */
function DisabledChip({
  icon: Icon,
  label,
  value,
  title,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  title: string;
}) {
  return (
    <span
      title={title}
      className="flex h-9 shrink-0 cursor-not-allowed items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] opacity-60"
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
      {label}
      <span className="font-semibold text-[var(--tessera-text-muted)]">{value}</span>
    </span>
  );
}

/**
 * Observed-agent count, reconciled with the active `?agent=` scope (1 when scoped
 * to a single agent, the fleet size otherwise) — registre §2. Lives in its own
 * Suspense boundary because it reads the URL via useSearchParams (build-safe, the
 * same pattern as AgentScopeFilter), so the bar never triggers a CSR bailout.
 */
function ObservedAgentsLabel({ fleetCount }: { fleetCount: number }) {
  const t = useTranslations("overview.time");
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));
  const n = isScopedToAgent(scope) ? 1 : fleetCount;
  return <span className="tabular-nums">{t("agentsObserved", { n })}</span>;
}
