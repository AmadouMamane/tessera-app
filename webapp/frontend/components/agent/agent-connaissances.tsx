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
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Link } from "@/i18n/navigation";
import { fetchAgentConnaissances, mutateConnaissancesSource } from "@/lib/api/client";
import type { AgentConnaissances as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import type { OverviewTone } from "@/lib/overview";
import { AgentTabs } from "./agent-tabs";

type DetailT = NonNullable<Data["details"]>[number];
type RowT = NonNullable<Data["table"]>["rows"][number];

const KPI_ICONS: LucideIcon[] = [Link2, Target, Clock, Quote, Search];
const KPI_TONE: Record<string, OverviewTone> = {
  sources: "info",
  coverage: "success",
  freshness: "neutral",
  citation: "gold",
  hitrate: "success",
};
const STATUS_TONE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  off: "border-red-500/30 bg-red-500/15 text-red-300",
};

type Status = "Tous" | "Active" | "Desactivee";
type TypeF = "Tous" | "Reglementation" | "Corpus produit";
// "Gerer le catalogue" -> the signal catalogue; "Sources & memoire" -> the memory page.
const CATALOG_HREF = "/configurer/signal-catalog" as const;
const MEMORY_HREF = "/configurer/sources-memoire" as const;
type NavHref = typeof CATALOG_HREF | typeof MEMORY_HREF;

const STATUS_OPTS: { value: Status; label: string }[] = [
  { value: "Tous", label: "Tous" },
  { value: "Active", label: "Active" },
  { value: "Desactivee", label: "Desactivee" },
];
const TYPE_OPTS: { value: TypeF; label: string }[] = [
  { value: "Tous", label: "Tous" },
  { value: "Reglementation", label: "Reglementation" },
  { value: "Corpus produit", label: "Corpus produit" },
];
const PERIOD_OPTS = [
  { value: "30", label: "30 derniers jours" },
  { value: "7", label: "7 derniers jours" },
  { value: "0", label: "Aujourd'hui" },
  { value: "99999", label: "Tout" },
];

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
  const [typeF, setTypeF] = useState<TypeF>("Tous");
  const [period, setPeriod] = useState("30");
  const [selected, setSelected] = useState<string | null>(null);
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
  const details = data.details ?? [];
  const detail = details.find((d) => d.key === selected);
  const periodDays = Number(period);
  const q = search.trim().toLowerCase();
  const allRows = data.table?.rows ?? [];
  const rows = allRows.filter(
    (r) =>
      (status === "Tous" || r.status === status) &&
      (typeF === "Tous" || r.type === typeF) &&
      (r.fresh_days ?? 0) <= periodDays &&
      (q === "" || r.name.toLowerCase().includes(q) || r.type.toLowerCase().includes(q)),
  );

  return (
    <div className="relative flex flex-col gap-3 overflow-hidden pb-2 text-[var(--tessera-text)]">
      <AgentTabs
        actions={
          <>
            <GhostLink href={CATALOG_HREF} label={a?.manage ?? ""} />
            <GhostLink href={MEMORY_HREF} label={a?.memory ?? ""} />
            <AttachMenu
              label={a?.attach ?? ""}
              items={data.attachable ?? []}
              pending={mut.isPending}
              onAttach={(key) => mut.mutate({ key, attached: true })}
            />
          </>
        }
      />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Link2} />
        ))}
      </div>

      <div className="flex min-w-0 flex-col gap-2.5">
        <Filters
          data={data}
          search={search}
          setSearch={setSearch}
          status={status}
          setStatus={setStatus}
          typeF={typeF}
          setTypeF={setTypeF}
          period={period}
          setPeriod={setPeriod}
        />
        <SourcesTable
          data={data}
          rows={rows}
          total={allRows.length}
          selected={selected}
          onSelect={setSelected}
        />
      </div>

      {detail ? (
        <DetailDrawer
          key={detail.key}
          detail={detail}
          pending={mut.isPending}
          onClose={() => setSelected(null)}
          onDetach={(key) => mut.mutate({ key, attached: false })}
          onToggle={(key, active) => mut.mutate({ key, active })}
        />
      ) : null}
    </div>
  );
}

function GhostLink({ href, label }: { href: NavHref; label: string }) {
  return (
    <Link
      href={href}
      className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
    >
      {label}
    </Link>
  );
}

function AttachMenu({
  label,
  items,
  pending,
  onAttach,
}: {
  label: string;
  items: { key: string; name: string; type: string }[];
  pending: boolean;
  onAttach: (key: string) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        disabled={pending}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 items-center gap-2 rounded-md border border-[#d98b1f] bg-[#e0a23a] px-3 text-xs font-medium text-[#1b1402] hover:bg-[#eab44e] disabled:opacity-60"
      >
        <Plus className="h-4 w-4" /> {label}
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-1 w-72 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg">
          {items.length === 0 ? (
            <p className="px-2 py-2 text-[0.72rem] text-[var(--tessera-text-muted)]">
              Toutes les sources du catalogue sont rattachees.
            </p>
          ) : (
            items.map((it) => (
              <button
                key={it.key}
                type="button"
                disabled={pending}
                onClick={() => {
                  onAttach(it.key);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-[0.72rem] text-[var(--tessera-text)] hover:bg-[var(--tessera-bg)] disabled:opacity-60"
              >
                <span className="truncate">{it.name}</span>
                <span className="shrink-0 text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {it.type}
                </span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[112px] flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-[#e0a23a]/30 bg-[#e0a23a]/10 text-[#e0a23a]">
          <Icon className="h-3.5 w-3.5" />
        </span>
        <span className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </span>
      </div>
      <p className="mt-1.5 text-[1.5rem] font-semibold leading-none tabular-nums text-white">
        {kpi.value}
      </p>
      <div className="mt-auto pt-1">
        <MetricSparkline values={kpi.series} tone={KPI_TONE[kpi.key] ?? "info"} height={30} />
      </div>
    </div>
  );
}

function FilterDropdown({
  label,
  value,
  options,
  onSelect,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onSelect: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value)?.label ?? value;
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] hover:border-[var(--tessera-text-muted)]"
      >
        <span className="text-[var(--tessera-text-muted)]">{label}</span>
        <span className="font-medium text-[var(--tessera-text)]">{current}</span>
        <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg">
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => {
                onSelect(o.value);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[0.72rem] hover:bg-[var(--tessera-bg)]",
                o.value === value
                  ? "text-[var(--tessera-text)]"
                  : "text-[var(--tessera-text-muted)]",
              )}
            >
              {o.label}
              {o.value === value ? <span className="text-[#5fd0c6]">&bull;</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Filters({
  data,
  search,
  setSearch,
  status,
  setStatus,
  typeF,
  setTypeF,
  period,
  setPeriod,
}: {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  status: Status;
  setStatus: (v: Status) => void;
  typeF: TypeF;
  setTypeF: (v: TypeF) => void;
  period: string;
  setPeriod: (v: string) => void;
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
      <FilterDropdown
        label="Statut"
        value={status}
        options={STATUS_OPTS}
        onSelect={(v) => setStatus(v as Status)}
      />
      <FilterDropdown
        label="Type"
        value={typeF}
        options={TYPE_OPTS}
        onSelect={(v) => setTypeF(v as TypeF)}
      />
      <FilterDropdown label="Periode" value={period} options={PERIOD_OPTS} onSelect={setPeriod} />
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
  rows,
  total,
  selected,
  onSelect,
}: {
  data: Data;
  rows: RowT[];
  total: number;
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const tbl = data.table;
  if (!tbl) return null;
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
                onClick={() => r.key && onSelect(r.key)}
                className={cn(
                  "cursor-pointer border-b border-[var(--tessera-border)]/60 last:border-0",
                  r.key && r.key === selected
                    ? "bg-[var(--tessera-bg)]/70"
                    : "hover:bg-[var(--tessera-bg)]/40",
                )}
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
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length}
                  className="px-3 py-6 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  Aucune source ne correspond aux filtres.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="border-t border-[var(--tessera-border)] px-3 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {rows.length === total ? tbl.count : `${rows.length} sur ${total} sources`}
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

function DetailDrawer({
  detail,
  pending,
  onClose,
  onDetach,
  onToggle,
}: {
  detail: DetailT;
  pending: boolean;
  onClose: () => void;
  onDetach: (key: string) => void;
  onToggle: (key: string, active: boolean) => void;
}) {
  return (
    <div
      className="absolute inset-0 z-30 flex justify-end overflow-hidden rounded-lg bg-[#020817]/70 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <DetailPanel
        detail={detail}
        pending={pending}
        onClose={onClose}
        onDetach={onDetach}
        onToggle={onToggle}
      />
    </div>
  );
}

function DetailPanel({
  detail,
  pending,
  onClose,
  onDetach,
  onToggle,
}: {
  detail: DetailT;
  pending: boolean;
  onClose: () => void;
  onDetach: (key: string) => void;
  onToggle: (key: string, active: boolean) => void;
}) {
  const tCommon = useTranslations("common");
  const [tab, setTab] = useState(detail.tabs[0] ?? "Usage");
  const d = detail;
  const key = d.key;
  return (
    <dialog
      open
      aria-modal="true"
      aria-label={d.name}
      className="static m-0 flex h-full w-full max-w-[460px] flex-col overflow-hidden border-0 border-l border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-0 text-[var(--tessera-text)] shadow-[-24px_0_60px_rgba(0,0,0,0.35)]"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--tessera-border)] px-3.5 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
            <FileGlyph />
          </span>
          <span className="truncate text-[0.85rem] font-semibold text-[var(--tessera-text)]">
            {d.name}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
              STATUS_TONE[d.status_tone] ?? STATUS_TONE.good,
            )}
          >
            {d.status}
          </span>
          <button
            type="button"
            aria-label={tCommon("close")}
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-bg)] hover:text-[var(--tessera-text)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <nav className="flex shrink-0 items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
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

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-3.5">
        {tab === d.tabs[0] ? (
          <>
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
          </>
        ) : null}

        {tab === d.tabs[1] ? (
          <div>
            <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.answers_title}
            </h3>
            {d.answers.length === 0 ? (
              <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
                Aucune reponse ancree pour le moment.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {d.answers.map((ans) => (
                  <li key={ans.text} className="flex items-start gap-2">
                    <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[0.72rem] text-[var(--tessera-text)]">
                        {ans.text}
                      </span>
                      <span className="block text-[0.62rem] text-[var(--tessera-text-muted)]">
                        {ans.time}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}

        {tab === d.tabs[2] ? (
          <div>
            <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.params_title ?? "Parametres"}
            </h3>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {(d.params ?? []).map((p) => (
                <li key={p.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{p.label}</span>
                  <span className="font-medium text-[var(--tessera-text)]">{p.value}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

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
          <Link
            href={MEMORY_HREF}
            className="mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[#b9a6ff] hover:text-white"
          >
            {d.full_sheet}
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </dialog>
  );
}
