"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  FileDown,
  Gauge,
  Landmark,
  ListChecks,
  type LucideIcon,
  Radio,
  Scale,
  ShieldCheck,
  Stethoscope,
  TrendingUp,
} from "lucide-react";
// Aliased for history: `Route` used to name a lucide icon in this module, and the bare name
// would read as the icon to anyone who remembers it.
import type { Route as NextRoute } from "next";
import { useLocale, useTranslations } from "next-intl";

import { QualityRegimeBand } from "@/components/surveiller/quality-regime-band";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { type ReactNode, useState } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { TabStrip } from "@/components/cockpit/tab-strip";
import { EVAL_PATHNAME, EVAL_VIEW_VALUE, evalQuery } from "@/components/eval/eval-route";
import { EvolutionChart } from "@/components/observability/evolution-chart";
import {
  EtatActuel,
  FaithGroundingScatter,
  OverviewKpis,
  PredictiveSignals,
  TopProblems,
} from "@/components/observability/overview-exec";
import {
  SignalHeatmap,
  SignalKpis,
  type SignalRow,
  SignalsRail,
  SignalsTable,
  ThemeDistribution,
  buildSignalRows,
} from "@/components/observability/signals-table";
import { useRailTimeline, useTemporalState } from "@/components/overview/temporal-rail";
import { SignalCommandBar } from "@/components/surveiller/signal-command-bar";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import {
  fetchAIAct,
  fetchAnomalies,
  fetchCalibration,
  fetchCitations,
  fetchConformance,
  fetchContradictions,
  fetchControlSeries,
  fetchCost,
  fetchFailedCases,
  fetchFailureClusters,
  fetchFailurePredictor,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchIntent,
  fetchJudgeDrift,
  fetchLocaleFormat,
  fetchLocalization,
  fetchMetricPairs,
  fetchPiiLeak,
  fetchRefusal,
  fetchRegressionRisk,
  fetchReleaseStatus,
  fetchRouting,
  fetchSLO,
  fetchScoreSeries,
  fetchSignalCoverage,
  fetchSignalStatusTrend,
  fetchToolValidity,
  fetchToxicity,
  fetchWhatChanged,
} from "@/lib/api/client";
import {
  CROSSED_TARGETS,
  DASHBOARD_TABS,
  DASHBOARD_TAB_PARAM,
  type DashboardTab,
  EVAL_TAB_PARAM,
  QUALITY_VIEW_PARAM,
  type QualityTarget,
  isDashboardTab,
} from "@/lib/quality-tabs";
import { SIGNAL_FOCUS_PARAM, readSignalFocus, registryIdFor } from "@/lib/signal-focus";
import { useWindowStore } from "@/lib/stores/window-store";
import { useUrlBackedView } from "@/lib/use-url-backed-view";

const POLL_MS = 5_000;

/**
 * The signal funnel, measured. There used to be two constants here —
 * `QUALITY_SIGNALS = 42` and `QUALITY_CATALOGUE = 200` — read from nothing, and on 2026-08-01
 * every one of their numbers was wrong: 44 catalogue signals declare this page, the catalogue
 * holds 202, and 19 rows actually render.
 *
 * The comment beside them was candid ("a coverage framing, not a live count"), which is exactly
 * the problem: the screen said nothing of the sort, and an operator cannot read a comment.
 *
 * "Covers 42 of 200" was also the wrong SHAPE of claim. 124 of the 202 are `planned` — designed,
 * never built — so a ratio against the whole catalogue measures a page against work that does
 * not exist. What answers the operator's real question ("why only three critical signals, why
 * twelve unavailable?") is the funnel: declared → active → on this page → wired → sampled →
 * breaching. Each stage loses signals for a DIFFERENT reason, and only the last two are alarms.
 */
interface SignalFunnel {
  /** Declared in `signal_catalog.yaml`, and how many were ever implemented. */
  catalogue: number;
  active: number;
  /** Catalogue signals whose declared home is this page. */
  declared: number;
  /** Rows this page can actually build — a reader exists in code. */
  wired: number;
  /** …of which returned a sample in the window. */
  sampled: number;
  /** …of which breach their bar. */
  breaching: number;
}

// The tab list and this strip's query parameter are declared in `lib/quality-tabs.ts`, beside
// the OTHER strip's — the two used to collide on `?tab=` and the separation is now a fact a
// test can read without importing this file.
const TAB_DEFS = DASHBOARD_TABS;
type TabKey = DashboardTab;

/** A translucent banded section grouping one cockpit zone, matching the
 * Sécurité & privacy page: a labelled band holding real sub-cards. The heading
 * carries an icon + label (no "A./B." numbering — that read as a worksheet, not
 * a dashboard). */
function Zone({
  label,
  icon: Icon,
  iconClassName = "text-[var(--tessera-green)]",
  info,
  children,
}: {
  label: string;
  icon: LucideIcon;
  /** Per-zone accent so each band's icon reads as its own facet. */
  iconClassName?: string;
  /** Optional ⓘ explainer rendered next to the band label. */
  info?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      data-slot="card"
      className="min-w-0 rounded-xl border border-[var(--tessera-border)]/50 bg-[var(--tessera-surface)]/25 p-2.5"
    >
      <h2 className="mt-0.5 mb-1.5 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        <Icon className={`h-3.5 w-3.5 shrink-0 ${iconClassName}`} />
        {label}
        {info}
      </h2>
      {children}
    </section>
  );
}

/** A ⓘ for a quality-page zone/section, reading quality.explain.<k>.{what,how,source}. */
function SectionInfo({ title, explainKey }: { title: string; explainKey: string }) {
  const te = useTranslations("quality.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${explainKey}.what`)}
      how={te(`${explainKey}.how`)}
      source={te.has(`${explainKey}.source`) ? te(`${explainKey}.source`) : undefined}
    />
  );
}

export function ObservabilityDashboard({ agentScope }: { agentScope?: ReactNode }) {
  const t = useTranslations("observability");
  const tq = useTranslations("quality");
  const tqr = useTranslations("qualityRegimes");
  const tcd = useTranslations("overview.controlDetail");
  const locale = useLocale();
  const [tab, setTab] = useUrlBackedView(TAB_DEFS, "overview", DASHBOARD_TAB_PARAM);
  const [selectedSignal, setSelectedSignal] = useState<SignalRow | null>(null);
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();
  const queryClient = useQueryClient();
  // Global agent scope (?agent=) — the score-/bundle-/audit-backed quality signals
  // read this agent's own turns; shared-policy probes (firewall, refusal) stay org.
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));
  // The window LENGTH, from the same store the header's period selector writes to. It rides
  // every windowable query below AND every one of their keys — a request that carries the
  // period while its key does not would be served the previous period's cached answer.
  const period = useWindowStore((st) => st.period);
  // …and its LABEL, for every title that names its window: a title with a hardcoded
  // "(7 d)" keeps saying seven days after the operator picks thirty.
  const tTime = useTranslations("overview.time");
  const windowLabel = tTime(period);
  const router = useRouter();
  const pathname = usePathname();

  /**
   * Selecting a signal in the registry FOCUSES it (`?signal=`), so the per-agent breakdown
   * above re-plans its lens on the server: it answers that signal, or — when the signal is
   * org-wide by construction — masks the table and says why. Without this the masked lens
   * would be unreachable, and an unreachable capability is a decoration.
   */
  /**
   * Open a drill-down destination, wherever it now lives.
   *
   * Four of the six targets the overview and the rails name — the run archive, the failed
   * cases, the model comparison, the judge — moved to the evaluations view. Their sentences
   * did not stop being true ("see the failed cases" still names something the operator can
   * see); only the address changed. So the handler resolves the address instead of every call
   * site learning about the boundary, and a link to a departed tab lands on the content rather
   * than on a tab strip that silently falls back to the overview.
   *
   * `?agent=` rides along: crossing the boundary must not quietly widen the scope from one
   * agent back to the whole fleet.
   */
  function openTarget(target: QualityTarget) {
    if (isDashboardTab(target)) {
      setTab(target);
      return;
    }
    const query = new URLSearchParams({
      [QUALITY_VIEW_PARAM]: EVAL_VIEW_VALUE,
      [EVAL_TAB_PARAM]: CROSSED_TARGETS[target],
    });
    const rawScope = searchParams.get(AGENT_SCOPE_PARAM);
    if (rawScope) query.set(AGENT_SCOPE_PARAM, rawScope);
    // `pathname` rather than `EVAL_PATHNAME`: the crossing is a query change on THIS route, and
    // the live pathname is the one that already carries the locale segment. The constant does
    // not, so pushing it would drop a German operator onto the French page.
    router.push(`${pathname}?${query.toString()}` as NextRoute);
  }

  function focusSignal(row: SignalRow) {
    setSelectedSignal(row);
    const params = new URLSearchParams(searchParams.toString());
    params.set(SIGNAL_FOCUS_PARAM, registryIdFor(row.key));
    router.replace(`${pathname}?${params.toString()}` as NextRoute, { scroll: false });
  }

  // Every control's curve, over the same window and the same agent scope as the numbers.
  // One request for the whole registry table; each bucket carries the payload `readControls`
  // already knows how to read, so no control needs a bespoke trend query.
  const controlSeries = useQuery({
    queryKey: ["control-series", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchControlSeries(signal, { days: period, at: asOf ?? undefined, agent: scope }),
    refetchInterval: historyMode ? false : 30_000,
    placeholderData: keepPreviousData,
  });
  const slo = useQuery({
    queryKey: ["slo", asOf, scope, period],
    queryFn: ({ signal }) => fetchSLO(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL_MS,
  });

  const scoreSeries = useQuery({
    queryKey: ["score-series", "faithfulness", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchScoreSeries(signal, asOf ?? undefined, "faithfulness", scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
    enabled: tab === "overview" || tab === "signals",
  });

  const groundingSeries = useQuery({
    queryKey: ["score-series", "grounding", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchScoreSeries(signal, asOf ?? undefined, "grounding", scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
    enabled: tab === "overview",
  });

  const metricPairs = useQuery({
    queryKey: ["metric-pairs", "faithfulness", "grounding", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchMetricPairs(signal, "faithfulness", "grounding", asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
    enabled: tab === "overview",
  });

  const hallucinationSeries = useQuery({
    queryKey: ["score-series", "hallucination", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchScoreSeries(signal, asOf ?? undefined, "hallucination", scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
    enabled: tab === "overview",
  });

  // Documented failure catalogue is static per locale (no polling, no as-of). Its only reader
  // left on this dashboard is the signal drill-down rail — the overview panels that consumed it
  // (failure bars, priority cases, right rail) crossed to the evaluations view with their tabs.
  const failedCases = useQuery({
    queryKey: ["failed-cases", locale],
    queryFn: ({ signal }) => fetchFailedCases(signal, locale),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: tab === "signals",
  });

  // Release state — read here ONLY for the signal drill-down rail. Every overview surface that
  // summarised it (KPI tiles, release card, regressions chart, status bar) belonged to the
  // evaluations view's question and left this dashboard.
  const releaseStatus = useQuery({
    queryKey: ["release-status"],
    queryFn: ({ signal }) => fetchReleaseStatus(signal),
    refetchInterval: 60_000,
    enabled: tab === "signals",
  });

  // Failure clustering embeds the whole corpus and is cached server-side; fetch once.
  const failureClusters = useQuery({
    queryKey: ["failure-clusters"],
    queryFn: ({ signal }) => fetchFailureClusters(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const failurePredictor = useQuery({
    queryKey: ["failure-predictor"],
    queryFn: ({ signal }) => fetchFailurePredictor(signal),
    refetchInterval: 15_000,
  });

  const toxicity = useQuery({
    queryKey: ["toxicity", asOf, scope, period],
    queryFn: ({ signal }) => fetchToxicity(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const localization = useQuery({
    queryKey: ["localization"],
    queryFn: ({ signal }) => fetchLocalization(signal),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: tab === "overview",
  });

  // The AI-Act read is NOT here as a query. Nothing on this page renders it: its single
  // consumer is the evidence bundle, i.e. a button most sessions never press — and it polled
  // every 30 seconds regardless, for the whole time the page stayed open. It is fetched at
  // click time now (see `downloadQualityEvidence`), which also makes it fresher than a cached
  // value up to 30 seconds old would have been.

  // Calibration is computed server-side (slow, judge over a gold set) and cached,
  // so fetch it once rather than polling.
  const calibration = useQuery({
    queryKey: ["calibration"],
    queryFn: ({ signal }) => fetchCalibration(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const judgeDrift = useQuery({
    queryKey: ["judge-drift", asOf, period],
    queryFn: ({ signal }) => fetchJudgeDrift(signal, asOf ?? undefined, undefined, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
    enabled: tab === "overview",
  });

  // Forward-looking regression risk for the "Signaux prédictifs" column (image 00).
  const regressionRisk = useQuery({
    queryKey: ["regression-risk", asOf, period],
    queryFn: ({ signal }) => fetchRegressionRisk(signal, asOf ?? undefined, undefined, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
    enabled: tab === "overview",
  });

  // Per-severity-band score-count trend for the Signaux KPI tiles (image 01).
  const signalStatusTrend = useQuery({
    queryKey: ["signal-status-trend", asOf, period],
    queryFn: ({ signal }) => fetchSignalStatusTrend(signal, asOf ?? undefined, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
    enabled: tab === "signals",
  });

  const firewall = useQuery({
    queryKey: ["firewall-efficacy"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const tools = useQuery({
    queryKey: ["tool-validity", asOf, scope, period],
    queryFn: ({ signal }) => fetchToolValidity(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const routing = useQuery({
    queryKey: ["routing", period],
    queryFn: ({ signal }) => fetchRouting(signal, period),
    refetchInterval: 15_000,
  });

  const piiLeak = useQuery({
    queryKey: ["pii-leak", asOf, scope, period],
    queryFn: ({ signal }) => fetchPiiLeak(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const contradictions = useQuery({
    queryKey: ["contradictions", period],
    queryFn: ({ signal }) => fetchContradictions(signal, period),
    refetchInterval: 20_000,
  });

  const whatChanged = useQuery({
    queryKey: ["what-changed", asOf, scope],
    queryFn: ({ signal }) => fetchWhatChanged(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 20_000,
    enabled: tab === "signals",
  });

  const anomalies = useQuery({
    queryKey: ["anomalies", asOf, scope, period],
    queryFn: ({ signal }) => fetchAnomalies(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 20_000,
  });

  const refusal = useQuery({
    queryKey: ["refusal"],
    queryFn: ({ signal }) => fetchRefusal(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const citations = useQuery({
    queryKey: ["citations", period],
    queryFn: ({ signal }) => fetchCitations(signal, period),
    refetchInterval: 15_000,
  });

  const localeFormat = useQuery({
    queryKey: ["locale-format", period],
    queryFn: ({ signal }) => fetchLocaleFormat(signal, period),
    refetchInterval: 15_000,
  });

  const conformance = useQuery({
    queryKey: ["conformance", asOf, scope, period],
    queryFn: ({ signal }) => fetchConformance(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const intent = useQuery({
    queryKey: ["intent", period],
    queryFn: ({ signal }) => fetchIntent(signal, period),
    refetchInterval: 15_000,
  });

  const cost = useQuery({
    queryKey: ["cost", asOf, scope, period],
    queryFn: ({ signal }) => fetchCost(signal, asOf ?? undefined, scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const funnel = useQuery({
    queryKey: ["funnel", asOf, scope],
    queryFn: ({ signal }) => fetchFunnel(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  // Newest first for display.

  // Unified signal catalogue derived from the live reports (reference image 01).
  const signalRows = buildSignalRows(
    t,
    {
      slo: slo.data,
      calibration: calibration.data,
      citations: citations.data,
      contradiction: contradictions.data,
      predictor: failurePredictor.data,
      clusters: failureClusters.data,
      firewall: firewall.data,
      toxicity: toxicity.data,
      pii: piiLeak.data,
      refusal: refusal.data,
      conformance: conformance.data,
      localeFormat: localeFormat.data,
      tools: tools.data,
      cost: cost.data,
      routing: routing.data,
      funnel: funnel.data,
      anomalies: anomalies.data,
      intent: intent.data,
    },
    // The supporting line for the eight shared rows, localised from the SAME catalogue the
    // overview reads. The previous version built `` `sous ${pct(...)}` `` inline — a French
    // literal in a trilingual component, which a German operator read in French.
    tcd,
    // …and the curve for each of them, over the window the numbers above are read under.
    // Until 2026-08-01 this column held a direction arrow and nothing else, on all 24 rows.
    controlSeries.data,
    // …and the language every number in those rows is written in. Without it the registry
    // falls back to French, which is right here and wrong on the other two locales.
    locale,
  );

  /**
   * The row `?signal=` names, if any — the URL is the source, not local click state.
   *
   * `?signal=` already drove the per-agent lens; it did NOT reach this table, so arriving from
   * "Investiguer" on Vue d'ensemble opened the right tab with nothing selected. The operator's
   * complaint was that the link landed on the wrong page; landing on the right page with the
   * row unmarked is the same complaint one step later.
   *
   * Reading it from the URL rather than from `selectedSignal` is what makes the link work on a
   * cold load and survive a refresh — click state does not exist yet when the page arrives.
   */
  /**
   * The funnel, counted from the rows this page ACTUALLY produced.
   *
   * The last four stages are facts about the screen, so they are counted where the screen is
   * built — asking the backend for them would repeat the constants' mistake in a place that
   * cannot see the screen. The first two come from the catalogue, which the backend ships.
   */
  const coverage = useQuery({
    queryKey: ["signal-coverage"],
    queryFn: ({ signal }) => fetchSignalCoverage(signal),
    staleTime: Number.POSITIVE_INFINITY, // the catalogue is shipped with the image
  });
  const cat = coverage.data?.catalogue;
  const signalFunnel: SignalFunnel = {
    catalogue: cat?.total ?? 0,
    active: cat?.active ?? 0,
    declared: cat?.on_quality_page ?? 0,
    wired: signalRows.length,
    sampled: signalRows.filter((r) => r.status !== "na").length,
    breaching: signalRows.filter((r) => r.status === "crit").length,
  };

  const focusedSignal = readSignalFocus(searchParams);
  const focusedKey =
    signalRows.find((r) => registryIdFor(r.key) === focusedSignal)?.key ??
    selectedSignal?.key ??
    null;

  // --- Real derived headline metrics (no fabrication — null ⇒ "—") -----------
  const signalSummary = signalRows.reduce(
    (acc, r) => {
      acc[r.status] += 1;
      acc.total += 1;
      return acc;
    },
    { ok: 0, warn: 0, crit: 0, na: 0, total: 0 },
  );
  const sloPct = slo.data && slo.data.n > 0 ? Math.round(slo.data.good_rate * 100) : null;

  async function downloadQualityEvidence() {
    // The one read this page does not render. Asked for HERE rather than polled all session:
    // it costs one request when the button is pressed instead of one every thirty seconds
    // forever, and a failure leaves `null` — an evidence pack may be short a section, never
    // wrong about one. Every other field below is already on screen.
    const aiAct = await queryClient
      .fetchQuery({
        queryKey: ["ai-act", asOf],
        queryFn: ({ signal }) => fetchAIAct(signal, asOf ?? undefined),
        staleTime: 30_000,
      })
      .catch(() => null);
    const bundle = {
      generated_at: new Date().toISOString(),
      page: "quality",
      // The window ACTUALLY selected on the rail — a static "last 7 days" here would
      // stamp the wrong window on an evidence pack generated under any other period.
      window: windowLabel,
      // The whole funnel, not a ratio: an evidence bundle that says "42/200" invites the
      // reader to conclude the other 158 are failing, when 124 of them were never built.
      signals: signalFunnel,
      slo: slo.data ?? null,
      refusal: refusal.data ?? null,
      conformance: conformance.data ?? null,
      calibration: calibration.data ?? null,
      toxicity: toxicity.data ?? null,
      pii_leak: piiLeak.data ?? null,
      ai_act: aiAct,
      failure_clusters: failureClusters.data ?? null,
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tessera-quality-evidence-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-2.5">
      {/* Sticky chrome: tab bar + business actions on one row (image normative),
          the shared compact temporal rail (Live/Replay) below. */}
      {/* On phones this chrome is taller than the viewport's useful content area. Making it
          sticky there lets it intercept taps on the first KPI row as the cards scroll behind
          it. It becomes sticky only once the viewport has enough room to keep controls and
          content simultaneously actionable. The main scroller owns 1.25rem of top padding;
          consuming it at the sticky threshold makes this opaque stack meet the header, so
          scrolling cards cannot remain visible in a strip above or between its bands. */}
      <div className="-mx-3 flex flex-col gap-1.5 bg-[var(--tessera-bg)] px-3 pb-1.5 pt-1.5 shadow-[0_-4px_0_0_var(--tessera-bg)] md:sticky md:-top-5 md:z-40">
        {/* The temporal rail LEADS the chrome — directly beneath the SLO alert the page
            renders above the dashboard (user feedback) — then the actions + tabs. */}
        <SignalCommandBar
          temporal={temporal}
          timeline={railTimeline.data}
          sloTarget={slo.data?.target}
          liveStatus={tq("temporal.liveData")}
        />
        {/* Action toolbar (image normative: actions sit on the title row). The tab
            bar keeps its own full-width row below so all six tabs stay visible. A
            left-aligned coverage descriptor anchors the band so the buttons never
            float unmoored. */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-1.5 text-[0.72rem] text-[var(--muted-foreground)]">
            <Gauge className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
            <span className="truncate">
              {/* The declared share comes from the catalogue read. When that read FAILED, the
                  descriptor says so instead of printing a zero declared-count — a failed read
                  is not an empty catalogue. Sampled and wired stay: facts about this screen. */}
              {coverage.isError && !coverage.data
                ? tq("rail.signalsFunnelUnread", {
                    sampled: signalFunnel.sampled,
                    wired: signalFunnel.wired,
                  })
                : tq("rail.signalsFunnel", {
                    sampled: signalFunnel.sampled,
                    wired: signalFunnel.wired,
                    declared: signalFunnel.declared,
                  })}
            </span>
          </span>
          {/* Wraps below 1024: four buttons plus the descriptor need ~840px, so on a
              tablet or a phone this row used to run 190-454px past the card with no
              way to scroll to it — the last two actions were simply unreachable. */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Two controls left this row on operator feedback (2026-08-12). The run-eval button
                was a disabled promise — no endpoint starts an evaluation, the harness is a
                command (`scripts/run_eval.py`) — and dead chrome earns no place on a toolbar.
                The model-comparison button answered the OTHER view's question; its content
                lives behind the evaluations door just above, under its own tab. */}
            {/* It opened the RUNS tab of this dashboard. The case set is not there — it is the
                versioned artefact on the other view, and this button is the shortest path
                across the boundary this page keeps blurring. A Link, so it is also a URL an
                operator can send. */}
            <Button size="sm" variant="outline" asChild className="h-8 gap-2 text-xs">
              <Link
                href={{
                  pathname: EVAL_PATHNAME,
                  query: evalQuery({ tab: "cases" }),
                }}
              >
                <Boxes className="h-3.5 w-3.5" />
                {tq("cta.openDataset")}
              </Link>
            </Button>
            <Button size="sm" onClick={downloadQualityEvidence} className="h-8 gap-2 text-xs">
              <FileDown className="h-3.5 w-3.5" />
              {tq("cta.evidence")}
            </Button>
          </div>
        </div>
        <TabBar active={tab} onChange={setTab} />
      </div>

      {/* Agent-scope context (filter · per-agent breakdown · note) sits BELOW the rail,
          so the temporal rail stays directly under the SLO alert. */}
      {agentScope ? <div className="-mt-0.5">{agentScope}</div> : null}

      {/* KPI strip (unlabeled, full page width above the zones — image normative).
          Production reads only: the four eval-archive tiles (non-regression, open
          regressions, judge agreement, evaluated cases) left with their tabs. */}
      {tab === "overview" ? (
        <OverviewKpis
          sloPct={sloPct}
          faithfulness={scoreSeries.data}
          grounding={groundingSeries.data}
          hallucination={hallucinationSeries.data}
          signalsCrit={signalSummary.total > 0 ? signalSummary.crit : null}
          loading={scoreSeries.isLoading}
          onOpen={openTarget}
        />
      ) : null}

      <div className="flex min-w-0 flex-col gap-2">
        {tab === "overview" && (
          <>
            {/* Each zone is a translucent band holding real sub-cards (like the
                Sécurité & privacy page). Row 1: état | signaux en défaut; row 2:
                avant-coureurs | tendances. Everything here samples PRODUCTION —
                the eval-archive panels this view used to summarise (failure bars,
                priority cases, judge κ, root-cause diff, release card, run tables)
                live on the evaluations view now, behind the door above. */}
            <div className="grid items-start gap-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]">
              <Zone
                label={tq("sec.etat")}
                icon={Gauge}
                iconClassName="text-[var(--tessera-fg-info)]"
                info={<SectionInfo title={tq("sec.etat")} explainKey="etat" />}
              >
                <EtatActuel
                  summary={signalSummary}
                  evolutionDelta={scoreSeries.data?.delta ?? null}
                  scorePct={sloPct}
                  series={scoreSeries.data}
                />
              </Zone>

              <Zone
                label={tq("sec.problems")}
                icon={Stethoscope}
                iconClassName="text-[var(--tessera-fg-warning)]"
                info={<SectionInfo title={tq("sec.problems")} explainKey="problems" />}
              >
                <TopProblems
                  rows={signalRows}
                  onSelect={(row) => {
                    setTab("signals");
                    focusSignal(row);
                  }}
                />
              </Zone>
            </div>

            <div className="grid items-start gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <Zone
                label={tq("sec.predictive")}
                icon={TrendingUp}
                iconClassName="text-[var(--tessera-fg-accent)]"
                info={<SectionInfo title={tq("sec.predictive")} explainKey="predictive" />}
              >
                <PredictiveSignals
                  series={scoreSeries.data}
                  risk={regressionRisk.data}
                  drift={judgeDrift.data}
                  predictor={failurePredictor.data}
                  intent={intent.data}
                  localization={localization.data}
                  loading={regressionRisk.isLoading}
                />
              </Zone>

              <Zone
                label={tq("sec.trends")}
                icon={Activity}
                iconClassName="text-[var(--tessera-fg-success)]"
                info={<SectionInfo title={tq("sec.trends")} explainKey="trends" />}
              >
                <div className="grid items-start gap-2 sm:grid-cols-2">
                  <EvolutionChart
                    series={scoreSeries.data}
                    loading={scoreSeries.isLoading}
                    windowLabel={windowLabel}
                  />
                  <FaithGroundingScatter
                    pairs={metricPairs.data}
                    loading={metricPairs.isLoading}
                    onOpen={openTarget}
                    windowLabel={windowLabel}
                  />
                </div>
              </Zone>
            </div>

            {/* The rating methods (ADR 0017 §A4), in the house mould and BELOW the
                temporal sequence (operator feedback 2026-08-25) — its counts span all
                history, independent of the rail's window, which its ⓘ says out loud. */}
            <Zone
              label={tqr("title")}
              icon={Scale}
              iconClassName="text-[var(--tessera-fg-accent)]"
              info={<SectionInfo title={tqr("title")} explainKey="regimes" />}
            >
              <QualityRegimeBand />
            </Zone>
          </>
        )}

        {tab === "signals" && (
          <div className="flex flex-col gap-2">
            {/* KPI strip + registre + analytics row (normative 01). */}
            <SignalKpis
              rows={signalRows}
              trend={signalStatusTrend.data}
              catalogue={signalFunnel.catalogue}
            />
            <SignalsTable rows={signalRows} selectedKey={focusedKey} onSelect={focusSignal} />
            <div className="grid gap-2 lg:grid-cols-3">
              <EvolutionChart
                series={scoreSeries.data}
                loading={scoreSeries.isLoading}
                windowLabel={windowLabel}
              />
              <ThemeDistribution rows={signalRows} />
              <SignalHeatmap rows={signalRows} />
            </div>
          </div>
        )}
      </div>

      {tab === "signals" && selectedSignal ? (
        <DetailDrawer
          title={selectedSignal.name}
          subtitle={`${selectedSignal.metric} · ${selectedSignal.entity}`}
          icon={<Radio className="h-4 w-4" />}
          onClose={() => setSelectedSignal(null)}
          width="max-w-[500px]"
        >
          <SignalsRail
            selected={selectedSignal}
            rows={signalRows}
            failed={failedCases.data}
            release={releaseStatus.data}
            whatChanged={whatChanged.data}
            onOpen={openTarget}
            onEvidence={downloadQualityEvidence}
          />
        </DetailDrawer>
      ) : null}

      <StatusBar
        crit={signalSummary.crit}
        warn={signalSummary.warn}
        signalsWired={signalFunnel.wired}
      />
    </div>
  );
}

/** Thin status bar that closes the page (image normative). It rides at the end
 * of the content — not `sticky`, which left it floating mid-scroll and masking
 * the rows behind it once the page grew past one viewport. `mt-auto` keeps it at
 * the bottom when the content is short.
 *
 * Its right corner is DERIVED, not declared: it used to print a green "Système OK"
 * as a constant, directly under a ribbon that could be showing six critical
 * signals — the same screen asserting two opposite things. It also carried the
 * active case set and its date, which are release facts from the other view. */
function StatusBar({
  crit,
  warn,
  signalsWired,
}: {
  /** Registry rows above their critical / warning bar — the same counts the tiles show. */
  crit: number;
  warn: number;
  /** Rows this page can build — a COUNT, not the constant 42 that used to sit here. */
  signalsWired: number;
}) {
  const tq = useTranslations("quality");
  const items = [
    { icon: Radio, label: tq("statusbar.realtime"), tone: "text-[var(--tessera-green)]" },
    { icon: ShieldCheck, label: tq("statusbar.truthChain") },
    { icon: Landmark, label: tq("statusbar.truthSource") },
    { icon: ListChecks, label: tq("statusbar.signals", { n: signalsWired }) },
  ];
  const status =
    crit > 0
      ? {
          text: tq("statusbar.systemCrit", { n: crit }),
          cls: "text-[var(--tessera-fg-danger)]",
          dot: "bg-red-500",
        }
      : warn > 0
        ? {
            text: tq("statusbar.systemWarn", { n: warn }),
            cls: "text-[var(--tessera-fg-warning)]",
            dot: "bg-amber-500",
          }
        : {
            text: tq("statusbar.systemOk"),
            cls: "text-[var(--tessera-green)]",
            dot: "bg-[var(--tessera-green)]",
          };
  return (
    <div className="mt-auto -mx-3 flex h-9 items-center gap-4 overflow-hidden border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-[0.7rem] text-[var(--tessera-text-muted)]">
      {items.map((it) => (
        <span key={it.label} className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
          <it.icon className={`h-3.5 w-3.5 shrink-0 ${it.tone ?? ""}`} />
          <span className="truncate">{it.label}</span>
        </span>
      ))}
      <span
        className={`ml-auto flex shrink-0 items-center gap-1.5 whitespace-nowrap ${status.cls}`}
      >
        <span className={`h-2 w-2 rounded-full ${status.dot}`} />
        {status.text}
      </span>
    </div>
  );
}

const TAB_META: Record<TabKey, typeof Gauge> = {
  overview: Gauge,
  signals: ListChecks,
};

function TabBar({ active, onChange }: { active: TabKey; onChange: (tab: TabKey) => void }) {
  const tq = useTranslations("quality");
  return (
    <TabStrip
      accent="green"
      active={active}
      onChange={onChange}
      items={TAB_DEFS.map((key) => ({
        key,
        label: tq(`tabs.${key}`),
        icon: TAB_META[key],
      }))}
    />
  );
}
