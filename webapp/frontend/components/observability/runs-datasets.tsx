"use client";

import {
  Activity,
  Boxes,
  ChevronRight,
  Clock,
  Coins,
  Database,
  FileDown,
  GitBranch,
  Layers,
  Workflow,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  FreshnessReport,
  ModelComparison,
  QualityDatasetsReport,
  ReleaseStatus,
  RunRegistry,
  RunSummary,
} from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";
const DASH = "—";

const DAY_MS = 86_400_000;
const WINDOW_DAYS = 7;

/** Tab target router (mirrors the rest of the cockpit). */
export type RunsTab = "overview" | "signals" | "runs" | "failed" | "models" | "judge";

// ─────────────────────────────── formatting helpers ───────────────────────────

/** Parse a compact run stamp ("20260606T075407Z") into epoch ms, or null. */
function parseRunAt(stamp: string): number | null {
  const m = stamp.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z?/);
  if (!m) return null;
  const [, y, mo, d, h, mi, s] = m;
  const t = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi), Number(s));
  return Number.isNaN(t) ? null : t;
}

function fmtDate(stamp: string): string {
  const t = parseRunAt(stamp);
  if (t == null) return stamp;
  const dt = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(dt.getUTCDate())}/${p(dt.getUTCMonth() + 1)}/${String(dt.getUTCFullYear()).slice(2)} ${p(dt.getUTCHours())}:${p(dt.getUTCMinutes())}`;
}

function fmtPct(rate: number | null | undefined): string {
  if (rate == null) return DASH;
  return `${Math.round(rate * 100)}%`;
}

function fmtEur(eur: number | null | undefined): string {
  if (eur == null) return DASH;
  if (eur === 0) return "0,00 €";
  return `${eur.toFixed(2).replace(".", ",")} €`;
}

function fmtDuration(ms: number | null | undefined): string {
  if (ms == null) return DASH;
  const total = Math.round(ms / 1000);
  if (total < 60) return `${total}s`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

/** Newest run timestamp → anchor for the rolling 7-day window. */
function windowRuns(registry: RunRegistry | undefined): RunSummary[] {
  const runs = registry?.runs ?? [];
  if (runs.length === 0) return [];
  const stamps = runs.map((r) => parseRunAt(r.run_at)).filter((t): t is number => t != null);
  const anchor = stamps.length ? Math.max(...stamps) : null;
  if (anchor == null) return runs;
  const start = anchor - WINDOW_DAYS * DAY_MS;
  return runs.filter((r) => {
    const t = parseRunAt(r.run_at);
    return t == null || t >= start;
  });
}

function langBadges(langs: string[]): string {
  return langs.length ? langs.map((l) => l.toUpperCase()).join(" ") : DASH;
}

/** Coverage band: ≥0.8 good, ≥0.5 watch, else low — drives the per-dataset colour. */
function coverageBand(c: number | null | undefined): "good" | "mid" | "low" | "none" {
  if (c == null) return "none";
  if (c >= 0.8) return "good";
  if (c >= 0.5) return "mid";
  return "low";
}

const BAND_FILL: Record<"good" | "mid" | "low" | "none", string> = {
  good: "#34d399",
  mid: "#f59e0b",
  low: "#f87171",
  none: "var(--muted)",
};

/** Drift magnitude colour: small=teal, moderate=amber, large=red (abs value). */
function driftFill(absDrift: number): string {
  if (absDrift >= 0.3) return "#f87171";
  if (absDrift >= 0.15) return "#f59e0b";
  return "#34d399";
}

/** Pass-rate band → status key for the datasets table. */
function statusBand(rate: number | null | undefined): "good" | "watch" | "alert" | "unknown" {
  if (rate == null) return "unknown";
  if (rate >= 0.8) return "good";
  if (rate >= 0.5) return "watch";
  return "alert";
}

/** Humanise a freshness age in seconds (days / hours / minutes). */
function fmtFreshness(seconds: number | null | undefined): string {
  if (seconds == null) return DASH;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86_400)}j`;
}

// ──────────────────────────────── KPI strip ──────────────────────────────────

/** Compact KPI tile — label, big value, optional sub-line. */
function Kpi({
  icon,
  label,
  value,
  tone,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: string;
  sub?: React.ReactNode;
}) {
  return (
    <Card className="flex flex-col gap-0.5 p-2">
      <div className="flex items-center gap-1 text-[0.65rem] leading-tight text-[var(--muted-foreground)]">
        <span className="opacity-70">{icon}</span>
        {label}
      </div>
      <div
        className={`text-lg font-semibold leading-tight tabular-nums ${tone ?? "text-[var(--foreground)]"}`}
      >
        {value}
      </div>
      {sub ? (
        <div className="text-[0.6rem] leading-tight text-[var(--muted-foreground)]">{sub}</div>
      ) : null}
    </Card>
  );
}

/** Seven-tile headline strip of the Runs & datasets tab (reference image 02). */
export function RunsKpis({
  registry,
  release,
  freshness,
  datasets,
}: {
  registry: RunRegistry | undefined;
  release: ReleaseStatus | undefined;
  freshness: FreshnessReport | undefined;
  datasets: QualityDatasetsReport | undefined;
}) {
  const tq = useTranslations("quality");
  const win = windowRuns(registry);
  const nRuns = win.length;
  const cases = win.reduce((acc, r) => acc + r.total, 0);
  const costs = win.map((r) => r.est_cost_eur).filter((c): c is number => c != null);
  const cost = costs.length ? costs.reduce((a, b) => a + b, 0) : 0;
  const lat = win.map((r) => r.mean_latency_ms).filter((m): m is number => m != null);
  const avgLat = lat.length ? lat.reduce((a, b) => a + b, 0) / lat.length : null;
  const version = registry?.catalogue_version ?? null;
  const langs = registry?.languages ?? [];
  const rel = release?.current ?? null;
  const regOpen = release?.n_regressions ?? null;
  const relTone = regOpen == null ? MUTED : regOpen > 0 ? WARN : GOOD;
  const staleN = freshness?.n_stale ?? null;
  // Mean absolute run-over-run drift across the themed datasets (real, or n/d).
  const drifts = (datasets?.datasets ?? [])
    .map((d) => d.drift)
    .filter((x): x is number => x != null)
    .map((x) => Math.abs(x));
  const meanDrift = drifts.length ? drifts.reduce((a, b) => a + b, 0) / drifts.length : null;

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
      <Kpi
        icon={<Activity className="h-3 w-3" />}
        label={tq("runs.kpi.runs7d")}
        value={String(nRuns)}
        sub={tq("runs.kpi.ofTotal", { n: registry?.n ?? 0 })}
      />
      <Kpi
        icon={<Layers className="h-3 w-3" />}
        label={tq("runs.kpi.catalogue")}
        value={version ? `v${version.split("-")[0]}` : DASH}
        sub={langBadges(langs)}
      />
      <Kpi
        icon={<Database className="h-3 w-3" />}
        label={tq("runs.kpi.cases")}
        value={cases.toLocaleString("fr-FR")}
        sub={tq("runs.kpi.casesSub", { n: registry?.catalogue_cases ?? 0 })}
      />
      <Kpi
        icon={<GitBranch className="h-3 w-3" />}
        label={tq("runs.kpi.drift")}
        value={meanDrift == null ? DASH : meanDrift.toFixed(2)}
        tone={meanDrift == null ? MUTED : meanDrift >= 0.3 ? WARN : undefined}
        sub={meanDrift == null ? tq("runs.kpi.driftNa") : tq("runs.kpi.driftMean")}
      />
      <Kpi
        icon={<Coins className="h-3 w-3" />}
        label={tq("runs.kpi.cost7d")}
        value={fmtEur(cost)}
        sub={costs.length ? tq("runs.kpi.costSub", { n: costs.length }) : tq("runs.free")}
      />
      <Kpi
        icon={<Workflow className="h-3 w-3" />}
        label={tq("runs.kpi.release")}
        value={rel ? rel.version : DASH}
        tone={relTone}
        sub={
          regOpen == null
            ? undefined
            : regOpen > 0
              ? tq("runs.kpi.regOpen", { n: regOpen })
              : tq("runs.kpi.ok")
        }
      />
      <Kpi
        icon={<Clock className="h-3 w-3" />}
        label={tq("runs.kpi.avgDuration")}
        value={fmtDuration(avgLat)}
        sub={staleN != null ? tq("runs.kpi.staleCorpora", { n: staleN }) : undefined}
      />
    </div>
  );
}

// ──────────────────────────────── Runs table ─────────────────────────────────

/** Pass-rate delta of a run versus the same model's chronologically previous run. */
function deltaForRun(registry: RunRegistry | undefined, run: RunSummary): number | null {
  const sameModel = (registry?.runs ?? [])
    .filter((r) => r.model === run.model)
    .map((r) => ({ r, t: parseRunAt(r.run_at) ?? 0 }))
    .sort((a, b) => a.t - b.t);
  const idx = sameModel.findIndex((x) => x.r.run_id === run.run_id);
  if (idx <= 0) return null;
  const prev = sameModel[idx - 1];
  if (!prev) return null;
  return run.pass_rate - prev.r.pass_rate;
}

function DeltaCell({ delta }: { delta: number | null }) {
  if (delta == null) return <span className={MUTED}>{DASH}</span>;
  const up = delta >= 0;
  const tone = Math.abs(delta) < 0.005 ? MUTED : up ? GOOD : BAD;
  const sign = up ? "+" : "−";
  return (
    <span className={`tabular-nums ${tone}`}>
      {sign}
      {Math.abs(delta).toFixed(2)}
    </span>
  );
}

/** Real eval-run archive, newest first, with row selection (reference image 02). */
export function RunsEvalTable({
  registry,
  selectedId,
  onSelect,
}: {
  registry: RunRegistry | undefined;
  selectedId: string | null;
  onSelect: (run: RunSummary) => void;
}) {
  const tq = useTranslations("quality");
  const tt = useTranslations("table");
  const runs = registry?.runs ?? [];
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-sm">{tq("runs.table.title")}</CardTitle>
        <Badge tone="neutral" className="text-[0.65rem]">
          {tq("runs.count", { n: registry?.n ?? 0 })}
        </Badge>
      </CardHeader>
      <CardContent className="max-h-[268px] overflow-auto">
        {runs.length === 0 ? (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            {tq("runs.empty")}
          </p>
        ) : (
          <table className="w-full min-w-[760px] table-fixed text-left text-[0.7rem]">
            <thead className="sticky top-0 z-10 bg-[var(--card)] text-[0.62rem] uppercase tracking-wide text-[var(--muted-foreground)]">
              <tr className="border-b border-[var(--border)]">
                <th className="w-[16%] py-1 pr-2 pl-5 font-medium">{tq("runs.table.model")}</th>
                <th className="w-[9%] px-2 py-1 font-medium">{tq("runs.table.catalogue")}</th>
                <th className="w-[6%] px-2 py-1 font-medium">{tq("runs.table.lang")}</th>
                <th className="w-[7%] px-2 py-1 text-right font-medium">
                  {tq("runs.table.cases")}
                </th>
                <th className="w-[7%] px-2 py-1 text-right font-medium">
                  {tq("runs.table.passed")}
                </th>
                <th className="w-[8%] px-2 py-1 text-right font-medium">{tq("runs.table.rate")}</th>
                <th className="w-[8%] px-2 py-1 text-right font-medium">
                  {tq("runs.table.delta")}
                </th>
                <th className="w-[9%] px-2 py-1 text-right font-medium">{tq("runs.table.cost")}</th>
                <th className="w-[9%] px-2 py-1 text-right font-medium">
                  {tq("runs.table.duration")}
                </th>
                <th className="w-[10%] px-2 py-1 font-medium">{tq("runs.table.status")}</th>
                <th className="w-24 py-1 pr-4 pl-2 font-medium">
                  <span className="sr-only">{tt("rowOpen")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const selected = r.run_id === selectedId;
                const rateTone = r.pass_rate >= 0.8 ? GOOD : r.pass_rate >= 0.6 ? WARN : BAD;
                return (
                  <tr
                    key={r.run_id}
                    onClick={() => onSelect(r)}
                    // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelect(r);
                      }
                    }}
                    className={`group cursor-pointer border-b border-[var(--border)]/60 outline-none transition-colors hover:bg-[var(--accent)]/40 focus-visible:bg-[var(--accent)]/40 ${
                      selected ? "bg-[var(--accent)]/60" : ""
                    }`}
                  >
                    <td className="py-1.5 pr-2 pl-5 font-medium text-[var(--foreground)]">
                      <span className="block truncate" title={r.model}>
                        {r.model}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 tabular-nums text-[var(--muted-foreground)]">
                      {r.catalogue_version ? `v${r.catalogue_version.split("-")[0]}` : DASH}
                    </td>
                    <td className="px-2 py-1.5 uppercase text-[var(--muted-foreground)]">
                      {r.language && r.language !== "None" ? r.language : DASH}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{r.total}</td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{r.passed}</td>
                    <td className={`px-2 py-1.5 text-right font-semibold tabular-nums ${rateTone}`}>
                      {fmtPct(r.pass_rate)}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <DeltaCell delta={deltaForRun(registry, r)} />
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-[var(--muted-foreground)]">
                      {fmtEur(r.est_cost_eur)}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-[var(--muted-foreground)]">
                      {fmtDuration(r.mean_latency_ms)}
                    </td>
                    <td className="px-2 py-1.5">
                      <span className="inline-flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                          {tq("runs.done")}
                        </span>
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 pl-2">
                      <span className="flex items-center justify-end gap-1 text-[0.64rem] text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#7ff0b6]">
                        <span className="opacity-0 transition-opacity group-hover:opacity-100">
                          {tt("rowOpen")}
                        </span>
                        <ChevronRight className="h-3.5 w-3.5" />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

// ──────────────────────── Contexte du run sélectionné ────────────────────────

function CtxRow({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5">
      <span className="shrink-0 text-[0.65rem] text-[var(--muted-foreground)]">{k}</span>
      <span className="text-right text-[0.72rem] font-medium text-[var(--foreground)]">
        {children}
      </span>
    </div>
  );
}

/** Detail panel for the selected (or newest) run — every field is a fact. */
export function RunContextPanel({
  run,
  release,
  onEvidence,
}: {
  run: RunSummary | undefined;
  release: ReleaseStatus | undefined;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const rateTone =
    run == null ? MUTED : run.pass_rate >= 0.8 ? GOOD : run.pass_rate >= 0.6 ? WARN : BAD;
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="text-sm">{tq("runs.ctx.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {run == null ? (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            {tq("runs.ctx.empty")}
          </p>
        ) : (
          <div className="divide-y divide-[var(--border)]/50">
            <CtxRow k={tq("runs.ctx.runId")}>
              <span className="font-mono text-[0.68rem]">{run.run_id}</span>
            </CtxRow>
            <CtxRow k={tq("runs.ctx.model")}>{run.model}</CtxRow>
            <CtxRow k={tq("runs.ctx.catalogue")}>{run.catalogue_version ?? DASH}</CtxRow>
            <CtxRow k={tq("runs.ctx.lang")}>
              <span className="uppercase">
                {run.language && run.language !== "None" ? run.language : DASH}
              </span>
            </CtxRow>
            <CtxRow k={tq("runs.ctx.window")}>{fmtDate(run.run_at)}</CtxRow>
            <CtxRow k={tq("runs.ctx.cases")}>
              <span className="tabular-nums">
                {run.passed}/{run.total}
              </span>
            </CtxRow>
            <CtxRow k={tq("runs.ctx.rate")}>
              <span className={`tabular-nums ${rateTone}`}>{fmtPct(run.pass_rate)}</span>
            </CtxRow>
            <CtxRow k={tq("runs.ctx.cost")}>
              <span className="tabular-nums">{fmtEur(run.est_cost_eur)}</span>
            </CtxRow>
            <CtxRow k={tq("runs.ctx.duration")}>
              <span className="tabular-nums">{fmtDuration(run.mean_latency_ms)}</span>
            </CtxRow>
            <CtxRow k={tq("runs.ctx.release")}>{release?.current?.version ?? DASH}</CtxRow>
            <CtxRow k={tq("runs.ctx.status")}>
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                {tq("runs.done")}
              </span>
            </CtxRow>
            <div className="flex items-center justify-between gap-3 pt-1.5">
              <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                {tq("runs.ctx.evidence")}
              </span>
              <button
                type="button"
                onClick={onEvidence}
                className="inline-flex items-center gap-1 text-[0.7rem] font-medium text-[var(--primary)] hover:underline"
              >
                <FileDown className="h-3 w-3" />
                {tq("runs.ctx.openEvidence")}
              </button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ──────────────────────────────── Datasets table ─────────────────────────────

/** Short theme date (no time) for the "Dernière maj" column. */
function fmtDay(stamp: string | null): string {
  if (stamp == null) return DASH;
  const t = parseRunAt(stamp);
  if (t == null) return stamp;
  const dt = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(dt.getUTCDate())}/${p(dt.getUTCMonth() + 1)}/${String(dt.getUTCFullYear()).slice(2)}`;
}

function DriftCell({ drift }: { drift: number | null }) {
  if (drift == null) return <span className={MUTED}>{DASH}</span>;
  const up = drift >= 0;
  const tone = Math.abs(drift) < 0.005 ? MUTED : up ? GOOD : BAD;
  return (
    <span className={`tabular-nums ${tone}`}>
      {up ? "+" : "−"}
      {Math.abs(drift).toFixed(2)}
    </span>
  );
}

function CoverageCell({ coverage }: { coverage: number | null }) {
  if (coverage == null) return <span className={MUTED}>{DASH}</span>;
  const band = coverageBand(coverage);
  const tone = band === "good" ? GOOD : band === "mid" ? WARN : BAD;
  return <span className={`tabular-nums ${tone}`}>{Math.round(coverage * 100)}%</span>;
}

const STATUS_DOT: Record<"good" | "watch" | "alert" | "unknown", string> = {
  good: "bg-emerald-500",
  watch: "bg-amber-500",
  alert: "bg-red-500",
  unknown: "bg-[var(--muted-foreground)]",
};

/** The real "Datasets de qualité" table — one row per failure-catalogue theme. */
export function DatasetsTable({ report }: { report: QualityDatasetsReport | undefined }) {
  const tq = useTranslations("quality");
  const rows = report?.datasets ?? [];
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle className="text-sm">{tq("runs.qdatasets.title")}</CardTitle>
        <Badge tone="neutral" className="text-[0.65rem]">
          {tq("runs.qdatasets.count", { n: report?.n ?? 0 })}
        </Badge>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {rows.length === 0 ? (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            {tq("runs.qdatasets.empty")}
          </p>
        ) : (
          <table className="w-full min-w-[860px] table-fixed text-left text-[0.7rem]">
            <thead className="text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
              <tr className="border-b border-[var(--border)]">
                <th className="w-[13%] py-1 pr-2 pl-5 font-medium">
                  {tq("runs.qdatasets.dataset")}
                </th>
                <th className="w-[22%] px-2 py-1 font-medium">
                  {tq("runs.qdatasets.description")}
                </th>
                <th className="w-[8%] px-2 py-1 font-medium">{tq("runs.qdatasets.langs")}</th>
                <th className="w-[7%] px-2 py-1 text-right font-medium">
                  {tq("runs.qdatasets.cases")}
                </th>
                <th className="w-[9%] px-2 py-1 font-medium">{tq("runs.qdatasets.updated")}</th>
                <th className="w-[8%] px-2 py-1 font-medium">{tq("runs.qdatasets.version")}</th>
                <th className="w-[8%] px-2 py-1 text-right font-medium">
                  {tq("runs.qdatasets.drift")}
                </th>
                <th className="w-[9%] px-2 py-1 text-right font-medium">
                  {tq("runs.qdatasets.coverage")}
                </th>
                <th className="w-[8%] px-2 py-1 font-medium">{tq("runs.qdatasets.owner")}</th>
                <th className="w-[8%] px-2 py-1 font-medium">{tq("runs.qdatasets.status")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => {
                const status = statusBand(d.pass_rate);
                return (
                  <tr key={d.key} className="border-b border-[var(--border)]/60">
                    <td className="py-1.5 pr-2 pl-5 font-medium text-[var(--foreground)]">
                      <span className="block truncate" title={tq(`runs.theme.${d.key}`)}>
                        {tq(`runs.theme.${d.key}`)}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-[var(--muted-foreground)]">
                      <span className="block truncate" title={tq(`runs.themeDesc.${d.key}`)}>
                        {tq(`runs.themeDesc.${d.key}`)}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 uppercase text-[var(--muted-foreground)]">
                      {langBadges(d.languages)}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{d.cases}</td>
                    <td className="px-2 py-1.5 tabular-nums text-[var(--muted-foreground)]">
                      {fmtDay(d.updated_at)}
                    </td>
                    <td className="px-2 py-1.5 tabular-nums text-[var(--muted-foreground)]">
                      {d.version ? `v${d.version.split("-")[0]}` : DASH}
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <DriftCell drift={d.drift} />
                    </td>
                    <td className="px-2 py-1.5 text-right">
                      <CoverageCell coverage={d.coverage} />
                    </td>
                    <td className="px-2 py-1.5 text-[var(--muted-foreground)]">
                      <span className="block truncate" title={d.owner}>
                        {d.owner}
                      </span>
                    </td>
                    <td className="px-2 py-1.5">
                      <span className="inline-flex items-center gap-1">
                        <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status]}`} />
                        <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                          {tq(`runs.qdatasets.st_${status}`)}
                        </span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

// ──────────────────────────────── mini-charts ────────────────────────────────

/** Tiny line chart of recent run pass-rates (oldest→newest).
 *
 * With ``band`` set, the line stays neutral (trend) while each point is coloured
 * by its value's quality band (value read as a 0–1 ratio), so weak runs stand out. */
function MiniLine({
  values,
  color = "#10b981",
  band = false,
}: {
  values: number[];
  color?: string;
  band?: boolean;
}) {
  if (values.length < 2) return <ChartEmpty />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 200;
  const h = 56;
  const pt = (v: number, i: number) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - 4 - ((v - min) / span) * (h - 8);
    return [x, y] as const;
  };
  const line = values.map((v, i) => {
    const [x, y] = pt(v, i);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const stroke = band ? "var(--muted-foreground)" : color;
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-14 w-full"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <path
        d={line.join(" ")}
        fill="none"
        stroke={stroke}
        strokeOpacity={band ? 0.6 : 1}
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
      {values.map((v, i) => {
        const [x, y] = pt(v, i);
        return (
          <circle
            key={`${x}-${y}`}
            cx={x}
            cy={y}
            r={1.8}
            fill={band ? BAND_FILL[coverageBand(v)] : color}
          />
        );
      })}
    </svg>
  );
}

/** Vertical bars (one per category) with a value label underneath.
 *
 * With ``band`` set, each bar is coloured by its value's quality band (the value
 * is read as a 0–100 percentage), so a weak model reads red, not green. */
function MiniBars({
  items,
  color = "#34d399",
  band = false,
}: {
  items: { label: string; value: number }[];
  color?: string;
  band?: boolean;
}) {
  if (items.length === 0) return <ChartEmpty />;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="flex h-14 items-end gap-1">
      {items.map((it) => (
        <div key={it.label} className="flex flex-1 flex-col items-center gap-0.5">
          <div
            className="w-full rounded-sm"
            style={{
              height: `${Math.max(4, (it.value / max) * 44)}px`,
              backgroundColor: band ? BAND_FILL[coverageBand(it.value / 100)] : color,
            }}
            title={`${it.label}: ${it.value}`}
          />
          <span className="max-w-full truncate text-[0.52rem] text-[var(--muted-foreground)]">
            {it.label}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Per-dataset coverage bars, each coloured by its band (Bien / Moyen / Faible). */
function CoverageBars({ items }: { items: { label: string; value: number }[] }) {
  const tq = useTranslations("quality");
  if (items.length === 0) return <ChartEmpty />;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex h-16 items-end gap-0.5">
        {items.map((it) => (
          <div key={it.label} className="flex flex-1 flex-col items-center justify-end">
            <div
              className="w-full rounded-sm"
              style={{
                height: `${Math.max(3, it.value * 60)}px`,
                backgroundColor: BAND_FILL[coverageBand(it.value)],
              }}
              title={`${it.label}: ${Math.round(it.value * 100)}%`}
            />
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[0.55rem] text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: BAND_FILL.good }} />
          {tq("runs.charts.bandGood")}
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: BAND_FILL.mid }} />
          {tq("runs.charts.bandMid")}
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: BAND_FILL.low }} />
          {tq("runs.charts.bandLow")}
        </span>
      </div>
    </div>
  );
}

/** Per-dataset mean drift, horizontal bars coloured by magnitude (teal→amber→red). */
function DriftBars({ items }: { items: { label: string; value: number }[] }) {
  if (items.length === 0) return <ChartEmpty />;
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 0.1);
  return (
    <div className="flex flex-col gap-1">
      {items.map((it) => {
        const abs = Math.abs(it.value);
        return (
          <div key={it.label} className="flex items-center gap-1.5 text-[0.6rem]">
            <span className="w-16 shrink-0 truncate text-[var(--muted-foreground)]">
              {it.label}
            </span>
            <div className="h-[4px] flex-1 overflow-hidden rounded-sm bg-[var(--tessera-border)]">
              <div
                className="h-full rounded-sm"
                style={{ width: `${(abs / max) * 100}%`, backgroundColor: driftFill(abs) }}
              />
            </div>
            <span className="w-8 shrink-0 text-right tabular-nums text-[var(--foreground)]">
              {abs.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** Two independently-scaled lines over shared x labels (cost + pass-rate). */
function DualLine({
  labels,
  costs,
  rates,
}: {
  labels: string[];
  costs: (number | null)[];
  rates: (number | null)[];
}) {
  const tq = useTranslations("quality");
  const n = labels.length;
  if (n < 2) return <ChartEmpty />;
  const w = 200;
  const h = 52;
  const norm = (vals: (number | null)[]): (number | null)[] => {
    const known = vals.filter((v): v is number => v != null);
    if (known.length === 0) return vals.map(() => null);
    const min = Math.min(...known);
    const max = Math.max(...known);
    const span = max - min || 1;
    return vals.map((v) => (v == null ? null : (v - min) / span));
  };
  const path = (vals: (number | null)[]): string => {
    const parts: string[] = [];
    vals.forEach((v, i) => {
      if (v == null) return;
      const x = (i / (n - 1)) * w;
      const y = h - 4 - v * (h - 8);
      parts.push(`${parts.length === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
    });
    return parts.join(" ");
  };
  const costN = norm(costs);
  const rateN = norm(rates);
  return (
    <div className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-13 w-full"
        aria-hidden="true"
        preserveAspectRatio="none"
      >
        <path
          d={path(rateN)}
          fill="none"
          stroke="#34d399"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        <path
          d={path(costN)}
          fill="none"
          stroke="#22d3ee"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
      </svg>
      <div className="flex gap-2 text-[0.55rem] text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#22d3ee]" />
          {tq("runs.charts.legendCost")}
        </span>
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-[#34d399]" />
          {tq("runs.charts.legendPass")}
        </span>
      </div>
    </div>
  );
}

const DONUT_COLORS = ["#34d399", "#60a5fa", "#f59e0b", "#a78bfa", "#f87171", "#22d3ee"];

/** Donut of category shares with a center total and a compact legend. */
function MiniDonut({
  items,
  center,
}: {
  items: { label: string; value: number }[];
  center: string;
}) {
  const total = items.reduce((a, b) => a + b.value, 0);
  if (total === 0) return <ChartEmpty />;
  const r = 26;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 64 64" className="h-16 w-16 shrink-0" aria-hidden="true">
        <g transform="rotate(-90 32 32)">
          {items.map((it, i) => {
            const frac = it.value / total;
            const dash = frac * c;
            const seg = (
              <circle
                key={it.label}
                cx={32}
                cy={32}
                r={r}
                fill="none"
                stroke={DONUT_COLORS[i % DONUT_COLORS.length]}
                strokeWidth={9}
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset}
              />
            );
            offset += dash;
            return seg;
          })}
        </g>
        <text
          x="32"
          y="35"
          textAnchor="middle"
          className="fill-[var(--foreground)] text-[0.6rem] font-semibold tabular-nums"
        >
          {center}
        </text>
      </svg>
      <ul className="flex flex-col gap-0.5 text-[0.6rem]">
        {items.map((it, i) => (
          <li key={it.label} className="flex items-center gap-1">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: DONUT_COLORS[i % DONUT_COLORS.length] }}
            />
            <span className="uppercase text-[var(--muted-foreground)]">{it.label}</span>
            <span className="tabular-nums text-[var(--foreground)]">
              {Math.round((it.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ChartEmpty() {
  const tq = useTranslations("quality");
  return (
    <div className="flex h-14 items-center justify-center text-[0.62rem] text-[var(--muted-foreground)]">
      {tq("runs.charts.noData")}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-[0.72rem] font-medium text-[var(--muted-foreground)]">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-1">{children}</CardContent>
    </Card>
  );
}

/** The six mini-charts row — every series derived from a real endpoint (image 02). */
export function RunsCharts({
  registry,
  models,
  datasets,
}: {
  registry: RunRegistry | undefined;
  models: ModelComparison | undefined;
  datasets: QualityDatasetsReport | undefined;
}) {
  const tq = useTranslations("quality");
  const themeLabel = (key: string) => tq(`runs.theme.${key}`);

  // 1. Pass-rate of the most recent full-catalogue runs, oldest→newest.
  const recent = [...(registry?.runs ?? [])]
    .filter((r) => r.total >= 10)
    .sort((a, b) => (parseRunAt(a.run_at) ?? 0) - (parseRunAt(b.run_at) ?? 0))
    .slice(-12)
    .map((r) => r.pass_rate);

  // 2. Coverage per dataset (theme), banded.
  const coverage = (datasets?.datasets ?? [])
    .filter((d) => d.coverage != null)
    .map((d) => ({ label: themeLabel(d.key), value: d.coverage ?? 0 }));

  // 3. Mean drift per dataset, largest magnitude first.
  const drift = (datasets?.datasets ?? [])
    .filter((d) => d.drift != null)
    .map((d) => ({ label: themeLabel(d.key), value: d.drift ?? 0 }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

  // 4. Case distribution by theme, donut centre = total catalogue cases.
  const caseDist = (datasets?.datasets ?? [])
    .map((d) => ({ label: themeLabel(d.key), value: d.cases }))
    .sort((a, b) => b.value - a.value);
  const totalCases = datasets?.total_cases ?? 0;

  // 5. Cost vs quality — per model, ordered by pass-rate; cost line skips nulls.
  const byRate = [...(models?.models ?? [])].sort((a, b) => a.pass_rate - b.pass_rate);
  const costLabels = byRate.map((m) => m.model.split(":")[0] ?? m.model);
  const costs = byRate.map((m) => m.est_cost_eur);
  const rates = byRate.map((m) => m.pass_rate * 100);

  // 6. Pass-rate per model.
  const perfPts = (models?.models ?? []).map((m) => ({
    label: m.model.split(":")[0] ?? m.model,
    value: Math.round(m.pass_rate * 100),
  }));

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      <ChartCard title={tq("runs.charts.passrate")}>
        <MiniLine values={recent} band />
      </ChartCard>
      <ChartCard title={tq("runs.charts.coverage")}>
        <CoverageBars items={coverage} />
      </ChartCard>
      <ChartCard title={tq("runs.charts.drift")}>
        <DriftBars items={drift} />
      </ChartCard>
      <ChartCard title={tq("runs.charts.distribution")}>
        <MiniDonut items={caseDist} center={totalCases.toLocaleString("fr-FR")} />
      </ChartCard>
      <ChartCard title={tq("runs.charts.costQuality")}>
        <DualLine labels={costLabels} costs={costs} rates={rates} />
      </ChartCard>
      <ChartCard title={tq("runs.charts.perfByModel")}>
        <MiniBars items={perfPts} band />
      </ChartCard>
    </div>
  );
}

// ──────────────────────────────── right rail ─────────────────────────────────

/** One pipeline-health row: label, value (or "—") and an OK/—/state pill. */
function HealthRow({
  label,
  value,
  ok,
}: {
  label: string;
  value: string;
  ok: boolean | null; // null → no real source (renders neutral, never a fake OK)
}) {
  const tq = useTranslations("quality");
  const tone = ok == null ? MUTED : ok ? GOOD : WARN;
  return (
    <div className="flex items-center justify-between gap-2 py-0.5 text-[0.7rem]">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <span className="flex items-center gap-1.5">
        <span className="tabular-nums text-[var(--foreground)]">{value}</span>
        <span className={`text-[0.6rem] font-medium ${tone}`}>
          {ok == null ? DASH : ok ? tq("runs.rail.pOk") : tq("runs.rail.pWatch")}
        </span>
      </span>
    </div>
  );
}

/** Tab-specific right rail for Runs & datasets — four cards (reference image 02). */
export function RunsRail({
  registry,
  datasets,
  release,
}: {
  registry: RunRegistry | undefined;
  datasets: QualityDatasetsReport | undefined;
  release: ReleaseStatus | undefined;
}) {
  const tq = useTranslations("quality");
  const rel = release?.current ?? null;
  const regOpen = release?.n_regressions ?? null;
  const relTone = regOpen == null ? MUTED : regOpen > 0 ? WARN : GOOD;
  const monitored = datasets?.monitored ?? 0;
  const coveragePct = datasets?.coverage_pct ?? null;
  const pipe = datasets?.pipeline;
  // Recent activity from the real archive — newest runs first.
  const activity = [...(registry?.runs ?? [])]
    .sort((a, b) => (parseRunAt(b.run_at) ?? 0) - (parseRunAt(a.run_at) ?? 0))
    .slice(0, 4);

  return (
    <aside className="flex w-full flex-col gap-2 2xl:w-72">
      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center gap-1.5 text-[0.8rem]">
            <Workflow className="h-3.5 w-3.5" />
            {tq("runs.rail.release")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-1">
          {rel == null ? (
            <p className="text-[0.7rem] text-[var(--muted-foreground)]">
              {tq("runs.rail.noRelease")}
            </p>
          ) : (
            <>
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-[var(--foreground)]">{rel.version}</span>
                <Badge tone="neutral" className={`text-[0.62rem] ${relTone}`}>
                  {regOpen != null && regOpen > 0 ? tq("runs.kpi.regOpen", { n: regOpen }) : "OK"}
                </Badge>
              </div>
              {rel.date ? (
                <p className="mt-0.5 text-[0.65rem] text-[var(--muted-foreground)]">
                  {tq("runs.rail.releaseDate", { d: rel.date })}
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center gap-1.5 text-[0.8rem]">
            <Boxes className="h-3.5 w-3.5" />
            {tq("runs.rail.datasets")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-1">
          <div className="flex items-baseline gap-1">
            <span className="text-xl font-semibold tabular-nums text-[var(--foreground)]">
              {monitored}
            </span>
            <span className="text-[0.65rem] text-[var(--muted-foreground)]">
              {tq("runs.rail.active")}
            </span>
          </div>
          <p className="text-[0.65rem] text-[var(--muted-foreground)]">
            {coveragePct == null
              ? DASH
              : tq("runs.rail.covered", { p: Math.round(coveragePct * 100) })}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center gap-1.5 text-[0.8rem]">
            <Activity className="h-3.5 w-3.5" />
            {tq("runs.rail.activity")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-1">
          {activity.length === 0 ? (
            <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("runs.empty")}</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {activity.map((r) => (
                <li key={r.run_id} className="flex items-start gap-1.5 text-[0.68rem]">
                  <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                  <div className="min-w-0">
                    <p className="truncate text-[var(--foreground)]">
                      {tq("runs.rail.runDone", { model: r.model, rate: fmtPct(r.pass_rate) })}
                    </p>
                    <p className="text-[0.6rem] text-[var(--muted-foreground)]">
                      {fmtDate(r.run_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center gap-1.5 text-[0.8rem]">
            <Database className="h-3.5 w-3.5" />
            {tq("runs.rail.health")}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-1">
          {/* Real signals: executions in window, data freshness, catalogue coverage.
              Workers / queue / evidence-retention have no source → "—", never faked. */}
          <HealthRow
            label={tq("runs.rail.pJobs")}
            value={pipe ? String(pipe.jobs_window) : DASH}
            ok={pipe ? pipe.jobs_window > 0 : null}
          />
          <HealthRow
            label={tq("runs.rail.pWorkers")}
            value={pipe?.workers != null ? String(pipe.workers) : DASH}
            ok={pipe?.workers != null ? pipe.workers > 0 : null}
          />
          <HealthRow
            label={tq("runs.rail.pQueue")}
            value={pipe?.queue_depth != null ? String(pipe.queue_depth) : DASH}
            ok={pipe?.queue_depth != null ? pipe.queue_depth === 0 : null}
          />
          <HealthRow
            label={tq("runs.rail.pFreshness")}
            value={fmtFreshness(pipe?.data_freshness_seconds)}
            ok={
              pipe?.data_freshness_seconds != null
                ? pipe.data_freshness_seconds < 14 * 86_400
                : null
            }
          />
          <HealthRow
            label={tq("runs.rail.pRetention")}
            value={
              pipe?.evidence_retention_days != null ? `${pipe.evidence_retention_days} j` : DASH
            }
            ok={pipe?.evidence_retention_days != null ? true : null}
          />
        </CardContent>
      </Card>
    </aside>
  );
}
