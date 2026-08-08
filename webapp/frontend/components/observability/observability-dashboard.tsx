"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  CalendarClock,
  ChevronRight,
  FileDown,
  Gauge,
  GitCompareArrows,
  Landmark,
  ListChecks,
  type LucideIcon,
  Play,
  Radio,
  Route,
  ShieldCheck,
  Stethoscope,
  TrendingUp,
} from "lucide-react";
// `Route` is already taken in this module by the lucide ICON of that name — alias Next's
// typed-route type so the cast below cannot silently mean the icon.
import type { Route as NextRoute } from "next";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { type ReactNode, useState } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { TabStrip } from "@/components/cockpit/tab-strip";
import { EVAL_PATHNAME, EVAL_VIEW_VALUE, evalQuery } from "@/components/eval/eval-route";
import { EvolutionChart } from "@/components/observability/evolution-chart";
import { FailureDistribution } from "@/components/observability/failed-cases";
import {
  CostQualityScatter,
  EtatActuel,
  FailureBars,
  FaithGroundingScatter,
  JudgeMini,
  OverviewKpis,
  PredictiveSignals,
  PriorityCases,
  RecommendedActions,
  RegressionsByRelease,
  RootCauseDiagnostic,
  RunsPassRateTable,
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Truncate } from "@/components/ui/truncate";
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
  fetchModelComparison,
  fetchPiiLeak,
  fetchRefusal,
  fetchRegressionRisk,
  fetchReleaseStatus,
  fetchRouting,
  fetchRuns,
  fetchSLO,
  fetchScoreSeries,
  fetchSignalCoverage,
  fetchSignalStatusTrend,
  fetchToolValidity,
  fetchToxicity,
  fetchWhatChanged,
} from "@/lib/api/client";
import type { FailedCasesReport, ReleaseStatus, RunRegistry, WhatChanged } from "@/lib/api/schemas";
import { fmtRunDay } from "@/lib/eval-score";
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
    queryKey: ["metric-pairs", "faithfulness", "grounding", asOf],
    queryFn: ({ signal }) =>
      fetchMetricPairs(signal, "faithfulness", "grounding", asOf ?? undefined),
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

  // Documented failure catalogue is static per locale (no polling, no as-of).
  const failedCases = useQuery({
    queryKey: ["failed-cases", locale],
    queryFn: ({ signal }) => fetchFailedCases(signal, locale),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: tab === "overview" || tab === "signals",
  });

  // Eval run archive — refreshes slowly; the report files change rarely. The archive's own
  // tab crossed to the evaluations view, which reads this endpoint under the SAME query key:
  // React Query then serves one cached answer to both, so the duplication costs no request.
  // Kept here because the overview's KPI strip, pass-rate table and right rail read it too.
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: ({ signal }) => fetchRuns(signal),
    refetchInterval: 60_000,
    enabled: tab === "overview",
  });

  const modelComparison = useQuery({
    queryKey: ["model-comparison"],
    queryFn: ({ signal }) => fetchModelComparison(signal),
    refetchInterval: 60_000,
    enabled: tab === "overview",
  });

  const releaseStatus = useQuery({
    queryKey: ["release-status"],
    queryFn: ({ signal }) => fetchReleaseStatus(signal),
    refetchInterval: 60_000,
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
    enabled: tab === "overview" || tab === "signals",
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
      window: tq("temporal.window"),
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
              {tq("rail.signalsFunnel", {
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
            {/* It said "Lancer" and it SWITCHED TABS. No endpoint starts an evaluation — the
                harness is a command (`scripts/run_eval.py`) — so the promise could never be
                kept, and a primary green button is the loudest place to make one. Disabled
                with the reason in its title, the way every other unwired action on this page
                already is; relabelling it "show the runs" would keep a control that competes
                for the eye with the actions that do work. */}
            <span title={tq("cta.runEvalNotWired")} className="flex">
              <Button
                size="sm"
                disabled
                className="h-8 gap-2 border border-[#007a55] bg-[#005c42] text-xs text-[#d6f0e3] hover:bg-[#006d4e]"
              >
                <Play className="h-3.5 w-3.5" />
                {tq("cta.runEval")}
              </Button>
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => openTarget("models")}
              className="h-8 gap-2 text-xs"
            >
              <GitCompareArrows className="h-3.5 w-3.5" />
              {tq("cta.compareModels")}
            </Button>
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

      {/* KPI strip (unlabeled, full page width above the zones+rail — image normative) */}
      {tab === "overview" ? (
        <OverviewKpis
          sloPct={sloPct}
          faithfulness={scoreSeries.data}
          grounding={groundingSeries.data}
          hallucination={hallucinationSeries.data}
          nonRegression={releaseStatus.data?.non_regression_rate ?? null}
          nRegressions={releaseStatus.data?.n_regressions ?? null}
          kappa={calibration.data?.kappa ?? null}
          evaluatedCount={runs.data?.catalogue_cases ?? null}
          loading={scoreSeries.isLoading}
          onOpen={openTarget}
        />
      ) : null}

      <div
        className={`grid gap-2 ${tab === "signals" ? "" : "lg:grid-cols-[minmax(0,1fr)_340px]"}`}
      >
        <div className="flex min-w-0 flex-col gap-2">
          {tab === "overview" && (
            <>
              {/* Each zone is a translucent band holding real sub-cards (like the
                  Sécurité & privacy page). Row 1: A | B with B at 3fr so its three
                  sub-cards get real width; row 2: C | D. */}
              <div className="grid items-start gap-2 xl:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]">
                <Zone
                  label={tq("sec.etat")}
                  icon={Gauge}
                  iconClassName="text-[var(--tessera-fg-info)]"
                  info={<SectionInfo title={tq("sec.etat")} explainKey="etat" />}
                >
                  <EtatActuel
                    summary={signalSummary}
                    release={releaseStatus.data}
                    evolutionDelta={scoreSeries.data?.delta ?? null}
                    scorePct={sloPct}
                    series={scoreSeries.data}
                  />
                </Zone>

                <Zone
                  label={tq("sec.diagnostic")}
                  icon={Stethoscope}
                  iconClassName="text-[var(--tessera-fg-warning)]"
                  info={<SectionInfo title={tq("sec.diagnostic")} explainKey="diagnostic" />}
                >
                  <div className="grid items-start gap-2 xl:grid-cols-3">
                    <FailureBars
                      report={failedCases.data}
                      loading={failedCases.isLoading}
                      onOpen={openTarget}
                    />
                    <JudgeMini
                      data={calibration.data}
                      loading={calibration.isLoading}
                      onOpen={openTarget}
                    />
                    <PriorityCases
                      report={failedCases.data}
                      loading={failedCases.isLoading}
                      onOpen={openTarget}
                    />
                  </div>
                  <div className="mt-2">
                    <RootCauseDiagnostic
                      whatChanged={whatChanged.data}
                      regressions={releaseStatus.data?.regressions ?? []}
                    />
                  </div>
                </Zone>
              </div>

              <div className="grid items-start gap-2 md:grid-cols-2">
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
                  label={tq("sec.actions")}
                  icon={ListChecks}
                  iconClassName="text-[var(--tessera-fg-success)]"
                  info={<SectionInfo title={tq("sec.actions")} explainKey="actions" />}
                >
                  <RecommendedActions
                    regressions={releaseStatus.data?.regressions ?? []}
                    failed={failedCases.data}
                    onOpen={openTarget}
                    onEvidence={downloadQualityEvidence}
                  />
                </Zone>
              </div>
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
                <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
                <ThemeDistribution rows={signalRows} />
                <SignalHeatmap rows={signalRows} />
              </div>
            </div>
          )}
        </div>

        {tab === "signals" ? null : (
          <RightRail
            failed={failedCases.data}
            // "Aucun problème" is the most reassuring sentence on this page, and an unread
            // list produces it exactly as a clean run does. The rail must be able to tell
            // them apart; only the query knows which happened.
            failedUnavailable={failedCases.isError && !failedCases.data}
            release={releaseStatus.data}
            whatChanged={whatChanged.data}
            runs={runs.data}
            onOpen={openTarget}
            onEvidence={downloadQualityEvidence}
          />
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

      {/* Full-width analytics row below the [main · rail] grid (image normative):
          Pass-rate des runs | Évolution | Répartition | Faith×Grounding | Régressions
          par release | Coût vs qualité — six charts spanning the whole page width. */}
      {tab === "overview" ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
          <RunsPassRateTable registry={runs.data} loading={runs.isLoading} />
          <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
          <FailureDistribution report={failedCases.data} loading={failedCases.isLoading} />
          <FaithGroundingScatter
            pairs={metricPairs.data}
            loading={metricPairs.isLoading}
            onOpen={openTarget}
          />
          <RegressionsByRelease release={releaseStatus.data} loading={releaseStatus.isLoading} />
          <CostQualityScatter data={modelComparison.data} loading={modelComparison.isLoading} />
        </div>
      ) : null}

      <StatusBar release={releaseStatus.data} signalsWired={signalFunnel.wired} />
    </div>
  );
}

/** Thin status bar that closes the page (image normative). It rides at the end
 * of the content — not `sticky`, which left it floating mid-scroll and masking
 * the rows behind it once the page grew past one viewport. `mt-auto` keeps it at
 * the bottom when the content is short. */
function StatusBar({
  release,
  signalsWired,
}: {
  release: ReleaseStatus | undefined;
  /** Rows this page can build — a COUNT, not the constant 42 that used to sit here. */
  signalsWired: number;
}) {
  const tq = useTranslations("quality");
  const dataset = release?.current ? `Llama · ${release.current.version}` : "—";
  const updated = release?.current?.date ?? "—";
  const items = [
    { icon: Radio, label: tq("statusbar.realtime"), tone: "text-[var(--tessera-green)]" },
    { icon: Boxes, label: `${tq("statusbar.dataset")} : ${dataset}` },
    { icon: ShieldCheck, label: tq("statusbar.truthChain") },
    { icon: Landmark, label: tq("statusbar.truthSource") },
    { icon: CalendarClock, label: `${tq("statusbar.lastUpdate")} : ${updated}` },
    { icon: ListChecks, label: tq("statusbar.signals", { n: signalsWired }) },
  ];
  return (
    <div className="mt-auto -mx-3 flex h-9 items-center gap-4 overflow-hidden border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-[0.7rem] text-[var(--tessera-text-muted)]">
      {items.map((it) => (
        <span key={it.label} className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
          <it.icon className={`h-3.5 w-3.5 shrink-0 ${it.tone ?? ""}`} />
          <span className="truncate">{it.label}</span>
        </span>
      ))}
      <span className="ml-auto flex shrink-0 items-center gap-1.5 whitespace-nowrap text-[var(--tessera-green)]">
        <span className="h-2 w-2 rounded-full bg-[var(--tessera-green)]" />
        {tq("statusbar.systemOk")}
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

/** Right rail (image normative): Derniers problèmes · Release actuelle · Actions
 * rapides · Activités récentes — all fed by live data, links into the tabs. */
function RightRail({
  failed,
  failedUnavailable = false,
  release,
  whatChanged,
  runs,
  onOpen,
  onEvidence,
}: {
  failed: FailedCasesReport | undefined;
  /** The failed-cases read did not answer — distinct from "it answered, and there are none". */
  failedUnavailable?: boolean;
  release: ReleaseStatus | undefined;
  whatChanged: WhatChanged | undefined;
  runs: RunRegistry | undefined;
  /** A destination, not a tab: three of the four this rail names now live on the other view. */
  onOpen: (target: QualityTarget) => void;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const current = release?.current ?? null;
  const nReg = release?.n_regressions ?? 0;
  const blocked = nReg > 0;
  const impact = nReg === 0 ? "low" : nReg <= 2 ? "medium" : "high";
  const problems = (failed?.cases ?? []).slice(0, 4);
  const quick: { label: string; icon: typeof Activity; action: () => void }[] = [
    { label: tq("rr.linkRuns"), icon: Activity, action: () => onOpen("runs") },
    { label: tq("rr.linkTraces"), icon: Route, action: () => onOpen("runs") },
    { label: tq("rr.linkDataset"), icon: Boxes, action: () => onOpen("runs") },
    { label: tq("rr.linkEvidence"), icon: FileDown, action: onEvidence },
  ];
  // Recent activity, derived from real data: the latest run, the release, the diff.
  const latestRun = [...(runs?.runs ?? [])].sort((a, b) => b.run_at.localeCompare(a.run_at))[0];
  const activity: { key: string; label: string; detail: string }[] = [];
  if (latestRun) {
    activity.push({
      key: "run",
      label: tq("rr.actRun", { n: latestRun.total }),
      detail: fmtRunDay(latestRun.run_at),
    });
  }
  if (current) {
    activity.push({
      key: "release",
      label: tq(blocked ? "rr.actReleaseBlocked" : "rr.actReleaseDeployed", {
        v: current.version,
      }),
      detail: current.date ?? "",
    });
  }
  for (const c of whatChanged?.changes ?? []) {
    activity.push({
      key: c.field,
      label: c.field,
      detail: `${c.before.slice(0, 8)} → ${c.after.slice(0, 8)}`,
    });
  }

  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2">
        {/* Derniers problèmes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.problems")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            {problems.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">
                {failedUnavailable ? tq("rr.problemsUnavailable") : tq("rr.noProblems")}
              </p>
            ) : (
              problems.map((p) => (
                <div
                  key={p.case_id}
                  className="flex items-start gap-1.5 text-[0.7rem]"
                  title={`${p.title} · ${p.severity}`}
                >
                  <span
                    className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                      p.severity === "critical"
                        ? "bg-red-500"
                        : p.severity === "high"
                          ? "bg-amber-500"
                          : "bg-[var(--muted-foreground)]"
                    }`}
                  />
                  <span className="line-clamp-2 min-w-0 flex-1 leading-snug">{p.title}</span>
                </div>
              ))
            )}
            <RailLink onClick={() => onOpen("failed")}>{tq("rr.seeCases")}</RailLink>
          </CardContent>
        </Card>

        {/* Release actuelle */}
        {current ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{tq("rr.release")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1 text-[0.7rem]">
              <div className="flex items-center gap-2">
                <span className="font-serif text-base font-semibold tabular-nums">
                  {current.version}
                </span>
                <Badge tone={blocked ? "danger" : "success"}>
                  {blocked ? tq("rr.blocked") : tq("rr.inProd")}
                </Badge>
              </div>
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-[var(--muted-foreground)]">{tq("rr.impact")}</span>
                <span
                  className={
                    impact === "high"
                      ? "text-[var(--tessera-fg-danger)]"
                      : impact === "medium"
                        ? "text-[var(--tessera-fg-warning)]"
                        : "text-[var(--muted-foreground)]"
                  }
                >
                  {tq(`exec.etat.${impact}`)}
                </span>
              </div>
              {current.date ? (
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-[var(--muted-foreground)]">{tq("rr.openedAt")}</span>
                  <span className="tabular-nums">{current.date}</span>
                </div>
              ) : null}
              <RailLink onClick={() => onOpen("models")}>{tq("rr.seeReleases")}</RailLink>
            </CardContent>
          </Card>
        ) : null}

        {/* Actions rapides */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.actions")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-0.5">
            {quick.map((q) => (
              <button
                key={q.label}
                type="button"
                onClick={q.action}
                className="flex items-center gap-2 rounded-md px-1.5 py-0.5 text-left text-[0.7rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
              >
                <q.icon className="h-3 w-3 shrink-0" />
                <span className="truncate">{q.label}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Activités récentes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.activity")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            {activity.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("rr.noActivity")}</p>
            ) : (
              activity.slice(0, 3).map((a) => (
                <div key={a.key} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tessera-green)]" />
                  <Truncate className="min-w-0 flex-1 text-[0.7rem]">{a.label}</Truncate>
                  <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                    {a.detail}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </aside>
  );
}

/** Small "see all →" link used at the foot of a right-rail card. */
function RailLink({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--tessera-green)] hover:underline"
    >
      {children}
      <ChevronRight className="h-3 w-3" />
    </button>
  );
}
