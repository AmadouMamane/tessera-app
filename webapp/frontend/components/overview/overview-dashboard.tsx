"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowRightLeft,
  ArrowUpRight,
  CalendarRange,
  ChevronRight,
  Clock,
  Coins,
  ExternalLink,
  Gauge,
  GitBranch,
  Inbox,
  Lightbulb,
  Network,
  Rocket,
  Route,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
  UploadCloud,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { TemporalMonitoringBreakdown } from "@/components/agent/temporal-monitoring-breakdown";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { PageEvidenceActions } from "@/components/overview/page-evidence-actions";
import { fmtStamp, useTemporalState } from "@/components/overview/temporal-rail";
import { SignalCommandBar } from "@/components/surveiller/signal-command-bar";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Truncate } from "@/components/ui/truncate";
import { Link, useRouter } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, isScopedToAgent, parseAgentScope } from "@/lib/agent-scope";
import {
  fetchAuditIntegrity,
  fetchBatch,
  fetchHealth,
  fetchOverviewCases,
  fetchOverviewSnapshot,
  fetchReadiness,
  fetchTimeline,
  runRedteam,
} from "@/lib/api/client";
import type { Fleet } from "@/lib/api/schemas";
import {
  AIActReportSchema,
  AnomalyReportSchema,
  ConformanceReportSchema,
  ControlSignalsSchema,
  CostReportSchema,
  EvalScoresResponseSchema,
  FirewallEfficacySchema,
  FunnelReportSchema,
  GovernanceFeedSchema,
  PIILeakSummarySchema,
  PlaybookReportSchema,
  RefusalReportSchema,
  RoadmapReportSchema,
  SLOReportSchema,
  ToolValiditySchema,
  ToxicityReportSchema,
  TracesObsSchema,
  TrendReportSchema,
  WhatChangedSchema,
} from "@/lib/api/schemas";
import type {
  AnomalyReport,
  ConformanceReport,
  ControlSignal,
  FirewallEfficacy,
  GovernanceEvent,
  GovernanceFeed,
  InboxOverview,
  PIILeakSummary,
  PlaybookReport,
  RefusalReport,
  SLOReport,
  ToolValidity,
  ToxicityReport,
  TracesObs,
  TrendReport,
} from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import {
  type ControlState,
  type OverviewTone,
  controlState,
  dotBg,
  pct,
  quickActions,
  rateTone,
  score100,
  toneBg,
  toneText,
} from "@/lib/overview";
import { panelOf, signalOf } from "@/lib/overview-snapshot";
import { isOrgWide, signalSupports } from "@/lib/signal-registry";

/**
 * The two snapshot subsets, split by POLL CADENCE rather than by topic.
 *
 * `anomalies` and `what_changed` refresh every 20s; the other seven every POLL_MS. Folding all
 * nine into one query would have silently retimed two of them. Two round-trips instead of nine
 * is the win; changing how often a card refreshes was never part of it.
 */
const SNAPSHOT_FAST = ["slo", "trend", "toxicity", "pii_leak", "cost", "funnel", "scores"] as const;
const SNAPSHOT_SLOW = ["anomalies", "what_changed"] as const;

const POLL_MS = 15_000;

// The ten individual public-aggregate card reads, fetched in ONE `/observability/batch` request
// instead of ten tunnel round-trips. Each panel is byte-identical to its own endpoint. The
// audit-integrity, the live scrubber timeline and the operator inbox stay on their own fetches.
const OV_BATCH_KEYS = [
  "refusal",
  "conformance",
  "tool-validity",
  "firewall-efficacy",
  "playbooks",
  "roadmap",
  "ai-act",
  "governance",
  "traces-obs",
  "control-signals",
] as const;
const POLL_FAST_MS = 10_000;

export function OverviewDashboard({
  children,
  lead,
  initialFleet,
  fleetScope,
  fleetLocale,
  initialFleetPeriod,
  initialFleetAt,
}: {
  children?: ReactNode;
  /** Rendered ABOVE the temporal rail (e.g. the SLO breach alert), so the rail sits
   * directly beneath the alert. The rest (per-agent breakdown) stays in `children`. */
  lead?: ReactNode;
  initialFleet: Fleet | null;
  fleetScope: string;
  fleetLocale: string;
  initialFleetPeriod: string;
  initialFleetAt: string | null;
}) {
  const t = useTranslations("overview");
  const locale = useLocale();
  // Global agent scope (?agent=) — the same filter the GOUVERNER/PLATEFORME surfaces
  // carry (lib/agent-scope). It descends into the score-/bundle-/audit-backed queries
  // so the whole dashboard reads ONE agent's own signals, not just the "Vue par agent"
  // table. `scope` is "all" (org view) or a concrete agent id; it rides every scoped
  // query's key so React Query re-fetches when the operator switches agent. Signals
  // with no per-agent substrate (the shared-policy probes refusal/firewall, the global
  // SR-01 rail) stay org-wide and are marked as such — never faked per agent.
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));
  const agentScoped = isScopedToAgent(scope);
  // SR-01 temporal state — the single shared hook (global window + URL deep-link +
  // Live/As-of/Historique reading). The SignalCommandBar owns the controls; the
  // page reads asOf/historyMode to scope its queries (ADR 0011).
  const temporal = useTemporalState();
  const { historyMode, reading, selectedAt, changeMode } = temporal;
  const [secondaryAsOf, setSecondaryAsOf] = useState<string | null>(null);
  // Returning to live releases every temporal key immediately.
  useEffect(() => {
    if (temporal.activeAt == null) setSecondaryAsOf(null);
  }, [temporal.activeAt]);
  // The fleet total is the first, most visible proof that the cursor took effect.
  // The heavier fan-out receives the exact same T only when that narrow read has
  // settled. This is deterministic under a warm or cold backend, unlike a timer.
  const finishTemporalFleet = useCallback((settledAt: string) => {
    setSecondaryAsOf(settledAt);
  }, []);
  // The provenance chip reflects the active READING (Lecture), never `historyMode`:
  // a scrubbed Historique reads the PERIOD's evolution ("Sur la période"), not a
  // single point — only "À un instant" (asof) reconstructs an instant ("À cet
  // instant"). One coherent badge per reading (registre §D): the cards can never say
  // "À cet instant" while the bar/actions read "Historique". Live carries no chip.
  const provenanceTag: TimeTagKind | null =
    reading === "asof" ? "atT" : reading === "historique" ? "period" : null;

  // --- Liveness ------------------------------------------------------------
  const health = useQuery({
    queryKey: ["overview-health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: POLL_FAST_MS,
  });
  const readiness = useQuery({
    queryKey: ["overview-readiness"],
    queryFn: ({ signal }) => fetchReadiness(signal),
    refetchInterval: POLL_FAST_MS,
  });

  // --- Quality / SRE -------------------------------------------------------
  // As-of-T queries re-key on `asOf`, so scrubbing the rail would normally blank
  // them to "—" on every step (a fresh key has no cache). keepPreviousData holds
  // the last value while the new T resolves, so the cockpit reads smoothly.
  // --- The batched snapshot (ADR 0015 §Performance) ------------------------
  // Nine cards used to fire nine requests per poll. The backend has always been able to
  // answer them in ONE pass over shared reads (`GET /observability/snapshot`, cached +
  // single-flight); the cockpit simply never asked. Each card now `select`s its slice and
  // validates it with the same schema its own route used, so this buys round-trips, not trust.
  //
  // TWO queries, not one, because two of the nine poll at a different cadence. Folding them
  // into a single key would silently change how often `anomalies` and `what_changed` refresh —
  // invisible on screen, and exactly the kind of "no behaviour change" that is not one.
  const snapshotFast = useQuery({
    queryKey: ["ov-snapshot-fast", secondaryAsOf, scope],
    queryFn: ({ signal }) =>
      fetchOverviewSnapshot(signal, secondaryAsOf ?? undefined, scope, SNAPSHOT_FAST),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const snapshotSlow = useQuery({
    queryKey: ["ov-snapshot-slow", secondaryAsOf, scope],
    queryFn: ({ signal }) =>
      fetchOverviewSnapshot(signal, secondaryAsOf ?? undefined, scope, SNAPSHOT_SLOW),
    refetchInterval: historyMode ? false : 20_000,
    placeholderData: keepPreviousData,
  });

  // Each card keeps its own loading/error/empty behaviour: it reads the query it depends on
  // and selects its own slice. A signal the backend could not compute stays `undefined` —
  // honest-empty, never a fabricated zero (`selectSignal`).
  const slo = signalOf(snapshotFast, "slo", SLOReportSchema);
  const trend = signalOf(snapshotFast, "trend", TrendReportSchema);
  const toxicity = signalOf(snapshotFast, "toxicity", ToxicityReportSchema);
  const piiLeak = signalOf(snapshotFast, "pii_leak", PIILeakSummarySchema);
  const cost = signalOf(snapshotFast, "cost", CostReportSchema);
  const funnel = signalOf(snapshotFast, "funnel", FunnelReportSchema);
  const scores = signalOf(snapshotFast, "scores", EvalScoresResponseSchema);
  const anomalies = signalOf(snapshotSlow, "anomalies", AnomalyReportSchema);
  const whatChanged = signalOf(snapshotSlow, "what_changed", WhatChangedSchema);

  // --- Safety / guard signals ---------------------------------------------
  // refusal + firewall measure a FIXED corpus through the guard "now" — a
  // property of the current policy, identical at any T — so they stay live.
  // The individual public-aggregate cards, fetched in ONE batch request (was ten fetches).
  const ovBatch = useQuery({
    queryKey: ["ov-batch", secondaryAsOf, scope, locale],
    queryFn: ({ signal }) =>
      fetchBatch(signal, OV_BATCH_KEYS, {
        at: secondaryAsOf ?? undefined,
        agent: scope,
        lang: locale,
      }),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const refusal = panelOf(ovBatch, "refusal", RefusalReportSchema);
  const conformance = panelOf(ovBatch, "conformance", ConformanceReportSchema);
  const tools = panelOf(ovBatch, "tool-validity", ToolValiditySchema);
  const firewall = panelOf(ovBatch, "firewall-efficacy", FirewallEfficacySchema);

  // --- Incidents / risk ----------------------------------------------------
  const playbooks = panelOf(ovBatch, "playbooks", PlaybookReportSchema);
  const roadmap = panelOf(ovBatch, "roadmap", RoadmapReportSchema);

  // --- Cost / compliance / audit ------------------------------------------
  // The audit COUNT honours T (append-only log → entries up to the instant); the
  // chain VERIFICATION stays a structural "now" check (server-side), so the card
  // reads "à T" like every other point-in-time signal instead of a lone "live".
  const aiAct = panelOf(ovBatch, "ai-act", AIActReportSchema);
  const audit = useQuery({
    queryKey: ["ov-audit", secondaryAsOf],
    queryFn: ({ signal }) => fetchAuditIntegrity(signal, secondaryAsOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  // The rail's own axis stays live (the full scrubbable window); moving its
  // cursor sets `selectedAt`, which is what re-reads the other blocks "à T".
  const timeline = useQuery({
    queryKey: ["ov-timeline"],
    queryFn: ({ signal }) => fetchTimeline(signal),
    refetchInterval: POLL_MS,
  });

  // --- Enrichments (real data) --------------------------------------------
  // Control → catalogue-signal resolver: static reference metadata (the mapping
  // does not vary with T), so it is cached hard and carries no temporal chip.
  const controlSignals = panelOf(ovBatch, "control-signals", ControlSignalsSchema);
  // Governed-activity feed — real S1 governance events, projected as-of-T like the
  // rest of the page (so it earns the provenance chip honestly).
  const governance = panelOf(ovBatch, "governance", GovernanceFeedSchema);
  // Operator control-cases queue — a LIVE operational backlog (no as-of substrate),
  // so it is never scoped to T; in a temporal reading it wears an honest live marker.
  const inbox = useQuery({
    queryKey: ["ov-inbox"],
    queryFn: ({ signal }) => fetchOverviewCases(signal),
    refetchInterval: POLL_MS,
  });
  // Trace observability read back from the running Langfuse stack (the OTel traces);
  // projects as-of-T via Langfuse toTimestamp, so it earns the provenance chip.
  const tracesObs = panelOf(ovBatch, "traces-obs", TracesObsSchema);

  const liveStatus = useMemo(() => {
    if (health.isError || readiness.isError) return t("status.degraded");
    if (readiness.data?.status === "ready") return t("status.ready");
    return health.data?.status ?? t("status.live");
  }, [health.data?.status, health.isError, readiness.data?.status, readiness.isError, t]);

  // Derived signal rows. At live, only signals that returned data are shown. In
  // history mode we keep a stable row for every tracked signal — empty ones read
  // "—" at T instead of vanishing — so scrubbing doesn't make the table jump
  // (no row pop-in/out → no page-level yoyo).
  const controls = useMemo(
    () =>
      buildControls(
        {
          slo: slo.data,
          trend: trend.data,
          toxicity: toxicity.data,
          pii: piiLeak.data,
          refusal: refusal.data,
          conformance: conformance.data,
          tools: tools.data,
          firewall: firewall.data,
        },
        historyMode,
      ),
    [
      historyMode,
      slo.data,
      trend.data,
      toxicity.data,
      piiLeak.data,
      refusal.data,
      conformance.data,
      tools.data,
      firewall.data,
    ],
  );

  // Counts/derived metrics ignore the "no data at T" placeholder rows so the
  // numbers stay honest; only the table renders the full, stable row set.
  const activeControls = controls.filter((c) => !c.noData);
  const failing = activeControls.filter((c) => c.state.key !== "ok");
  const openRisks = (anomalies.data?.n_anomalous ?? 0) + (playbooks.data?.n_triggered ?? 0);
  const signalsLive = activeControls.length;
  // Only treat the SLO as readable when it actually scored turns: at a T before
  // any data, the backend honestly returns n=0 / good_rate=0 — showing "0/100"
  // there would fabricate a bad score, so the card reads "—" instead (matching
  // the controls table, which drops the row when n=0).
  const sloReady = slo.data && slo.data.n > 0 ? slo.data : undefined;

  return (
    <div className="flex w-full flex-col gap-2.5 pb-6">
      {/* The alert and the page-level evidence actions share one opening band on wide
          cockpit screens: the actions no longer reserve an otherwise empty 36px row
          above the alert. On narrower screens they stack without compressing the SLO
          gauge. The actions remain outside the temporal bar (registre §2). */}
      <div className="grid gap-2.5 2xl:grid-cols-[minmax(0,1fr)_auto] 2xl:items-center">
        <div className="min-w-0">{lead}</div>
        <PageEvidenceActions className="self-center" />
      </div>

      {/* The main scroller owns 1.25rem of top padding. The matching negative sticky
          offset consumes that padding only once the rail pins, so its opaque fill meets
          the header and scrolling content cannot remain visible in a strip above it. */}
      <div className="sticky -top-5 z-40 -mx-4 bg-[var(--tessera-bg)] px-4 pb-1 shadow-[0_-4px_0_0_var(--tessera-bg)] sm:-mx-6 sm:px-6">
        <SignalCommandBar
          temporal={temporal}
          timeline={timeline.data}
          sloTarget={slo.data?.threshold}
          hasPresentScore={Boolean(sloReady)}
          liveStatus={liveStatus}
          refreshServerOnCommit={false}
          knownFleetCount={initialFleet?.agents?.length ?? 0}
        />
      </div>

      {/* The only as-of server child used to force a whole-page RSC navigation.
          It now reads its narrow fleet endpoint directly and keeps the prior
          payload visible while the new T resolves. */}
      <TemporalMonitoringBreakdown
        initialFleet={initialFleet}
        scope={fleetScope}
        locale={fleetLocale}
        period={temporal.periodKey}
        at={temporal.activeAt}
        initialPeriod={initialFleetPeriod}
        initialAt={initialFleetAt}
        onTemporalLoadSettled={finishTemporalFleet}
      />

      {/* Below the rail: the remaining static server content. */}
      {children}

      <section className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-6">
        <KpiCard
          label={t("kpi.quality")}
          infoKey="quality"
          href="/surveiller/qualite-ia"
          value={sloReady ? score100(sloReady.good_rate) : "—"}
          delta={
            sloReady
              ? historyMode
                ? t("kpi.vsBaseline", { delta: signedPts(sloReady.good_rate - sloReady.target) })
                : t("kpi.qualityDelta", { burn: sloReady.burn_rate.toFixed(1) })
              : historyMode
                ? t("kpi.noDataAtT")
                : ""
          }
          tone={sloReady ? rateTone(sloReady.good_rate) : "neutral"}
          icon={Activity}
          loading={slo.isLoading && !slo.data}
          tag={provenanceTag ?? undefined}
        />
        <KpiCard
          label={t("kpi.failingControls")}
          infoKey="failingControls"
          href="/surveiller/qualite-ia"
          value={signalsLive ? `${failing.length}/${signalsLive}` : "—"}
          delta={t("kpi.failingDelta", { n: failing.length })}
          tone={
            failing.some((c) => c.state.key === "fail")
              ? "danger"
              : failing.length
                ? "warning"
                : "success"
          }
          icon={ShieldAlert}
          loading={controls.length === 0 && slo.isLoading}
          tag={provenanceTag ?? undefined}
        />
        <KpiCard
          label={t("kpi.openRisks")}
          infoKey="openRisks"
          href="/agir/incidents-playbooks"
          value={anomalies.data || playbooks.data ? String(openRisks) : "—"}
          delta={t("kpi.openRisksDelta", {
            anomalies: anomalies.data?.n_anomalous ?? 0,
            playbooks: playbooks.data?.n_triggered ?? 0,
          })}
          tone={openRisks === 0 ? "success" : openRisks > 3 ? "danger" : "warning"}
          icon={TriangleAlert}
          loading={anomalies.isLoading && playbooks.isLoading}
          tag={provenanceTag ?? undefined}
        />
        <KpiCard
          label={t("kpi.regression")}
          infoKey="regression"
          href="/agir/release-control"
          value={
            whatChanged.data?.available
              ? whatChanged.data.regressed
                ? t("kpi.regressed")
                : t("kpi.stable")
              : "—"
          }
          delta={
            whatChanged.data?.score_delta != null
              ? `${whatChanged.data.score_delta >= 0 ? "+" : ""}${whatChanged.data.score_delta.toFixed(2)}`
              : ""
          }
          tone={
            whatChanged.data?.regressed
              ? "danger"
              : whatChanged.data?.available
                ? "success"
                : "neutral"
          }
          icon={GitBranch}
          loading={whatChanged.isLoading}
          tag={provenanceTag ?? undefined}
        />
        <KpiCard
          label={t("kpi.cost")}
          infoKey="cost"
          href="/surveiller/fiabilite-cout"
          value={cost.data ? `${cost.data.estimated_cost_eur.toFixed(2)} €` : "—"}
          delta={
            cost.data ? t("kpi.costDelta", { tokens: cost.data.total_tokens.toLocaleString() }) : ""
          }
          tone={cost.data && cost.data.n_anomalies > 0 ? "warning" : "info"}
          icon={Coins}
          loading={cost.isLoading}
          tag={provenanceTag ?? undefined}
        />
        <KpiCard
          label={t("kpi.audit")}
          infoKey="audit"
          href="/prouver/audit-logs"
          value={audit.data ? String(audit.data.length) : "—"}
          delta={audit.data ? (audit.data.verified ? t("kpi.auditOk") : t("kpi.auditBroken")) : ""}
          tone={audit.data ? (audit.data.verified ? "success" : "danger") : "neutral"}
          icon={ShieldCheck}
          loading={audit.isLoading}
          tag={provenanceTag ?? undefined}
        />
      </section>

      <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_320px] 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-2.5">
          <CriticalControlsTable
            controls={controls}
            signals={controlSignals.data?.controls}
            loading={slo.isLoading && controls.length === 0}
            historyMode={historyMode}
            provTag={provenanceTag}
            agentScoped={agentScoped}
          />
          <ControlCasesTriage
            inbox={inbox.data}
            loading={inbox.isLoading}
            provTag={provenanceTag}
          />
          <ControlCasesSection
            playbooks={playbooks.data}
            loading={playbooks.isLoading}
            provTag={provenanceTag}
          />
          <GovernedActivityCard
            feed={governance.data}
            loading={governance.isLoading}
            provTag={provenanceTag}
          />
          <AnalyticsSection
            trend={trend.data}
            funnel={funnel.data}
            controls={activeControls}
            provTag={provenanceTag}
          />
          <GovernanceSection
            roadmap={roadmap.data}
            loading={roadmap.isLoading}
            provTag={provenanceTag}
          />
        </div>
        <aside className="flex min-w-0 flex-col gap-2.5">
          <IncidentsCard
            playbooks={playbooks.data}
            anomalies={anomalies.data}
            loading={playbooks.isLoading && anomalies.isLoading}
            provTag={provenanceTag}
          />
          <ReleaseCard
            whatChanged={whatChanged.data}
            slo={slo.data}
            toxicity={toxicity.data}
            pii={piiLeak.data}
            aiActRate={aiAct.data?.compliance_rate}
            conformance={conformance.data}
            provTag={provenanceTag}
          />
          <QuickActionsCard
            onReplayAt={() => temporal.setReading("historique")}
            historyMode={historyMode}
            onBackToLive={() => changeMode("live")}
          />
          <RecentActivitiesCard
            scores={scores.data?.scores}
            loading={scores.isLoading}
            provTag={provenanceTag}
          />
          <ObservabilityTracesCard
            data={tracesObs.data}
            loading={tracesObs.isLoading}
            provTag={provenanceTag}
          />
        </aside>
      </div>

      <TrustFooter
        controls={activeControls}
        verified={audit.data?.verified}
        auditLength={audit.data?.length}
        systemsOk={!health.isError && !readiness.isError && readiness.data?.status === "ready"}
        asOf={historyMode ? (selectedAt as number) : null}
        provTag={provenanceTag}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Signal derivation
// ---------------------------------------------------------------------------

interface ControlRow {
  id: string; // i18n key under overview.signals
  value: string;
  target: string;
  state: ControlState;
  /** 0..1 severity (higher = worse) for the impact bars. */
  severity: number;
  impactKey: string;
  trend?: number[];
  /** True when the row's source is persisted, so it can be read "à T" (ADR 0011). */
  asOfCapable: boolean;
  /** Placeholder row: the signal is tracked but has no data at the focused T. */
  noData?: boolean;
}

const NEUTRAL_STATE: ControlState = { key: "ok", tone: "neutral" };

/** Stable "—" placeholder so a tracked-but-empty-at-T signal keeps its row. */
function noDataRow(
  id: string,
  target: string,
  impactKey: string,
  asOfCapable: boolean,
): ControlRow {
  return {
    id,
    value: "—",
    target,
    state: NEUTRAL_STATE,
    severity: 0,
    impactKey,
    asOfCapable,
    noData: true,
  };
}

function buildControls(
  d: {
    slo?: SLOReport;
    trend?: TrendReport;
    toxicity?: ToxicityReport;
    pii?: PIILeakSummary;
    refusal?: RefusalReport;
    conformance?: ConformanceReport;
    tools?: ToolValidity;
    firewall?: FirewallEfficacy;
  },
  historyMode: boolean,
): ControlRow[] {
  const rows: ControlRow[] = [];

  // Each signal: a real row when it has data; in history mode, a stable "—"
  // placeholder when the source is present but empty at T, so the table keeps
  // the same rows across the scrub (no pop-in/out → no page yoyo).
  const { slo, toxicity, pii, refusal, conformance, tools, firewall } = d;

  if (slo && slo.n > 0) {
    rows.push({
      id: "faithfulness",
      value: pct(slo.good_rate),
      target: `≥ ${pct(slo.target)}`,
      state: slo.breaching
        ? { key: "fail", tone: "danger" }
        : controlState(slo.good_rate, slo.target, "higher"),
      severity: 1 - slo.good_rate,
      impactKey: "rag",
      trend: d.trend?.buckets.map((b) => b.mean),
      asOfCapable: true, // backed by the durable score log
    });
  } else if (historyMode && slo) {
    rows.push(noDataRow("faithfulness", `≥ ${pct(slo.target)}`, "rag", true));
  }

  if (toxicity && toxicity.n_turns > 0) {
    rows.push({
      id: "toxicity",
      value: pct(toxicity.toxicity_rate, 2),
      target: "≤ 0.10%",
      state: controlState(toxicity.toxicity_rate, 0.001, "lower"),
      severity: Math.min(toxicity.toxicity_rate * 50, 1),
      impactKey: "safety",
      asOfCapable: true, // bundle-backed (captured_at filterable)
    });
  } else if (historyMode && toxicity) {
    rows.push(noDataRow("toxicity", "≤ 0.10%", "safety", true));
  }

  if (pii && pii.n_turns > 0) {
    rows.push({
      id: "pii",
      value: pct(pii.leak_rate, 2),
      target: "≤ 0.50%",
      state: controlState(pii.leak_rate, 0.005, "lower"),
      severity: Math.min(pii.leak_rate * 20, 1),
      impactKey: "privacy",
      asOfCapable: true, // bundle-backed (captured_at filterable)
    });
  } else if (historyMode && pii) {
    rows.push(noDataRow("pii", "≤ 0.50%", "privacy", true));
  }

  if (refusal && refusal.n_legit + refusal.n_forbidden > 0) {
    const worst = Math.max(refusal.over_refusal_rate, refusal.under_refusal_rate);
    rows.push({
      id: "refusal",
      value: pct(worst),
      target: "≤ 5%",
      state: controlState(worst, 0.05, "lower"),
      severity: Math.min(worst, 1),
      impactKey: "quality",
      asOfCapable: false, // fixed-corpus probe of the current policy → live by nature
    });
  } else if (historyMode && refusal) {
    rows.push(noDataRow("refusal", "≤ 5%", "quality", false));
  }

  if (conformance && conformance.n_calls > 0) {
    rows.push({
      id: "conformance",
      value: pct(conformance.conformance_rate),
      target: "≥ 95%",
      state: controlState(conformance.conformance_rate, 0.95, "higher"),
      severity: 1 - conformance.conformance_rate,
      impactKey: "tools",
      asOfCapable: true, // audit-log-backed (occurred_at filterable)
    });
  } else if (historyMode && conformance) {
    rows.push(noDataRow("conformance", "≥ 95%", "tools", true));
  }

  if (tools && tools.total > 0) {
    rows.push({
      id: "tools",
      value: pct(tools.validity_rate),
      target: "≥ 95%",
      state: controlState(tools.validity_rate, 0.95, "higher"),
      severity: 1 - tools.validity_rate,
      impactKey: "tools",
      asOfCapable: true, // audit-log-backed (occurred_at filterable)
    });
  } else if (historyMode && tools) {
    rows.push(noDataRow("tools", "≥ 95%", "tools", true));
  }

  if (firewall && firewall.n_positive > 0) {
    rows.push({
      id: "firewall",
      value: pct(firewall.recall),
      target: "≥ 90%",
      state: controlState(firewall.recall, 0.9, "higher"),
      severity: 1 - firewall.recall,
      impactKey: "security",
      asOfCapable: false, // fixed adversarial-corpus probe → live by nature
    });
  } else if (historyMode && firewall) {
    rows.push(noDataRow("firewall", "≥ 90%", "security", false));
  }

  return rows;
}

// ---------------------------------------------------------------------------
// Header — live / replay rail
// ---------------------------------------------------------------------------

/** Position (0..100%) of an instant inside the timeline window. */

// ---------------------------------------------------------------------------
// KPI cards
// ---------------------------------------------------------------------------

/** Provenance of a block in history mode: reconstructed AT the instant, or a live
 * signal that does not vary with the chosen instant. */
type TimeTagKind = "atT" | "period" | "live";

/**
 * One self-describing provenance chip per card/section (never per-cell — that
 * over-stamped the same fact on every row). It mirrors the active READING so the
 * whole page carries one coherent badge (registre §D):
 * - "atT" (À un instant) — a point-in-time reconstruction, gold + clock glyph.
 * - "period" (Historique) — the period's evolution, NOT an instant: neutral + a
 *   range glyph + "Sur la période".
 * - "live" (Maintenant) — the current signal, neutral.
 * The label is explicit (never the cryptic "à T") with a tooltip for the anchor.
 */
function TimeTagChip({ kind, className }: { kind: TimeTagKind; className?: string }) {
  const t = useTranslations("overview.time");
  const config = {
    atT: {
      label: t("atTLabel"),
      title: t("atTTooltip"),
      icon: Clock,
      tone: "border border-gold-500/40 bg-gold-500/10 text-gold-300",
    },
    period: {
      label: t("periodTagLabel"),
      title: t("periodTagTooltip"),
      icon: CalendarRange,
      tone: "border border-[var(--border)] bg-[var(--muted)]/40 text-[var(--muted-foreground)]",
    },
    live: {
      label: t("liveSignal"),
      title: t("liveTooltip"),
      icon: null,
      tone: "border border-[var(--border)] bg-[var(--muted)]/40 text-[var(--muted-foreground)]",
    },
  }[kind];
  const Icon = config.icon;
  return (
    <span
      title={config.title}
      className={cn(
        "inline-flex cursor-help items-center gap-1 rounded px-1.5 py-0.5 text-[0.58rem] font-medium uppercase leading-none tracking-wide",
        config.tone,
        className,
      )}
    >
      {Icon ? <Icon className="h-2.5 w-2.5" aria-hidden /> : null}
      {config.label}
    </span>
  );
}

/** Signed /100-point delta (e.g. −4 / +3) for an "à T vs baseline" reading. */
function signedPts(fraction: number): string {
  const pts = Math.round(fraction * 100);
  return `${pts >= 0 ? "+" : ""}${pts}`;
}

/** A ⓘ for a section title, reading its explanation from overview.explain.<k>. */
function SectionInfo({ title, explainKey }: { title: string; explainKey: string }) {
  const te = useTranslations("overview.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${explainKey}.what`)}
      how={te(`${explainKey}.how`)}
      source={te.has(`${explainKey}.source`) ? te(`${explainKey}.source`) : undefined}
    />
  );
}

function KpiCard({
  label,
  value,
  delta,
  tone,
  icon: Icon,
  trend,
  trendEmptyLabel,
  loading,
  tag,
  infoKey,
  href,
}: {
  label: string;
  value: string;
  delta: string;
  tone: OverviewTone;
  icon: typeof Activity;
  trend?: number[];
  trendEmptyLabel?: string;
  loading?: boolean;
  tag?: TimeTagKind;
  /** Key under overview.explain — renders a ⓘ "what is this / how computed". */
  infoKey?: string;
  /** Real source this counter drills into — makes the whole card a link. */
  href?: string;
}) {
  const te = useTranslations("overview.explain");
  const tk = useTranslations("overview.kpi");
  return (
    <Card
      data-testid={infoKey ? `overview-kpi-${infoKey}` : undefined}
      className={cn(
        "group relative h-full overflow-hidden rounded-lg",
        href && "transition-colors hover:border-blue-400/40",
      )}
    >
      <div className={cn("absolute inset-x-0 top-0 h-0.5", dotBg[tone])} />
      {/* Whole-card drill-down to the real source. The clickable layer is an overlay
          <Link> that is a SIBLING of the content (never an ancestor), so the ⓘ
          popover trigger inside can't trigger navigation; the content is
          pointer-transparent except the ⓘ, which re-enables its own clicks. */}
      {href ? (
        <Link
          href={href}
          aria-label={tk("openSource", { label })}
          className="absolute inset-0 z-10 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/40"
        />
      ) : null}
      <CardContent className={cn("p-4", href && "pointer-events-none relative z-20")}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
              {label}
              {infoKey ? (
                <span className={href ? "pointer-events-auto" : undefined}>
                  <MetricInfo
                    title={label}
                    what={te(`${infoKey}.what`)}
                    how={te(`${infoKey}.how`)}
                    source={te.has(`${infoKey}.source`) ? te(`${infoKey}.source`) : undefined}
                  />
                </span>
              ) : null}
              {tag ? <TimeTagChip kind={tag} /> : null}
            </p>
            {loading ? (
              <Skeleton className="mt-2 h-7 w-16" />
            ) : (
              <p
                data-testid={infoKey ? `overview-kpi-${infoKey}-value` : undefined}
                className="mt-2 font-serif text-2xl font-semibold tabular-nums"
              >
                {value}
              </p>
            )}
          </div>
          <span className={cn("rounded-lg border p-2", toneBg[tone])}>
            <Icon className="h-4 w-4" />
          </span>
        </div>
        {delta ? <p className={cn("mt-1 text-[0.7rem]", toneText[tone])}>{delta}</p> : null}
        {/* The card always reserves the chart slot when it tracks a trend, and
            keeps a permanent horizontal axis: a real curve when there are enough
            points, otherwise the bare axis + an "aucune donnée" label — so
            scrubbing never shrinks the card or pops the curve in and out. */}
        {trend ? (
          <div className="relative mt-2 h-8">
            <MetricSparkline values={trend.length > 1 ? trend : []} tone={tone} />
            {/* Only label the chart when the KPI itself has a value but no
                drawable trend yet; when there's no data at all the delta line
                already says "Aucune donnée à T", so don't repeat it here. */}
            {trend.length <= 1 && value !== "—" ? (
              <span className="absolute inset-0 flex items-center justify-center text-[0.58rem] text-[var(--muted-foreground)]">
                {trendEmptyLabel}
              </span>
            ) : null}
          </div>
        ) : null}
      </CardContent>
      {/* Persistent-but-discreet drill affordance: a faint corner arrow that
          brightens on hover, signalling the whole card opens its real source. */}
      {href ? (
        <ArrowUpRight className="pointer-events-none absolute bottom-2.5 right-2.5 z-20 h-3.5 w-3.5 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-80" />
      ) : null}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Critical controls table
// ---------------------------------------------------------------------------

// Which controls are org-wide (a fixed-corpus probe of the shared policy, identical for
// every agent) is no longer hand-listed here: it is *declared* in the signal registry
// (`lib/signal-registry` → `isOrgWide`), the single source of honesty truth mirrored from
// the backend `capabilities.py`. The badge below reads that declaration, so the org-wide
// marker can never drift from what a signal can actually be sliced by (ADR 0015).

function CriticalControlsTable({
  controls,
  signals,
  loading,
  historyMode,
  provTag,
  agentScoped,
}: {
  controls: ControlRow[];
  /** Real catalogue-signal resolution per control id (id/name/route), or undefined. */
  signals?: ControlSignal[];
  loading: boolean;
  historyMode: boolean;
  provTag: TimeTagKind | null;
  /** True when a single agent is selected — org-wide rows then wear an honest badge. */
  agentScoped: boolean;
}) {
  const t = useTranslations("overview.criticalControls");
  const tas = useTranslations("agentScope");
  const ts = useTranslations("overview.signals");
  const tst = useTranslations("overview.states");
  const ti = useTranslations("overview.impact");
  const tt = useTranslations("overview.time");
  const tci = useTranslations("overview.controlInfo");
  const signalById = useMemo(() => new Map((signals ?? []).map((s) => [s.id, s])), [signals]);

  return (
    <Card className="overflow-hidden rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          <SectionInfo title={t("title")} explainKey="criticalControls" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--muted-foreground)]">
            {t("count", { n: controls.length })}
          </span>
          <Link
            href="/surveiller/qualite-ia"
            className="flex items-center gap-1 whitespace-nowrap text-xs text-[var(--tessera-fg-info)] hover:underline"
          >
            {t("viewAll")}
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="flex flex-col gap-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : controls.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-[var(--muted-foreground)]">
            {t("empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="px-4 py-2 font-medium">{t("signal")}</th>
                  <th className="py-2 pr-4 font-medium">{t("state")}</th>
                  <th className="py-2 pr-4 font-medium">{t("current")}</th>
                  <th className="py-2 pr-4 font-medium">{t("target")}</th>
                  <th className="py-2 pr-4 font-medium">{t("trend")}</th>
                  <th className="py-2 pr-4 font-medium">{t("impact")}</th>
                  <th className="py-2 pr-4 font-medium">{t("action")}</th>
                </tr>
              </thead>
              <tbody>
                {controls.map((c) => {
                  const sig = signalById.get(c.id);
                  return (
                    <tr key={c.id} className="border-b border-[var(--border)]/50">
                      <td className="px-4 py-2">
                        {/* Real signal identity (normative): the human label + its REAL
                          catalogue id/technical name; the two live policy probes
                          (toxicity, refusal) are honestly marked "hors catalogue". */}
                        <div className="flex items-center gap-1.5 font-medium">
                          {ts(c.id)}
                          {/* Per-control "what/how/source" explainer, same affordance as the
                            KPI cards — reads its plain-language definition from the registry-
                            aligned controlInfo namespace (honest: matches the real computation). */}
                          {tci.has(`${c.id}.what`) ? (
                            <MetricInfo
                              title={ts(c.id)}
                              what={tci(`${c.id}.what`)}
                              how={tci.has(`${c.id}.how`) ? tci(`${c.id}.how`) : undefined}
                              source={tci.has(`${c.id}.source`) ? tci(`${c.id}.source`) : undefined}
                            />
                          ) : null}
                          {/* A shared-policy probe does not vary by agent: under an
                            agent scope it carries an honest "org-wide" badge rather
                            than pretending to be that agent's own number. */}
                          {agentScoped && isOrgWide(c.id) ? (
                            <span
                              title={tas("orgWideHint")}
                              className="inline-flex cursor-help items-center rounded border border-[var(--border)] bg-[var(--muted)]/40 px-1 py-0.5 text-[0.55rem] font-medium uppercase leading-none tracking-wide text-[var(--muted-foreground)]"
                            >
                              {tas("orgWide")}
                            </span>
                          ) : null}
                          {/* A temporal instant is selected but this signal declares no `time`
                            dimension: it is a probe of the CURRENTLY-DEPLOYED guard policy
                            (fixed test corpus → policy.yaml), deterministic and unchanged until
                            the policy is redeployed — NOT a real-time stream, and NOT the policy
                            as it stood at the chosen past instant. So the honest, plain-language
                            badge is "current policy", driven by the registry (`signalSupports`)
                            so it can never drift from the declaration. */}
                          {historyMode && !c.noData && !signalSupports(c.id, "time") ? (
                            <span
                              title={t("currentPolicyHint")}
                              className="inline-flex cursor-help items-center gap-1 rounded border border-amber-500/40 bg-amber-500/10 px-1 py-0.5 text-[0.55rem] font-medium uppercase leading-none tracking-wide text-amber-300/90"
                            >
                              <Activity className="h-2.5 w-2.5" />
                              {t("currentPolicy")}
                            </span>
                          ) : null}
                        </div>
                        {sig?.catalogued && sig.signal_name ? (
                          <div className="font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                            {sig.signal_id} · {sig.signal_name}
                          </div>
                        ) : sig ? (
                          <div
                            className="text-[0.6rem] text-[var(--muted-foreground)]"
                            title={tt("liveTooltip")}
                          >
                            {t("liveProbe")}
                          </div>
                        ) : null}
                      </td>
                      <td className="py-2 pr-4">
                        <span
                          className={cn(
                            "inline-flex rounded-full border px-2 py-0.5 text-xs",
                            toneBg[c.state.tone],
                          )}
                        >
                          {c.noData ? "—" : tst(c.state.key)}
                        </span>
                      </td>
                      {/* No per-cell time badge — the section already carries ONE "À
                        cet instant" chip, so repeating it on every row was pure
                        over-stamping. A row whose source can't be reconstructed
                        historically (a live current-policy probe) keeps an honest
                        tooltip instead of a second visible badge. */}
                      <td
                        className="py-2 pr-4 tabular-nums"
                        title={
                          historyMode && !c.noData && !c.asOfCapable ? tt("liveTooltip") : undefined
                        }
                      >
                        {c.value}
                      </td>
                      <td className="py-2 pr-4 text-[var(--muted-foreground)]">{c.target}</td>
                      <td className="w-24 py-2 pr-4">
                        {/* permanent axis on every row → constant cell height; a
                          curve only where there's a real trend to draw */}
                        <MetricSparkline
                          values={c.trend && c.trend.length > 1 ? c.trend : []}
                          tone={c.trend && c.trend.length > 1 ? c.state.tone : "neutral"}
                          className="h-6"
                          height={26}
                        />
                      </td>
                      <td className="py-2 pr-4 text-[var(--muted-foreground)]">
                        {ti(c.impactKey)}
                      </td>
                      {/* Drill-down to the control's REAL investigation surface — the
                        normative "Action recommandée / Case" intent, as honest
                        navigation (every control has a real SURVEILLER route). */}
                      <td className="py-2 pr-4">
                        {sig ? (
                          <Link
                            href={sig.route}
                            title={t("investigate")}
                            className="inline-flex items-center gap-0.5 whitespace-nowrap text-xs text-[var(--tessera-fg-info)] hover:underline"
                          >
                            {t("investigate")}
                            <ChevronRight className="h-3.5 w-3.5" />
                          </Link>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Control-cases triage (real operator queue) — enrichment #3
// ---------------------------------------------------------------------------

const CASE_PRIORITY_TONE: Record<string, OverviewTone> = {
  urgent: "danger",
  high: "warning",
  medium: "gold",
  low: "neutral",
};
const CASE_SLA_TONE: Record<string, OverviewTone> = {
  crit: "danger",
  warn: "warning",
  ok: "success",
};
const CASE_TABS = ["all", "urgent", "high", "medium", "low"] as const;
const CASE_RANK: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 };

/**
 * A compact severity-tabbed triage of the REAL operator queue
 * (``/observability/inbox``) — the normative "Control Cases à traiter". It is a LIVE
 * operational backlog (no as-of-T substrate), so under a mode chip it wears an honest
 * "live" marker; the full queue lives on /à-traiter.
 */
function ControlCasesTriage({
  inbox,
  loading,
  provTag,
}: {
  inbox?: InboxOverview;
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.cases");
  const [tab, setTab] = useState<(typeof CASE_TABS)[number]>("all");
  const items = inbox?.items ?? [];
  const counts = useMemo(() => {
    const c: Record<string, number> = { all: items.length, urgent: 0, high: 0, medium: 0, low: 0 };
    for (const it of items) c[it.priority] = (c[it.priority] ?? 0) + 1;
    return c;
  }, [items]);
  const shown = useMemo(() => {
    const filtered = tab === "all" ? items : items.filter((i) => i.priority === tab);
    return [...filtered]
      .sort((a, b) => (CASE_RANK[a.priority] ?? 9) - (CASE_RANK[b.priority] ?? 9))
      .slice(0, 4);
  }, [items, tab]);

  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          <SectionInfo title={t("title")} explainKey="cases" />
          {provTag ? <TimeTagChip kind="live" /> : null}
        </CardTitle>
        <Link
          href="/a-traiter"
          className="flex items-center gap-1 text-xs text-[var(--tessera-fg-info)] hover:underline"
        >
          <Inbox className="h-3.5 w-3.5" />
          {t("viewAll", { n: inbox?.total_items ?? items.length })}
        </Link>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-1.5">
          {CASE_TABS.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setTab(k)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs transition-colors",
                tab === k
                  ? "border-blue-400/50 bg-blue-500/15 text-blue-200"
                  : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]/40",
              )}
            >
              {t(`tab.${k}`)} <span className="tabular-nums">{counts[k] ?? 0}</span>
            </button>
          ))}
        </div>
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : shown.length === 0 ? (
          <p className="py-6 text-center text-sm text-emerald-400">{t("empty")}</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {shown.map((it) => (
              <li key={it.id}>
                <Link
                  href="/a-traiter"
                  title={t("openCase")}
                  className="grid grid-cols-[auto_1fr_auto] items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--muted)]/20 px-3 py-2 text-xs transition-colors hover:border-blue-400/40 hover:bg-blue-500/5"
                >
                  <span
                    className={cn(
                      "h-2 w-2 shrink-0 rounded-full",
                      dotBg[CASE_PRIORITY_TONE[it.priority] ?? "neutral"],
                    )}
                  />
                  <span className="min-w-0">
                    <Truncate full={it.title} className="font-medium text-[var(--foreground)]">
                      {it.title}
                    </Truncate>
                    <Truncate
                      full={`${it.source} · ${it.assignee}`}
                      className="text-[var(--muted-foreground)]"
                    >
                      {it.source} · {it.assignee}
                    </Truncate>
                  </span>
                  <Badge
                    className={cn("shrink-0", toneBg[CASE_SLA_TONE[it.sla_tone] ?? "neutral"])}
                  >
                    {it.sla}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Governed-activity feed (real S1 governance events) — enrichment #2
// ---------------------------------------------------------------------------

const GOV_ICON: Record<GovernanceEvent["kind"], typeof Activity> = {
  routing: Route,
  handoff: ArrowRightLeft,
  proposed: Lightbulb,
  released: Rocket,
  blocked: ShieldAlert,
  deploy_model: UploadCloud,
  deploy_prompt: UploadCloud,
  deploy_policy: UploadCloud,
};
const GOV_TONE: Record<GovernanceEvent["kind"], OverviewTone> = {
  routing: "info",
  handoff: "gold",
  proposed: "info",
  released: "success",
  blocked: "danger",
  deploy_model: "info",
  deploy_prompt: "info",
  deploy_policy: "info",
};

/** Short DD/MM HH:MM stamp for a governance event (tabular, locale-formatted). */
function fmtGovTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
}

function governanceLabel(ev: GovernanceEvent, t: ReturnType<typeof useTranslations>): string {
  switch (ev.kind) {
    case "handoff":
      return t("handoff", { from: ev.from_agent ?? "?", to: ev.to_agent ?? ev.agent_id ?? "?" });
    case "routing":
      return t("routing", { agent: ev.agent_id ?? "?" });
    case "proposed":
      return t("proposed", { agent: ev.detail || ev.agent_id || "?" });
    case "released":
      return t("released", { agent: ev.agent_id ?? "?" });
    case "blocked":
      return t("blocked", { agent: ev.agent_id ?? "?" });
    case "deploy_model":
      return t("deployModel", { version: ev.detail });
    case "deploy_prompt":
      return t("deployPrompt", { version: ev.detail });
    case "deploy_policy":
      return t("deployPolicy", { version: ev.detail });
    default:
      return ev.detail;
  }
}

/**
 * Governed-activity feed (normatives 02/03) — real, append-only S1 governance
 * events (agent routing / hand-overs / proposals / releases) + lineage deploys,
 * newest-first. Projects as-of-T (carries the page's provenance chip honestly).
 * Only real events appear — sparse categories show an honest empty state.
 */
function GovernedActivityCard({
  feed,
  loading,
  provTag,
}: {
  feed?: GovernanceFeed;
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.governed");
  const events = feed?.events ?? [];
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          <SectionInfo title={t("title")} explainKey="governed" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--muted-foreground)]">
            {t("count", { n: feed?.total ?? 0 })}
          </span>
          <Link
            href="/prouver/audit-logs"
            className="flex items-center gap-1 whitespace-nowrap text-xs text-[var(--tessera-fg-info)] hover:underline"
          >
            {t("viewAll")}
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : events.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
        ) : (
          // Two columns from md up: the labels are short, so a single column wasted
          // the right ~60% of the card. The grid fills the width and halves the height.
          <div className="grid gap-x-5 gap-y-2 md:grid-cols-2">
            {events.map((ev, i) => {
              const Icon = GOV_ICON[ev.kind] ?? Activity;
              const tone = GOV_TONE[ev.kind] ?? "neutral";
              const label = governanceLabel(ev, t);
              const meta = `${fmtGovTime(ev.occurred_at)} · ${ev.actor}${ev.evidence ? ` · ${ev.evidence}` : ""}`;
              return (
                <div
                  key={`${ev.occurred_at}-${ev.kind}-${i}`}
                  className="grid grid-cols-[auto_1fr] items-center gap-2 text-xs"
                >
                  <span
                    className={cn(
                      "flex h-6 w-6 items-center justify-center rounded-md border",
                      toneBg[tone],
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0">
                    <Truncate
                      full={ev.count > 1 ? `${label} · ×${ev.count}` : label}
                      className="text-[var(--foreground)]"
                    >
                      {label}
                      {ev.count > 1 ? (
                        <span className="text-[var(--muted-foreground)]"> · ×{ev.count}</span>
                      ) : null}
                    </Truncate>
                    <Truncate
                      full={meta}
                      className="font-mono text-[0.6rem] text-[var(--muted-foreground)]"
                    >
                      {meta}
                    </Truncate>
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Trace observability — real Langfuse data (best tool for the job)
// ---------------------------------------------------------------------------

/** Latency seconds → a compact "N ms" / "N.N s" label. */
function fmtLatency(s: number | null): string {
  if (s == null) return "—";
  return s < 1 ? `${Math.round(s * 1000)} ms` : `${s.toFixed(2)} s`;
}

function TraceLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 text-[0.7rem] text-[var(--tessera-fg-info)] transition-colors hover:bg-[var(--muted)]/40"
    >
      <ExternalLink className="h-3 w-3" />
      {label}
    </a>
  );
}

/**
 * Real trace observability read back from the running **Langfuse** stack (the OTel
 * traces Tessera already emits) — the right tool for trace inspection. Shows the live
 * trace volume + p50/p95 latency + top operations, projects as-of-T (Langfuse
 * toTimestamp), and deep-links the operator to each tool for its job (Langfuse =
 * trace explorer, Grafana = dashboards, Phoenix = retrieval). Honest empty state when
 * the stack is unreachable.
 */
function ObservabilityTracesCard({
  data,
  loading,
  provTag,
}: {
  data?: TracesObs;
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.traces");
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Network className="h-4 w-4 text-[var(--tessera-fg-info)]" />
          {t("title")}
          <SectionInfo title={t("title")} explainKey="traces" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
        <span className="text-[0.7rem] text-[var(--muted-foreground)]">Langfuse</span>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {loading && !data ? (
          <Skeleton className="h-20 w-full" />
        ) : !data?.available ? (
          <p className="py-4 text-center text-xs text-[var(--muted-foreground)]">
            {t("unavailable")}
          </p>
        ) : (
          <>
            <div className="flex items-end justify-between gap-3">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">{t("traces")}</p>
                <p className="font-serif text-2xl font-semibold tabular-nums">
                  {data.total.toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-3 text-right">
                <Gauge className="h-4 w-4 text-[var(--muted-foreground)]" />
                <div>
                  <p className="text-[0.6rem] uppercase text-[var(--muted-foreground)]">p50</p>
                  <p className="font-mono text-sm tabular-nums">{fmtLatency(data.latency_p50_s)}</p>
                </div>
                <div>
                  <p className="text-[0.6rem] uppercase text-[var(--muted-foreground)]">p95</p>
                  <p className="font-mono text-sm tabular-nums">{fmtLatency(data.latency_p95_s)}</p>
                </div>
              </div>
            </div>
            {data.top_ops.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {data.top_ops.slice(0, 4).map((o) => (
                  <li
                    key={o.name}
                    className="grid grid-cols-[1fr_auto] items-center gap-2 text-[0.68rem]"
                  >
                    <Truncate full={o.name} className="font-mono text-[var(--muted-foreground)]">
                      {o.name}
                    </Truncate>
                    <span className="tabular-nums text-[var(--muted-foreground)]">{o.count}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              <TraceLink href={data.langfuse_url} label="Langfuse" />
              <TraceLink href={data.grafana_url} label="Grafana" />
              <TraceLink href={data.phoenix_url} label="Phoenix" />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Control cases (triggered playbooks)
// ---------------------------------------------------------------------------

const playbookTone: Record<string, OverviewTone> = {
  critical: "danger",
  high: "warning",
  medium: "gold",
};
const caseBorder: Record<OverviewTone, string> = {
  danger: "border-red-500/45",
  warning: "border-orange-500/45",
  gold: "border-gold-500/45",
  success: "border-emerald-500/45",
  info: "border-blue-500/45",
  neutral: "border-[var(--border)]",
};

function ControlCasesSection({
  playbooks,
  loading,
  provTag,
}: {
  playbooks?: PlaybookReport;
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.controlCases");
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          <SectionInfo title={t("title")} explainKey="controlCases" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--muted-foreground)]">
            {t("count", { n: playbooks?.n_triggered ?? 0 })}
          </span>
          <Link
            href="/agir/incidents-playbooks"
            className="flex items-center gap-1 whitespace-nowrap text-xs text-[var(--tessera-fg-info)] hover:underline"
          >
            {t("viewAll")}
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </CardHeader>
      {/* A capped 2-up grid (not flex-1): a single triggered procedure stays a
          right-sized card instead of stretching into a half-empty full-width banner,
          and several incidents tile two-per-row. Each card opens its real incident. */}
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {loading ? (
          <Skeleton className="h-28 w-full sm:col-span-2" />
        ) : !playbooks || playbooks.n_triggered === 0 ? (
          <p className="py-6 text-center text-sm text-emerald-400 sm:col-span-2">{t("clear")}</p>
        ) : (
          playbooks.playbooks.map((p) => {
            const tone = playbookTone[p.severity] ?? "neutral";
            return (
              <Link
                key={p.incident}
                href="/agir/incidents-playbooks"
                className={cn(
                  "block rounded-lg border bg-[var(--muted)]/20 p-3 transition-colors hover:bg-[var(--muted)]/40",
                  caseBorder[tone],
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-sans text-sm font-semibold">{p.incident}</h3>
                  <Badge className={toneBg[tone]}>{p.severity}</Badge>
                </div>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">{p.trigger}</p>
                <ol className="mt-2 ml-4 flex list-decimal flex-col gap-0.5 text-xs text-[var(--muted-foreground)]">
                  {p.steps.slice(0, 3).map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </Link>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Right column — incidents, release, quick actions, activity
// ---------------------------------------------------------------------------

function IncidentsCard({
  playbooks,
  anomalies,
  loading,
  provTag,
}: {
  playbooks?: PlaybookReport;
  anomalies?: AnomalyReport;
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.rightColumn");
  const items: { label: string; tone: OverviewTone; meta: string }[] = [];
  for (const p of playbooks?.playbooks ?? []) {
    items.push({
      label: p.incident,
      tone: playbookTone[p.severity] ?? "neutral",
      meta: p.severity,
    });
  }
  for (const s of anomalies?.sessions ?? []) {
    if (s.anomalous)
      items.push({
        label: s.reasons[0] ?? s.conversation_id,
        tone: "gold",
        meta: `${s.n_turns} t`,
      });
  }

  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("incidents")}
          <SectionInfo title={t("incidents")} explainKey="rightIncidents" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
        <Link
          href="/agir/incidents-playbooks"
          className="flex items-center gap-1 whitespace-nowrap text-xs text-[var(--tessera-fg-info)] hover:underline"
        >
          {t("viewIncidents")}
          <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {loading ? (
          <Skeleton className="h-16 w-full" />
        ) : items.length === 0 ? (
          <p className="py-4 text-center text-xs text-emerald-400">{t("noIncidents")}</p>
        ) : (
          items.slice(0, 6).map((it, i) => (
            <div
              key={`${it.label}-${i}`}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-2 text-xs"
            >
              <span className={cn("h-2 w-2 rounded-full", dotBg[it.tone])} />
              <Truncate full={it.label}>{it.label}</Truncate>
              <Badge className={toneBg[it.tone]}>{it.meta}</Badge>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function ReleaseCard({
  whatChanged,
  slo,
  toxicity,
  pii,
  aiActRate,
  conformance,
  provTag,
}: {
  whatChanged?: import("@/lib/api/schemas").WhatChanged;
  slo?: SLOReport;
  toxicity?: ToxicityReport;
  pii?: PIILeakSummary;
  aiActRate?: number;
  conformance?: ConformanceReport;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.rightColumn");

  const qualityPass = slo ? !slo.breaching : undefined;
  const securityPass =
    toxicity || pii ? (toxicity?.n_toxic ?? 0) === 0 && (pii?.n_with_leak ?? 0) === 0 : undefined;
  const compliancePass =
    aiActRate != null || conformance
      ? (aiActRate ?? 1) >= 1 && (conformance?.conformance_rate ?? 1) >= 0.95
      : undefined;

  const gates: { key: string; pass?: boolean }[] = [
    { key: "quality", pass: qualityPass },
    { key: "security", pass: securityPass },
    { key: "compliance", pass: compliancePass },
  ];

  const blocked = gates.some((g) => g.pass === false);

  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-start justify-between pb-2">
        <div>
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("release")}
            <SectionInfo title={t("release")} explainKey="rightRelease" />
            {provTag ? <TimeTagChip kind={provTag} /> : null}
          </CardTitle>
          {whatChanged?.available &&
          whatChanged.score_before != null &&
          whatChanged.score_after != null ? (
            <p className="mt-2 font-serif text-xl font-semibold tabular-nums">
              {whatChanged.score_before.toFixed(2)} → {whatChanged.score_after.toFixed(2)}
            </p>
          ) : (
            <p className="mt-2 text-sm text-[var(--muted-foreground)]">{t("noBaseline")}</p>
          )}
        </div>
        {blocked ? (
          <Badge tone="danger">{t("blocked")}</Badge>
        ) : (
          <Badge tone="success">{t("clear")}</Badge>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {gates.map((g) => (
          <div key={g.key} className="flex items-center justify-between text-xs">
            <span>{t(`gates.${g.key}`)}</span>
            {g.pass == null ? (
              <Badge tone="neutral">—</Badge>
            ) : (
              <Badge className={toneBg[g.pass ? "success" : "danger"]}>
                {g.pass ? "PASS" : "FAIL"}
              </Badge>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function QuickActionsCard({
  onReplayAt,
  historyMode,
  onBackToLive,
}: { onReplayAt: () => void; historyMode: boolean; onBackToLive: () => void }) {
  const t = useTranslations("overview.quick");
  const router = useRouter();
  const [status, setStatus] = useState<string | null>(null);
  const [frozen, setFrozen] = useState(false);
  const redteam = useMutation({
    mutationFn: () => runRedteam(),
    onSuccess: () => setStatus(t("redteamDone")),
    onError: () => setStatus(t("redteamErr")),
  });

  // "Risk governs execution" (ADR 0011 §3): write/dangerous actions cannot run
  // against the past, so in history mode they are disabled; the freeze toggle
  // transforms into a read-only "compare to live" that returns to now.
  const writeKeys = new Set(["redteam", "ticket"]);

  function handle(key: string) {
    if (historyMode && key === "freezeReleases") {
      onBackToLive();
      return;
    }
    switch (key) {
      case "redteam":
        setStatus(t("redteamRunning"));
        redteam.mutate();
        break;
      case "freezeReleases":
        setFrozen((f) => !f);
        setStatus(frozen ? t("unfrozen") : t("frozen"));
        break;
      case "replay":
        router.push("/surveiller/qualite-ia");
        break;
      case "replayAt":
        onReplayAt();
        break;
      case "ticket":
        setStatus(t("ticketCreated"));
        break;
    }
  }

  return (
    <Card className="rounded-lg">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{t("title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        {quickActions.map((action) => {
          const Icon = action.icon;
          const busy = action.key === "redteam" && redteam.isPending;
          const histDisabled = historyMode && writeKeys.has(action.key);
          const label =
            historyMode && action.key === "freezeReleases" ? t("compareLive") : t(action.key);
          return (
            <button
              key={action.key}
              type="button"
              disabled={busy || histDisabled}
              title={histDisabled ? t("histDisabled") : undefined}
              onClick={() => handle(action.key)}
              className="rounded-md border border-[var(--border)] bg-[var(--muted)]/25 px-3 py-2 text-left transition-colors hover:border-blue-400/40 hover:bg-blue-500/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="flex items-center gap-2 text-sm">
                <Icon className={cn("h-4 w-4", toneText[action.tone])} />
                {label}
                {action.key === "freezeReleases" && frozen && !historyMode ? (
                  <Badge tone="warning" className="ml-auto">
                    {t("frozenBadge")}
                  </Badge>
                ) : null}
                {histDisabled ? (
                  <span className="ml-auto text-[0.6rem] uppercase text-[var(--muted-foreground)]">
                    {t("histTag")}
                  </span>
                ) : null}
              </span>
            </button>
          );
        })}
        {status ? (
          <p className="px-1 pt-1 text-[0.7rem] text-[var(--muted-foreground)]">{status}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function RecentActivitiesCard({
  scores,
  loading,
  provTag,
}: {
  scores?: import("@/lib/api/schemas").EvalScore[];
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.rightColumn");
  const rows = scores ? [...scores].reverse().slice(0, 6) : [];
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("activities")}
          <SectionInfo title={t("activities")} explainKey="rightActivities" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {loading ? (
          <Skeleton className="h-16 w-full" />
        ) : rows.length === 0 ? (
          <p className="py-4 text-center text-xs text-[var(--muted-foreground)]">
            {t("noActivity")}
          </p>
        ) : (
          rows.map((s, i) => (
            <div
              key={`${s.scored_at}-${i}`}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-2 text-xs"
            >
              <span className={cn("h-2 w-2 rounded-full", dotBg[rateTone(s.score)])} />
              <Truncate full={`${s.metric} · ${s.language}`}>
                {s.metric} · <span className="uppercase">{s.language}</span>
              </Truncate>
              <span className="font-mono tabular-nums text-[var(--muted-foreground)]">
                {s.score.toFixed(2)}
              </span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Analytics — quality trend, language distribution, signal impact
// ---------------------------------------------------------------------------

function AnalyticsSection({
  trend,
  funnel,
  controls,
  provTag,
}: {
  trend?: TrendReport;
  funnel?: import("@/lib/api/schemas").FunnelReport;
  controls: ControlRow[];
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.analytics");
  const ts = useTranslations("overview.signals");
  const directionTone: OverviewTone =
    trend?.direction === "improving"
      ? "success"
      : trend?.direction === "degrading"
        ? "danger"
        : "info";

  return (
    <section className="grid gap-2.5 xl:grid-cols-3">
      <Card className="rounded-lg">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("scores")}
            <SectionInfo title={t("scores")} explainKey="analyticsScores" />
            {provTag ? <TimeTagChip kind={provTag} /> : null}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {trend && trend.buckets.length > 1 ? (
            <div className="h-32 rounded-md border border-[var(--border)] bg-[var(--muted)]/20 p-3">
              <MetricSparkline
                values={trend.buckets.map((b) => b.mean)}
                tone={directionTone}
                className="h-16"
                height={64}
              />
              <div className="mt-2 flex items-center justify-between text-[0.65rem] text-[var(--muted-foreground)]">
                <span>{t(`direction.${trend.direction}`)}</span>
                <span className="tabular-nums">
                  {trend.first_half_mean.toFixed(2)} → {trend.second_half_mean.toFixed(2)}
                </span>
              </div>
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-lg">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("distribution")}
            <SectionInfo title={t("distribution")} explainKey="analyticsDistribution" />
            {provTag ? <TimeTagChip kind={provTag} /> : null}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-xs">
          {funnel && funnel.languages.length > 0 ? (
            funnel.languages.map((lang) => {
              const share = funnel.n_turns ? lang.n_turns / funnel.n_turns : 0;
              return (
                <div
                  key={lang.language}
                  className="grid grid-cols-[44px_1fr_auto] items-center gap-2"
                >
                  <span className="uppercase text-[var(--muted-foreground)]">{lang.language}</span>
                  <span className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
                    <span
                      className={cn("block h-full rounded-full", dotBg[rateTone(lang.mean_score)])}
                      style={{ width: `${share * 100}%` }}
                    />
                  </span>
                  <span className="tabular-nums text-[var(--muted-foreground)]">
                    {lang.n_turns}
                  </span>
                </div>
              );
            })
          ) : (
            <p className="py-8 text-center text-[var(--muted-foreground)]">{t("empty")}</p>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-lg">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("impact")}
            <SectionInfo title={t("impact")} explainKey="analyticsImpact" />
            {provTag ? <TimeTagChip kind={provTag} /> : null}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {controls.length > 0 ? (
            [...controls]
              .sort((a, b) => b.severity - a.severity)
              .map((c) => (
                <div
                  key={c.id}
                  className="grid grid-cols-[120px_1fr_44px] items-center gap-2 text-xs"
                >
                  <span className="truncate text-[var(--muted-foreground)]">{ts(c.id)}</span>
                  <span className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
                    <span
                      className={cn("block h-full rounded-full", dotBg[c.state.tone])}
                      style={{ width: `${Math.min(c.severity * 100, 100)}%` }}
                    />
                  </span>
                  <span className="font-mono tabular-nums">{c.value}</span>
                </div>
              ))
          ) : (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Governance — real roadmap-derived recommended actions
// ---------------------------------------------------------------------------

const severityTone: Record<string, OverviewTone> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

function GovernanceSection({
  roadmap,
  loading,
  provTag,
}: {
  roadmap?: import("@/lib/api/schemas").RoadmapReport;
  loading: boolean;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.governance");
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          <SectionInfo title={t("title")} explainKey="governanceSection" />
          {provTag ? <TimeTagChip kind={provTag} /> : null}
        </CardTitle>
        <Badge tone="neutral">{t("subtitle")}</Badge>
      </CardHeader>
      <CardContent className="grid gap-2 sm:grid-cols-2">
        {loading ? (
          <Skeleton className="h-20 w-full sm:col-span-2" />
        ) : !roadmap || roadmap.n_items === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)] sm:col-span-2">
            {t("empty")}
          </p>
        ) : (
          roadmap.items.map((item) => (
            <div
              key={item.signal}
              className="rounded-md border border-[var(--border)] bg-[var(--muted)]/20 p-3"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{item.theme}</span>
                <Badge className={toneBg[severityTone[item.severity] ?? "neutral"]}>
                  {item.severity}
                </Badge>
              </div>
              <p className="mt-1 text-[0.7rem] text-[var(--muted-foreground)]">{item.suggestion}</p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Footer — audit chain + signal census
// ---------------------------------------------------------------------------

function TrustFooter({
  controls,
  verified,
  auditLength,
  systemsOk,
  asOf,
  provTag,
}: {
  controls: ControlRow[];
  verified?: boolean;
  auditLength?: number;
  systemsOk?: boolean;
  asOf: number | null;
  provTag: TimeTagKind | null;
}) {
  const t = useTranslations("overview.footer");
  const tt = useTranslations("overview.time");
  // Signal confidence = share of tracked signals currently meeting their target.
  const ok = controls.filter((c) => c.state.key === "ok").length;
  const confidence = controls.length ? Math.round((ok / controls.length) * 100) : null;
  const confTone: OverviewTone =
    confidence == null
      ? "neutral"
      : confidence >= 80
        ? "success"
        : confidence >= 50
          ? "warning"
          : "danger";

  return (
    <footer className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-[var(--border)] bg-[var(--card)]/70 px-4 py-3 text-[0.8rem] text-[var(--muted-foreground)] shadow-[var(--shadow-card)]">
      {/* The footer mirrors the active reading (registre §D): a reconstructed
          instant + its timestamp ONLY in "À un instant"; in Historique the page
          reads the period's evolution, so the chip says "Sur la période" with NO
          single instant (the scrubbed instant belongs to the rail detail alone,
          never the whole-page footer). Live carries no chip. */}
      {provTag === "atT" && asOf != null ? (
        <span className="flex items-center gap-2">
          <TimeTagChip kind="atT" />
          <span className="tabular-nums">{tt("asOfEvidence", { time: fmtStamp(asOf) })}</span>
        </span>
      ) : provTag === "period" ? (
        <span className="flex items-center gap-2">
          <TimeTagChip kind="period" />
        </span>
      ) : null}
      <span className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", dotBg[confTone])} />
        {t("confidence")} :{" "}
        <b className={cn("font-semibold tabular-nums", toneText[confTone])}>
          {confidence == null ? "—" : `${confidence}%`}
        </b>
        <SectionInfo title={t("confidence")} explainKey="footerConfidence" />
      </span>
      <span className="h-[4px] w-32 overflow-hidden rounded-full bg-[var(--tessera-border)]">
        <span
          className={cn("block h-full rounded-full", dotBg[confTone])}
          style={{ width: `${confidence ?? 0}%` }}
        />
      </span>
      {/* The audit COUNT projects as-of-T (entries ≤ T), but the chain INTEGRITY is a
          structural "now" check over the whole log (registre §9 / rail-data-provenance
          §5). Under a mode chip, a tooltip says so — the badge never implies the
          integrity was reconstructed at a past instant. */}
      <span className="flex items-center gap-2" title={provTag ? t("auditAsOfTip") : undefined}>
        <span
          className={cn("h-2 w-2 rounded-full", dotBg[verified === false ? "danger" : "success"])}
        />
        {verified === false
          ? t("auditBroken")
          : verified
            ? t("auditIntact", { n: auditLength ?? 0 })
            : t("auditUnknown")}
      </span>
      {/* Process liveness has NO as-of-T substrate (rail-data-provenance §5): it is a
          present-tense now-check, never reconstructed at T. So under a mode chip it
          carries an explicit "live" marker — the footer's reading chip never implies
          the systems were "operational at that past instant". */}
      <span className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", dotBg[systemsOk ? "success" : "warning"])} />
        {systemsOk ? t("systemsOk") : t("systemsDegraded")}
        {provTag ? <TimeTagChip kind="live" /> : null}
      </span>
      <Link
        href="/surveiller/observabilite"
        className="ml-auto text-[var(--tessera-fg-info)] hover:underline"
      >
        {t("viewHealth")} →
      </Link>
    </footer>
  );
}
