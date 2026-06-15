"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  FileSignature,
  Layers,
  type LucideIcon,
  PlusCircle,
  Search,
  StickyNote,
  UserPlus,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { fetchAgentAFaire } from "@/lib/api/client";
import type { AgentAFaire as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const SPARK: Record<string, string> = {
  red: "#f87171",
  teal: "#34d399",
  amber: "#e0a23a",
  green: "#34d399",
};
const PRIO_TONE: Record<string, string> = {
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
  high: "border-orange-500/30 bg-orange-500/15 text-orange-300",
  mod: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  low: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const STATUS_TONE: Record<string, string> = {
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
  todo: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  progress: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  done: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const SLA_TONE: Record<string, string> = {
  crit: "text-red-300",
  warn: "text-amber-300",
  ok: "text-emerald-300",
};
const EVENT_DOT: Record<string, string> = {
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
  crit: "bg-red-400",
};

export function AgentAFaire() {
  const t = useTranslations("agentAFaire");
  const { data } = useQuery({
    queryKey: ["agent-a-faire"],
    queryFn: ({ signal }) => fetchAgentAFaire(signal),
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

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <Rail data={data} />
      <Timeline data={data} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-8">
        {(data.kpis ?? []).map((k) => (
          <Kpi key={k.key} kpi={k} />
        ))}
      </div>

      <div className="grid min-w-0 gap-2.5 xl:grid-cols-[200px_minmax(0,1fr)]">
        <Filters data={data} />
        <div className="flex min-w-0 flex-col gap-2.5">
          <div className="grid min-w-0 gap-2.5 xl:grid-cols-[minmax(0,1fr)_minmax(0,440px)]">
            <TaskTable data={data} />
            <aside className="flex min-w-0 flex-col gap-2.5">
              <Donut data={data} />
              <Sla data={data} />
              <Quick data={data} />
              <Activity data={data} />
            </aside>
          </div>
          <DetailBand data={data} />
        </div>
      </div>

      <Footer data={data} />
    </div>
  );
}

function Rail({ data }: { data: Data }) {
  const r = data.rail;
  if (!r) return null;
  return (
    <section className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-[#5b4bbd]/40 bg-[var(--tessera-surface)] px-3.5 py-2 text-xs">
      <span className="flex items-center gap-1.5 font-medium text-emerald-300">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" /> {r.live}
      </span>
      {r.segments.map((s) => (
        <span key={s} className="flex items-center gap-3 text-[var(--tessera-text-muted)]">
          <span className="text-[var(--tessera-border-strong)]">·</span> {s}
        </span>
      ))}
      <span className="ml-auto flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[var(--tessera-text-muted)]">
        {r.period} <ChevronDown className="h-3.5 w-3.5" />
      </span>
      <span className="tabular-nums text-[var(--tessera-text)]">{r.updated}</span>
      <span className="flex items-center gap-1 text-emerald-300">
        <ArrowUpRight className="h-3.5 w-3.5" /> {r.now}
      </span>
      <span className="flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[var(--tessera-text-muted)]">
        {r.scope} <ChevronDown className="h-3.5 w-3.5" />
      </span>
      <button
        type="button"
        className="flex h-8 items-center gap-1.5 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/60 px-3 text-[#c4b5fd] hover:bg-[#4c3fb0]/80"
      >
        <Layers className="h-3.5 w-3.5" /> {r.bulk}
      </button>
    </section>
  );
}

function Timeline({ data }: { data: Data }) {
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <section className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-2">
      <span className="text-[0.6rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {tl.title}
      </span>
      {tl.events.map((e) => (
        <span key={`${e.time}-${e.ref}`} className="flex items-center gap-2">
          <span className={cn("h-1.5 w-1.5 rounded-full", EVENT_DOT[e.tone] ?? "bg-slate-400")} />
          <span className="text-[0.68rem]">
            <span className="tabular-nums text-[var(--tessera-text-muted)]">{e.time}</span>{" "}
            <span className="text-[var(--tessera-text)]">{e.label}</span>{" "}
            <span className="font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
              {e.ref}
            </span>
          </span>
        </span>
      ))}
      <button
        type="button"
        className="ml-auto flex items-center gap-1 text-[0.66rem] text-[#87bfff] hover:text-[#a9d2ff]"
      >
        {tl.cta} <ChevronRight className="h-3 w-3" />
      </button>
    </section>
  );
}

function Kpi({ kpi }: { kpi: NonNullable<Data["kpis"]>[number] }) {
  return (
    <div className="flex h-[96px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="truncate text-[0.62rem] font-medium text-[var(--tessera-text-muted)]">
        {kpi.label}
      </p>
      <p className="mt-0.5 whitespace-nowrap text-[1.3rem] font-semibold leading-none text-white">
        {kpi.value}
      </p>
      <p
        className={cn(
          "mt-0.5 text-[0.56rem] font-medium",
          kpi.good ? "text-emerald-400" : "text-red-300",
        )}
      >
        {kpi.delta}
      </p>
      <Spark className="mt-auto" values={kpi.series} color={SPARK[kpi.tone] ?? "#8b7cf0"} />
    </div>
  );
}

function Spark({
  values,
  color,
  className,
}: { values: number[]; color: string; className?: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 80;
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
      className={cn("h-4 w-full", className)}
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
    <aside className="flex min-w-0 flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="text-[0.74rem] font-semibold text-[var(--tessera-text)]">{f.title}</h3>
      <div className="flex h-8 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <span className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">{f.search}</span>
      </div>
      <ul className="flex flex-col gap-2">
        {f.selects.map((s) => (
          <li key={s.label} className="flex flex-col gap-1">
            <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.label}</span>
            <button
              type="button"
              className="flex h-8 items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.68rem] text-[var(--tessera-text)]"
            >
              {s.value} <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="flex items-center gap-1 text-[0.64rem] text-[#87bfff] hover:text-[#a9d2ff]"
      >
        <PlusCircle className="h-3.5 w-3.5" /> {f.more}
      </button>
      <div className="border-t border-[var(--tessera-border)] pt-2.5">
        <h4 className="mb-1.5 text-[0.62rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {f.views_title}
        </h4>
        <ul className="flex flex-col gap-1">
          {f.views.map((v, i) => (
            <li key={v}>
              <button
                type="button"
                className={cn(
                  "flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[0.68rem]",
                  i === 0
                    ? "bg-[#6d4aed]/15 text-[var(--tessera-text)]"
                    : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
                )}
              >
                <Eye className="h-3 w-3 shrink-0" /> {v}
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-1.5 flex items-center gap-1 text-[0.62rem] text-[#87bfff] hover:text-[#a9d2ff]"
        >
          {f.views_cta} <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </aside>
  );
}

function TaskTable({ data }: { data: Data }) {
  const tbl = data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="border-b border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] font-medium text-[var(--tessera-text)]">
        {tbl.count}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c) => (
                <th key={c} className="whitespace-nowrap px-2.5 py-1.5 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tbl.tasks.map((it) => (
              <tr
                key={`${it.title}-${it.ref}`}
                className="cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors last:border-0 hover:bg-[var(--tessera-bg)]/50"
              >
                <td className="px-2.5 py-2">
                  <Badge className={PRIO_TONE[it.prio_tone] ?? PRIO_TONE.mod}>{it.priority}</Badge>
                </td>
                <td className="whitespace-nowrap px-2.5 py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
                  {it.type}
                </td>
                <td className="px-2.5 py-2 text-[0.7rem] text-[var(--tessera-text)]">{it.title}</td>
                <td className="whitespace-nowrap px-2.5 py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
                  {it.source} <span className="font-mono text-[0.56rem]">{it.ref}</span>
                </td>
                <td className="whitespace-nowrap px-2.5 py-2 text-[0.66rem] text-[var(--tessera-text)]">
                  {it.assignee}
                </td>
                <td
                  className={cn(
                    "whitespace-nowrap px-2.5 py-2 text-[0.66rem] font-medium tabular-nums",
                    SLA_TONE[it.sla_tone] ?? "",
                  )}
                >
                  {it.sla}
                </td>
                <td className="whitespace-nowrap px-2.5 py-2 font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">
                  {it.due}
                </td>
                <td className="px-2.5 py-2">
                  <Badge className={STATUS_TONE[it.status_tone] ?? STATUS_TONE.todo}>
                    {it.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        <span>{tbl.showing}</span>
        <span className="flex items-center gap-1">
          <ChevronRight className="h-3.5 w-3.5 rotate-180" />
          {tbl.pages.map((n, i) => (
            <span
              key={n}
              className={cn(
                "flex h-6 min-w-6 items-center justify-center rounded border px-1.5",
                i === 0
                  ? "border-[#6d4aed] bg-[#6d4aed]/15 text-[var(--tessera-text)]"
                  : "border-[var(--tessera-border)]",
              )}
            >
              {n}
            </span>
          ))}
          <ChevronRight className="h-3.5 w-3.5" />
        </span>
        <span className="flex items-center gap-1.5">
          {tbl.per_page_label}
          <span className="inline-flex items-center gap-1 rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5">
            {tbl.per_page} <ChevronDown className="h-3 w-3" />
          </span>
        </span>
      </div>
    </section>
  );
}

function DetailBand({ data }: { data: Data }) {
  const d = data.detail;
  const s = data.status;
  if (!d) return null;
  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
        {d.title}
      </div>
      <div className="grid gap-px bg-[var(--tessera-border)] lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,0.9fr)]">
        {/* selected summary */}
        <div className="flex flex-col gap-2 bg-[var(--tessera-surface)] p-3">
          <div className="flex items-center justify-between gap-2">
            <Badge className={PRIO_TONE[d.selected.prio_tone] ?? PRIO_TONE.crit}>
              {d.selected.priority}
            </Badge>
            <span className="font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
              {d.selected.id}
            </span>
          </div>
          <div>
            <p className="text-[0.76rem] font-medium text-[var(--tessera-text)]">
              {d.selected.title}
            </p>
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{d.selected.subtitle}</p>
          </div>
          <button
            type="button"
            className="mt-auto flex w-fit items-center gap-1 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/40 px-2.5 py-1.5 text-[0.66rem] text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
          >
            {d.selected.cta} <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* contexte tabs + fields */}
        <div className="flex flex-col gap-2 bg-[var(--tessera-surface)] p-3">
          <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)]">
            {d.tabs.map((tb, i) => (
              <span
                key={tb}
                className={cn(
                  "-mb-px border-b-2 py-1.5 text-[0.66rem]",
                  i === 0
                    ? "border-emerald-400 font-medium text-[var(--tessera-text)]"
                    : "border-transparent text-[var(--tessera-text-muted)]",
                )}
              >
                {tb}
              </span>
            ))}
          </nav>
          <ul className="flex flex-col gap-1 text-[0.66rem]">
            {d.context.map((c) => (
              <li key={c.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{c.label}</span>
                <span className="min-w-0 truncate text-[var(--tessera-text)]">{c.value}</span>
              </li>
            ))}
          </ul>
          <div>
            <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{d.summary_label}</p>
            <p className="text-[0.66rem] leading-snug text-[var(--tessera-text)]">{d.summary}</p>
          </div>
        </div>

        {/* echeance & sla */}
        <div className="flex flex-col gap-2 bg-[var(--tessera-surface)] p-3">
          <h4 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">{d.sla_title}</h4>
          <div>
            <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">SLA</p>
            <p className="text-[0.9rem] font-semibold tabular-nums text-red-300">{d.sla_value}</p>
            <p className="text-[0.58rem] text-red-300">{d.sla_note}</p>
          </div>
          <ul className="flex flex-col gap-1 text-[0.66rem]">
            {d.sla_rows.map((r) => (
              <li key={r.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{r.label}</span>
                <span className="tabular-nums text-[var(--tessera-text)]">{r.value}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* assignation */}
        <div className="flex flex-col gap-2 bg-[var(--tessera-surface)] p-3">
          <h4 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">
            {d.assign_title}
          </h4>
          <div>
            <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{d.assign_label}</p>
            <span className="mt-0.5 inline-flex items-center gap-1.5 text-[0.7rem] text-[var(--tessera-text)]">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#6d4aed]/20 text-[0.5rem] font-medium text-[#b9a6ff]">
                {d.assignee
                  .split(" ")
                  .map((p) => p[0] ?? "")
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </span>
              {d.assignee}
            </span>
          </div>
          <div>
            <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{d.team_label}</p>
            <p className="text-[0.7rem] text-[var(--tessera-text)]">{d.team}</p>
          </div>
          <button
            type="button"
            className="mt-auto flex items-center justify-center gap-1 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/40 px-2.5 py-1.5 text-[0.66rem] text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
          >
            {d.reassign}
          </button>
        </div>

        {/* statut & actions */}
        <div className="flex flex-col gap-2 bg-[var(--tessera-surface)] p-3">
          {s ? (
            <>
              <h4 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">{s.title}</h4>
              <div>
                <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.label}</p>
                <button
                  type="button"
                  className="mt-0.5 flex h-8 w-full items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.68rem] text-[var(--tessera-text)]"
                >
                  {s.value} <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
                </button>
              </div>
              <button
                type="button"
                className="mt-auto flex h-9 items-center justify-center rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-[0.7rem] font-medium text-white hover:bg-[#7c5cf5]"
              >
                {s.primary}
              </button>
              <button
                type="button"
                className="flex h-8 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
              >
                {s.secondary}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function Panel({ title, cta, children }: { title: string; cta?: string; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[0.74rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
        {cta ? (
          <button
            type="button"
            className="flex items-center gap-0.5 text-[0.62rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]"
          >
            {cta} <ChevronRight className="h-3 w-3" />
          </button>
        ) : null}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

function Donut({ data }: { data: Data }) {
  const d = data.donut;
  if (!d) return null;
  const sum = d.segments.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <Panel title={d.title} cta={d.cta}>
      <div className="flex items-center gap-3">
        <div className="relative h-[92px] w-[92px] shrink-0">
          <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle cx="36" cy="36" r={R} fill="none" stroke="var(--tessera-bg)" strokeWidth="9" />
            {d.segments.map((s) => {
              const frac = s.count / sum;
              const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
              off += frac;
              return (
                <circle
                  key={s.label}
                  cx="36"
                  cy="36"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="9"
                  strokeDasharray={`${seg.dash} ${seg.gap}`}
                  strokeDashoffset={seg.o}
                />
              );
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-base font-semibold tabular-nums text-white">{d.center}</span>
            <span className="text-[0.46rem] uppercase text-[var(--tessera-text-muted)]">
              {d.center_label}
            </span>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.62rem]">
          {d.segments.map((s) => (
            <li key={s.label} className="flex items-center gap-1.5">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{s.label}</span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {s.count} ({s.share})
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function Sla({ data }: { data: Data }) {
  const s = data.sla;
  if (!s) return null;
  const max = Math.max(...s.buckets.map((b) => b.count), 1);
  return (
    <Panel title={s.title} cta={s.cta}>
      <ul className="flex flex-col gap-2">
        {s.buckets.map((b) => (
          <li key={b.label} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-16 shrink-0 text-[var(--tessera-text)]">{b.label}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(b.count / max) * 100}%`, background: b.color }}
              />
            </div>
            <span className="w-5 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {b.count}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Quick({ data }: { data: Data }) {
  const q = data.quick;
  if (!q) return null;
  const icons: LucideIcon[] = [
    ArrowUpRight,
    UserPlus,
    StickyNote,
    CheckCircle2,
    PlusCircle,
    FileSignature,
  ];
  return (
    <Panel title={q.title}>
      <div className="grid grid-cols-3 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? ArrowUpRight;
          return (
            <button
              key={it}
              type="button"
              className="flex flex-col items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-2 text-center text-[0.6rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 text-[#b9a6ff]" />
              <span className="min-w-0 truncate">{it}</span>
            </button>
          );
        })}
      </div>
    </Panel>
  );
}

function Activity({ data }: { data: Data }) {
  const a = data.activity;
  if (!a) return null;
  return (
    <Panel title={a.title} cta={a.cta}>
      <ul className="flex flex-col gap-1.5">
        {a.items.map((it) => (
          <li key={`${it.time}-${it.action}`} className="flex items-center gap-2 text-[0.64rem]">
            <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-400" />
            <span className="shrink-0 font-medium text-[var(--tessera-text)]">{it.actor}</span>
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
              {it.action}
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {it.time}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.56rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function Footer({ data }: { data: Data }) {
  const f = data.footer;
  if (!f) return null;
  return (
    <footer className="mt-1 flex flex-wrap items-center gap-x-3 border-t border-[var(--tessera-border)] pt-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
      <span>{f.check}</span>
      <span className="inline-flex items-center gap-1 text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" /> {f.status}
      </span>
    </footer>
  );
}
