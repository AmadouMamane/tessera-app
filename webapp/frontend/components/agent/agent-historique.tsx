"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  ChevronDown,
  ChevronRight,
  Clock,
  Coins,
  Download,
  GitCompare,
  type LucideIcon,
  MessagesSquare,
  Play,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { fetchAgentHistorique } from "@/lib/api/client";
import type { AgentHistorique as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { AgentTabs } from "./agent-tabs";

const KPI_ICONS: LucideIcon[] = [MessagesSquare, MessagesSquare, Sparkles, Target, Clock, Coins];
const SPARK_TONE: Record<string, string> = {
  violet: "#8b7cf0",
  blue: "#4c8bf5",
  green: "#34d399",
  amber: "#e0a23a",
};
const TONE_TEXT: Record<string, string> = {
  good: "text-emerald-400",
  bad: "text-red-400",
  muted: "text-[var(--tessera-text-muted)]",
};
const SCORE_TEXT: Record<string, string> = {
  good: "text-emerald-300",
  warn: "text-amber-300",
  crit: "text-red-300",
};
const STATUS_BADGE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  info: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  warn: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
};
const SEG_FILL: Record<string, string> = {
  green: "#34d399",
  blue: "#4c8bf5",
  amber: "#e0a23a",
  red: "#f87171",
};
const SEG_DOT: Record<string, string> = {
  green: "bg-emerald-400",
  blue: "bg-sky-400",
  amber: "bg-amber-400",
  red: "bg-red-400",
};
const WATCH_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  crit: "bg-red-400",
};

export function AgentHistorique() {
  const t = useTranslations("agentHistorique");
  const [subtab, setSubtab] = useState("");
  const { data } = useQuery({
    queryKey: ["agent-historique"],
    queryFn: ({ signal }) => fetchAgentHistorique(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  const a = data.actions;
  const subtabs = data.subtabs ?? [];
  const active = subtab || subtabs[0] || "";
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <AgentTabs
        actions={
          <>
            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
            >
              <Download className="h-4 w-4" /> {a?.export}
            </button>
            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
            >
              <GitCompare className="h-4 w-4" /> {a?.compare}
            </button>
            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5]"
            >
              {a?.create}
            </button>
          </>
        }
      />

      <nav className="flex flex-wrap items-center gap-1 border-b border-[var(--tessera-border)] pb-1.5">
        {subtabs.map((tb) => {
          const on = tb === active;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setSubtab(tb)}
              className={cn(
                "-mb-px shrink-0 border-b-2 px-3 py-1.5 text-[0.74rem] transition-colors",
                on
                  ? "border-[#6d4aed] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tb}
            </button>
          );
        })}
      </nav>

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Sparkles} />
        ))}
      </div>

      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
          <Filters data={data} />
          <SessionsTable data={data} />
          <div className="grid gap-2.5 lg:grid-cols-2 xl:grid-cols-4">
            <TrendCard data={data} />
            <ByAgent data={data} />
            <ScoreDonut data={data} />
            <SuccessCard data={data} />
          </div>
          <div className="grid gap-2.5 md:grid-cols-2">
            <Watch data={data} />
            <Quick data={data} />
          </div>
        </div>
        <Detail data={data} className="xl:col-span-4" />
      </div>
    </div>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[96px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <span className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </span>
      </div>
      <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {kpi.value}
      </p>
      <div className="flex items-end justify-between gap-2">
        <span
          className={cn(
            "text-[0.58rem] tabular-nums",
            TONE_TEXT[kpi.delta_tone] ?? TONE_TEXT.muted,
          )}
        >
          {kpi.delta}
        </span>
        <Spark values={kpi.series} color={SPARK_TONE[kpi.tone] ?? "#8b7cf0"} />
      </div>
    </div>
  );
}

function Spark({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 52;
  const H = 18;
  const d = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - ((v - min) / span) * H;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-4 w-14"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth="1.4"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Filters({ data }: { data: Data }) {
  const f = data.filters;
  if (!f) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[220px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <span className="truncate text-[0.74rem] text-[var(--tessera-text-muted)]">{f.search}</span>
      </div>
      {f.selects.map((s) => (
        <button
          key={s.label}
          type="button"
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <span>{s.label}</span>
          <span className="font-medium text-[var(--tessera-text)]">{s.value}</span>
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      ))}
      <button
        type="button"
        className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        {f.more}
      </button>
    </div>
  );
}

function SessionsTable({ data }: { data: Data }) {
  const tbl = data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[840px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => (
                <th
                  key={c}
                  className={cn("px-3 py-2 font-medium", i === 0 ? "" : "whitespace-nowrap")}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tbl.rows.map((r) => (
              <tr
                key={r.sid}
                className="border-b border-[var(--tessera-border)]/60 last:border-0 hover:bg-[var(--tessera-bg)]/40"
              >
                <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[0.66rem] text-[#b9a6ff]">
                  {r.sid}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  <span className="inline-flex items-center gap-1.5 text-[0.7rem] text-[var(--tessera-text)]">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#6d4aed]/20 text-[0.52rem] font-medium text-[#b9a6ff]">
                      {initials(r.user)}
                    </span>
                    {r.user}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
                  {r.agent}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                  {r.start}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text)]">
                  {r.messages}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  <span
                    className={cn(
                      "text-[0.7rem] font-medium tabular-nums",
                      SCORE_TEXT[r.score_tone] ?? "",
                    )}
                  >
                    {r.score}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                      STATUS_BADGE[r.status_tone] ?? STATUS_BADGE.good,
                    )}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                  {r.latency}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                  {r.tokens}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        <span>{tbl.count}</span>
        <span className="flex items-center gap-1">
          {[1, 2, 3].map((n) => (
            <span
              key={n}
              className={cn(
                "flex h-6 min-w-6 items-center justify-center rounded border px-1.5",
                n === 1
                  ? "border-[#6d4aed] bg-[#6d4aed]/15 text-[var(--tessera-text)]"
                  : "border-[var(--tessera-border)]",
              )}
            >
              {n}
            </span>
          ))}
          <span className="px-1">...</span>
          <span className="flex h-6 min-w-6 items-center justify-center rounded border border-[var(--tessera-border)] px-1.5">
            {tbl.pages}
          </span>
        </span>
      </div>
    </section>
  );
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function PanelCard({
  title,
  control,
  cta,
  children,
}: { title: string; control?: string; cta?: string; children: React.ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[0.72rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
        {control ? (
          <span className="inline-flex items-center gap-1 rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[0.6rem] text-[var(--tessera-text-muted)]">
            {control} <ChevronDown className="h-3 w-3" />
          </span>
        ) : null}
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta ? (
        <button
          type="button"
          className="mt-2.5 flex items-center gap-1 self-start text-[0.64rem] text-[#b9a6ff] hover:text-white"
        >
          {cta} <ChevronRight className="h-3 w-3" />
        </button>
      ) : null}
    </section>
  );
}

function TrendCard({ data }: { data: Data }) {
  const tr = data.trend;
  if (!tr) return null;
  return (
    <PanelCard title={tr.title} control={tr.control}>
      <LineChart a={tr.series} b={tr.prev} />
      <div className="mt-2 flex flex-wrap items-center gap-3 text-[0.6rem] text-[var(--tessera-text-muted)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[#8b7cf0]" /> {tr.legend}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-slate-500" /> {tr.legend_prev}
        </span>
      </div>
    </PanelCard>
  );
}

function LineChart({ a, b }: { a: number[]; b: number[] }) {
  const all = [...a, ...b];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const W = 100;
  const H = 46;
  const path = (vals: number[]) =>
    vals
      .map((v, i) => {
        const x = (i / (vals.length - 1)) * W;
        const y = H - ((v - min) / span) * (H - 4) - 2;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-16 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={path(b)}
        fill="none"
        stroke="#64748b"
        strokeWidth="1.2"
        strokeDasharray="3 2"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={path(a)}
        fill="none"
        stroke="#8b7cf0"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ByAgent({ data }: { data: Data }) {
  const b = data.by_agent;
  if (!b) return null;
  return (
    <PanelCard title={b.title} cta={b.cta}>
      <ul className="flex flex-col gap-2">
        {b.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2 text-[0.66rem]">
              <span className="min-w-0 truncate text-[var(--tessera-text)]">{it.label}</span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {it.value} <span className="text-[0.58rem]">({it.share})</span>
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
              <div className="h-full rounded-full bg-[#8b7cf0]" style={{ width: `${it.pct}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function ScoreDonut({ data }: { data: Data }) {
  const s = data.scores;
  if (!s) return null;
  let acc = 0;
  return (
    <PanelCard title={s.title}>
      <div className="flex items-center gap-3">
        <span className="relative inline-flex h-[68px] w-[68px] shrink-0 items-center justify-center">
          <svg viewBox="0 0 36 36" className="h-[68px] w-[68px] -rotate-90" aria-hidden="true">
            <circle
              cx="18"
              cy="18"
              r="15.915"
              fill="none"
              stroke="var(--tessera-bg)"
              strokeWidth="3.4"
            />
            {s.segments.map((seg) => {
              const dash = `${seg.pct} ${100 - seg.pct}`;
              const off = -acc;
              acc += seg.pct;
              return (
                <circle
                  key={seg.label}
                  cx="18"
                  cy="18"
                  r="15.915"
                  fill="none"
                  stroke={SEG_FILL[seg.tone] ?? "#64748b"}
                  strokeWidth="3.4"
                  strokeDasharray={dash}
                  strokeDashoffset={off}
                />
              );
            })}
          </svg>
          <span className="absolute flex flex-col items-center">
            <span className="text-[0.7rem] font-semibold tabular-nums text-[var(--tessera-text)]">
              {s.center}
            </span>
            <span className="text-[0.5rem] text-[var(--tessera-text-muted)]">{s.center_label}</span>
          </span>
        </span>
        <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.62rem]">
          {s.segments.map((seg) => (
            <li key={seg.label} className="flex items-center justify-between gap-1.5">
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    SEG_DOT[seg.tone] ?? "bg-slate-400",
                  )}
                />
                <span className="truncate text-[var(--tessera-text-muted)]">{seg.label}</span>
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text)]">
                {seg.value} <span className="text-[var(--tessera-text-muted)]">({seg.share})</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </PanelCard>
  );
}

function SuccessCard({ data }: { data: Data }) {
  const s = data.success;
  if (!s) return null;
  const r = 15.915;
  const off = 100 - s.gauge;
  return (
    <PanelCard title={s.title} cta={s.cta}>
      <div className="flex flex-1 flex-col items-center justify-center gap-1">
        <span className="relative inline-flex h-[80px] w-[80px] items-center justify-center">
          <svg viewBox="0 0 36 36" className="h-[80px] w-[80px] -rotate-90" aria-hidden="true">
            <circle
              cx="18"
              cy="18"
              r={r}
              fill="none"
              stroke="var(--tessera-bg)"
              strokeWidth="3.4"
            />
            <circle
              cx="18"
              cy="18"
              r={r}
              fill="none"
              stroke="#34d399"
              strokeWidth="3.4"
              strokeLinecap="round"
              strokeDasharray={`${s.gauge} ${off}`}
            />
          </svg>
          <span className="absolute text-[0.95rem] font-semibold tabular-nums text-[var(--tessera-text)]">
            {s.value}
          </span>
        </span>
        <span className="text-[0.66rem] text-emerald-300">{s.note}</span>
      </div>
    </PanelCard>
  );
}

function Watch({ data }: { data: Data }) {
  const w = data.watch;
  if (!w) return null;
  return (
    <PanelCard title={w.title} cta={w.cta}>
      <ul className="flex flex-col gap-2.5">
        {w.items.map((it) => (
          <li key={it.title} className="flex items-start gap-2">
            <span
              className={cn(
                "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                WATCH_DOT[it.tone] ?? "bg-slate-400",
              )}
            />
            <span className="min-w-0">
              <span className="block truncate text-[0.72rem] text-[var(--tessera-text)]">
                {it.title}
              </span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {it.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function Quick({ data }: { data: Data }) {
  const q = data.quick;
  if (!q) return null;
  const icons = [BarChart3, Target, Download, Play];
  return (
    <PanelCard title={q.title}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? Play;
          return (
            <button
              key={it}
              type="button"
              className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.68rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
              <span className="min-w-0 truncate">{it}</span>
            </button>
          );
        })}
      </div>
    </PanelCard>
  );
}

function Detail({ data, className }: { data: Data; className?: string }) {
  const d = data.detail;
  const [tab, setTab] = useState(d?.tabs[0] ?? "Resume");
  if (!d) return null;
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-3">
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          Details de la session
        </p>
        <div className="mt-1 flex items-center gap-2">
          <MessagesSquare className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
          <span className="truncate font-mono text-[0.82rem] font-semibold text-[var(--tessera-text)]">
            {d.sid}
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {d.tabs.map((tb) => {
          const on = tb === tab;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(tb)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.7rem] transition-colors",
                on
                  ? "border-[#8b7cf0] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tb}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col gap-4 p-3.5">
        <ul className="flex flex-col gap-1.5 text-[0.72rem]">
          {d.fields.map((f) => (
            <li key={f.label} className="flex items-center justify-between gap-2">
              <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
              <span
                className={cn(
                  "font-medium tabular-nums",
                  f.tone === "good" ? "text-emerald-300" : "text-[var(--tessera-text)]",
                )}
              >
                {f.value}
              </span>
            </li>
          ))}
        </ul>

        <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
          <h3 className="mb-1.5 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
            {d.config_title}
          </h3>
          <div className="flex items-center justify-between gap-2 text-[0.72rem]">
            <span className="text-[var(--tessera-text)]">{d.config_value}</span>
            <span className="rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]">
              {d.config_version}
            </span>
          </div>
        </div>

        <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
          <div className="mb-2 flex items-center justify-between gap-2">
            <h3 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">
              {d.eval_title}
            </h3>
          </div>
          <ul className="flex flex-col gap-1.5 text-[0.72rem]">
            {d.eval.map((e) => (
              <li key={e.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{e.label}</span>
                <span className="tabular-nums">
                  <span
                    className={cn(
                      "font-semibold",
                      e.lead ? "text-[1rem] text-emerald-300" : "text-[var(--tessera-text)]",
                    )}
                  >
                    {e.value}
                  </span>
                  <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{e.scale}</span>
                </span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="mt-2 flex items-center gap-1 self-start text-[0.64rem] text-[#b9a6ff] hover:text-white"
          >
            {d.eval_cta} <ChevronRight className="h-3 w-3" />
          </button>
        </div>

        <div>
          <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
            {d.info_title}
          </h3>
          <ul className="flex flex-col gap-1.5 text-[0.72rem]">
            {d.info.map((it) => (
              <li key={it.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{it.label}</span>
                <span className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
                  {it.value}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
