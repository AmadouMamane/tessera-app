"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Boxes, Siren } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { FailedBoard, FailedRail } from "@/components/observability/failed-board";
import { JudgeCalibration, JudgeRail } from "@/components/observability/judge-calibration";
import {
  DEFAULT_PERIOD,
  ModelsBoard,
  type ModelsPeriod,
  ModelsPeriodRail,
} from "@/components/observability/models-board";
import {
  DatasetsTable,
  RunContextPanel,
  RunsCharts,
  RunsEvalTable,
  RunsKpis,
  RunsRail,
} from "@/components/observability/runs-datasets";
import {
  fetchCalibration,
  fetchCorpusFreshness,
  fetchEmbeddingSkew,
  fetchEvalDatasets,
  fetchFailedRuns,
  fetchJudgeConsensus,
  fetchJudgeDrift,
  fetchModelComparison,
  fetchReleaseStatus,
  fetchRuns,
} from "@/lib/api/client";
import type { FailedRunCase, RunSummary } from "@/lib/api/schemas";
import { useWindowStore } from "@/lib/stores/window-store";

/** The tabs that crossed the boundary. Declared as a union so a caller cannot mount this on
 * `cases`/`runs`/`compare`, which the server renders from the sweep and this component knows
 * nothing about. */
export type EvalDashboardTab = "archive" | "failed" | "models" | "judge";

/**
 * The four eval-archive surfaces, on the view that asks their question.
 *
 * They spent their life as tabs of the *monitoring* dashboard, next to signals sampled from
 * production. Not one of them reads a live turn: three read the report archive under
 * `eval/reports`, the fourth reads the judge's human gold set. Every one of them answers
 * "should this go live" — which is this view's entire question, and not the other one's.
 *
 * They are CLIENT-side because they always were: React Query, polling, local selection state,
 * two detail drawers. The view around them is server-rendered from the sweep, so this component
 * is the seam — and a seam is exactly where a Server Component may not hand a function across
 * (a `ComponentType` prop crashed this page once already; the gate cannot see it, only the
 * browser can). Nothing crosses into here but a string.
 *
 * On the temporal reading: this view carries no replay rail, so `asOf` is always *now*. Only
 * `judgeDrift` is windowed at all, and it takes the same global period the rest of the cockpit
 * reads. Inventing a second, local time control here would let the same drift number differ
 * between two screens for a reason neither of them states.
 */
export function EvalDashboard({ tab }: { tab: EvalDashboardTab }) {
  const tq = useTranslations("quality");
  const te = useTranslations("eval.population");
  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null);
  const [selectedFailed, setSelectedFailed] = useState<FailedRunCase | null>(null);
  const [modelsPeriod, setModelsPeriod] = useState<ModelsPeriod>(DEFAULT_PERIOD);
  const period = useWindowStore((st) => st.period);

  // ── The archive (`eval/reports`), read by three of the four tabs ─────────────────────────
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: ({ signal }) => fetchRuns(signal),
    refetchInterval: 60_000,
    enabled: tab === "archive" || tab === "models",
  });

  const modelComparison = useQuery({
    queryKey: ["model-comparison"],
    queryFn: ({ signal }) => fetchModelComparison(signal),
    refetchInterval: 60_000,
    enabled: tab === "archive" || tab === "models",
  });

  const releaseStatus = useQuery({
    queryKey: ["release-status"],
    queryFn: ({ signal }) => fetchReleaseStatus(signal),
    refetchInterval: 60_000,
  });

  const failedRuns = useQuery({
    queryKey: ["failed-runs"],
    queryFn: ({ signal }) => fetchFailedRuns(signal),
    refetchInterval: 60_000,
    enabled: tab === "failed",
  });

  const corpusFreshness = useQuery({
    queryKey: ["corpus-freshness"],
    queryFn: ({ signal }) => fetchCorpusFreshness(signal),
    refetchInterval: 60_000,
    enabled: tab === "archive",
  });

  // Query/corpus embedding lineage, measured from the model active at query time and the
  // fingerprints persisted at ingestion. Its health-registry link follows the tab across the
  // boundary: it used to point at `?tab=runs`, a dashboard tab that no longer exists.
  const embeddingSkew = useQuery({
    queryKey: ["embedding-skew"],
    queryFn: ({ signal }) => fetchEmbeddingSkew(signal),
    refetchInterval: 60_000,
    enabled: tab === "archive",
    meta: {
      health: {
        label: tq("dataSources.embeddingCompatibility"),
        href: "/surveiller/qualite-ia?vue=evaluations&tab=archive",
      },
    },
  });

  const evalDatasets = useQuery({
    queryKey: ["eval-datasets"],
    queryFn: ({ signal }) => fetchEvalDatasets(signal),
    refetchInterval: 60_000,
    enabled: tab === "archive",
  });

  // ── The judge (a human gold set), read by two tabs ────────────────────────────────────────
  // Computed server-side (slow: a judge over a gold set) and cached, so fetched once.
  const calibration = useQuery({
    queryKey: ["calibration"],
    queryFn: ({ signal }) => fetchCalibration(signal),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: tab === "models" || tab === "judge",
  });

  const judgeDrift = useQuery({
    queryKey: ["judge-drift", null, period],
    queryFn: ({ signal }) => fetchJudgeDrift(signal, undefined, undefined, period),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
    enabled: tab === "models" || tab === "judge",
  });

  const groundingDrift = useQuery({
    queryKey: ["judge-drift", "grounding", null, period],
    queryFn: ({ signal }) => fetchJudgeDrift(signal, undefined, "grounding", period),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
    enabled: tab === "models",
  });

  const judgeConsensus = useQuery({
    queryKey: ["judge-consensus"],
    queryFn: ({ signal }) => fetchJudgeConsensus(signal),
    staleTime: Number.POSITIVE_INFINITY,
    enabled: tab === "models" || tab === "judge",
  });

  /**
   * Evidence for THIS view — the archive and the judge, not the monitoring signals.
   *
   * The dashboard's bundle carried the signal funnel, the SLO, the firewall. None of that is
   * on screen here, and a bundle that exports what the operator cannot see is a bundle nobody
   * can check. `page` names which of the two it is.
   */
  function downloadEvalEvidence() {
    const bundle = {
      generated_at: new Date().toISOString(),
      page: "evaluations",
      surface: tab,
      window: period,
      release: releaseStatus.data ?? null,
      runs: runs.data ?? null,
      model_comparison: modelComparison.data ?? null,
      failed_runs: failedRuns.data ?? null,
      calibration: calibration.data ?? null,
      judge_drift: judgeDrift.data ?? null,
      judge_consensus: judgeConsensus.data ?? null,
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tessera-evaluations-evidence-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // `failed` fills the width — its board carries its own detail column — so it takes no rail.
  const rail =
    tab === "archive" ? (
      <RunsRail registry={runs.data} datasets={evalDatasets.data} release={releaseStatus.data} />
    ) : tab === "models" ? (
      <ModelsPeriodRail registry={runs.data} period={modelsPeriod} onApply={setModelsPeriod} />
    ) : tab === "judge" ? (
      <JudgeRail
        data={calibration.data}
        drift={judgeDrift.data}
        release={releaseStatus.data}
        onEvidence={downloadEvalEvidence}
      />
    ) : null;

  return (
    <div className="flex flex-col gap-2.5">
      {/* Which population this tab reads, in one sentence, above the numbers rather than in a
          legend. Three models score 90-92 % on the sweep and 52-87 % across the archive; the
          two statements are both true and neither is wrong, so the only thing that can go
          wrong is a reader who does not know which one they are looking at. */}
      <p className="text-[0.74rem] leading-relaxed text-[var(--tessera-text-muted)]">{te(tab)}</p>

      <div className={`grid gap-2 ${rail ? "lg:grid-cols-[minmax(0,1fr)_340px]" : ""}`}>
        <div className="flex min-w-0 flex-col gap-2">
          {tab === "archive" && (
            <div className="flex flex-col gap-2">
              <RunsKpis
                registry={runs.data}
                release={releaseStatus.data}
                freshness={corpusFreshness.data}
                datasets={evalDatasets.data}
                skewQuery={embeddingSkew}
              />
              <div className="flex flex-col gap-2">
                <RunsEvalTable
                  registry={runs.data}
                  selectedId={selectedRun?.run_id ?? null}
                  onSelect={setSelectedRun}
                />
                <DatasetsTable report={evalDatasets.data} />
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
              selected={selectedFailed}
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
              period={modelsPeriod}
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
        {rail}
      </div>

      {tab === "archive" && selectedRun ? (
        <DetailDrawer
          title={selectedRun.run_id}
          subtitle={`${selectedRun.model} · ${selectedRun.language}`}
          icon={<Boxes className="h-4 w-4" />}
          onClose={() => setSelectedRun(null)}
          width="max-w-[480px]"
        >
          <RunContextPanel
            run={selectedRun}
            release={releaseStatus.data}
            onEvidence={downloadEvalEvidence}
          />
        </DetailDrawer>
      ) : null}

      {tab === "failed" && selectedFailed ? (
        <DetailDrawer
          title={selectedFailed.id}
          subtitle={`${selectedFailed.category} · ${selectedFailed.severity}`}
          icon={<Siren className="h-4 w-4" />}
          onClose={() => setSelectedFailed(null)}
          width="max-w-[500px]"
        >
          <FailedRail
            failedCase={selectedFailed}
            release={releaseStatus.data}
            onEvidence={downloadEvalEvidence}
          />
        </DetailDrawer>
      ) : null}
    </div>
  );
}
