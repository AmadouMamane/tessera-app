"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Link2,
  type LucideIcon,
  Plus,
  Quote,
  Search,
  SlidersHorizontal,
  Target,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { fetchAgentConnaissances, mutateConnaissancesSource } from "@/lib/api/client";
import type { AgentConnaissances as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { AgentTabs } from "./agent-tabs";

const KPI_ICONS: LucideIcon[] = [Link2, Target, Clock, Quote, Search];
const STATUS_TONE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  off: "border-red-500/30 bg-red-500/15 text-red-300",
};

type Status = "Tous" | "Active" | "Desactivee";

export function AgentConnaissances() {
  const t = useTranslations("agentConnaissances");
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["agent-connaissances"],
    queryFn: ({ signal }) => fetchAgentConnaissances(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<Status>("Tous");
  const mut = useMutation({
    mutationFn: mutateConnaissancesSource,
    onSuccess: (fresh) => qc.setQueryData(["agent-connaissances"], fresh),
  });

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  const a = data.actions;
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <AgentTabs
        actions={
          <>
            <GhostBtn label={a?.manage ?? ""} />
            <GhostBtn label={a?.memory ?? ""} />
            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md border border-[#d98b1f] bg-[#e0a23a] px-3 text-xs font-medium text-[#1b1402] hover:bg-[#eab44e]"
            >
              <Plus className="h-4 w-4" /> {a?.attach}
            </button>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Link2} />
        ))}
      </div>

      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
          <Filters
            data={data}
            search={search}
            setSearch={setSearch}
            status={status}
            setStatus={setStatus}
          />
          <SourcesTable data={data} search={search} status={status} />
        </div>
        <Detail
          data={data}
          className="xl:col-span-4"
          pending={mut.isPending}
          onDetach={(key) => mut.mutate({ key, attached: false })}
          onToggle={(key, active) => mut.mutate({ key, active })}
        />
      </div>
    </div>
  );
}

function GhostBtn({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
    >
      {label}
    </button>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[88px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-md border border-[#e0a23a]/30 bg-[#e0a23a]/10 text-[#e0a23a]">
          <Icon className="h-3.5 w-3.5" />
        </span>
        <span className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </span>
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className="text-[1.4rem] font-semibold tabular-nums text-[var(--tessera-text)]">
          {kpi.value}
        </span>
        <Spark values={kpi.series} />
      </div>
    </div>
  );
}

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 56;
  const H = 20;
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
      className="h-5 w-14"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={d}
        fill="none"
        stroke="#5fd0c6"
        strokeWidth="1.4"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const STATUS_CYCLE: Record<Status, Status> = {
  Tous: "Active",
  Active: "Desactivee",
  Desactivee: "Tous",
};
const STATUS_LABEL: Record<Status, string> = {
  Tous: "Tous",
  Active: "Active",
  Desactivee: "Desactivee",
};

function Filters({
  data,
  search,
  setSearch,
  status,
  setStatus,
}: {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  status: Status;
  setStatus: (v: Status) => void;
}) {
  const f = data.filters;
  if (!f) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[220px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={f.search}
          className="min-w-0 flex-1 bg-transparent text-[0.74rem] text-[var(--tessera-text)] placeholder:text-[var(--tessera-text-muted)] focus:outline-none"
        />
      </div>
      <button
        type="button"
        onClick={() => setStatus(STATUS_CYCLE[status])}
        className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        <span className="text-[var(--tessera-text-muted)]">Statut</span>
        <span className="font-medium text-[var(--tessera-text)]">{STATUS_LABEL[status]}</span>
        <ChevronDown className="h-3.5 w-3.5" />
      </button>
      {f.selects.slice(1).map((s) => (
        <button
          key={s.label}
          type="button"
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <span className="text-[var(--tessera-text-muted)]">{s.label}</span>
          <span className="font-medium text-[var(--tessera-text)]">{s.value}</span>
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      ))}
      <button
        type="button"
        className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        <SlidersHorizontal className="h-3.5 w-3.5" /> {f.more}
      </button>
    </div>
  );
}

function SourcesTable({
  data,
  search,
  status,
}: {
  data: Data;
  search: string;
  status: Status;
}) {
  const tbl = data.table;
  if (!tbl) return null;
  const q = search.trim().toLowerCase();
  const rows = tbl.rows.filter(
    (r) =>
      (status === "Tous" || r.status === status) &&
      (q === "" || r.name.toLowerCase().includes(q) || r.type.toLowerCase().includes(q)),
  );
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.64rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
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
            {rows.map((r) => (
              <tr
                key={r.name}
                className="border-b border-[var(--tessera-border)]/60 last:border-0 hover:bg-[var(--tessera-bg)]/40"
              >
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                      <FileGlyph />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[0.76rem] font-medium text-[var(--tessera-text)]">
                        {r.name}
                      </span>
                      <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                        {r.path}
                      </span>
                    </span>
                  </div>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.72rem] text-[var(--tessera-text-muted)]">
                  {r.type}
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
                      STATUS_TONE[r.status_tone] ?? STATUS_TONE.good,
                    )}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  {r.coverage === null ? (
                    <span className="text-[0.72rem] text-[var(--tessera-text-muted)]">-</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="w-9 shrink-0 text-[0.72rem] tabular-nums text-[var(--tessera-text)]">
                        {r.coverage}%
                      </span>
                      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-[var(--tessera-bg)] sm:block">
                        <span
                          className="block h-full rounded-full bg-[#5fd0c6]"
                          style={{ width: `${r.coverage}%` }}
                        />
                      </span>
                    </div>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.72rem] text-[var(--tessera-text-muted)]">
                  {r.freshness}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.72rem] tabular-nums text-[var(--tessera-text)]">
                  {r.citation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-[var(--tessera-border)] px-3 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {rows.length === tbl.rows.length
          ? tbl.count
          : `${rows.length} sur ${tbl.rows.length} sources`}
      </div>
    </section>
  );
}

function FileGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M14 2v6h6" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

function Detail({
  data,
  className,
  pending,
  onDetach,
  onToggle,
}: {
  data: Data;
  className?: string;
  pending: boolean;
  onDetach: (key: string) => void;
  onToggle: (key: string, active: boolean) => void;
}) {
  const d = data.detail;
  const [tab, setTab] = useState(d?.tabs[0] ?? "Usage");
  if (!d) return null;
  const key = d.key;
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)] px-3.5 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
            <FileGlyph />
          </span>
          <span className="truncate text-[0.85rem] font-semibold text-[var(--tessera-text)]">
            {d.name}
          </span>
        </div>
        <span
          className={cn(
            "shrink-0 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            STATUS_TONE[d.status_tone] ?? STATUS_TONE.good,
          )}
        >
          {d.status}
        </span>
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
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
                on
                  ? "border-[#5fd0c6] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tb}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col gap-4 p-3.5">
        <div>
          <h3 className="mb-1 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
            {d.summary_title}
          </h3>
          <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {d.summary}
          </p>
        </div>

        <div>
          <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
            {d.usage_title}
          </h3>
          <ul className="flex flex-col gap-1.5 text-[0.72rem]">
            {d.usage.map((u) => (
              <li key={u.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{u.label}</span>
                <span className="font-medium tabular-nums text-[var(--tessera-text)]">
                  {u.value}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
            {d.answers_title}
          </h3>
          <ul className="flex flex-col gap-2">
            {d.answers.map((ans) => (
              <li key={ans.text} className="flex items-start gap-2">
                <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[0.72rem] text-[var(--tessera-text)]">
                    {ans.text}
                  </span>
                  <span className="block text-[0.62rem] text-[var(--tessera-text-muted)]">
                    {ans.time}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
            {d.actions_title}
          </h3>
          <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2">
            <span className="text-[0.72rem] text-[var(--tessera-text)]">{d.toggle_label}</span>
            <button
              type="button"
              disabled={pending || !key}
              aria-pressed={d.toggle_on}
              onClick={() => key && onToggle(key, !d.toggle_on)}
              className={cn(
                "flex h-4 w-8 items-center rounded-full px-0.5 transition-colors disabled:opacity-60",
                d.toggle_on ? "justify-end bg-emerald-500" : "justify-start bg-slate-600",
              )}
            >
              <span className="h-3 w-3 rounded-full bg-white" />
            </button>
          </div>
          <button
            type="button"
            disabled={pending || !key}
            onClick={() => key && onDetach(key)}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-red-500/40 bg-red-500/5 px-3 py-2 text-[0.72rem] font-medium text-red-300 hover:bg-red-500/10 disabled:opacity-60"
          >
            {d.detach}
          </button>
          <button
            type="button"
            className="mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[#b9a6ff] hover:text-white"
          >
            {d.full_sheet}
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </section>
  );
}
