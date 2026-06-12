"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Coins,
  Flag,
  GitBranch,
  History,
  Info,
  Pause,
  PlayCircle,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  SkipBack,
  SkipForward,
  TriangleAlert,
} from "lucide-react";
import { useTranslations } from "next-intl";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRouter } from "@/i18n/navigation";
import {
  fetchAIAct,
  fetchAnomalies,
  fetchAuditIntegrity,
  fetchConformance,
  fetchCost,
  fetchEvalScores,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchHealth,
  fetchPiiLeak,
  fetchPlaybooks,
  fetchReadiness,
  fetchRefusal,
  fetchRoadmap,
  fetchSLO,
  fetchTimeline,
  fetchToolValidity,
  fetchToxicity,
  fetchTrend,
  fetchWhatChanged,
  runRedteam,
} from "@/lib/api/client";
import type {
  AnomalyReport,
  ConformanceReport,
  FirewallEfficacy,
  PIILeakSummary,
  PlaybookReport,
  RefusalReport,
  SLOReport,
  TimelineReport,
  ToolValidity,
  ToxicityReport,
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
import { setTemporalContext } from "@/lib/temporal-context";

const POLL_MS = 15_000;
const POLL_FAST_MS = 10_000;

export function OverviewDashboard() {
  const t = useTranslations("overview");
  const [mode, setMode] = useState<"live" | "replay">("live");
  // T being viewed, lifted out of the rail so the whole page reads "à T" (ADR
  // 0011). null = live (now); a number is a paused instant on the rail. The
  // cursor (`selectedAt`) moves continuously for a smooth UI; the value fed to
  // the backend (`committedAt`) is debounced so dragging fires one request per
  // settle, not one per pixel (the backend is rate-limited).
  const [selectedAt, setSelectedAt] = useState<number | null>(null);
  const [committedAt, setCommittedAt] = useState<number | null>(null);
  // The visible window; lifted from the rail so the shared temporal context
  // (and thus the topbar evidence pack) knows the active period.
  const [periodKey, setPeriodKey] = useState("d7");
  useEffect(() => {
    const id = window.setTimeout(() => setCommittedAt(selectedAt), 250);
    return () => window.clearTimeout(id);
  }, [selectedAt]);
  // ISO instant fed to the as-of-T-capable queries (slo/trend/scores). null in
  // live mode → the backend reads the live buffer; set → it recomputes ≤ T.
  const asOf =
    mode === "replay" && committedAt != null ? new Date(committedAt).toISOString() : null;
  const historyMode = asOf != null;
  // Mirror the temporal context so the topbar's evidence pack / report export is
  // scoped to (period, asOf), not just "now" (ADR 0011 §3/§5).
  useEffect(() => {
    setTemporalContext({ asOf, period: periodKey });
  }, [asOf, periodKey]);
  // Returning to live clears the focused instant so every block re-reads "now".
  function changeMode(next: "live" | "replay") {
    if (next === "live") setSelectedAt(null);
    setMode(next);
  }

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
  const slo = useQuery({
    queryKey: ["ov-slo", asOf],
    queryFn: ({ signal }) => fetchSLO(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const trend = useQuery({
    queryKey: ["ov-trend", asOf],
    queryFn: ({ signal }) => fetchTrend(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const whatChanged = useQuery({
    queryKey: ["ov-what-changed", asOf],
    queryFn: ({ signal }) => fetchWhatChanged(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : 20_000,
    placeholderData: keepPreviousData,
  });

  // --- Safety / guard signals ---------------------------------------------
  // refusal + firewall measure a FIXED corpus through the guard "now" — a
  // property of the current policy, identical at any T — so they stay live.
  const toxicity = useQuery({
    queryKey: ["ov-toxicity", asOf],
    queryFn: ({ signal }) => fetchToxicity(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const piiLeak = useQuery({
    queryKey: ["ov-pii", asOf],
    queryFn: ({ signal }) => fetchPiiLeak(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const refusal = useQuery({
    queryKey: ["ov-refusal"],
    queryFn: ({ signal }) => fetchRefusal(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const conformance = useQuery({
    queryKey: ["ov-conformance", asOf],
    queryFn: ({ signal }) => fetchConformance(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const tools = useQuery({
    queryKey: ["ov-tools", asOf],
    queryFn: ({ signal }) => fetchToolValidity(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const firewall = useQuery({
    queryKey: ["ov-firewall"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  // --- Incidents / risk ----------------------------------------------------
  const anomalies = useQuery({
    queryKey: ["ov-anomalies", asOf],
    queryFn: ({ signal }) => fetchAnomalies(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : 20_000,
    placeholderData: keepPreviousData,
  });
  const playbooks = useQuery({
    queryKey: ["ov-playbooks", asOf],
    queryFn: ({ signal }) => fetchPlaybooks(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const roadmap = useQuery({
    queryKey: ["ov-roadmap", asOf],
    queryFn: ({ signal }) => fetchRoadmap(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : 20_000,
    placeholderData: keepPreviousData,
  });

  // --- Cost / compliance / audit ------------------------------------------
  // audit integrity is a structural hash-chain check (a "now" property) and is
  // bearer-gated, so it stays live.
  const cost = useQuery({
    queryKey: ["ov-cost", asOf],
    queryFn: ({ signal }) => fetchCost(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const aiAct = useQuery({
    queryKey: ["ov-ai-act", asOf],
    queryFn: ({ signal }) => fetchAIAct(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : 30_000,
    placeholderData: keepPreviousData,
  });
  const audit = useQuery({
    queryKey: ["ov-audit"],
    queryFn: ({ signal }) => fetchAuditIntegrity(signal),
    refetchInterval: POLL_MS,
  });
  const funnel = useQuery({
    queryKey: ["ov-funnel", asOf],
    queryFn: ({ signal }) => fetchFunnel(signal, asOf ?? undefined),
    refetchInterval: historyMode ? false : POLL_MS,
    placeholderData: keepPreviousData,
  });
  const scores = useQuery({
    queryKey: ["ov-scores", asOf],
    queryFn: ({ signal }) => fetchEvalScores(signal, asOf ?? undefined),
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
    <div className="flex w-full flex-col gap-4 pb-8">
      {/* A second header row: the time rail pins flush under the page topbar and
          stays there while the cockpit scrolls behind it. The rail keeps its own
          framed border (border-y); the wrapper only supplies the opaque bg that
          hides scrolled content. -mx-4 bleeds the bg over the side padding; the
          upward bg box-shadow fills the strip left by the main's top padding
          (clipped by main's overflow) so nothing shows through. */}
      <div className="sticky top-0 z-40 -mx-4 bg-[var(--tessera-bg)] px-4 pb-3 pt-3 shadow-[0_-16px_0_0_var(--tessera-bg)]">
        <TemporalRail
          mode={mode}
          liveStatus={liveStatus}
          timeline={timeline.data}
          sloTarget={slo.data?.threshold}
          selectedAt={selectedAt}
          onSelectedAtChange={setSelectedAt}
          periodKey={periodKey}
          onPeriodChange={setPeriodKey}
          onModeChange={changeMode}
        />
      </div>

      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <KpiCard
          label={t("kpi.quality")}
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
          trend={trend.data?.buckets.map((b) => b.mean)}
          trendEmptyLabel={t("kpi.noTrend")}
          loading={slo.isLoading && !slo.data}
          tag={historyMode ? { label: t("time.atT"), kind: "atT" } : undefined}
        />
        <KpiCard
          label={t("kpi.failingControls")}
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
          tag={historyMode ? { label: t("time.atT"), kind: "atT" } : undefined}
        />
        <KpiCard
          label={t("kpi.openRisks")}
          value={anomalies.data || playbooks.data ? String(openRisks) : "—"}
          delta={t("kpi.openRisksDelta", {
            anomalies: anomalies.data?.n_anomalous ?? 0,
            playbooks: playbooks.data?.n_triggered ?? 0,
          })}
          tone={openRisks === 0 ? "success" : openRisks > 3 ? "danger" : "warning"}
          icon={TriangleAlert}
          loading={anomalies.isLoading && playbooks.isLoading}
          tag={historyMode ? { label: t("time.atT"), kind: "atT" } : undefined}
        />
        <KpiCard
          label={t("kpi.regression")}
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
          tag={historyMode ? { label: t("time.atT"), kind: "atT" } : undefined}
        />
        <KpiCard
          label={t("kpi.cost")}
          value={cost.data ? `${cost.data.estimated_cost_eur.toFixed(2)} €` : "—"}
          delta={
            cost.data ? t("kpi.costDelta", { tokens: cost.data.total_tokens.toLocaleString() }) : ""
          }
          tone={cost.data && cost.data.n_anomalies > 0 ? "warning" : "info"}
          icon={Coins}
          loading={cost.isLoading}
          tag={historyMode ? { label: t("time.atT"), kind: "atT" } : undefined}
        />
        <KpiCard
          label={t("kpi.audit")}
          value={audit.data ? String(audit.data.length) : "—"}
          delta={audit.data ? (audit.data.verified ? t("kpi.auditOk") : t("kpi.auditBroken")) : ""}
          tone={audit.data ? (audit.data.verified ? "success" : "danger") : "neutral"}
          icon={ShieldCheck}
          loading={audit.isLoading}
          tag={historyMode ? { label: t("time.liveSignal"), kind: "live" } : undefined}
        />
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px] 2xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-4">
          <CriticalControlsTable
            controls={controls}
            loading={slo.isLoading && controls.length === 0}
            historyMode={historyMode}
          />
          <ControlCasesSection
            playbooks={playbooks.data}
            loading={playbooks.isLoading}
            historyMode={historyMode}
          />
          <AnalyticsSection
            trend={trend.data}
            funnel={funnel.data}
            controls={activeControls}
            historyMode={historyMode}
          />
          <GovernanceSection
            roadmap={roadmap.data}
            loading={roadmap.isLoading}
            historyMode={historyMode}
          />
        </div>
        <aside className="flex min-w-0 flex-col gap-4">
          <IncidentsCard
            playbooks={playbooks.data}
            anomalies={anomalies.data}
            loading={playbooks.isLoading && anomalies.isLoading}
            historyMode={historyMode}
          />
          <ReleaseCard
            whatChanged={whatChanged.data}
            slo={slo.data}
            toxicity={toxicity.data}
            pii={piiLeak.data}
            aiActRate={aiAct.data?.compliance_rate}
            conformance={conformance.data}
            historyMode={historyMode}
          />
          <QuickActionsCard
            onReplayAt={() => setMode("replay")}
            historyMode={historyMode}
            onBackToLive={() => changeMode("live")}
          />
          <RecentActivitiesCard
            scores={scores.data?.scores}
            loading={scores.isLoading}
            historyMode={historyMode}
          />
        </aside>
      </div>

      <TrustFooter
        controls={activeControls}
        verified={audit.data?.verified}
        auditLength={audit.data?.length}
        systemsOk={!health.isError && !readiness.isError && readiness.data?.status === "ready"}
        asOf={historyMode ? (selectedAt as number) : null}
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
function railPos(at: string, start: number, span: number): number {
  const v = new Date(at).getTime();
  if (!Number.isFinite(v) || span <= 0) return 100;
  return Math.min(100, Math.max(0, ((v - start) / span) * 100));
}

// Fixed-length date/time formatters: with tabular-nums the rendered width stays
// constant as the value changes, so the "viewing-at" label never jitters.
function fmtStamp(ms: number): string {
  return new Date(ms).toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

const PERIODS: { key: string; ms: number }[] = [
  { key: "h24", ms: 24 * 3600_000 },
  { key: "d7", ms: 7 * 24 * 3600_000 },
  { key: "d30", ms: 30 * 24 * 3600_000 },
];

function TemporalRail({
  mode,
  liveStatus,
  timeline,
  sloTarget,
  selectedAt,
  onSelectedAtChange,
  periodKey,
  onPeriodChange,
  onModeChange,
}: {
  mode: "live" | "replay";
  liveStatus: string;
  timeline?: TimelineReport;
  sloTarget?: number;
  // Controlled by the page so the focused instant T drives every block (ADR 0011).
  selectedAt: number | null;
  onSelectedAtChange: Dispatch<SetStateAction<number | null>>;
  periodKey: string;
  onPeriodChange: (period: string) => void;
  onModeChange: (mode: "live" | "replay") => void;
}) {
  const t = useTranslations("overview.time");
  const [compare, setCompare] = useState("target");
  // T being viewed and the period live at page level now; these are the rail's
  // write handles into them.
  const setSelectedAt = onSelectedAtChange;
  const setPeriodKey = onPeriodChange;
  const [playing, setPlaying] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  // The visible axis spans the chosen period, ending "now" — so 24h / 7d / 30d
  // each render a distinct scale. Real data may begin later than the window
  // start (we only have ~38h of history), marked by `dataStart`.
  const end = timeline ? new Date(timeline.window_end).getTime() : Date.now();
  const periodMs = PERIODS.find((p) => p.key === periodKey)?.ms ?? 7 * 24 * 3600_000;
  const rawStart = timeline ? new Date(timeline.window_start).getTime() : end - periodMs;
  const viewStart = end - periodMs;
  const span = Math.max(1, end - viewStart);
  const dataStart = Math.max(rawStart, viewStart);
  const events = (timeline?.events ?? []).filter((e) => {
    const v = new Date(e.at).getTime();
    return v >= viewStart && v <= end;
  });
  const currentT = selectedAt ?? end;
  // Prev/next move by a natural, perceptible unit: 1 h in 24h view, 1 day otherwise.
  const stepUnit = periodKey === "h24" ? 3600_000 : 24 * 3600_000;

  // Real quality points, used for the baseline-delta comparison (#201).
  const scorePoints = events
    .filter((e) => e.kind === "score")
    .map((e) => ({
      at: new Date(e.at).getTime(),
      v: Number.parseFloat(e.label.replace(/[^0-9.]/g, "")),
    }))
    .filter((p) => Number.isFinite(p.v));
  // Natural, computable baselines: the quality target (SLO), or the present value.
  const presentScore = scorePoints.length
    ? scorePoints.reduce((best, p) => (Math.abs(p.at - end) < Math.abs(best.at - end) ? p : best)).v
    : null;
  const baseline =
    compare === "none" ? null : compare === "now" ? presentScore : (sloTarget ?? 0.8); // "target"
  // Score nearest the focused instant (present included), for the vs-baseline delta.
  const nearestScore = scorePoints.reduce<{ v: number; d: number } | null>((best, p) => {
    const d = Math.abs(p.at - currentT);
    return !best || d < best.d ? { v: p.v, d } : best;
  }, null);
  const baselineDelta = baseline != null && nearestScore != null ? nearestScore.v - baseline : null;

  function seekToClientX(clientX: number) {
    const el = trackRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const at = viewStart + frac * span;
    setSelectedAt(at >= end - 1000 ? null : at);
  }
  function step(dir: -1 | 1) {
    const nextT = Math.min(end, Math.max(viewStart, currentT + dir * stepUnit));
    setSelectedAt(nextT >= end - 1000 ? null : nextT);
  }
  // Event nearest the focused instant (present included), for the detail panel.
  const nearest =
    events.reduce<{ ev: TimelineReport["events"][number]; d: number } | null>((best, ev) => {
      const d = Math.abs(new Date(ev.at).getTime() - currentT);
      return !best || d < best.d ? { ev, d } : best;
    }, null)?.ev ?? null;

  // Playback: sweep T across the window; reaching the end returns to live.
  useEffect(() => {
    if (!playing || mode !== "replay") return;
    const id = window.setInterval(() => {
      setSelectedAt((cur) => {
        const from = cur ?? dataStart;
        const nextT = from + span / 90;
        return nextT >= end ? null : nextT;
      });
    }, 60);
    return () => window.clearInterval(id);
  }, [playing, mode, dataStart, span, end, setSelectedAt]);
  useEffect(() => {
    if (selectedAt == null && playing) setPlaying(false);
  }, [selectedAt, playing]);

  // Compact Live rail (default): real-time badge, period, last update, Relire à T.
  if (mode === "live") {
    const last = timeline ? new Date(timeline.window_end) : null;
    return (
      <section className="flex min-h-[42px] flex-wrap items-center gap-3 border-y border-[var(--tessera-border)] bg-transparent px-1 py-2">
        <Badge className="rounded-md border-[#005c42] bg-[#003f30] px-3 py-1 text-[#7ff0b6]">
          {t("live")}
        </Badge>
        <span className="flex items-center gap-2 text-sm text-[var(--tessera-text)]">
          <span className="h-2 w-2 rounded-full bg-[var(--tessera-green)] shadow-[0_0_10px_rgba(0,200,120,0.85)]" />
          {t("realtime")}
        </span>
        <span className="h-5 w-px bg-[var(--tessera-border)]" />
        <span className="text-sm text-[var(--tessera-text-muted)]">
          {t("period")} :{" "}
          <span className="font-semibold text-[var(--tessera-text)]">{t(periodKey)}</span>
        </span>
        {last ? (
          <span className="hidden text-xs text-[var(--tessera-text-muted)] md:inline">
            {t("lastUpdate")} {last.toLocaleTimeString()}
          </span>
        ) : null}
        <span className="ml-auto hidden text-xs text-[var(--tessera-text-muted)] lg:inline">
          {liveStatus}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 border-[#9a5f18] bg-transparent px-4 text-[#f0a23a] hover:bg-[#3e260c]/35"
          onClick={() => onModeChange("replay")}
        >
          <History className="h-4 w-4" />
          {t("replayAtT")}
        </Button>
      </section>
    );
  }

  // Expanded time-travel rail: period · viewing-at-T · compare-to-baseline ·
  // playback, then an interactive scrubber over the real lineage timeline (#201).
  const handlePos = railPos(new Date(currentT).toISOString(), viewStart, span);

  return (
    <section className="rounded-md border border-[#9a5f18]/60 bg-[var(--tessera-surface)] p-4 shadow-[var(--shadow-card)]">
      {/* Auto-sized controls (no wrap); only the "viewing-at" value is fixed-width
          so dragging the scrubber never reflows this row. */}
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 px-3 text-xs text-[var(--muted-foreground)]">
          <Clock3 className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("period")}
          <select
            value={periodKey}
            onChange={(e) => {
              setPeriodKey(e.target.value);
              setSelectedAt(null);
            }}
            className="cursor-pointer rounded bg-transparent font-semibold text-[var(--foreground)] outline-none"
          >
            {PERIODS.map((p) => (
              <option key={p.key} value={p.key} className="bg-[var(--card)]">
                {t(p.key)}
              </option>
            ))}
          </select>
        </label>
        <span
          className={cn(
            "flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border px-3 text-xs",
            selectedAt == null
              ? "border-[var(--border)] bg-[var(--muted)]/30 text-[var(--muted-foreground)]"
              : "border-gold-500/50 bg-gold-500/10 text-gold-200",
          )}
        >
          <Flag className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("viewingAt")}
          <b className="font-semibold tabular-nums text-[var(--foreground)]">
            {selectedAt == null ? t("nowLive") : fmtStamp(currentT)}
          </b>
        </span>
        <label className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 px-3 text-xs text-[var(--muted-foreground)]">
          <ArrowLeftRight className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("compareTo")}
          <select
            value={compare}
            onChange={(e) => setCompare(e.target.value)}
            className="cursor-pointer rounded bg-transparent font-semibold text-[var(--foreground)] outline-none"
          >
            <option value="target" className="bg-[var(--card)]">
              {t("baselineTarget")}
            </option>
            <option value="now" className="bg-[var(--card)]">
              {t("baselineNow")}
            </option>
            <option value="none" className="bg-[var(--card)]">
              {t("noBaseline")}
            </option>
          </select>
        </label>
        <span className="ml-auto flex h-9 shrink-0 items-center gap-1 rounded-lg border border-[var(--border)] px-2 text-[var(--muted-foreground)]">
          <PlaybackButton
            label={t("first")}
            onClick={() => {
              setPlaying(false);
              setSelectedAt(viewStart);
            }}
          >
            <SkipBack className="h-3.5 w-3.5" />
          </PlaybackButton>
          <PlaybackButton
            label={t("prev")}
            onClick={() => {
              setPlaying(false);
              step(-1);
            }}
          >
            <ChevronLeft className="h-4 w-4" />
          </PlaybackButton>
          <PlaybackButton
            label={playing ? t("pause") : t("play")}
            active={playing}
            onClick={() => {
              if (selectedAt == null) setSelectedAt(dataStart);
              setPlaying((p) => !p);
            }}
          >
            {playing ? (
              <Pause className="h-4 w-4 text-gold-400" />
            ) : (
              <PlayCircle className="h-4 w-4 text-gold-400" />
            )}
          </PlaybackButton>
          <PlaybackButton
            label={t("next")}
            onClick={() => {
              setPlaying(false);
              step(1);
            }}
          >
            <ChevronRight className="h-4 w-4" />
          </PlaybackButton>
          <PlaybackButton
            label={t("now")}
            onClick={() => {
              setPlaying(false);
              setSelectedAt(null);
            }}
          >
            <SkipForward className="h-3.5 w-3.5" />
          </PlaybackButton>
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-9"
          onClick={() => {
            setPlaying(false);
            onModeChange("live");
          }}
        >
          <RotateCcw className="h-4 w-4" />
          {t("exitReplay")}
        </Button>
      </div>

      {/* Interactive scrubber — click or drag to pick T; markers are real events. */}
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label={t("viewingAt")}
        aria-valuemin={viewStart}
        aria-valuemax={end}
        aria-valuenow={currentT}
        aria-valuetext={selectedAt == null ? t("nowLive") : new Date(currentT).toLocaleString()}
        className="relative mt-6 h-14 cursor-pointer select-none"
        onPointerDown={(e) => {
          setPlaying(false);
          trackRef.current?.setPointerCapture(e.pointerId);
          seekToClientX(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) seekToClientX(e.clientX);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") step(1);
          if (e.key === "ArrowLeft") step(-1);
        }}
      >
        <div className="pointer-events-none absolute inset-x-0 top-2.5 h-0.5 rounded-full bg-[linear-gradient(90deg,#363d48,#454e5d)]" />
        {/* "real data begins here" marker — this is where the timeline data
            starts, NOT the comparison baseline. The baseline (target / present)
            is a value, shown in the detail-panel delta, so it has no fixed point
            on the time axis; pinning a "baseline" dot here was misleading. */}
        {timeline && dataStart > viewStart + span * 0.01 ? (
          <RailMarker
            pos={railPos(new Date(dataStart).toISOString(), viewStart, span)}
            label={t("dataStart")}
            variant="baseline"
          />
        ) : null}
        {/* event markers (click to seek): quality scores are labelled, guard
            noise stays a faint tick with a tooltip. */}
        {events.map((ev, i) => {
          // Only annotate lineage changes (deploy / judge) — scores and guard
          // noise stay as coloured ticks so labels never overlap.
          const annotated = ev.kind === "model_change" || ev.kind === "judge_change";
          // Guard denials carry no useful detail (target is always "user_input").
          const detail = ev.kind === "guard_denial" ? "" : ev.detail;
          return (
            <RailEvent
              key={`${ev.at}-${ev.kind}-${i}`}
              pos={railPos(ev.at, viewStart, span)}
              tone={ev.tone as OverviewTone}
              label={annotated ? ev.label : ""}
              dim={ev.kind === "guard_denial"}
              title={`${fmtStamp(new Date(ev.at).getTime())} · ${ev.label}${detail ? ` · ${detail}` : ""}`}
              onSeek={() => setSelectedAt(new Date(ev.at).getTime())}
            />
          );
        })}
        {/* the moving head — a slim downward caret crowning a thin gold stem.
            The single time readout lives in the "Tu regardes" box. */}
        <div
          className="pointer-events-none absolute top-0 -translate-x-1/2 transition-opacity"
          style={{ left: `${handlePos}%`, opacity: selectedAt == null ? 0.6 : 1 }}
        >
          {/* stem centred vertically on the timeline track (10–14px → centre 12px) */}
          <span className="absolute left-1/2 top-1.5 h-3 w-px -translate-x-1/2 bg-gold-400" />
          <span className="absolute left-1/2 top-[-1px] h-0 w-0 -translate-x-1/2 border-l-[5px] border-r-[5px] border-t-[7px] border-l-transparent border-r-transparent border-t-gold-400 drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)]" />
        </div>
        {selectedAt == null ? (
          <span
            className="pointer-events-none absolute top-7 -translate-x-1/2 whitespace-nowrap text-[0.65rem] font-medium text-gold-400"
            style={{ left: "96%" }}
          >
            {t("now")}
          </span>
        ) : null}
      </div>

      {/* Legend — what the scrubber ticks mean. */}
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.62rem] text-[var(--muted-foreground)]">
        <span className="font-medium text-[var(--foreground)]">{t("legendScores")} :</span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-0.5 rounded bg-emerald-400" />
          {t("legendGood")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-0.5 rounded bg-orange-400" />
          {t("legendFair")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-0.5 rounded bg-red-400" />
          {t("legendBad")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-px bg-red-400 opacity-40" />
          {t("legendGuard")}
        </span>
      </div>

      {/* Detail panel — always shown in replay: "live state" at the present,
          "state at the replayed instant" when paused. Reflects the focused
          event so stepping prev/next gives clear feedback even when ticks cluster. */}
      <div
        className={cn(
          "mt-2 flex items-center gap-3 rounded-md border px-3 py-2 text-xs",
          selectedAt == null
            ? "border-emerald-500/30 bg-emerald-500/5"
            : "border-gold-500/30 bg-gold-500/5",
        )}
      >
        <Badge tone={selectedAt == null ? "success" : "gold"} className="shrink-0">
          {selectedAt == null ? t("liveState") : t("relitAtBadge")}
        </Badge>
        {/* The focused-event label takes the flexible middle and truncates, so a
            varying count (e.g. "Garde — 22 refus") never shifts the badge/button
            on the right. */}
        {nearest ? (
          <span className="flex min-w-0 flex-1 items-center gap-2 text-[var(--muted-foreground)]">
            <span
              className={cn("h-2 w-2 shrink-0 rounded-full", dotBg[nearest.tone as OverviewTone])}
            />
            <span className="truncate">
              {nearest.label}
              {nearest.detail && nearest.kind !== "guard_denial" ? (
                <span className="opacity-70"> · {nearest.detail}</span>
              ) : null}
            </span>
          </span>
        ) : (
          <span className="min-w-0 flex-1 truncate text-[var(--muted-foreground)]">
            {t("noEventNear")}
          </span>
        )}
        {baselineDelta != null && baseline != null ? (
          <Badge tone={baselineDelta >= 0 ? "success" : "danger"} className="shrink-0 tabular-nums">
            {baselineDelta >= 0 ? "+" : ""}
            {baselineDelta.toFixed(2)} {t("vsBaseline")} {baseline.toFixed(2)}
          </Badge>
        ) : null}
        {selectedAt != null ? (
          <button
            type="button"
            className="shrink-0 whitespace-nowrap text-blue-300 hover:underline"
            onClick={() => {
              setPlaying(false);
              setSelectedAt(null);
            }}
          >
            {t("backToNow")} →
          </button>
        ) : null}
      </div>
    </section>
  );
}

function PlaybackButton({
  label,
  onClick,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={label}
      onClick={onClick}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded text-[var(--foreground)] transition-all hover:bg-[var(--muted)] active:scale-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500/50",
        active && "bg-gold-500/20 text-gold-300",
      )}
    >
      {children}
    </button>
  );
}

function RailMarker({
  pos,
  label,
  variant,
}: {
  pos: number;
  label: string;
  variant: "baseline";
}) {
  return (
    <>
      <div
        className="pointer-events-none absolute top-1.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-slate-400 shadow-[0_0_0_4px_rgba(130,140,153,0.15)]"
        style={{ left: `${pos}%`, opacity: variant === "baseline" ? 1 : 0.8 }}
      />
      <span
        className="pointer-events-none absolute top-7 -translate-x-1/2 whitespace-nowrap text-[0.65rem] text-[var(--muted-foreground)]"
        style={{ left: `${pos}%` }}
      >
        {label}
      </span>
    </>
  );
}

function RailEvent({
  pos,
  tone,
  label,
  title,
  dim,
  onSeek,
}: {
  pos: number;
  tone: OverviewTone;
  label: string;
  title: string;
  dim?: boolean;
  onSeek: () => void;
}) {
  return (
    <button
      type="button"
      className="absolute top-1 flex -translate-x-1/2 flex-col items-center"
      style={{ left: `${pos}%` }}
      title={title}
      onPointerDown={(e) => {
        e.stopPropagation();
        onSeek();
      }}
    >
      <span
        className={cn(
          "rounded transition-all",
          dotBg[tone] ?? dotBg.info,
          dim ? "h-2.5 w-px opacity-40 hover:opacity-80" : "h-4 w-0.5 hover:w-1",
        )}
      />
      {label ? (
        <span className="mt-1.5 max-w-[7rem] truncate text-[0.6rem] font-medium text-[var(--foreground)]">
          {label}
        </span>
      ) : null}
    </button>
  );
}

// ---------------------------------------------------------------------------
// KPI cards
// ---------------------------------------------------------------------------

/** A small "à T" / "live" provenance chip shown on blocks in history mode. */
type TimeTag = { label: string; kind: "atT" | "live" };

function TimeTagChip({ tag, className }: { tag: TimeTag; className?: string }) {
  return (
    <span
      className={cn(
        "rounded px-1.5 py-0.5 text-[0.58rem] font-medium uppercase leading-none tracking-wide",
        tag.kind === "atT"
          ? "border border-gold-500/40 bg-gold-500/10 text-gold-300"
          : "border border-[var(--border)] bg-[var(--muted)]/40 text-[var(--muted-foreground)]",
        className,
      )}
    >
      {tag.label}
    </span>
  );
}

/** Signed /100-point delta (e.g. −4 / +3) for an "à T vs baseline" reading. */
function signedPts(fraction: number): string {
  const pts = Math.round(fraction * 100);
  return `${pts >= 0 ? "+" : ""}${pts}`;
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
}: {
  label: string;
  value: string;
  delta: string;
  tone: OverviewTone;
  icon: typeof Activity;
  trend?: number[];
  trendEmptyLabel?: string;
  loading?: boolean;
  tag?: TimeTag;
}) {
  return (
    <Card className="group relative overflow-hidden rounded-lg">
      <div className={cn("absolute inset-x-0 top-0 h-0.5", dotBg[tone])} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
              {label}
              {tag ? <TimeTagChip tag={tag} /> : null}
            </p>
            {loading ? (
              <Skeleton className="mt-2 h-7 w-16" />
            ) : (
              <p className="mt-2 font-serif text-2xl font-semibold tabular-nums">{value}</p>
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
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Critical controls table
// ---------------------------------------------------------------------------

function CriticalControlsTable({
  controls,
  loading,
  historyMode,
}: { controls: ControlRow[]; loading: boolean; historyMode: boolean }) {
  const t = useTranslations("overview.criticalControls");
  const ts = useTranslations("overview.signals");
  const tst = useTranslations("overview.states");
  const ti = useTranslations("overview.impact");
  const tt = useTranslations("overview.time");

  return (
    <Card className="overflow-hidden rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
        </CardTitle>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("count", { n: controls.length })}
        </span>
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
                </tr>
              </thead>
              <tbody>
                {controls.map((c) => (
                  <tr key={c.id} className="border-b border-[var(--border)]/50">
                    <td className="px-4 py-2 font-medium">{ts(c.id)}</td>
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
                    <td className="py-2 pr-4 tabular-nums">
                      <span className="inline-flex items-center gap-1.5">
                        {c.value}
                        {historyMode && !c.noData ? (
                          <TimeTagChip
                            tag={
                              c.asOfCapable
                                ? { label: tt("atT"), kind: "atT" }
                                : { label: tt("liveSignal"), kind: "live" }
                            }
                          />
                        ) : null}
                      </span>
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
                    <td className="py-2 pr-4 text-[var(--muted-foreground)]">{ti(c.impactKey)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
  historyMode,
}: { playbooks?: PlaybookReport; loading: boolean; historyMode: boolean }) {
  const t = useTranslations("overview.controlCases");
  const tt = useTranslations("overview.time");
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between gap-3 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
        </CardTitle>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("count", { n: playbooks?.n_triggered ?? 0 })}
        </span>
      </CardHeader>
      <CardContent className="grid min-h-[4.5rem] gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {loading ? (
          <Skeleton className="h-28 w-full sm:col-span-2 xl:col-span-3" />
        ) : !playbooks || playbooks.n_triggered === 0 ? (
          <p className="py-6 text-center text-sm text-emerald-400 sm:col-span-2 xl:col-span-3">
            {t("clear")}
          </p>
        ) : (
          playbooks.playbooks.map((p) => {
            const tone = playbookTone[p.severity] ?? "neutral";
            return (
              <article
                key={p.incident}
                className={cn("rounded-lg border bg-[var(--muted)]/20 p-3", caseBorder[tone])}
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
              </article>
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
  historyMode,
}: {
  playbooks?: PlaybookReport;
  anomalies?: AnomalyReport;
  loading: boolean;
  historyMode: boolean;
}) {
  const t = useTranslations("overview.rightColumn");
  const tt = useTranslations("overview.time");
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
          {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[4.5rem] flex-col gap-2">
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
              <span className="truncate">{it.label}</span>
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
  historyMode,
}: {
  whatChanged?: import("@/lib/api/schemas").WhatChanged;
  slo?: SLOReport;
  toxicity?: ToxicityReport;
  pii?: PIILeakSummary;
  aiActRate?: number;
  conformance?: ConformanceReport;
  historyMode: boolean;
}) {
  const t = useTranslations("overview.rightColumn");
  const tt = useTranslations("overview.time");

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
            {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
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
        router.push("/observability");
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
  historyMode,
}: {
  scores?: import("@/lib/api/schemas").EvalScore[];
  loading: boolean;
  historyMode: boolean;
}) {
  const t = useTranslations("overview.rightColumn");
  const tt = useTranslations("overview.time");
  const rows = scores ? [...scores].reverse().slice(0, 6) : [];
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("activities")}
          {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[9.5rem] flex-col gap-2">
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
              <span className="truncate">
                {s.metric} · <span className="uppercase">{s.language}</span>
              </span>
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
  historyMode,
}: {
  trend?: TrendReport;
  funnel?: import("@/lib/api/schemas").FunnelReport;
  controls: ControlRow[];
  historyMode: boolean;
}) {
  const t = useTranslations("overview.analytics");
  const ts = useTranslations("overview.signals");
  const tt = useTranslations("overview.time");
  const directionTone: OverviewTone =
    trend?.direction === "improving"
      ? "success"
      : trend?.direction === "degrading"
        ? "danger"
        : "info";

  return (
    <section className="grid gap-4 xl:grid-cols-3">
      <Card className="rounded-lg">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("scores")}
            {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
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
            {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
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
                  <span className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
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
            {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
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
                  <span className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
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
  historyMode,
}: {
  roadmap?: import("@/lib/api/schemas").RoadmapReport;
  loading: boolean;
  historyMode: boolean;
}) {
  const t = useTranslations("overview.governance");
  const tt = useTranslations("overview.time");
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("title")}
          {historyMode ? <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} /> : null}
        </CardTitle>
        <Badge tone="neutral">{t("subtitle")}</Badge>
      </CardHeader>
      <CardContent className="grid min-h-[4.5rem] gap-2 sm:grid-cols-2">
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
}: {
  controls: ControlRow[];
  verified?: boolean;
  auditLength?: number;
  systemsOk?: boolean;
  asOf: number | null;
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
      {asOf != null ? (
        <span className="flex items-center gap-2">
          <TimeTagChip tag={{ label: tt("atT"), kind: "atT" }} />
          <span className="tabular-nums">{tt("asOfEvidence", { time: fmtStamp(asOf) })}</span>
        </span>
      ) : null}
      <span className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", dotBg[confTone])} />
        {t("confidence")} :{" "}
        <b className={cn("font-semibold tabular-nums", toneText[confTone])}>
          {confidence == null ? "—" : `${confidence}%`}
        </b>
        <Info className="h-3 w-3 opacity-60" />
      </span>
      <span className="h-1.5 w-32 overflow-hidden rounded-full bg-[var(--muted)]">
        <span
          className={cn("block h-full rounded-full", dotBg[confTone])}
          style={{ width: `${confidence ?? 0}%` }}
        />
      </span>
      <span className="flex items-center gap-2">
        <span
          className={cn("h-2 w-2 rounded-full", dotBg[verified === false ? "danger" : "success"])}
        />
        {verified === false
          ? t("auditBroken")
          : verified
            ? t("auditIntact", { n: auditLength ?? 0 })
            : t("auditUnknown")}
      </span>
      <span className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", dotBg[systemsOk ? "success" : "warning"])} />
        {systemsOk ? t("systemsOk") : t("systemsDegraded")}
      </span>
      <button type="button" className="ml-auto text-blue-300 hover:underline">
        {t("viewHealth")} →
      </button>
    </footer>
  );
}
