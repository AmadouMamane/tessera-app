"use client";

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

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
  FirewallEfficacy,
  FunnelReport,
  IntentReport,
  LocaleFormatSummary,
  PIILeakSummary,
  PredictorEvaluation,
  RefusalReport,
  RoutingReport,
  SLOReport,
  ToolValidity,
  ToxicityReport,
} from "@/lib/api/schemas";

export type SignalStatus = "ok" | "warn" | "crit" | "na";
export type SignalCategory = "fidelity" | "security" | "compliance" | "reliability" | "sessions";

export interface SignalRow {
  key: string;
  name: string;
  category: SignalCategory;
  status: SignalStatus;
  score: string;
  threshold: string;
  sample: string;
}

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
export function buildSignalRows(t: (key: string) => string, d: SignalData): SignalRow[] {
  const rows: SignalRow[] = [];

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

  return rows;
}

const STATUS_RANK: Record<SignalStatus, number> = { crit: 0, warn: 1, ok: 2, na: 3 };
const STATUS_TONE: Record<SignalStatus, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  warn: "warning",
  crit: "danger",
  na: "neutral",
};
const CATEGORIES: SignalCategory[] = [
  "fidelity",
  "security",
  "compliance",
  "reliability",
  "sessions",
];
const STATUSES: SignalStatus[] = ["ok", "warn", "crit", "na"];

export function summarizeSignals(
  rows: SignalRow[],
): Record<SignalStatus, number> & { total: number } {
  const s = { ok: 0, warn: 0, crit: 0, na: 0, total: rows.length };
  for (const r of rows) s[r.status] += 1;
  return s;
}

/** Filterable, sortable catalogue of every quality signal (reference image 01). */
export function SignalsTable({ rows }: { rows: SignalRow[] }) {
  const tq = useTranslations("quality");
  const [cat, setCat] = useState<SignalCategory | "all">("all");
  const [status, setStatus] = useState<SignalStatus | "all">("all");

  const shown = useMemo(() => {
    return rows
      .filter(
        (r) => (cat === "all" || r.category === cat) && (status === "all" || r.status === status),
      )
      .sort(
        (a, b) => STATUS_RANK[a.status] - STATUS_RANK[b.status] || a.name.localeCompare(b.name),
      );
  }, [rows, cat, status]);

  const summary = summarizeSignals(rows);

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm">{tq("tabs.signals")}</CardTitle>
          <span className="text-xs text-[var(--muted-foreground)]">
            {tq("signalsTable.count", { shown: shown.length, total: summary.total })}
          </span>
        </div>
        {/* Category chips */}
        <div className="flex flex-wrap gap-1.5">
          <Chip active={cat === "all"} onClick={() => setCat("all")}>
            {tq("signalsTable.all")}
          </Chip>
          {CATEGORIES.map((c) => (
            <Chip key={c} active={cat === c} onClick={() => setCat(c)}>
              {tq(`signalsTable.cat.${c}`)}
            </Chip>
          ))}
        </div>
        {/* Status filter */}
        <div className="flex flex-wrap gap-1.5">
          <Chip active={status === "all"} onClick={() => setStatus("all")}>
            {tq("signalsTable.all")}
          </Chip>
          {STATUSES.map((s) => (
            <Chip key={s} active={status === s} onClick={() => setStatus(s)} tone={STATUS_TONE[s]}>
              {tq(`signalsTable.status.${s}`)} · {summary[s]}
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
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.signal")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.category")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.status")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.score")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.threshold")}</th>
                  <th className="py-2 font-medium">{tq("signalsTable.cols.sample")}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.key} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-4 font-medium text-[var(--foreground)]">{r.name}</td>
                    <td className="py-2 pr-4 text-[var(--muted-foreground)]">
                      {tq(`signalsTable.cat.${r.category}`)}
                    </td>
                    <td className="py-2 pr-4">
                      <Badge tone={STATUS_TONE[r.status]}>
                        {tq(`signalsTable.status.${r.status}`)}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4 font-semibold tabular-nums">{r.score}</td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {r.threshold}
                    </td>
                    <td className="py-2 tabular-nums text-[var(--muted-foreground)]">{r.sample}</td>
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
