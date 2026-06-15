"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Boxes,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  FileCode2,
  FlaskConical,
  type LucideIcon,
  Plus,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { fetchAgentPrompts } from "@/lib/api/client";
import type { AgentPrompts as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { AgentSubtabs } from "./agent-subtabs";
import { AgentTabs } from "./agent-tabs";

const KPI_ICONS: LucideIcon[] = [
  FileCode2,
  Boxes,
  FlaskConical,
  FlaskConical,
  FlaskConical,
  FlaskConical,
];
const TYPE_TONE: Record<string, string> = {
  sys: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  tpl: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  agt: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  fct: "border-amber-500/30 bg-amber-500/15 text-amber-300",
};
const STATUS_TONE: Record<string, string> = {
  good: "text-emerald-300",
  off: "text-[var(--tessera-text-muted)]",
};
const QUALITY_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  warn: "bg-amber-400",
  mut: "bg-slate-500",
};
const WATCH_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  crit: "bg-red-400",
};
const COV_BAR: Record<string, string> = {
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
};

export function AgentPrompts() {
  const t = useTranslations("agentPrompts");
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const [subtab, setSubtab] = useState("");
  const { data } = useQuery({
    queryKey: ["agent-prompts"],
    queryFn: ({ signal }) => fetchAgentPrompts(signal),
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
              <CalendarClock className="h-4 w-4" /> {a?.asof}
            </button>
            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5]"
            >
              <Plus className="h-4 w-4" /> {a?.create}
            </button>
          </>
        }
      />

      <AgentSubtabs tabs={subtabs} active={active} onSelect={setSubtab} />

      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        onModeChange={temporal.changeMode}
      />

      <Snapshot data={data} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? FileCode2} />
        ))}
      </div>

      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
          <Filters data={data} />
          <PromptsTable data={data} />
          <div className="grid gap-2.5 md:grid-cols-3">
            <Watch data={data} />
            <Quick data={data} />
            <ByType data={data} />
          </div>
        </div>
        <Detail data={data} className="xl:col-span-4" />
      </div>

      <Footer data={data} />
    </div>
  );
}

function Snapshot({ data }: { data: Data }) {
  const s = data.snapshot;
  if (!s) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-x-7 gap-y-2">
        <Field>
          <span className="text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {s.tag}
          </span>
          <span className="text-[0.92rem] font-semibold text-[var(--tessera-text)]">{s.label}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.updated_label}</span>
          <span className="text-[0.82rem] font-medium tabular-nums text-[var(--tessera-text)]">
            {s.updated}
          </span>
          <span className="text-[0.58rem] text-[var(--tessera-text-muted)]">{s.updated_rel}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.version_label}</span>
          <span className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{s.version}</span>
          <span className="text-[0.58rem] text-emerald-300">{s.version_status}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.evalset_label}</span>
          <span className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{s.evalset}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.coverage_label}</span>
          <span className="flex items-center gap-2">
            <Gauge pct={s.coverage} />
            <span className="text-[0.7rem] text-emerald-300">{s.coverage_tone}</span>
          </span>
        </Field>
      </div>
      <div className="flex flex-col items-start gap-1 text-[0.68rem]">
        <button
          type="button"
          className="inline-flex items-center gap-1 text-[#b9a6ff] hover:text-white"
        >
          <ChevronRight className="h-3.5 w-3.5" /> {s.compare}
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <CalendarClock className="h-3.5 w-3.5" /> {s.asof}
        </button>
      </div>
    </div>
  );
}

function Field({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-0.5">{children}</div>;
}

function Gauge({ pct }: { pct: number }) {
  const r = 11;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <span className="relative inline-flex h-8 w-8 items-center justify-center">
      <svg viewBox="0 0 28 28" className="h-8 w-8 -rotate-90" aria-hidden="true">
        <circle cx="14" cy="14" r={r} fill="none" stroke="var(--tessera-border)" strokeWidth="3" />
        <circle
          cx="14"
          cy="14"
          r={r}
          fill="none"
          stroke="#34d399"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={off}
        />
      </svg>
      <span className="absolute text-[0.52rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {pct}%
      </span>
    </span>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[88px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <span className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </span>
      </div>
      {kpi.gauge !== null ? (
        <div className="flex items-center gap-2">
          <Gauge pct={kpi.gauge} />
          <span className="text-[0.78rem] font-medium text-emerald-300">{kpi.value}</span>
        </div>
      ) : (
        <div>
          <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text)]">
            {kpi.value}
          </p>
          {kpi.delta ? (
            <p
              className={cn(
                "text-[0.6rem] tabular-nums",
                kpi.good ? "text-emerald-400" : "text-red-400",
              )}
            >
              {kpi.delta}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}

function Filters({ data }: { data: Data }) {
  const f = data.filters;
  if (!f) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[200px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
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
        <SlidersHorizontal className="h-3.5 w-3.5" /> {f.more}
      </button>
    </div>
  );
}

function PromptsTable({ data }: { data: Data }) {
  const tbl = data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
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
                key={r.name}
                className="border-b border-[var(--tessera-border)]/60 last:border-0 hover:bg-[var(--tessera-bg)]/40"
              >
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <FileCode2 className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
                    <span className="truncate text-[0.74rem] font-medium text-[var(--tessera-text)]">
                      {r.name}
                    </span>
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                      TYPE_TONE[r.type_tone] ?? TYPE_TONE.tpl,
                    )}
                  >
                    {r.type}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 text-[0.68rem]",
                      STATUS_TONE[r.status_tone] ?? STATUS_TONE.good,
                    )}
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        r.status_tone === "good" ? "bg-emerald-400" : "bg-slate-500",
                      )}
                    />
                    {r.status}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] tabular-nums text-[var(--tessera-text)]">
                  {r.version}
                </td>
                <td className="px-3 py-2.5">
                  <span className="inline-flex items-center gap-1.5 text-[0.7rem] tabular-nums text-[var(--tessera-text)]">
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        QUALITY_DOT[r.quality_tone] ?? "bg-slate-400",
                      )}
                    />
                    {r.quality === "-" ? "-" : `${r.quality} / 10`}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)]">
                  {r.updated}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] text-[var(--tessera-text)]">
                  {r.owner}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)]">
                  {r.tests}
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

function PanelCard({
  title,
  cta,
  children,
}: { title: string; cta?: string; children: React.ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="mb-2 text-[0.74rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta ? (
        <button
          type="button"
          className="mt-2.5 flex items-center gap-1 self-start text-[0.66rem] text-[#b9a6ff] hover:text-white"
        >
          {cta} <ChevronRight className="h-3.5 w-3.5" />
        </button>
      ) : null}
    </section>
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
  const icons = [FlaskConical, Copy, Plus, Code2];
  return (
    <PanelCard title={q.title}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? FlaskConical;
          return (
            <button
              key={it}
              type="button"
              className="flex flex-col items-start gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.68rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 text-[#b9a6ff]" />
              <span className="min-w-0 truncate">{it}</span>
            </button>
          );
        })}
      </div>
    </PanelCard>
  );
}

function ByType({ data }: { data: Data }) {
  const b = data.by_type;
  if (!b) return null;
  return (
    <PanelCard title={b.title} cta={b.cta}>
      <ul className="flex flex-col gap-2.5">
        {b.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.7rem]">
              <span className="text-[var(--tessera-text)]">{it.label}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.value} / 10</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
              <div
                className={cn("h-full rounded-full", COV_BAR[it.tone] ?? "bg-slate-500")}
                style={{ width: `${it.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
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
          Details du prompt
        </p>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode2 className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
            <span className="min-w-0">
              <span className="block truncate text-[0.85rem] font-semibold text-[var(--tessera-text)]">
                {d.name}
              </span>
              <span className="block truncate font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                {d.id}
              </span>
            </span>
          </div>
          <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.6rem] font-medium text-emerald-300">
            {d.status}
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
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
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
        <div>
          <h3 className="mb-1 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
            Description
          </h3>
          <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {d.description}
          </p>
        </div>

        <ul className="flex flex-col gap-1.5 text-[0.72rem]">
          {d.fields.map((f) => (
            <li key={f.label} className="flex items-center justify-between gap-2">
              <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
              <span
                className={cn(
                  "font-medium",
                  f.tone === "good" ? "text-emerald-300" : "text-[var(--tessera-text)]",
                )}
              >
                {f.value}
              </span>
            </li>
          ))}
        </ul>

        <div>
          <p className="mb-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">{d.tags_label}</p>
          <div className="flex flex-wrap gap-1.5">
            {d.tags.map((tg) => (
              <span
                key={tg}
                className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
                {tg}
              </span>
            ))}
          </div>
        </div>

        <DetailBlock title={d.config_title} cta={d.config_cta}>
          <ul className="flex flex-col gap-1.5 text-[0.72rem]">
            {d.config.map((c) => (
              <li key={c.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{c.label}</span>
                <span className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
                  {c.value}
                </span>
              </li>
            ))}
          </ul>
        </DetailBlock>

        <DetailBlock title={d.rbac_title} cta={d.rbac_cta}>
          <ul className="flex flex-col gap-1.5 text-[0.72rem]">
            {d.rbac.map((r) => (
              <li key={r.role} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{r.role}</span>
                <span className="font-medium text-[var(--tessera-text)]">{r.access}</span>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="mt-2 flex items-center gap-1 self-start text-[0.66rem] text-[#b9a6ff] hover:text-white"
          >
            {d.rbac_more} <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </DetailBlock>

        <div>
          <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
            {d.info_title}
          </h3>
          <ul className="flex flex-col gap-1.5 text-[0.72rem]">
            {d.info.map((it) => (
              <li key={it.label} className="flex items-center justify-between gap-2">
                <span className="text-[var(--tessera-text-muted)]">{it.label}</span>
                <span className="font-medium text-[var(--tessera-text)]">{it.value}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function DetailBlock({
  title,
  cta,
  children,
}: { title: string; cta: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
        <button type="button" className="text-[0.64rem] text-[#b9a6ff] hover:text-white">
          {cta}
        </button>
      </div>
      {children}
    </div>
  );
}

function Footer({ data }: { data: Data }) {
  const f = data.footer;
  if (!f?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
      {f.map((it) => (
        <span key={it.label}>
          {it.label} : <span className="text-[var(--tessera-text)]">{it.value}</span>
        </span>
      ))}
    </div>
  );
}
