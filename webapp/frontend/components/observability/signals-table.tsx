"use client";

import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { Fragment, useMemo, useState } from "react";

import { QInfo } from "@/components/observability/quality-info";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  AnomalyReport,
  Calibration,
  CitationSummary,
  ClusterReport,
  ConformanceReport,
  ContradictionReport,
  CostReport,
  FailedCasesReport,
  FirewallEfficacy,
  FunnelReport,
  IntentReport,
  LocaleFormatSummary,
  PIILeakSummary,
  PredictorEvaluation,
  RefusalReport,
  ReleaseStatus,
  RoutingReport,
  SLOReport,
  StatusBand,
  StatusCountsTrend,
  ToolValidity,
  ToxicityReport,
  WhatChanged,
} from "@/lib/api/schemas";

/** Tabs a signals-rail link can route to (mirrors the dashboard TabKey). */
export type SignalsTab = "overview" | "signals" | "runs" | "failed" | "models" | "judge";

export type SignalStatus = "ok" | "warn" | "crit" | "na";
export type SignalCategory = "fidelity" | "security" | "compliance" | "reliability" | "sessions";
/** Owning entity of a signal (image 01 "Entité" column / filter chips). */
export type SignalEntity =
  | "judge"
  | "answer"
  | "corpus"
  | "model"
  | "session"
  | "graph"
  | "retrieval"
  | "guard"
  | "tool";

export interface SignalRow {
  key: string;
  name: string;
  category: SignalCategory;
  status: SignalStatus;
  score: string;
  threshold: string;
  sample: string;
  /** Enriched on output for the image-01 registry table. */
  id: string;
  metric: string;
  entity: SignalEntity;
  delta: number | null;
  action: string;
  role: "operator" | "admin";
}

/** Per-signal registry metadata (image 01): metric code, owning entity, the
 * governed remediation + required role. Labels/routing only — no fabricated data. */
const SIGNAL_META: Record<
  string,
  { metric: string; entity: SignalEntity; action: string; role: "operator" | "admin" }
> = {
  slo: { metric: "rag.faithfulness.mean", entity: "answer", action: "playbook", role: "operator" },
  calibration: {
    metric: "judge.cohen_kappa",
    entity: "judge",
    action: "recalibrate",
    role: "admin",
  },
  citations: {
    metric: "citation.validity",
    entity: "retrieval",
    action: "corpus",
    role: "operator",
  },
  contradiction: {
    metric: "answer.contradiction",
    entity: "answer",
    action: "review",
    role: "operator",
  },
  predictor: {
    metric: "failure.predictor.precision",
    entity: "model",
    action: "review",
    role: "operator",
  },
  clusters: { metric: "failure.clusters", entity: "answer", action: "curate", role: "operator" },
  firewall: { metric: "guard.firewall.f1", entity: "guard", action: "policy", role: "admin" },
  toxicity: { metric: "safety.toxicity.rate", entity: "answer", action: "policy", role: "admin" },
  piiLeak: { metric: "privacy.pii_leak.rate", entity: "answer", action: "policy", role: "admin" },
  refusal: { metric: "policy.refusal.rate", entity: "answer", action: "review", role: "operator" },
  conformance: {
    metric: "schema.conformance.rate",
    entity: "tool",
    action: "review",
    role: "operator",
  },
  localeFormat: {
    metric: "locale.format.rate",
    entity: "answer",
    action: "review",
    role: "operator",
  },
  tools: { metric: "tool.validity.rate", entity: "tool", action: "review", role: "operator" },
  cost: { metric: "cost.tokens.mean", entity: "model", action: "review", role: "operator" },
  routing: { metric: "routing.mismatch.rate", entity: "graph", action: "review", role: "operator" },
  funnel: {
    metric: "funnel.low_score.rate",
    entity: "session",
    action: "curate",
    role: "operator",
  },
  anomalies: {
    metric: "session.anomaly.count",
    entity: "session",
    action: "review",
    role: "operator",
  },
  intent: {
    metric: "intent.low_confidence.rate",
    entity: "session",
    action: "review",
    role: "operator",
  },
};

/** Raw report data already fetched by the dashboard, bundled for row derivation. */
export interface SignalData {
  slo?: SLOReport;
  calibration?: Calibration;
  citations?: CitationSummary;
  contradiction?: ContradictionReport;
  predictor?: PredictorEvaluation;
  clusters?: ClusterReport;
  firewall?: FirewallEfficacy;
  toxicity?: ToxicityReport;
  pii?: PIILeakSummary;
  refusal?: RefusalReport;
  conformance?: ConformanceReport;
  localeFormat?: LocaleFormatSummary;
  tools?: ToolValidity;
  cost?: CostReport;
  routing?: RoutingReport;
  funnel?: FunnelReport;
  anomalies?: AnomalyReport;
  intent?: IntentReport;
}

const pct = (x: number) => `${Math.round(x * 100)}%`;

/**
 * Derive one normalized row per quality signal from the live report data. Every
 * status/score is computed from real fields — a signal with no data reads "na"
 * and "—" rather than a fabricated value (Tessera no-mock discipline).
 */
type RawRow = Omit<SignalRow, "id" | "metric" | "entity" | "delta" | "action" | "role">;

export function buildSignalRows(t: (key: string) => string, d: SignalData): SignalRow[] {
  const rows: RawRow[] = [];

  if (d.slo) {
    const n = d.slo.n;
    rows.push({
      key: "slo",
      name: t("slo.title"),
      category: "fidelity",
      status: n === 0 ? "na" : d.slo.breaching ? "crit" : d.slo.burn_rate > 1 ? "warn" : "ok",
      score: n === 0 ? "—" : pct(d.slo.good_rate),
      threshold: `≥ ${d.slo.threshold.toFixed(2)}`,
      sample: n === 0 ? "—" : `${n} tours`,
    });
  }
  if (d.calibration) {
    const a = d.calibration;
    rows.push({
      key: "calibration",
      name: t("calibration.title"),
      category: "fidelity",
      status: !a.available ? "na" : a.lenient ? "warn" : "ok",
      score: a.available ? pct(a.agreement ?? 0) : "—",
      threshold: "κ ≥ 0.60",
      sample: a.available && a.kappa != null ? `κ ${a.kappa.toFixed(2)}` : "—",
    });
  }
  if (d.citations) {
    const c = d.citations;
    rows.push({
      key: "citations",
      name: t("citations.title"),
      category: "fidelity",
      status:
        c.n_citations === 0
          ? "na"
          : c.validity_rate >= 0.95
            ? "ok"
            : c.validity_rate >= 0.8
              ? "warn"
              : "crit",
      score: c.n_citations === 0 ? "—" : pct(c.validity_rate),
      threshold: "≥ 95%",
      sample: `${c.n_unsupported}/${c.n_citations}`,
    });
  }
  if (d.contradiction) {
    const c = d.contradiction;
    rows.push({
      key: "contradiction",
      name: t("contradiction.title"),
      category: "fidelity",
      status:
        c.n_turns === 0
          ? "na"
          : c.n_contradictions === 0
            ? "ok"
            : c.n_contradictions <= 2
              ? "warn"
              : "crit",
      score: String(c.n_contradictions),
      threshold: "= 0",
      sample: `${c.n_sessions} sessions`,
    });
  }
  if (d.predictor) {
    const p = d.predictor;
    rows.push({
      key: "predictor",
      name: t("predictor.title"),
      category: "fidelity",
      status: p.n === 0 ? "na" : p.precision >= 0.7 ? "ok" : p.precision >= 0.4 ? "warn" : "crit",
      score: p.n === 0 ? "—" : pct(p.precision),
      threshold: "≥ 70%",
      sample: p.n === 0 ? "—" : `R ${pct(p.recall)}`,
    });
  }
  if (d.clusters) {
    const c = d.clusters;
    rows.push({
      key: "clusters",
      name: t("clusters.title"),
      category: "fidelity",
      status: !c.available ? "na" : (c.n_failures ?? 0) === 0 ? "ok" : "warn",
      score: c.available ? String(c.n_failures ?? 0) : "—",
      threshold: "—",
      sample: c.available ? `${c.k ?? 0} thèmes` : "—",
    });
  }

  if (d.firewall) {
    const f = d.firewall;
    rows.push({
      key: "firewall",
      name: t("firewall.title"),
      category: "security",
      status: f.f1 >= 0.9 ? "ok" : f.f1 >= 0.7 ? "warn" : "crit",
      score: pct(f.f1),
      threshold: "F1 ≥ 0.90",
      sample: `P ${pct(f.precision)} · R ${pct(f.recall)}`,
    });
  }
  if (d.toxicity) {
    const x = d.toxicity;
    rows.push({
      key: "toxicity",
      name: t("toxicity.title"),
      category: "security",
      status: x.n_turns === 0 ? "na" : x.n_toxic === 0 ? "ok" : "crit",
      score: `${x.n_toxic}/${x.n_turns}`,
      threshold: "= 0",
      sample: x.n_turns === 0 ? "—" : pct(x.toxicity_rate),
    });
  }
  if (d.pii) {
    const p = d.pii;
    rows.push({
      key: "piiLeak",
      name: t("piiLeak.title"),
      category: "security",
      status: p.n_turns === 0 ? "na" : p.n_with_leak === 0 ? "ok" : "crit",
      score: `${p.n_with_leak}/${p.n_turns}`,
      threshold: "= 0",
      sample: p.n_turns === 0 ? "—" : pct(p.leak_rate),
    });
  }

  if (d.refusal) {
    const r = d.refusal;
    const worst = Math.max(r.over_refusal_rate, r.under_refusal_rate);
    rows.push({
      key: "refusal",
      name: t("refusal.title"),
      category: "compliance",
      status: worst === 0 ? "ok" : worst <= 0.1 ? "warn" : "crit",
      score: pct(r.over_refusal_rate),
      threshold: "≤ 10%",
      sample: `sous ${pct(r.under_refusal_rate)}`,
    });
  }
  if (d.conformance) {
    const c = d.conformance;
    rows.push({
      key: "conformance",
      name: t("conformance.title"),
      category: "compliance",
      status:
        c.n_fields_checked === 0
          ? "na"
          : c.conformance_rate >= 1
            ? "ok"
            : c.conformance_rate >= 0.9
              ? "warn"
              : "crit",
      score: c.n_fields_checked === 0 ? "—" : pct(c.conformance_rate),
      threshold: "= 100%",
      sample: `${c.n_violations} viol.`,
    });
  }
  if (d.localeFormat) {
    const l = d.localeFormat;
    rows.push({
      key: "localeFormat",
      name: t("localeFormat.title"),
      category: "compliance",
      status:
        l.n_amounts === 0
          ? "na"
          : l.correctness_rate >= 1
            ? "ok"
            : l.correctness_rate >= 0.95
              ? "warn"
              : "crit",
      score: l.n_amounts === 0 ? "—" : pct(l.correctness_rate),
      threshold: "= 100%",
      sample: `${l.n_violations}/${l.n_amounts}`,
    });
  }

  if (d.tools) {
    const tl = d.tools;
    rows.push({
      key: "tools",
      name: t("tools.title"),
      category: "reliability",
      status:
        tl.total === 0
          ? "na"
          : tl.validity_rate >= 0.95
            ? "ok"
            : tl.validity_rate >= 0.85
              ? "warn"
              : "crit",
      score: tl.total === 0 ? "—" : pct(tl.validity_rate),
      threshold: "≥ 95%",
      sample: `${tl.denied + tl.errored + tl.arg_failures} rejets`,
    });
  }
  if (d.cost) {
    const c = d.cost;
    rows.push({
      key: "cost",
      name: t("cost.title"),
      category: "reliability",
      status: c.n_turns === 0 ? "na" : c.n_anomalies === 0 ? "ok" : "warn",
      score: `${Math.round(c.mean_tokens)} tok`,
      threshold: `≤ ${Math.round(c.threshold_tokens)}`,
      sample: `${c.estimated_cost_eur.toFixed(2)} €`,
    });
  }

  if (d.routing) {
    const r = d.routing;
    rows.push({
      key: "routing",
      name: t("routing.title"),
      category: "sessions",
      status:
        r.n === 0 ? "na" : r.mismatch_rate === 0 ? "ok" : r.mismatch_rate <= 0.05 ? "warn" : "crit",
      score: r.n === 0 ? "—" : pct(1 - r.mismatch_rate),
      threshold: "≥ 95%",
      sample: `${r.mismatches} mismatch`,
    });
  }
  if (d.funnel) {
    const langs = d.funnel.languages ?? [];
    const worst = langs.reduce((m, l) => Math.max(m, l.low_score_rate), 0);
    rows.push({
      key: "funnel",
      name: t("funnel.title"),
      category: "sessions",
      status: langs.length === 0 ? "na" : worst <= 0.1 ? "ok" : worst <= 0.25 ? "warn" : "crit",
      score: langs.length === 0 ? "—" : pct(1 - worst),
      threshold: "≥ 90%",
      sample: `${d.funnel.n_turns} tours`,
    });
  }
  if (d.anomalies) {
    const a = d.anomalies;
    rows.push({
      key: "anomalies",
      name: t("anomalies.title"),
      category: "sessions",
      status: a.n_sessions === 0 ? "na" : a.n_anomalous === 0 ? "ok" : "warn",
      score: `${a.n_anomalous}/${a.n_sessions}`,
      threshold: "= 0",
      sample: `${a.n_sessions} sessions`,
    });
  }
  if (d.intent) {
    const i = d.intent;
    rows.push({
      key: "intent",
      name: t("intent.title"),
      category: "sessions",
      status:
        i.n === 0
          ? "na"
          : i.low_confidence_rate <= 0.1
            ? "ok"
            : i.low_confidence_rate <= 0.25
              ? "warn"
              : "crit",
      score: i.n === 0 ? "—" : pct(1 - i.low_confidence_rate),
      threshold: "≥ 90%",
      sample: `${i.unknown} inconnus`,
    });
  }

  // Enrich each row with its registry metadata + a stable id (image 01).
  const fallback = {
    metric: "—",
    entity: "answer" as SignalEntity,
    action: "review" as const,
    role: "operator" as const,
  };
  return rows.map((r, i) => {
    const meta = SIGNAL_META[r.key] ?? fallback;
    return {
      ...r,
      id: `#${String(i + 1).padStart(3, "0")}`,
      metric: meta.metric,
      entity: meta.entity,
      delta: null,
      action: meta.action,
      role: meta.role,
    };
  });
}

const STATUS_TONE: Record<SignalStatus, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  warn: "warning",
  crit: "danger",
  na: "neutral",
};
const STATUSES: SignalStatus[] = ["ok", "warn", "crit", "na"];

export function summarizeSignals(
  rows: SignalRow[],
): Record<SignalStatus, number> & { total: number } {
  const s = { ok: 0, warn: 0, crit: 0, na: 0, total: rows.length };
  for (const r of rows) s[r.status] += 1;
  return s;
}

const GAUGE_COLORS: Record<SignalStatus, string> = {
  ok: "#10b981",
  warn: "#f59e0b",
  crit: "#ef4444",
  na: "#64748b",
};

/** Radial health gauge: green signals over total, ring split by status (image 00). */
export function QualityGauge({ summary }: { summary: ReturnType<typeof summarizeSignals> }) {
  const tq = useTranslations("quality");
  const total = summary.total || 1;
  const r = 54;
  const circ = 2 * Math.PI * r;
  let acc = 0;
  return (
    <Card className="flex flex-col items-center gap-4 p-5">
      <div className="relative h-[150px] w-[150px]">
        <svg viewBox="0 0 150 150" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="75"
            cy="75"
            r={r}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="13"
          />
          {STATUSES.map((key) => {
            const len = (summary[key] / total) * circ;
            const seg = (
              <circle
                key={key}
                cx="75"
                cy="75"
                r={r}
                fill="none"
                stroke={GAUGE_COLORS[key]}
                strokeWidth="13"
                strokeDasharray={`${len} ${circ - len}`}
                strokeDashoffset={-acc}
              />
            );
            acc += len;
            return seg;
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-serif text-4xl font-semibold tabular-nums text-emerald-500">
            {summary.ok}
          </span>
          <span className="text-[0.7rem] text-[var(--muted-foreground)]">
            / {summary.total} {tq("signalsTable.status.ok").toLowerCase()}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-xs">
        {STATUSES.map((key) => (
          <span key={key} className="flex items-center gap-1.5 text-[var(--muted-foreground)]">
            <span className="h-2 w-2 rounded-full" style={{ background: GAUGE_COLORS[key] }} />
            {tq(`signalsTable.status.${key}`)} {summary[key]}
          </span>
        ))}
      </div>
    </Card>
  );
}

/** Filterable, sortable catalogue of every quality signal (reference image 01). */
/** Display order of the severity groups in the registry (crit first, image 01). */
const GROUP_ORDER: SignalStatus[] = ["crit", "warn", "ok", "na"];
const COLS = 11;

/** "Registre des signaux qualité" — the full registry table grouped by severity,
 * with search + entity/status filter chips (reference image 01). */
export function SignalsTable({
  rows,
  selectedKey,
  onSelect,
}: {
  rows: SignalRow[];
  selectedKey?: string | null;
  onSelect?: (row: SignalRow) => void;
}) {
  const tq = useTranslations("quality");
  const tt = useTranslations("table");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<SignalStatus | "all">("all");
  const [entity, setEntity] = useState<SignalEntity | "all">("all");
  const [collapsed, setCollapsed] = useState<Set<SignalStatus>>(new Set());
  const toggle = (s: SignalStatus) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(s) ? next.delete(s) : next.add(s);
      return next;
    });

  const entities = useMemo(() => Array.from(new Set(rows.map((r) => r.entity))).sort(), [rows]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (status !== "all" && r.status !== status) return false;
      if (entity !== "all" && r.entity !== entity) return false;
      if (!q) return true;
      return (
        r.name.toLowerCase().includes(q) ||
        r.metric.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q) ||
        r.entity.toLowerCase().includes(q)
      );
    });
  }, [rows, query, status, entity]);

  const summary = summarizeSignals(rows);
  const groups = GROUP_ORDER.map((s) => ({
    status: s,
    rows: shown.filter((r) => r.status === s).sort((a, b) => a.name.localeCompare(b.name)),
  })).filter((g) => g.rows.length > 0);

  return (
    <Card>
      <CardHeader className="gap-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="flex items-center gap-1.5">
            <CardTitle className="text-sm">{tq("signalsTable.title")}</CardTitle>
            <QInfo title={tq("signalsTable.title")} k="sigRegistry" />
          </span>
          <span className="text-xs text-[var(--muted-foreground)]">
            {tq("signalsTable.count", { shown: shown.length, total: summary.total })}
          </span>
        </div>
        {/* Search + status filter on one row */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="-translate-y-1/2 absolute top-1/2 left-2.5 h-3.5 w-3.5 text-[var(--muted-foreground)]" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={tq("signalsTable.search")}
              className="h-8 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pr-2 pl-8 text-xs text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-[var(--tessera-border-strong)] focus:outline-none"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={status === "all"} onClick={() => setStatus("all")}>
              {tq("signalsTable.all")}
            </Chip>
            {GROUP_ORDER.map((s) => (
              <Chip
                key={s}
                active={status === s}
                onClick={() => setStatus(s)}
                tone={STATUS_TONE[s]}
              >
                {tq(`signalsTable.status.${s}`)} · {summary[s]}
              </Chip>
            ))}
          </div>
        </div>
        {/* Entity filter chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[0.7rem] text-[var(--muted-foreground)]">
            {tq("signalsTable.cols.entity")} :
          </span>
          <Chip active={entity === "all"} onClick={() => setEntity("all")}>
            {tq("signalsTable.all")}
          </Chip>
          {entities.map((e) => (
            <Chip key={e} active={entity === e} onClick={() => setEntity(e)}>
              {tq(`signalsTable.entity.${e}`)}
            </Chip>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {shown.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("signalsTable.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] table-fixed text-xs">
              <thead>
                <tr className="border-[var(--border)] border-b text-left text-[0.66rem] uppercase tracking-wide text-[var(--muted-foreground)]">
                  <th className="w-[7%] py-1.5 pr-2 pl-5 font-medium">
                    {tq("signalsTable.cols.id")}
                  </th>
                  <th className="w-[20%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.signal")}
                  </th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.theme")}
                  </th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.entity")}
                  </th>
                  <th className="w-[7%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.value")}
                  </th>
                  <th className="w-[8%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.threshold")}
                  </th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.status")}
                  </th>
                  <th className="w-[8%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.trend")}
                  </th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">
                    {tq("signalsTable.cols.action")}
                  </th>
                  <th className="w-[8%] px-2 py-1.5 font-medium">{tq("signalsTable.cols.role")}</th>
                  <th className="w-28 py-1.5 pr-4 pl-2 font-medium">
                    <span className="sr-only">{tt("rowOpen")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => {
                  const open = !collapsed.has(g.status);
                  const tone =
                    g.status === "crit"
                      ? "text-red-500"
                      : g.status === "warn"
                        ? "text-amber-500"
                        : g.status === "ok"
                          ? "text-emerald-500"
                          : "text-[var(--muted-foreground)]";
                  return (
                    <Fragment key={g.status}>
                      <tr>
                        <td colSpan={COLS} className="pt-3 pb-1">
                          <button
                            type="button"
                            onClick={() => toggle(g.status)}
                            className={`flex items-center gap-1 text-[0.7rem] font-semibold ${tone}`}
                          >
                            {open ? (
                              <ChevronDown className="h-3 w-3" />
                            ) : (
                              <ChevronRight className="h-3 w-3" />
                            )}
                            {tq(`signalsTable.group.${g.status}`)} ({g.rows.length})
                          </button>
                        </td>
                      </tr>
                      {open &&
                        g.rows.map((r) => (
                          <tr
                            key={r.key}
                            onClick={() => onSelect?.(r)}
                            // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                            role="button"
                            tabIndex={0}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                onSelect?.(r);
                              }
                            }}
                            className={`group cursor-pointer border-[var(--border)]/50 border-b outline-none transition-colors hover:bg-[var(--tessera-muted)] focus-visible:bg-[var(--tessera-muted)] ${
                              selectedKey === r.key ? "bg-[var(--tessera-muted)]" : ""
                            }`}
                          >
                            <td className="py-2 pr-2 pl-5 font-mono text-[var(--muted-foreground)]">
                              <span className="block truncate" title={r.id}>
                                {r.id}
                              </span>
                            </td>
                            <td className="px-2 py-2">
                              <div className="flex min-w-0 flex-col">
                                <span
                                  className="truncate font-medium text-[var(--foreground)]"
                                  title={r.name}
                                >
                                  {r.name}
                                </span>
                                <span
                                  className="truncate font-mono text-[0.65rem] text-[var(--muted-foreground)]"
                                  title={r.metric}
                                >
                                  {r.metric}
                                </span>
                              </div>
                            </td>
                            <td className="px-2 py-2 text-[var(--muted-foreground)]">
                              <span className="block truncate">
                                {tq(`signalsTable.cat.${r.category}`)}
                              </span>
                            </td>
                            <td className="px-2 py-2 text-[var(--muted-foreground)]">
                              <span className="block truncate">
                                {tq(`signalsTable.entity.${r.entity}`)}
                              </span>
                            </td>
                            <td className="px-2 py-2 font-semibold tabular-nums">{r.score}</td>
                            <td className="px-2 py-2 tabular-nums text-[var(--muted-foreground)]">
                              {r.threshold}
                            </td>
                            <td className="px-2 py-2">
                              <Badge tone={STATUS_TONE[r.status]}>
                                {tq(`signalsTable.status.${r.status}`)}
                              </Badge>
                            </td>
                            <td className="px-2 py-2 text-[var(--muted-foreground)]">
                              {r.delta == null ? "—" : `${r.delta >= 0 ? "↑" : "↓"} ${r.sample}`}
                            </td>
                            <td className="px-2 py-2 text-[var(--muted-foreground)]">
                              <span className="block truncate">
                                {tq(`signalsTable.action.${r.action}`)}
                              </span>
                            </td>
                            <td className="px-2 py-2">
                              <Badge tone={r.role === "admin" ? "warning" : "success"}>
                                {r.role === "admin" ? "Admin+" : "Operator+"}
                              </Badge>
                            </td>
                            <td className="py-2 pr-4 pl-2">
                              <span className="flex items-center justify-end gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#7ff0b6]">
                                <span className="opacity-0 transition-opacity group-hover:opacity-100">
                                  {tt("rowOpen")}
                                </span>
                                <ChevronRight className="h-3.5 w-3.5" />
                              </span>
                            </td>
                          </tr>
                        ))}
                    </Fragment>
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

function Chip({
  active,
  onClick,
  tone,
  children,
}: {
  active: boolean;
  onClick: () => void;
  tone?: "success" | "warning" | "danger" | "neutral";
  children: React.ReactNode;
}) {
  const dot =
    tone === "success"
      ? "bg-emerald-500"
      : tone === "warning"
        ? "bg-amber-500"
        : tone === "danger"
          ? "bg-red-500"
          : tone === "neutral"
            ? "bg-[var(--muted-foreground)]"
            : "";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors ${
        active
          ? "border-gold-500/50 bg-gold-500/10 text-gold-200"
          : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      }`}
    >
      {dot ? <span className={`h-1.5 w-1.5 rounded-full ${dot}`} /> : null}
      {children}
    </button>
  );
}

const CATEGORY_LIST: SignalCategory[] = [
  "fidelity",
  "security",
  "compliance",
  "reliability",
  "sessions",
];
const THEME_COLORS: Record<SignalCategory, string> = {
  fidelity: "#3b82f6",
  security: "#ef4444",
  compliance: "#f59e0b",
  reliability: "#10b981",
  sessions: "#8b5cf6",
};

/** "Répartition par thème" — signal counts per category as a donut (image 01). */
export function ThemeDistribution({ rows }: { rows: SignalRow[] }) {
  const tq = useTranslations("quality");
  const counts = CATEGORY_LIST.map((c) => ({
    cat: c,
    n: rows.filter((r) => r.category === c).length,
  })).filter((e) => e.n > 0);
  const total = counts.reduce((s, e) => s + e.n, 0) || 1;
  const r = 46;
  const circ = 2 * Math.PI * r;
  let acc = 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5 text-sm">
          {tq("signalsTable.themeTitle")}
          <QInfo title={tq("signalsTable.themeTitle")} k="sigTheme" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative h-[104px] w-[104px] shrink-0">
            <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90" aria-hidden="true">
              <circle
                cx="60"
                cy="60"
                r={r}
                fill="none"
                stroke="var(--tessera-border)"
                strokeWidth="12"
              />
              {counts.map((e) => {
                const len = (e.n / total) * circ;
                const seg = (
                  <circle
                    key={e.cat}
                    cx="60"
                    cy="60"
                    r={r}
                    fill="none"
                    stroke={THEME_COLORS[e.cat]}
                    strokeWidth="12"
                    strokeDasharray={`${len} ${circ - len}`}
                    strokeDashoffset={-acc}
                  />
                );
                acc += len;
                return seg;
              })}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-serif text-xl font-semibold tabular-nums">{total}</span>
              <span className="text-[0.6rem] text-[var(--muted-foreground)]">
                {tq("signalsTable.signalsLabel")}
              </span>
            </div>
          </div>
          <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.7rem]">
            {counts.map((e) => (
              <li key={e.cat} className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span
                    className="h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: THEME_COLORS[e.cat] }}
                  />
                  <span className="truncate">{tq(`signalsTable.cat.${e.cat}`)}</span>
                </span>
                <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
                  {Math.round((e.n / total) * 100)}% · {e.n}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

/** Heatmap of signal counts per entity × severity (image 01). */
export function SignalHeatmap({ rows }: { rows: SignalRow[] }) {
  const tq = useTranslations("quality");
  const cols: SignalStatus[] = ["ok", "warn", "crit"];
  const entities = Array.from(new Set(rows.map((r) => r.entity))).sort();
  const cell = (e: SignalEntity, s: SignalStatus) =>
    rows.filter((r) => r.entity === e && r.status === s).length;
  const max = Math.max(1, ...entities.flatMap((e) => cols.map((s) => cell(e, s))));
  const tone: Record<SignalStatus, string> = {
    ok: "16, 185, 129",
    warn: "245, 158, 11",
    crit: "239, 68, 68",
    na: "100, 116, 139",
  };
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5 text-sm">
          {tq("signalsTable.heatmapTitle")}
          <QInfo title={tq("signalsTable.heatmapTitle")} k="sigHeatmap" />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-[0.65rem]">
            <thead>
              <tr className="text-[var(--muted-foreground)]">
                <th className="pb-1 text-left font-medium">{tq("signalsTable.cols.entity")}</th>
                {cols.map((s) => (
                  <th key={s} className="pb-1 px-1 text-center font-medium">
                    {tq(`signalsTable.status.${s}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entities.map((e) => (
                <tr key={e}>
                  <td className="py-0.5 pr-2 text-[var(--muted-foreground)]">
                    {tq(`signalsTable.entity.${e}`)}
                  </td>
                  {cols.map((s) => {
                    const n = cell(e, s);
                    return (
                      <td key={s} className="px-0.5 py-0.5">
                        <div
                          className="flex h-5 items-center justify-center rounded tabular-nums"
                          style={{
                            background:
                              n === 0
                                ? "var(--tessera-border)"
                                : `rgba(${tone[s]}, ${0.25 + (n / max) * 0.6})`,
                            color: n === 0 ? "var(--muted-foreground)" : "#fff",
                          }}
                        >
                          {n || ""}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

const STATUS_HEX: Record<SignalStatus, string> = {
  ok: "#10b981",
  warn: "#f59e0b",
  crit: "#ef4444",
  na: "#64748b",
};

/** A filled-area sparkline over a band's per-bucket counts (signal KPI tiles, image 01). */
function AreaSpark({ counts, color }: { counts: number[]; color: string }) {
  if (counts.length < 2) return <div className="h-9 w-full" />;
  const max = Math.max(1, ...counts);
  const w = 120;
  const h = 36;
  const xy = counts.map((v, i) => ({
    x: (i / (counts.length - 1)) * w,
    y: h - (v / max) * (h - 2) - 1,
  }));
  const line = xy
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${w},${h} L0,${h} Z`;
  const gid = `area-${color.replace("#", "")}`;
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-9 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} stroke="none" />
      <path d={line} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}

/** A "▲/▼ +N vs hier" delta label under a KPI number (image 01). */
function DeltaVsYesterday({
  delta,
  color,
  goodUp,
}: {
  delta: number | null;
  color: string;
  goodUp: boolean;
}) {
  const tq = useTranslations("quality");
  if (delta == null)
    return <span className="text-[0.65rem] text-[var(--muted-foreground)]">—</span>;
  if (delta === 0)
    return (
      <span className="text-[0.65rem] text-[var(--muted-foreground)]">
        — {tq("signalsKpi.stable")}
      </span>
    );
  const up = delta > 0;
  const tone = up === goodUp ? "#10b981" : color;
  return (
    <span className="flex items-center gap-1 text-[0.65rem] tabular-nums" style={{ color: tone }}>
      {up ? "▲" : "▼"} {up ? "+" : ""}
      {delta} {tq("signalsKpi.vsYesterday")}
    </span>
  );
}

/** The top KPI row of the Signaux tab: active-signal count + per-severity counts,
 * each with a REAL filled-area sparkline + a vs-yesterday delta from the durable
 * score log (image 01). */
export function SignalKpis({
  rows,
  trend,
  catalogue = 200,
}: {
  rows: SignalRow[];
  trend: StatusCountsTrend | undefined;
  catalogue?: number;
}) {
  const tq = useTranslations("quality");
  const s = summarizeSignals(rows);
  const tiles: {
    key: string;
    label: string;
    value: string;
    status: SignalStatus;
    band: StatusBand | undefined;
    goodUp: boolean;
  }[] = [
    {
      key: "active",
      label: tq("signalsKpi.active"),
      value: `${s.total}/${catalogue}`,
      status: "ok",
      band: trend?.active,
      goodUp: true,
    },
    {
      key: "crit",
      label: tq("signalsTable.group.crit"),
      value: String(s.crit),
      status: "crit",
      band: trend?.crit,
      goodUp: false,
    },
    {
      key: "warn",
      label: tq("signalsTable.group.warn"),
      value: String(s.warn),
      status: "warn",
      band: trend?.warn,
      goodUp: false,
    },
    {
      key: "ok",
      label: tq("signalsTable.group.ok"),
      value: String(s.ok),
      status: "ok",
      band: trend?.ok,
      goodUp: true,
    },
    {
      key: "na",
      label: tq("signalsTable.group.na"),
      value: String(s.na),
      status: "na",
      band: undefined,
      goodUp: true,
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
      {tiles.map((t) => (
        <Card key={t.key} className="flex flex-col gap-1 p-2.5">
          <div className="flex items-center gap-1.5 text-[0.7rem] text-[var(--muted-foreground)]">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: STATUS_HEX[t.status] }}
            />
            <span className="truncate">{t.label}</span>
            {/* Severity keys map 1:1 to quality.explain.sig{Active,Crit,Warn,Ok,Na}. */}
            <QInfo
              title={t.label}
              k={`sig${t.key.charAt(0).toUpperCase()}${t.key.slice(1)}`}
              className="ml-auto"
            />
          </div>
          <div className="flex items-end justify-between gap-2">
            <div className="flex flex-col">
              <span
                className="text-xl font-semibold tabular-nums leading-none"
                style={{ color: t.key === "active" ? undefined : STATUS_HEX[t.status] }}
              >
                {t.value}
              </span>
              <DeltaVsYesterday
                delta={t.band?.delta ?? null}
                color={STATUS_HEX[t.status]}
                goodUp={t.goodUp}
              />
            </div>
            <div className="h-9 w-[42%] shrink-0">
              {t.band ? <AreaSpark counts={t.band.counts} color={STATUS_HEX[t.status]} /> : null}
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

const SEV_BADGE: Record<string, "danger" | "warning" | "neutral"> = {
  critical: "danger",
  high: "warning",
  medium: "neutral",
  low: "neutral",
};

function gate(rows: SignalRow[], cat: SignalCategory): boolean {
  // PASS unless a signal of this category is in a critical state.
  return !rows.some((r) => r.category === cat && r.status === "crit");
}

/** Right rail of the Signaux tab (image 01): Fiche signal · Cas liés · Release
 * qualité (gates) · Activités récentes · Actions prescriptives. */
export function SignalsRail({
  selected,
  rows,
  failed,
  release,
  whatChanged,
  onOpen,
  onEvidence,
}: {
  selected: SignalRow | null;
  rows: SignalRow[];
  failed: FailedCasesReport | undefined;
  release: ReleaseStatus | undefined;
  whatChanged: WhatChanged | undefined;
  onOpen: (tab: SignalsTab) => void;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const sig = selected ?? rows.find((r) => r.status === "crit") ?? rows[0] ?? null;
  const current = release?.current ?? null;
  const blocked = (release?.n_regressions ?? 0) > 0;
  const cases = (failed?.cases ?? []).slice(0, 4);
  const gates: { key: string; cat: SignalCategory }[] = [
    { key: "quality", cat: "fidelity" },
    { key: "security", cat: "security" },
    { key: "compliance", cat: "compliance" },
  ];
  const activity: { key: string; label: string; detail: string }[] = [];
  if (current)
    activity.push({
      key: "release",
      label: tq(blocked ? "rr.actReleaseBlocked" : "rr.actReleaseDeployed", { v: current.version }),
      detail: current.date ?? "",
    });
  for (const c of whatChanged?.changes ?? [])
    activity.push({
      key: c.field,
      label: c.field,
      detail: `${c.before.slice(0, 8)} → ${c.after.slice(0, 8)}`,
    });
  const fiche = sig;
  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-28">
        {/* Fiche signal */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("signalsRail.fiche")}
              <QInfo title={tq("signalsRail.fiche")} k="sigRailFiche" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5 text-[0.7rem]">
            {fiche ? (
              <>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-[var(--foreground)]">{fiche.name}</span>
                  <Badge tone={STATUS_TONE[fiche.status]}>
                    {tq(`signalsTable.status.${fiche.status}`)}
                  </Badge>
                </div>
                <span className="font-mono text-[var(--muted-foreground)]">{fiche.metric}</span>
                <RailKV
                  k={tq("signalsTable.cols.value")}
                  v={`${fiche.score} (${fiche.threshold})`}
                />
                <RailKV
                  k={tq("signalsTable.cols.entity")}
                  v={tq(`signalsTable.entity.${fiche.entity}`)}
                />
                <RailKV k={tq("signalsRail.source")} v="Signal Catalog · YAML" />
                <RailKV k={tq("signalsRail.collector")} v="tessera-eval" />
                <RailKV k={tq("signalsRail.scope")} v="Prod · Crédit Aurore" />
              </>
            ) : (
              <span className="text-[var(--muted-foreground)]">—</span>
            )}
          </CardContent>
        </Card>

        {/* Cas liés */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-1.5">
                {tq("signalsRail.cases")}
                <QInfo title={tq("signalsRail.cases")} k="sigRailCases" />
              </span>
              <RailLink onClick={() => onOpen("failed")}>{tq("rr.seeCases")}</RailLink>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {cases.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("failed.empty")}</p>
            ) : (
              cases.map((c) => (
                <div key={c.case_id} className="flex items-center gap-2 text-[0.7rem]">
                  <span className="shrink-0 font-mono text-[var(--tessera-green)]">
                    {c.case_id}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[var(--muted-foreground)]">
                    {c.title}
                  </span>
                  <Badge tone={SEV_BADGE[c.severity] ?? "neutral"}>{c.severity}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Release qualité — gates */}
        {current ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5 text-sm">
                {tq("signalsRail.release")}
                <QInfo title={tq("signalsRail.release")} k="sigRailRelease" />
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1.5 text-[0.7rem]">
              <div className="flex items-center gap-2">
                <span className="font-serif text-base font-semibold tabular-nums">
                  {current.version}
                </span>
                <Badge tone={blocked ? "danger" : "success"}>
                  {blocked ? tq("rr.blocked") : tq("rr.inProd")}
                </Badge>
              </div>
              {gates.map((g) => {
                const pass = gate(rows, g.cat);
                return (
                  <div key={g.key} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--muted-foreground)]">
                      {tq(`signalsRail.gate_${g.key}`)}
                    </span>
                    <Badge tone={pass ? "success" : "danger"}>{pass ? "PASS" : "FAIL"}</Badge>
                  </div>
                );
              })}
              <RailLink onClick={() => onOpen("models")}>{tq("rr.seeReleases")}</RailLink>
            </CardContent>
          </Card>
        ) : null}

        {/* Activités récentes */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("rr.activity")}
              <QInfo title={tq("rr.activity")} k="sigRailActivity" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
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

        {/* Actions prescriptives */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("signalsRail.actions")}
              <QInfo title={tq("signalsRail.actions")} k="sigRailActions" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            <RailAction onClick={() => onOpen("failed")}>{tq("signalsRail.createCase")}</RailAction>
            <RailAction onClick={() => onOpen("failed")}>
              {tq("signalsRail.assignOwner")}
            </RailAction>
            <RailAction onClick={() => onOpen("signals")}>{tq("reco.catalog")}</RailAction>
            <RailAction onClick={onEvidence}>{tq("reco.seeEvidence")}</RailAction>
            <div className="mt-0.5 flex items-center justify-between gap-2 rounded-md border border-red-500/40 px-2 py-1 text-[0.7rem]">
              <span className="text-red-400">{tq("reco.block")}</span>
              <Badge tone="warning">{tq("signalsRail.dualControl")}</Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </aside>
  );
}

function RailKV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{k}</span>
      <span className="truncate text-right">{v}</span>
    </div>
  );
}

function RailLink({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1 text-[0.7rem] text-[var(--tessera-green)] hover:underline"
    >
      {children}
      <ChevronRight className="h-3 w-3" />
    </button>
  );
}

function RailAction({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 rounded-md px-1.5 py-0.5 text-left text-[0.7rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
    >
      <ChevronRight className="h-3 w-3 shrink-0" />
      <span className="truncate">{children}</span>
    </button>
  );
}
