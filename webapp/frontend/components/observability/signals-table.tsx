"use client";

import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { Fragment, useMemo, useState } from "react";

import { AuthorityLabel } from "@/components/cockpit/authority-label";
import { QInfo } from "@/components/observability/quality-info";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Truncate } from "@/components/ui/truncate";
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
import { type ControlId, type ControlReading, readControls } from "@/lib/control-registry";
import { registryIdFor } from "@/lib/signal-focus";
import { capabilityFor } from "@/lib/signal-registry";

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

/**
 * Derive one normalized row per quality signal from the live report data. Every
 * status/score is computed from real fields — a signal with no data reads "na"
 * and "—" rather than a fabricated value (Tessera no-mock discipline).
 */
type RawRow = Omit<SignalRow, "id" | "metric" | "entity" | "delta" | "action" | "role"> & {
  /** Present on rows read from `lib/control-registry.ts` — their metric id comes from there. */
  metric?: string;
};

/**
 * The eight rows this table shares with `overview-dashboard` and `security-dashboard`, and the
 * shape they take here.
 *
 * Until 2026-08-01 each of the three surfaces built these itself. Six of seven disagreed:
 * `refusal` displayed `over` (0 %) with a status computed from `max(over, under)` (60 %), so
 * the row read "0 % · seuil ≤ 10 % · Critique"; `firewall` showed F1 here and recall on the
 * overview, 86 % against 76 %, same label. What a control MEANS now comes from one module; how
 * this table lays it out stays here, which is the correct division.
 */
const SHARED: readonly {
  readonly id: ControlId;
  readonly key: string;
  readonly nameKey: string;
  readonly category: SignalCategory;
}[] = [
  { id: "faithfulness", key: "slo", nameKey: "slo.title", category: "fidelity" },
  { id: "calibration", key: "calibration", nameKey: "calibration.title", category: "fidelity" },
  { id: "citations", key: "citations", nameKey: "citations.title", category: "fidelity" },
  {
    id: "contradiction",
    key: "contradiction",
    nameKey: "contradiction.title",
    category: "fidelity",
  },
  { id: "predictor", key: "predictor", nameKey: "predictor.title", category: "fidelity" },
  { id: "clusters", key: "clusters", nameKey: "clusters.title", category: "fidelity" },
  { id: "firewall", key: "firewall", nameKey: "firewall.title", category: "security" },
  { id: "toxicity", key: "toxicity", nameKey: "toxicity.title", category: "security" },
  { id: "pii", key: "piiLeak", nameKey: "piiLeak.title", category: "security" },
  // Two rows where there was one. Over-refusal costs utility, under-refusal is a safety
  // incident; their maximum named neither, and the label did not say which face you saw.
  { id: "refusalOver", key: "refusalOver", nameKey: "refusal.over", category: "compliance" },
  { id: "refusalUnder", key: "refusalUnder", nameKey: "refusal.under", category: "compliance" },
  { id: "conformance", key: "conformance", nameKey: "conformance.title", category: "compliance" },
  {
    id: "localeFormat",
    key: "localeFormat",
    nameKey: "localeFormat.title",
    category: "compliance",
  },
  { id: "tools", key: "tools", nameKey: "tools.title", category: "reliability" },
  { id: "cost", key: "cost", nameKey: "cost.title", category: "reliability" },
  { id: "routing", key: "routing", nameKey: "routing.title", category: "sessions" },
  { id: "funnel", key: "funnel", nameKey: "funnel.title", category: "sessions" },
  { id: "anomalies", key: "anomalies", nameKey: "anomalies.title", category: "sessions" },
  { id: "intent", key: "intent", nameKey: "intent.title", category: "sessions" },
];

/** A registry reading, laid out as a row of this table. */
function sharedRow(
  spec: (typeof SHARED)[number],
  reading: ControlReading,
  t: (key: string) => string,
  td: (key: string, values: Record<string, string>) => string,
): RawRow {
  return {
    key: spec.key,
    name: t(spec.nameKey),
    category: spec.category,
    // `fail` is this table's `crit`. The mapping is a vocabulary difference between two
    // surfaces, not a second judgement: the state itself is computed once, from the value the
    // operator sees against the bar the operator sees.
    status: reading.noData ? "na" : reading.state.key === "fail" ? "crit" : reading.state.key,
    score: reading.value,
    threshold: reading.target,
    sample: reading.detail ? td(reading.detail.key, reading.detail.values) : "—",
    metric: reading.metric,
  };
}

export function buildSignalRows(
  t: (key: string) => string,
  d: SignalData,
  td: (key: string, values: Record<string, string>) => string,
): SignalRow[] {
  const rows: RawRow[] = [];

  const shared = new Map(
    readControls(
      d,
      SHARED.map((s) => s.id),
    ).map((r) => [r.id, r]),
  );
  const pushShared = (id: ControlId) => {
    const spec = SHARED.find((s) => s.id === id);
    const reading = shared.get(id);
    if (spec && reading) rows.push(sharedRow(spec, reading, t, td));
  };

  pushShared("faithfulness");
  pushShared("calibration");
  pushShared("citations");
  pushShared("contradiction");
  pushShared("predictor");
  pushShared("clusters");
  pushShared("firewall");
  pushShared("toxicity");
  pushShared("pii");
  pushShared("refusalOver");
  pushShared("refusalUnder");
  pushShared("conformance");
  pushShared("localeFormat");
  pushShared("tools");
  pushShared("cost");
  pushShared("routing");
  pushShared("funnel");
  pushShared("anomalies");
  pushShared("intent");

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
      // A shared row's metric id travels WITH its reading. `SIGNAL_META` held a second copy of
      // the same strings — the join key with the signal catalogue, duplicated exactly the way
      // the thresholds were, and one edit away from pointing two surfaces at two catalogue
      // entries for one measurement.
      metric: r.metric ?? meta.metric,
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

/** A VERDICT, so it wears the status roles — not the categorical ramp, which is
 *  reserved for identity and would say nothing about whether the signal is healthy. */
const GAUGE_COLORS: Record<SignalStatus, string> = {
  ok: "var(--tessera-fg-success)",
  warn: "var(--tessera-fg-warning)",
  crit: "var(--tessera-fg-danger)",
  na: "var(--tessera-text-muted)",
};

/** Radial health gauge: green signals over total, ring split by status (image 00). */
export function QualityGauge({ summary }: { summary: ReturnType<typeof summarizeSignals> }) {
  const tq = useTranslations("quality");
  const total = summary.total || 1;
  const r = 67;
  const circ = 2 * Math.PI * r;
  let acc = 0;
  return (
    <Card className="flex flex-col items-center gap-4 p-5">
      <div className="relative h-[176px] w-[176px]">
        <svg viewBox="0 0 176 176" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="88"
            cy="88"
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
                cx="88"
                cy="88"
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
        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
          <span className="max-w-[88px] truncate font-serif text-4xl font-semibold leading-none tabular-nums text-[var(--tessera-fg-success)]">
            {summary.ok}
          </span>
          <span className="line-clamp-2 max-w-[88px] break-words text-center text-[0.7rem] leading-tight text-[var(--muted-foreground)]">
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
                      ? "text-[var(--tessera-fg-danger)]"
                      : g.status === "warn"
                        ? "text-[var(--tessera-fg-warning)]"
                        : g.status === "ok"
                          ? "text-[var(--tessera-fg-success)]"
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
                              <Truncate full={r.id}>{r.id}</Truncate>
                            </td>
                            <td className="px-2 py-2">
                              <div className="flex min-w-0 flex-col">
                                <Truncate
                                  full={r.name}
                                  className="font-medium text-[var(--foreground)]"
                                >
                                  {r.name}
                                </Truncate>
                                <Truncate
                                  full={r.metric}
                                  className="font-mono text-[0.65rem] text-[var(--muted-foreground)]"
                                >
                                  {r.metric}
                                </Truncate>
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
                                <AuthorityLabel
                                  authority={r.role === "admin" ? "Admin+" : "Operator+"}
                                />
                              </Badge>
                            </td>
                            <td className="py-2 pr-4 pl-2">
                              <span className="flex items-center justify-end gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[var(--tessera-fg-success)]">
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
          ? "border-gold-500/50 bg-gold-500/10 text-[var(--tessera-fg-gold)]"
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
/** IDENTITY: which theme a signal belongs to, not how it is doing. Categorical ramp. */
const THEME_COLORS: Record<SignalCategory, string> = {
  fidelity: "var(--tessera-cat-1)",
  security: "var(--tessera-cat-2)",
  compliance: "var(--tessera-cat-3)",
  reliability: "var(--tessera-cat-4)",
  sessions: "var(--tessera-cat-5)",
};

/** "Répartition par thème" — signal counts per category as a donut (image 01). */
export function ThemeDistribution({ rows }: { rows: SignalRow[] }) {
  const tq = useTranslations("quality");
  const counts = CATEGORY_LIST.map((c) => ({
    cat: c,
    n: rows.filter((r) => r.category === c).length,
  })).filter((e) => e.n > 0);
  const total = counts.reduce((s, e) => s + e.n, 0) || 1;
  const r = 49;
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
          <div className="relative h-[128px] w-[128px] shrink-0">
            <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90" aria-hidden="true">
              <circle
                cx="64"
                cy="64"
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
                    cx="64"
                    cy="64"
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
            <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
              <span className="max-w-[63px] truncate font-serif text-xl font-semibold leading-none tabular-nums">
                {total}
              </span>
              <span className="line-clamp-2 max-w-[63px] break-words text-center text-[0.6rem] leading-tight text-[var(--muted-foreground)]">
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
  ok: "var(--tessera-fg-success)",
  warn: "var(--tessera-fg-warning)",
  crit: "var(--tessera-fg-danger)",
  na: "var(--tessera-text-muted)",
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
  const tone = up === goodUp ? "var(--tessera-fg-success)" : color;
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

/**
 * The "Décomposable par agent" value for the Fiche signal — read from the capability
 * registry (the `capabilities.py` mirror), NEVER guessed. It is the SAME descriptor that
 * masks the per-agent breakdown table, so the rail can never explain an absence the table
 * did not have, nor stay silent about one it did.
 *
 * Three honest states: a declared per-agent signal says yes; a declared org-wide signal says
 * why the breakdown cannot exist for it; an undeclared id says so rather than defaulting to
 * "yes" — a witness that cannot see may never report "ok" (ADR 0026).
 */
function byAgentState(uiKey: string): "yes" | "no" | "undeclared" {
  const capability = capabilityFor(registryIdFor(uiKey));
  if (capability === undefined) return "undeclared";
  return capability.dimensions.includes("agent") ? "yes" : "no";
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
                <RailKV
                  k={tq("signalsRail.byAgent")}
                  v={tq(`signalsRail.byAgent_${byAgentState(fiche.key)}`)}
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
                  <Truncate className="min-w-0 flex-1 text-[var(--muted-foreground)]">
                    {c.title}
                  </Truncate>
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
                  <Truncate className="min-w-0 flex-1 text-[0.7rem]">{a.label}</Truncate>
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
              <span className="text-[var(--tessera-fg-danger)]">{tq("reco.block")}</span>
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
      {/* The rail is narrow and the value truncates; the reveal keeps it READABLE. A reason an
          operator cannot finish reading ("org-wide par construc…") explains nothing. */}
      <Truncate full={v} className="text-right">
        {v}
      </Truncate>
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
