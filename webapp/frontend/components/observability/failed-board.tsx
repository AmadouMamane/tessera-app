"use client";

import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileDown,
  FilePlus2,
  GitBranch,
  Layers,
  LinkIcon,
  Repeat,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { QInfo } from "@/components/observability/quality-info";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FailedRunCase, FailedRunsReport, ReleaseStatus } from "@/lib/api/schemas";

const DASH = "—";
const PAGE_SIZE = 25;

/** Trigger a client-side JSON download (no server round-trip). */
function downloadJson(name: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

const KNOWN_CATEGORIES = [
  "prompt_injection",
  "pii_leak",
  "hallucination",
  "overconfidence",
  "regulatory_misstatement",
  "citation_fabrication",
  "tool_misuse",
  "policy_violation",
  "language_mixing",
  "escalation_failure",
];

const SEV_TONE: Record<string, "danger" | "warning" | "neutral"> = {
  critical: "danger",
  high: "warning",
  medium: "neutral",
  low: "neutral",
};

const DONUT_COLORS = [
  "#ef4444",
  "#f59e0b",
  "#3b82f6",
  "#8b5cf6",
  "#10b981",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#64748b",
  "#a3a3a3",
];

function useCatLabel() {
  const tq = useTranslations("quality");
  return (c: string) =>
    KNOWN_CATEGORIES.includes(c) ? tq(`failed.cat.${c}`) : c.replace(/_/g, " ");
}

function pct(n: number, total: number): string {
  if (total <= 0) return "0%";
  return `${Math.round((n / total) * 100)}%`;
}

function shortModel(model: string): string {
  return model || DASH;
}

function fmtDay(stamp: string): string {
  const m = stamp.match(/^(\d{4})(\d{2})(\d{2})/);
  if (!m) return stamp;
  const [, , mo, d] = m;
  return `${d}/${mo}`;
}

// ───────────────────────────────── sparkline ─────────────────────────────────

/** Tiny filled-area sparkline of the daily failure trend. */
function Spark({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return <div className="h-6" />;
  const max = Math.max(...values, 1);
  const w = 96;
  const h = 24;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - 2 - (v / max) * (h - 4);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-6 w-full"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}

// ──────────────────────────────── KPI strip ──────────────────────────────────

function KpiTile({
  icon,
  label,
  value,
  sub,
  tone,
  spark,
  sparkColor,
  explainKey,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  tone?: string;
  spark?: number[];
  sparkColor?: string;
  explainKey?: string;
}) {
  return (
    <Card className="flex flex-col gap-1 p-2.5">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-[0.65rem] text-[var(--muted-foreground)]">
          <span className="opacity-70">{icon}</span>
          {label}
          {explainKey ? <QInfo title={label} k={explainKey} /> : null}
        </span>
        {sub ? <span className="text-[0.6rem] text-[var(--muted-foreground)]">{sub}</span> : null}
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className={`text-2xl font-semibold leading-none tabular-nums ${tone ?? ""}`}>
          {value}
        </span>
        {spark && sparkColor ? (
          <span className="w-24 shrink-0">
            <Spark values={spark} color={sparkColor} />
          </span>
        ) : null}
      </div>
    </Card>
  );
}

function FailedKpis({ report }: { report: FailedRunsReport | undefined }) {
  const tq = useTranslations("quality");
  const total = report?.n ?? 0;
  const trend = (report?.trend ?? []).map((t) => t.n);
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      <KpiTile
        icon={<AlertCircle className="h-3.5 w-3.5" />}
        label={tq("failed.kpi.total")}
        explainKey="failTotal"
        value={String(total)}
        tone="text-red-500 dark:text-red-400"
        spark={trend}
        sparkColor="#ef4444"
      />
      <KpiTile
        icon={<AlertCircle className="h-3.5 w-3.5" />}
        label={tq("failed.kpi.critical")}
        explainKey="failCritical"
        value={String(report?.n_critical ?? 0)}
        sub={pct(report?.n_critical ?? 0, total)}
        tone="text-red-500 dark:text-red-400"
        spark={trend}
        sparkColor="#f87171"
      />
      <KpiTile
        icon={<Sparkles className="h-3.5 w-3.5" />}
        label={tq("failed.kpi.new")}
        explainKey="failNew"
        value={String(report?.n_new ?? 0)}
        sub={pct(report?.n_new ?? 0, total)}
        tone="text-amber-500 dark:text-amber-400"
        spark={trend}
        sparkColor="#f59e0b"
      />
      <KpiTile
        icon={<Repeat className="h-3.5 w-3.5" />}
        label={tq("failed.kpi.recurrent")}
        explainKey="failRecurrent"
        value={String(report?.n_recurrent ?? 0)}
        sub={pct(report?.n_recurrent ?? 0, total)}
        tone="text-violet-500 dark:text-violet-400"
        spark={trend}
        sparkColor="#8b5cf6"
      />
    </div>
  );
}

// ──────────────────────────────── filter bar ─────────────────────────────────

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-[0.7rem] text-[var(--foreground)]"
    >
      {children}
    </select>
  );
}

// ─────────────────────────────── bottom charts ───────────────────────────────

function MiniDonut({
  items,
  center,
  label,
}: {
  items: { key: string; label: string; value: number }[];
  center: string;
  label: string;
}) {
  const total = items.reduce((a, b) => a + b.value, 0);
  if (total === 0) return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{DASH}</p>;
  const r = 26;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-16 w-16 shrink-0">
        <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90" aria-hidden="true">
          {items.map((it, i) => {
            const len = (it.value / total) * c;
            const seg = (
              <circle
                key={it.key}
                cx="32"
                cy="32"
                r={r}
                fill="none"
                stroke={DONUT_COLORS[i % DONUT_COLORS.length]}
                strokeWidth={9}
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
              />
            );
            offset += len;
            return seg;
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-sm font-semibold tabular-nums">{center}</span>
          <span className="text-[0.55rem] text-[var(--muted-foreground)]">{label}</span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.6rem]">
        {items.slice(0, 5).map((it, i) => (
          <li key={it.key} className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-1">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }}
              />
              <span className="truncate text-[var(--muted-foreground)]">{it.label}</span>
            </span>
            <span className="shrink-0 tabular-nums">{Math.round((it.value / total) * 100)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Severity stack order (bottom → top) + colours for the failures-over-time chart.
const SEV_STACK = [
  { key: "critical", color: "#ef4444" },
  { key: "high", color: "#f59e0b" },
  { key: "medium", color: "#3b82f6" },
  { key: "low", color: "#64748b" },
] as const;

type TrendPt = { date: string; n: number; by_severity: Record<string, number> };

/** Failed cases per day as severity-stacked bars; the day total sits above each
 *  bar so volume, composition and the count are all visible at once. */
function TrendStacked({ points }: { points: TrendPt[] }) {
  const tq = useTranslations("quality");
  if (points.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{DASH}</p>;
  const max = Math.max(...points.map((p) => p.n), 1);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex h-20 items-end justify-around gap-3">
        {points.map((p) => (
          <div key={p.date} className="flex w-12 flex-col items-center gap-0.5">
            <span className="text-[0.6rem] font-medium tabular-nums">{p.n}</span>
            <div
              className="flex w-7 flex-col justify-end overflow-hidden rounded-sm"
              style={{ height: `${Math.max(4, (p.n / max) * 56)}px` }}
              title={SEV_STACK.map((s) => `${s.key}: ${p.by_severity[s.key] ?? 0}`).join(" · ")}
            >
              {SEV_STACK.map((s) => {
                const v = p.by_severity[s.key] ?? 0;
                if (v === 0) return null;
                return (
                  <div key={s.key} style={{ height: `${(v / p.n) * 100}%`, background: s.color }} />
                );
              })}
            </div>
            <span className="text-[0.5rem] tabular-nums text-[var(--muted-foreground)]">
              {fmtDay(p.date)}
            </span>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[0.5rem] text-[var(--muted-foreground)]">
        {SEV_STACK.map((s) => (
          <span key={s.key} className="flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.color }} />
            {tq(`failed.sev.${s.key}`)}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Top root causes — bars share the donut's per-category colours so a category
 *  keeps the same identity colour across "Répartition" and "Top causes". */
function CauseBars({ items }: { items: { key: string; label: string; value: number }[] }) {
  if (items.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{DASH}</p>;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="flex flex-col gap-1">
      {items.map((it, i) => (
        <div key={it.key} className="flex items-center gap-1.5 text-[0.6rem]">
          <span className="flex w-24 shrink-0 items-center gap-1 truncate text-[var(--muted-foreground)]">
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full"
              style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }}
            />
            <span className="truncate">{it.label}</span>
          </span>
          <div className="h-[4px] flex-1 overflow-hidden rounded-sm bg-[var(--tessera-border)]">
            <div
              className="h-full rounded-sm"
              style={{
                width: `${(it.value / max) * 100}%`,
                background: DONUT_COLORS[i % DONUT_COLORS.length],
              }}
            />
          </div>
          <span className="w-6 shrink-0 text-right tabular-nums">{it.value}</span>
        </div>
      ))}
    </div>
  );
}

// ──────────────────────────────── the board ──────────────────────────────────

/** The full Cas échoués board — KPI, filters, table, charts (reference image 03). */
export function FailedBoard({
  report,
  selected,
  onSelect,
}: {
  report: FailedRunsReport | undefined;
  selected: FailedRunCase | null;
  onSelect: (c: FailedRunCase) => void;
}) {
  const tq = useTranslations("quality");
  const tt = useTranslations("table");
  const catLabel = useCatLabel();
  const [sev, setSev] = useState("all");
  const [cat, setCat] = useState("all");
  const [model, setModel] = useState("all");
  const [lang, setLang] = useState("all");
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const cases = report?.cases ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return cases.filter(
      (c) =>
        (sev === "all" || c.severity === sev) &&
        (cat === "all" || c.category === cat) &&
        (model === "all" || c.model === model) &&
        (lang === "all" || c.language === lang) &&
        (status === "all" || c.status === status) &&
        (q === "" ||
          c.id.toLowerCase().includes(q) ||
          c.prompt.toLowerCase().includes(q) ||
          c.response.toLowerCase().includes(q)),
    );
  }, [cases, sev, cat, model, lang, status, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  // The same case id fails under several languages/models within one run, so
  // run_id:id is not unique — include language + model to avoid duplicate keys.
  const rowKey = (c: FailedRunCase) => `${c.run_id}:${c.id}:${c.language}:${c.model}`;
  const selectedKey = selected ? rowKey(selected) : null;
  const toggle = (c: FailedRunCase) => {
    const k = rowKey(c);
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  const exportSelection = () => {
    const chosen = filtered.filter((c) => picked.has(rowKey(c)));
    downloadJson("tessera-cas-echoues.json", chosen.length ? chosen : filtered);
  };

  const total = report?.n ?? 0;
  const dist = Object.entries(report?.by_category ?? {})
    .map(([key, value]) => ({ key, label: catLabel(key), value }))
    .sort((a, b) => b.value - a.value);
  const causes = dist.slice(0, 5);
  const meanLatency = report?.mean_latency_ms ?? null;

  return (
    <div className="flex flex-col gap-2">
      <FailedKpis report={report} />

      {/* filters + bulk actions */}
      <Card className="flex flex-col gap-2 p-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Select value={sev} onChange={setSev}>
            <option value="all">{tq("failed.filters.severity")}</option>
            {["critical", "high", "medium", "low"].map((s) => (
              <option key={s} value={s}>
                {tq(`failed.sev.${s}`)}
              </option>
            ))}
          </Select>
          <Select value={cat} onChange={setCat}>
            <option value="all">{tq("failed.filters.category")}</option>
            {Object.keys(report?.by_category ?? {}).map((c) => (
              <option key={c} value={c}>
                {catLabel(c)}
              </option>
            ))}
          </Select>
          <Select value={model} onChange={setModel}>
            <option value="all">{tq("failed.filters.model")}</option>
            {(report?.models ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
          <Select value={lang} onChange={setLang}>
            <option value="all">{tq("failed.filters.lang")}</option>
            {(report?.languages ?? []).map((l) => (
              <option key={l} value={l}>
                {l.toUpperCase()}
              </option>
            ))}
          </Select>
          <Select value={status} onChange={setStatus}>
            <option value="all">{tq("failed.filters.status")}</option>
            <option value="new">{tq("failed.status.new")}</option>
            <option value="recurrent">{tq("failed.status.recurrent")}</option>
          </Select>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={tq("failed.filters.search")}
            className="min-w-[12rem] flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-[0.7rem]"
          />
          <span className="text-[0.65rem] text-[var(--muted-foreground)]">
            {tq("failed.count", { shown: filtered.length, total })}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t border-[var(--border)] pt-2 text-[0.68rem]">
          <span className="text-[var(--muted-foreground)]">
            {tq("failed.bulk.selected", { n: picked.size })}
          </span>
          <button
            type="button"
            onClick={exportSelection}
            className="inline-flex items-center gap-1 text-[var(--primary)] hover:underline"
          >
            <Download className="h-3 w-3" />
            {tq("failed.bulk.export")}
          </button>
          <span className="inline-flex items-center gap-1 text-[var(--muted-foreground)]">
            <Layers className="h-3 w-3" />
            {tq("failed.bulk.addDataset")}
            <Badge tone="neutral" className="text-[0.55rem]">
              Admin+
            </Badge>
          </span>
          <span className="inline-flex items-center gap-1 text-[var(--muted-foreground)]">
            <FilePlus2 className="h-3 w-3" />
            {tq("failed.bulk.createCase")}
            <Badge tone="neutral" className="text-[0.55rem]">
              Admin+
            </Badge>
          </span>
          <span className="inline-flex items-center gap-1 text-[var(--muted-foreground)]">
            <UserPlus className="h-3 w-3" />
            {tq("failed.bulk.assignOwner")}
            <Badge tone="neutral" className="text-[0.55rem]">
              Admin+
            </Badge>
          </span>
        </div>
      </Card>

      {/* main table */}
      <Card>
        <CardContent className="overflow-x-auto py-2">
          {rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
              {tq("failed.empty")}
            </p>
          ) : (
            <table className="w-full min-w-[940px] table-fixed text-left text-[0.7rem]">
              <thead className="text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
                <tr className="border-b border-[var(--border)]">
                  <th className="w-9 py-1.5 pl-4" />
                  <th className="w-[8%] px-2 py-1.5 font-medium">{tq("failed.cols.id")}</th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">{tq("failed.cols.severity")}</th>
                  <th className="w-[10%] px-2 py-1.5 font-medium">{tq("failed.cols.category")}</th>
                  <th className="w-[22%] px-2 py-1.5 font-medium">{tq("failed.cols.prompt")}</th>
                  <th className="w-[6%] px-2 py-1.5 text-right font-medium">
                    {tq("failed.cols.score")}
                  </th>
                  <th className="w-[7%] px-2 py-1.5 font-medium">{tq("failed.cols.run")}</th>
                  <th className="w-[10%] px-2 py-1.5 font-medium">{tq("failed.cols.model")}</th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">{tq("failed.cols.owner")}</th>
                  <th className="w-[9%] px-2 py-1.5 font-medium">{tq("failed.cols.status")}</th>
                  <th className="w-24 py-1.5 pr-4 pl-2 font-medium">
                    <span className="sr-only">{tt("rowOpen")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => {
                  const k = rowKey(c);
                  const isSelected = k === selectedKey;
                  return (
                    <tr
                      key={k}
                      onClick={() => onSelect(c)}
                      // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(c);
                        }
                      }}
                      className={`group cursor-pointer border-b border-[var(--border)]/50 outline-none transition-colors hover:bg-[var(--accent)]/40 focus-visible:bg-[var(--accent)]/40 ${
                        isSelected ? "bg-[var(--accent)]/60" : ""
                      }`}
                    >
                      <td className="py-1.5 pl-4">
                        <input
                          type="checkbox"
                          checked={picked.has(k)}
                          onChange={() => toggle(c)}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={c.id}
                        />
                      </td>
                      <td className="px-2 py-2 font-mono text-[0.65rem] text-[var(--muted-foreground)]">
                        <span className="block truncate" title={c.id}>
                          {c.id}
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <Badge tone={SEV_TONE[c.severity] ?? "neutral"} className="text-[0.6rem]">
                          {tq(`failed.sev.${c.severity}`)}
                        </Badge>
                      </td>
                      <td className="px-2 py-2">
                        <span className="block truncate" title={catLabel(c.category)}>
                          {catLabel(c.category)}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-[var(--muted-foreground)]">
                        <span className="block truncate" title={c.prompt}>
                          {c.prompt}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-right tabular-nums text-[var(--muted-foreground)]">
                        {DASH}
                      </td>
                      <td className="px-2 py-2 font-mono text-[0.62rem] text-[var(--muted-foreground)]">
                        {c.catalogue_version ? `v${c.catalogue_version.split("-")[0]}` : DASH}
                      </td>
                      <td className="px-2 py-2">
                        <span className="block truncate" title={c.model}>
                          {shortModel(c.model)}
                        </span>
                      </td>
                      <td className="px-2 py-2 text-[var(--muted-foreground)]">
                        <span className="block truncate" title={c.owner}>
                          {c.owner}
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <span
                          className={`inline-flex items-center gap-1 text-[0.62rem] ${
                            c.status === "new"
                              ? "text-amber-600 dark:text-amber-400"
                              : "text-violet-600 dark:text-violet-400"
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              c.status === "new" ? "bg-amber-500" : "bg-violet-500"
                            }`}
                          />
                          {tq(`failed.status.${c.status}`)}
                        </span>
                      </td>
                      <td className="py-2 pr-4 pl-2">
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
        {filtered.length > PAGE_SIZE ? (
          <div className="flex items-center justify-end gap-2 border-t border-[var(--border)] px-3 py-1.5 text-[0.65rem] text-[var(--muted-foreground)]">
            <span>
              {tq("failed.page.range", {
                from: safePage * PAGE_SIZE + 1,
                to: Math.min(filtered.length, (safePage + 1) * PAGE_SIZE),
                total: filtered.length,
              })}
            </span>
            <button
              type="button"
              disabled={safePage === 0}
              onClick={() => setPage(safePage - 1)}
              className="rounded p-0.5 disabled:opacity-40"
              aria-label="prev"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage(safePage + 1)}
              className="rounded p-0.5 disabled:opacity-40"
              aria-label="next"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </Card>

      {/* bottom analytics row */}
      <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-1.5 text-[0.72rem] font-medium text-[var(--muted-foreground)]">
              {tq("failed.distribution")}
              <QInfo title={tq("failed.distribution")} k="failDistribution" />
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-1">
            <MiniDonut items={dist} center={String(total)} label={tq("failed.casesLabel")} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-1.5 text-[0.72rem] font-medium text-[var(--muted-foreground)]">
              {tq("failed.charts.evolution")}
              <QInfo title={tq("failed.charts.evolution")} k="failEvolution" />
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-1">
            <TrendStacked points={report?.trend ?? []} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-1.5 text-[0.72rem] font-medium text-[var(--muted-foreground)]">
              {tq("failed.charts.causes")}
              <QInfo title={tq("failed.charts.causes")} k="failCauses" />
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-1">
            <CauseBars items={causes} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-1.5 text-[0.72rem] font-medium text-[var(--muted-foreground)]">
              {tq("failed.charts.sla")}
              <QInfo title={tq("failed.charts.sla")} k="failSla" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 pt-1 text-[0.7rem]">
            <SlaRow label={tq("failed.sla.meanLatency")} value={fmtLatency(meanLatency)} />
            <SlaRow label={tq("failed.sla.critical")} value={pct(report?.n_critical ?? 0, total)} />
            <SlaRow label={tq("failed.sla.new")} value={pct(report?.n_new ?? 0, total)} />
            <SlaRow label={tq("failed.sla.models")} value={String(report?.models.length ?? 0)} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function fmtLatency(ms: number | null): string {
  if (ms == null) return DASH;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function SlaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}

// ──────────────────────────────── selected rail ──────────────────────────────

/** Build the eval-failure-shaped candidate for "Ajouter au dataset". */
function datasetCandidate(c: FailedRunCase): Record<string, unknown> {
  return {
    id: c.id,
    category: c.category,
    title: c.title,
    severity: c.severity,
    prompts: { [c.language]: { user: c.prompt } },
    expected_behavior: c.expected,
    observed_failure: {
      model: c.model,
      run_id: c.run_id,
      response: c.response,
      reasons: c.reasons,
    },
  };
}

/** Right-rail fiche for the selected failed case (reference image 03). */
export function FailedRail({
  failedCase,
  release,
  onEvidence,
}: {
  failedCase: FailedRunCase | undefined;
  release?: ReleaseStatus | undefined;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const catLabel = useCatLabel();

  const exportReport = () => {
    if (failedCase) downloadJson(`tessera-cas-${failedCase.id}.json`, failedCase);
  };
  const addToDataset = () => {
    if (failedCase)
      downloadJson(`eval-failure-${failedCase.id}.json`, datasetCandidate(failedCase));
  };
  const createControlCase = () => {
    if (failedCase)
      downloadJson(`control-case-${failedCase.id}.json`, {
        kind: "control_case",
        case_id: failedCase.id,
        category: failedCase.category,
        run_id: failedCase.run_id,
        release: release?.current?.version ?? null,
        expected: failedCase.expected,
      });
  };

  return (
    <aside className="flex w-full flex-col gap-2 2xl:w-80">
      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="flex items-center justify-between gap-2 text-[0.8rem]">
            <span className="flex items-center gap-1.5 font-mono text-[0.72rem]">
              {failedCase?.id ?? tq("failed.rail.none")}
              <QInfo title={tq("failed.rail.fiche")} k="failFiche" />
            </span>
            <span className="flex items-center gap-1.5">
              {failedCase ? (
                <Badge tone={SEV_TONE[failedCase.severity] ?? "neutral"} className="text-[0.6rem]">
                  {tq(`failed.sev.${failedCase.severity}`)}
                </Badge>
              ) : null}
              {failedCase ? (
                <>
                  <button
                    type="button"
                    onClick={exportReport}
                    title={tq("failed.rail.exportReport")}
                    className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={onEvidence}
                    title={tq("failed.rail.genEvidence")}
                    className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  >
                    <FileDown className="h-3.5 w-3.5" />
                  </button>
                </>
              ) : null}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-1">
          {failedCase == null ? (
            <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
              {tq("failed.rail.empty")}
            </p>
          ) : (
            <div className="flex flex-col gap-2 text-[0.7rem]">
              <RailKV k={tq("failed.rail.category")} v={catLabel(failedCase.category)} />
              <RailKV k={tq("failed.rail.model")} v={failedCase.model} />
              <RailKV k={tq("failed.rail.lang")} v={failedCase.language.toUpperCase()} />
              <RailKV k={tq("failed.rail.owner")} v={failedCase.owner} />
              <RailKV k={tq("failed.rail.status")} v={tq(`failed.status.${failedCase.status}`)} />

              <Section title={tq("failed.rail.prompt")}>{failedCase.prompt || DASH}</Section>
              <Section title={tq("failed.rail.expected")}>{failedCase.expected || DASH}</Section>
              <Section title={tq("failed.rail.response")} tone="bad">
                {failedCase.response || DASH}
              </Section>
              {failedCase.reasons.length ? (
                <div>
                  <p className="mb-0.5 text-[0.62rem] font-medium uppercase text-[var(--muted-foreground)]">
                    {tq("failed.rail.rootCause")}
                  </p>
                  <ul className="flex flex-col gap-1">
                    {failedCase.reasons.map((r) => (
                      <li
                        key={r}
                        className="flex items-start gap-1 rounded bg-red-500/10 px-1.5 py-1 text-[0.65rem] text-red-700 dark:text-red-300"
                      >
                        <AlertCircle className="mt-0.5 h-3 w-3 shrink-0" />
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="flex flex-col gap-1 border-t border-[var(--border)] pt-2">
                <span className="inline-flex items-center justify-between gap-2 text-[0.65rem] text-[var(--muted-foreground)]">
                  <span className="flex items-center gap-1">
                    <GitBranch className="h-3 w-3" />
                    {tq("failed.rail.run")}
                  </span>
                  <span className="font-mono text-[0.62rem] text-[var(--foreground)]">
                    {failedCase.run_id}
                  </span>
                </span>
                <span className="inline-flex items-center justify-between gap-2 text-[0.65rem] text-[var(--muted-foreground)]">
                  <span>{tq("failed.rail.release")}</span>
                  <span className="text-[0.62rem] text-[var(--foreground)]">
                    {release?.current?.version ?? DASH}
                  </span>
                </span>
              </div>

              {/* Governed actions — every button produces a real artifact; applying
                  to the repo requires the stated role (no fake success state). */}
              <div className="flex flex-col gap-1.5 border-t border-[var(--border)] pt-2">
                <p className="text-[0.62rem] font-medium uppercase text-[var(--muted-foreground)]">
                  {tq("failed.rail.actions")}
                </p>
                <ActionButton
                  icon={<Layers className="h-3.5 w-3.5" />}
                  label={tq("failed.rail.addDataset")}
                  requiredRole="Admin+"
                  tone="primary"
                  onClick={addToDataset}
                />
                <ActionButton
                  icon={<LinkIcon className="h-3.5 w-3.5" />}
                  label={tq("failed.rail.controlCase")}
                  requiredRole="Admin+"
                  tone="info"
                  onClick={createControlCase}
                />
                <ActionButton
                  icon={<Download className="h-3.5 w-3.5" />}
                  label={tq("failed.rail.exportReport")}
                  requiredRole="Operator+"
                  tone="outline"
                  onClick={exportReport}
                />
                <ActionButton
                  icon={<FileDown className="h-3.5 w-3.5" />}
                  label={tq("failed.rail.genEvidence")}
                  requiredRole="Operator+"
                  tone="accent"
                  onClick={onEvidence}
                />
                <p className="flex items-center gap-1 pt-0.5 text-[0.58rem] text-[var(--muted-foreground)]">
                  <ShieldCheck className="h-3 w-3" />
                  {tq("failed.rail.safety")}
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </aside>
  );
}

const ACTION_TONE: Record<string, string> = {
  primary: "border-emerald-600/40 bg-emerald-600/15 text-emerald-700 dark:text-emerald-300",
  info: "border-blue-600/40 bg-blue-600/15 text-blue-700 dark:text-blue-300",
  accent: "border-[var(--primary)]/40 bg-[var(--primary)]/10 text-[var(--primary)]",
  outline: "border-[var(--border)] text-[var(--foreground)]",
};

function ActionButton({
  icon,
  label,
  requiredRole,
  tone,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  requiredRole: string;
  tone: "primary" | "info" | "accent" | "outline";
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-between gap-2 rounded-md border px-2.5 py-1.5 text-[0.7rem] font-medium transition-colors hover:brightness-110 ${ACTION_TONE[tone]}`}
    >
      <span className="flex items-center gap-1.5">
        {icon}
        {label}
      </span>
      <Badge tone="neutral" className="text-[0.55rem]">
        {requiredRole}
      </Badge>
    </button>
  );
}

function RailKV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{k}</span>
      <span className="font-medium text-[var(--foreground)]">{v}</span>
    </div>
  );
}

function Section({
  title,
  tone,
  children,
}: {
  title: string;
  tone?: "bad";
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-0.5 text-[0.62rem] font-medium uppercase text-[var(--muted-foreground)]">
        {title}
      </p>
      <p
        className={`line-clamp-4 rounded px-1.5 py-1 text-[0.65rem] ${
          tone === "bad"
            ? "bg-red-500/5 text-[var(--foreground)]"
            : "bg-[var(--muted)]/30 text-[var(--muted-foreground)]"
        }`}
      >
        {children}
      </p>
    </div>
  );
}
