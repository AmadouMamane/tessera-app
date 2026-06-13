"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
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
  Play,
  Radio,
  Route,
  Scale,
  ShieldCheck,
  Siren,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { EvolutionChart } from "@/components/observability/evolution-chart";
import { FailedBoard, FailedRail } from "@/components/observability/failed-board";
import { FailureDistribution } from "@/components/observability/failed-cases";
import { JudgeCalibration } from "@/components/observability/judge-calibration";
import { ModelsBoard } from "@/components/observability/models-board";
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
  DatasetsTable,
  RunContextPanel,
  RunsCharts,
  RunsEvalTable,
  RunsKpis,
  RunsRail,
} from "@/components/observability/runs-datasets";
import {
  SignalHeatmap,
  SignalKpis,
  type SignalRow,
  SignalsRail,
  SignalsTable,
  ThemeDistribution,
  buildSignalRows,
} from "@/components/observability/signals-table";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  fetchAIAct,
  fetchAnomalies,
  fetchCalibration,
  fetchCitations,
  fetchConformance,
  fetchContradictions,
  fetchCorpusFreshness,
  fetchCost,
  fetchEvalDatasets,
  fetchFailedCases,
  fetchFailedRuns,
  fetchFailureClusters,
  fetchFailurePredictor,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchIntent,
  fetchJudgeConsensus,
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
  fetchSignalStatusTrend,
  fetchToolValidity,
  fetchToxicity,
  fetchWhatChanged,
} from "@/lib/api/client";
import type {
  FailedCasesReport,
  FailedRunCase,
  ReleaseStatus,
  RunRegistry,
  RunSummary,
  WhatChanged,
} from "@/lib/api/schemas";

const POLL_MS = 5_000;

// The Qualité IA page covers 42 of the 200-signal global catalogue (normative — see
// docs/ui-reference/qualite-ia-ui-reference/README.md). This is a coverage framing,
// not a live count, so it is a constant rather than a fabricated metric.
const QUALITY_SIGNALS = 42;
const QUALITY_CATALOGUE = 200;

const TAB_DEFS = ["overview", "signals", "runs", "failed", "models", "judge"] as const;
type TabKey = (typeof TAB_DEFS)[number];

export function ObservabilityDashboard() {
  const t = useTranslations("observability");
  const tq = useTranslations("quality");
  const locale = useLocale();
  const [tab, setTab] = useState<TabKey>("overview");
  const [selectedSignal, setSelectedSignal] = useState<SignalRow | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null);
  const [selectedFailed, setSelectedFailed] = useState<FailedRunCase | null>(null);
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();

  const slo = useQuery({
    queryKey: ["slo", asOf],
    queryFn: ({ signal }) => fetchSLO(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL_MS,
  });

  const scoreSeries = useQuery({
    queryKey: ["score-series", "faithfulness", asOf],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "faithfulness"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const groundingSeries = useQuery({
    queryKey: ["score-series", "grounding", asOf],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "grounding"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const metricPairs = useQuery({
    queryKey: ["metric-pairs", "faithfulness", "grounding", asOf],
    queryFn: ({ signal }) =>
      fetchMetricPairs(signal, "faithfulness", "grounding", asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const hallucinationSeries = useQuery({
    queryKey: ["score-series", "hallucination", asOf],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "hallucination"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  // Documented failure catalogue is static per locale (no polling, no as-of).
  const failedCases = useQuery({
    queryKey: ["failed-cases", locale],
    queryFn: ({ signal }) => fetchFailedCases(signal, locale),
    staleTime: Number.POSITIVE_INFINITY,
  });

  // Real failed cases from the run archive (Cas échoués tab) — refresh slowly.
  const failedRuns = useQuery({
    queryKey: ["failed-runs"],
    queryFn: ({ signal }) => fetchFailedRuns(signal),
    refetchInterval: 60_000,
  });

  // Eval run archive — refreshes slowly; the report files change rarely.
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: ({ signal }) => fetchRuns(signal),
    refetchInterval: 60_000,
  });

  const modelComparison = useQuery({
    queryKey: ["model-comparison"],
    queryFn: ({ signal }) => fetchModelComparison(signal),
    refetchInterval: 60_000,
  });

  // Real corpus inventory — feeds the KPI strip + pipeline freshness fallback.
  const corpusFreshness = useQuery({
    queryKey: ["corpus-freshness"],
    queryFn: ({ signal }) => fetchCorpusFreshness(signal),
    refetchInterval: 60_000,
  });

  // Themed quality datasets (failure-catalogue themes × runs) — the Runs tab table.
  const evalDatasets = useQuery({
    queryKey: ["eval-datasets"],
    queryFn: ({ signal }) => fetchEvalDatasets(signal),
    refetchInterval: 60_000,
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
    queryKey: ["toxicity", asOf],
    queryFn: ({ signal }) => fetchToxicity(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const localization = useQuery({
    queryKey: ["localization"],
    queryFn: ({ signal }) => fetchLocalization(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const aiAct = useQuery({
    queryKey: ["ai-act", asOf],
    queryFn: ({ signal }) => fetchAIAct(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Calibration is computed server-side (slow, judge over a gold set) and cached,
  // so fetch it once rather than polling.
  const calibration = useQuery({
    queryKey: ["calibration"],
    queryFn: ({ signal }) => fetchCalibration(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const judgeDrift = useQuery({
    queryKey: ["judge-drift", asOf],
    queryFn: ({ signal }) => fetchJudgeDrift(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Grounding-metric drift for the Comparaison des modèles "Drift & stabilité" panel.
  const groundingDrift = useQuery({
    queryKey: ["judge-drift", "grounding", asOf],
    queryFn: ({ signal }) => fetchJudgeDrift(signal, asOf ?? undefined, "grounding"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Forward-looking regression risk for the "Signaux prédictifs" column (image 00).
  const regressionRisk = useQuery({
    queryKey: ["regression-risk", asOf],
    queryFn: ({ signal }) => fetchRegressionRisk(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Per-severity-band score-count trend for the Signaux KPI tiles (image 01).
  const signalStatusTrend = useQuery({
    queryKey: ["signal-status-trend", asOf],
    queryFn: ({ signal }) => fetchSignalStatusTrend(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Multi-judge consensus runs a panel of local judges server-side and is cached;
  // fetch once (it is slow and stable per process).
  const judgeConsensus = useQuery({
    queryKey: ["judge-consensus"],
    queryFn: ({ signal }) => fetchJudgeConsensus(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const firewall = useQuery({
    queryKey: ["firewall-efficacy"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const tools = useQuery({
    queryKey: ["tool-validity", asOf],
    queryFn: ({ signal }) => fetchToolValidity(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const routing = useQuery({
    queryKey: ["routing"],
    queryFn: ({ signal }) => fetchRouting(signal),
    refetchInterval: 15_000,
  });

  const piiLeak = useQuery({
    queryKey: ["pii-leak", asOf],
    queryFn: ({ signal }) => fetchPiiLeak(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const contradictions = useQuery({
    queryKey: ["contradictions"],
    queryFn: ({ signal }) => fetchContradictions(signal),
    refetchInterval: 20_000,
  });

  const whatChanged = useQuery({
    queryKey: ["what-changed", asOf],
    queryFn: ({ signal }) => fetchWhatChanged(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 20_000,
  });

  const anomalies = useQuery({
    queryKey: ["anomalies", asOf],
    queryFn: ({ signal }) => fetchAnomalies(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 20_000,
  });

  const refusal = useQuery({
    queryKey: ["refusal"],
    queryFn: ({ signal }) => fetchRefusal(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const citations = useQuery({
    queryKey: ["citations"],
    queryFn: ({ signal }) => fetchCitations(signal),
    refetchInterval: 15_000,
  });

  const localeFormat = useQuery({
    queryKey: ["locale-format"],
    queryFn: ({ signal }) => fetchLocaleFormat(signal),
    refetchInterval: 15_000,
  });

  const conformance = useQuery({
    queryKey: ["conformance", asOf],
    queryFn: ({ signal }) => fetchConformance(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const intent = useQuery({
    queryKey: ["intent"],
    queryFn: ({ signal }) => fetchIntent(signal),
    refetchInterval: 15_000,
  });

  const cost = useQuery({
    queryKey: ["cost", asOf],
    queryFn: ({ signal }) => fetchCost(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const funnel = useQuery({
    queryKey: ["funnel", asOf],
    queryFn: ({ signal }) => fetchFunnel(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  // Newest first for display.

  // Unified signal catalogue derived from the live reports (reference image 01).
  const signalRows = buildSignalRows(t, {
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
  });

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

  function downloadQualityEvidence() {
    const bundle = {
      generated_at: new Date().toISOString(),
      page: "quality",
      window: tq("temporal.window"),
      signals_covered: `${QUALITY_SIGNALS}/${QUALITY_CATALOGUE}`,
      slo: slo.data ?? null,
      refusal: refusal.data ?? null,
      conformance: conformance.data ?? null,
      calibration: calibration.data ?? null,
      toxicity: toxicity.data ?? null,
      pii_leak: piiLeak.data ?? null,
      ai_act: aiAct.data ?? null,
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
    <div className="flex flex-col gap-2">
      {/* Sticky chrome: tab bar + business actions on one row (image normative),
          the shared compact temporal rail (Live/Replay) below. */}
      <div className="sticky top-0 z-30 -mx-3 flex flex-col gap-1.5 bg-[var(--tessera-bg)] px-3 pb-1.5 pt-1.5 shadow-[0_-16px_0_0_var(--tessera-bg)]">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <TabBar active={tab} onChange={setTab} />
          <div className="flex shrink-0 items-center gap-2">
            <Button
              size="sm"
              onClick={() => setTab("runs")}
              className="h-8 gap-2 border border-[#007a55] bg-[#005c42] text-xs text-[#d6f0e3] hover:bg-[#006d4e]"
            >
              <Play className="h-3.5 w-3.5" />
              {tq("cta.runEval")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTab("models")}
              className="h-8 gap-2 text-xs"
            >
              <GitCompareArrows className="h-3.5 w-3.5" />
              {tq("cta.compareModels")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTab("runs")}
              className="h-8 gap-2 text-xs"
            >
              <Boxes className="h-3.5 w-3.5" />
              {tq("cta.openDataset")}
            </Button>
            <Button size="sm" onClick={downloadQualityEvidence} className="h-8 gap-2 text-xs">
              <FileDown className="h-3.5 w-3.5" />
              {tq("cta.evidence")}
            </Button>
          </div>
        </div>
        <TemporalRail
          mode={temporal.mode}
          liveStatus={tq("temporal.liveData")}
          timeline={railTimeline.data}
          sloTarget={slo.data?.target}
          selectedAt={temporal.selectedAt}
          onSelectedAtChange={temporal.setSelectedAt}
          periodKey={temporal.periodKey}
          onPeriodChange={temporal.setPeriodKey}
          onModeChange={temporal.changeMode}
        />
      </div>

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
          failedCount={failedCases.data?.n ?? null}
          loading={scoreSeries.isLoading}
        />
      ) : null}

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-2">
          {tab === "overview" && (
            <>
              {/* A · B · C · D as four side-by-side zones (image normative). The zones
                  are deliberately different heights ⇒ items-start (no stretch). */}
              <div className="grid items-start gap-2 lg:grid-cols-2 2xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1.15fr)_minmax(0,1.45fr)]">
                {/* A. État actuel */}
                <EtatActuel
                  summary={signalSummary}
                  release={releaseStatus.data}
                  evolutionDelta={scoreSeries.data?.delta ?? null}
                  scorePct={sloPct}
                  series={scoreSeries.data}
                />

                {/* B. Diagnostic racine — Répartition | Calibration | Cas prioritaires,
                    then the "Qu'est-ce qui a changé / Causes probables" diagnostic. */}
                <div className="flex min-w-0 flex-col gap-2">
                  <SectionLabel>{tq("sec.diagnostic")}</SectionLabel>
                  <div className="grid items-start gap-2 sm:grid-cols-3">
                    <FailureBars report={failedCases.data} loading={failedCases.isLoading} />
                    <JudgeMini data={calibration.data} loading={calibration.isLoading} />
                    <PriorityCases
                      report={failedCases.data}
                      loading={failedCases.isLoading}
                      onOpen={setTab}
                    />
                  </div>
                  <RootCauseDiagnostic
                    whatChanged={whatChanged.data}
                    regressions={releaseStatus.data?.regressions ?? []}
                  />
                </div>

                {/* C. Signaux prédictifs */}
                <PredictiveSignals
                  series={scoreSeries.data}
                  risk={regressionRisk.data}
                  drift={judgeDrift.data}
                  predictor={failurePredictor.data}
                  intent={intent.data}
                  localization={localization.data}
                  loading={regressionRisk.isLoading}
                />

                {/* D. Actions recommandées */}
                <RecommendedActions
                  regressions={releaseStatus.data?.regressions ?? []}
                  failed={failedCases.data}
                  onOpen={setTab}
                  onEvidence={downloadQualityEvidence}
                />
              </div>
            </>
          )}

          {tab === "signals" && (
            <div className="flex flex-col gap-2">
              {/* KPI strip + registre + analytics row (normative 01). */}
              <SignalKpis
                rows={signalRows}
                trend={signalStatusTrend.data}
                catalogue={QUALITY_CATALOGUE}
              />
              <SignalsTable
                rows={signalRows}
                selectedKey={selectedSignal?.key ?? null}
                onSelect={setSelectedSignal}
              />
              <div className="grid gap-2 lg:grid-cols-3">
                <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
                <ThemeDistribution rows={signalRows} />
                <SignalHeatmap rows={signalRows} />
              </div>
            </div>
          )}

          {tab === "runs" && (
            <div className="flex flex-col gap-2">
              {/* KPI strip + [runs · datasets | contexte] + six mini-charts (image 02). */}
              <RunsKpis
                registry={runs.data}
                release={releaseStatus.data}
                freshness={corpusFreshness.data}
                datasets={evalDatasets.data}
              />
              <div className="grid gap-2 2xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] 2xl:items-start">
                <div className="flex flex-col gap-2">
                  <RunsEvalTable
                    registry={runs.data}
                    selectedId={(selectedRun ?? runs.data?.runs[0])?.run_id ?? null}
                    onSelect={setSelectedRun}
                  />
                  <DatasetsTable report={evalDatasets.data} />
                </div>
                <RunContextPanel
                  run={selectedRun ?? runs.data?.runs[0]}
                  release={releaseStatus.data}
                  onEvidence={downloadQualityEvidence}
                />
              </div>
              <RunsCharts
                registry={runs.data}
                models={modelComparison.data}
                datasets={evalDatasets.data}
              />
            </div>
          )}

          {tab === "failed" && (
            <FailedBoard
              report={failedRuns.data}
              selected={selectedFailed ?? failedRuns.data?.cases[0] ?? null}
              onSelect={setSelectedFailed}
            />
          )}

          {tab === "models" && (
            <ModelsBoard
              comparison={modelComparison.data}
              calibration={calibration.data}
              release={releaseStatus.data}
              registry={runs.data}
              faithDrift={judgeDrift.data}
              groundingDrift={groundingDrift.data}
              consensus={judgeConsensus.data}
            />
          )}

          {tab === "judge" && (
            <JudgeCalibration
              data={calibration.data}
              drift={judgeDrift.data}
              consensus={judgeConsensus.data}
              loading={calibration.isLoading}
            />
          )}
        </div>

        {tab === "signals" ? (
          <SignalsRail
            selected={selectedSignal}
            rows={signalRows}
            failed={failedCases.data}
            release={releaseStatus.data}
            whatChanged={whatChanged.data}
            onOpen={setTab}
            onEvidence={downloadQualityEvidence}
          />
        ) : tab === "runs" ? (
          <RunsRail
            registry={runs.data}
            datasets={evalDatasets.data}
            release={releaseStatus.data}
          />
        ) : tab === "failed" ? (
          <FailedRail
            failedCase={selectedFailed ?? failedRuns.data?.cases[0]}
            release={releaseStatus.data}
            onEvidence={downloadQualityEvidence}
          />
        ) : (
          <RightRail
            failed={failedCases.data}
            release={releaseStatus.data}
            whatChanged={whatChanged.data}
            runs={runs.data}
            onOpen={setTab}
            onEvidence={downloadQualityEvidence}
          />
        )}
      </div>

      {/* Full-width analytics row below the [main · rail] grid (image normative):
          Pass-rate des runs | Évolution | Répartition | Faith×Grounding | Régressions
          par release | Coût vs qualité — six charts spanning the whole page width. */}
      {tab === "overview" ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
          <RunsPassRateTable registry={runs.data} loading={runs.isLoading} />
          <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
          <FailureDistribution report={failedCases.data} loading={failedCases.isLoading} />
          <FaithGroundingScatter pairs={metricPairs.data} loading={metricPairs.isLoading} />
          <RegressionsByRelease release={releaseStatus.data} loading={releaseStatus.isLoading} />
          <CostQualityScatter data={modelComparison.data} loading={modelComparison.isLoading} />
        </div>
      ) : null}

      <StatusBar release={releaseStatus.data} />
    </div>
  );
}

/** Compact section heading (A. / B. / C. / D.) above each overview row. */
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
      {children}
    </h2>
  );
}

/** Thin sticky status bar pinned to the bottom of the page (image normative). */
function StatusBar({ release }: { release: ReleaseStatus | undefined }) {
  const tq = useTranslations("quality");
  const dataset = release?.current ? `Llama · ${release.current.version}` : "—";
  const updated = release?.current?.date ?? "—";
  const items = [
    { icon: Radio, label: tq("statusbar.realtime"), tone: "text-[var(--tessera-green)]" },
    { icon: Boxes, label: `${tq("statusbar.dataset")} : ${dataset}` },
    { icon: ShieldCheck, label: tq("statusbar.truthChain") },
    { icon: Landmark, label: tq("statusbar.truthSource") },
    { icon: CalendarClock, label: `${tq("statusbar.lastUpdate")} : ${updated}` },
    { icon: ListChecks, label: tq("statusbar.signals", { n: QUALITY_SIGNALS }) },
  ];
  return (
    <div className="sticky bottom-0 z-20 -mx-3 flex h-9 items-center gap-4 overflow-hidden border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-[0.7rem] text-[var(--tessera-text-muted)]">
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
  runs: Boxes,
  failed: Siren,
  models: GitCompareArrows,
  judge: Scale,
};

function TabBar({ active, onChange }: { active: TabKey; onChange: (tab: TabKey) => void }) {
  const tq = useTranslations("quality");
  return (
    <nav className="flex min-w-0 items-center gap-1 overflow-x-auto border-b border-[var(--tessera-border)]">
      {TAB_DEFS.map((key) => {
        const Icon = TAB_META[key];
        const on = key === active;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[0.8rem] transition-colors ${
              on
                ? "border-[var(--tessera-green)] font-medium text-[var(--tessera-text)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Icon className="h-4 w-4" />
            {tq(`tabs.${key}`)}
          </button>
        );
      })}
    </nav>
  );
}

/** Right rail (image normative): Derniers problèmes · Release actuelle · Actions
 * rapides · Activités récentes — all fed by live data, links into the tabs. */
function RightRail({
  failed,
  release,
  whatChanged,
  runs,
  onOpen,
  onEvidence,
}: {
  failed: FailedCasesReport | undefined;
  release: ReleaseStatus | undefined;
  whatChanged: WhatChanged | undefined;
  runs: RunRegistry | undefined;
  onOpen: (tab: TabKey) => void;
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
      detail: latestRun.run_at.slice(0, 10),
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
      <div className="flex flex-col gap-2 xl:sticky xl:top-28">
        {/* Derniers problèmes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.problems")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            {problems.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("rr.noProblems")}</p>
            ) : (
              problems.map((p) => (
                <div key={p.case_id} className="flex items-center gap-1.5 text-[0.7rem]">
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      p.severity === "critical"
                        ? "bg-red-500"
                        : p.severity === "high"
                          ? "bg-amber-500"
                          : "bg-[var(--muted-foreground)]"
                    }`}
                  />
                  <span className="min-w-0 flex-1 truncate">{p.title}</span>
                  <span className="shrink-0 text-[0.6rem] text-[var(--muted-foreground)]">
                    {p.severity}
                  </span>
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
                      ? "text-red-500"
                      : impact === "medium"
                        ? "text-amber-500"
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
                  <span className="min-w-0 flex-1 truncate text-[0.7rem]">{a.label}</span>
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
