"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ChevronRight,
  Database,
  Download,
  FileSearch,
  GitBranch,
  MoreVertical,
  PlayCircle,
  Plus,
  RefreshCcw,
  Ticket,
  Timer,
  UserPlus,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { StretchChart } from "@/components/cockpit/stretch-chart";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { fetchIncidentsOverview } from "@/lib/api/client";
import type { IncidentsOverview as IncidentsOverviewData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const SEV_BADGE: Record<string, string> = {
  critique: "border-red-500/30 bg-red-500/15 text-red-300",
  eleve: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  moyen: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const SEV_DOT: Record<string, string> = {
  critique: "bg-red-400",
  eleve: "bg-amber-400",
  moyen: "bg-sky-400",
};
const STATUS_TEXT: Record<string, string> = {
  ouvert: "text-amber-300",
  encours: "text-sky-300",
  resolu: "text-emerald-300",
};
const TONE_TEXT: Record<string, string> = {
  crit: "text-red-300",
  warn: "text-amber-300",
  ok: "text-emerald-300",
};

const TABS = [
  "overview",
  "incidents",
  "playbooks",
  "orchestration",
  "automations",
  "postmortems",
  "journal",
] as const;

export function IncidentsOverview() {
  const t = useTranslations("incidents");
  const { data } = useQuery({
    queryKey: ["incidents-overview"],
    queryFn: ({ signal }) => fetchIncidentsOverview(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} />
      <LiveRail t={t} data={data} />

      {/* A · État actuel */}
      <Zone label={t("zone.actual")}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {data.kpis.map((kpi) => (
            <KpiTile key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} vs={t("delta.vs7d")} />
          ))}
        </div>
      </Zone>

      {/* B · Diagnostic / triage */}
      <Zone label={t("zone.triage")}>
        <div className="grid gap-3 xl:grid-cols-12">
          <div className="flex min-w-0 flex-col gap-3 xl:col-span-7">
            <PriorityQueue t={t} data={data} />
            <Catalog t={t} data={data} />
          </div>
          <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:col-span-5">
            <RecentIncidents t={t} data={data} />
            <SlaEscalations t={t} data={data} />
            <Distribution t={t} data={data} />
            <ControlCases t={t} data={data} />
          </div>
        </div>
      </Zone>

      {/* C · Exécution & automation */}
      <Zone label={t("zone.execution")}>
        <div className="grid gap-3 xl:grid-cols-12">
          <RunningPlaybook t={t} data={data} className="xl:col-span-4" />
          <ResponseJournal t={t} data={data} className="xl:col-span-4" />
          <Automations t={t} data={data} className="xl:col-span-2" />
          <QuickActions t={t} className="xl:col-span-2" />
        </div>
      </Zone>

      {/* D · Impact & performance */}
      <Zone label={t("zone.impact")}>
        <div className="grid gap-3 xl:grid-cols-12">
          <MttrChart t={t} data={data} className="xl:col-span-3" />
          <ResolutionBars t={t} data={data} className="xl:col-span-3" />
          <DomainBars t={t} data={data} className="xl:col-span-3" />
          <Postmortems t={t} data={data} className="xl:col-span-3" />
        </div>
      </Zone>

      <Footer t={t} data={data} />
    </div>
  );
}

type T = ReturnType<typeof useTranslations<"incidents">>;
type Data = IncidentsOverviewData;

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({ t }: { t: T }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={cn(
              "h-8 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors",
              tab === "overview"
                ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          size="sm"
          className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
        >
          <Plus className="h-4 w-4" /> {t("actions.createTicket")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <PlayCircle className="h-4 w-4" /> {t("actions.launchPlaybook")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <FileSearch className="h-4 w-4" /> {t("actions.evidencePack")}
        </Button>
        <IconBtn icon={Download} />
        <IconBtn icon={MoreVertical} />
      </div>
    </section>
  );
}

function LiveRail({ t, data }: { t: T; data: Data }) {
  return (
    <section className="flex min-h-[42px] shrink-0 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 text-xs text-[var(--tessera-text-muted)] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="flex items-center gap-1.5 font-medium text-[var(--tessera-green)]">
        <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--tessera-green)]" />{" "}
        {t("rail.live")}
      </span>
      <Sep />
      <span>{t("rail.realtime")}</span>
      <Sep />
      <span>{t("rail.period", { days: data.period_days })}</span>
      <Sep />
      <span>{t("rail.updated", { time: data.updated_at })}</span>
      <button
        type="button"
        className="ml-auto flex h-7 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
      >
        <RefreshCcw className="h-3.5 w-3.5" /> {t("rail.replay")}
      </button>
    </section>
  );
}

// ── zone B ───────────────────────────────────────────────────────────────────

function PriorityQueue({ t, data }: { t: T; data: Data }) {
  const cols = [
    "id",
    "severity",
    "trigger",
    "domain",
    "status",
    "owner",
    "sla",
    "playbook",
    "role",
  ] as const;
  return (
    <Panel title={t("triage.queue")} action={<ViewAll label={t("triage.viewAll")} />}>
      <div className="-mx-1 overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.66rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                  {t(`col.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.priority_incidents.map((inc) => (
              <tr key={inc.id} className="border-b border-[var(--tessera-border)]/60 last:border-0">
                <td className="px-2 py-1.5 font-mono text-[0.7rem] text-[#87bfff]">{inc.id}</td>
                <td className="px-2 py-1.5">
                  <SevBadge severity={inc.severity} t={t} />
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text)]">{inc.trigger}</td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                  {t(`domain.${inc.domain}`)}
                </td>
                <td className={cn("px-2 py-1.5 font-medium", STATUS_TEXT[inc.status])}>
                  {t(`status.${inc.status}`)}
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{inc.owner}</td>
                <td
                  className={cn(
                    "whitespace-nowrap px-2 py-1.5 font-medium tabular-nums",
                    TONE_TEXT[inc.sla_tone],
                  )}
                >
                  {inc.sla}
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text)]">{inc.playbook}</td>
                <td className="px-2 py-1.5">
                  <RoleBadge role={inc.role} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        {t("triage.incidentsCount", { n: data.priority_incidents.length })}
      </p>
    </Panel>
  );
}

function Catalog({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("triage.catalog")} action={<ViewAll label={t("triage.viewCatalog")} />}>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
        {data.playbook_catalog.map((pb) => (
          <div
            key={pb.name}
            className="flex flex-col gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <div className="flex items-center gap-1.5">
              <PlayCircle className="h-3.5 w-3.5 shrink-0 text-[#87bfff]" />
              <span className="truncate text-[0.72rem] font-medium text-[var(--tessera-text)]">
                {pb.name}
              </span>
            </div>
            <p className="line-clamp-2 text-[0.62rem] leading-tight text-[var(--tessera-text-muted)]">
              {pb.desc}
            </p>
            <span className="mt-auto text-[0.62rem] font-medium text-[var(--tessera-green)]">
              {t("triage.runs", { n: pb.runs })}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RecentIncidents({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("triage.recent")} action={<ViewAll label={t("triage.viewAll")} />}>
      <ul className="flex flex-col gap-1.5">
        {data.recent_incidents.map((inc) => (
          <li key={inc.id} className="flex items-center gap-2 text-[0.72rem]">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", SEV_DOT[inc.severity])} />
            <span className="font-mono text-[0.66rem] text-[#87bfff]">{inc.id}</span>
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{inc.label}</span>
            <SevBadge severity={inc.severity} t={t} />
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {inc.time}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
        {t("triage.recentMore", { n: data.recent_more })}
      </p>
    </Panel>
  );
}

function SlaEscalations({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("triage.sla")} action={<ViewAll label={t("triage.viewAll")} />}>
      <ul className="flex flex-col gap-1.5">
        {data.sla_escalations.map((e) => (
          <li key={e.id} className="flex items-center gap-2 text-[0.72rem]">
            <Timer className={cn("h-3.5 w-3.5 shrink-0", TONE_TEXT[e.tone])} />
            <span className="font-mono text-[0.66rem] text-[#87bfff]">{e.id}</span>
            <span className={cn("ml-auto shrink-0 tabular-nums font-medium", TONE_TEXT[e.tone])}>
              {e.remaining}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Distribution({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("triage.distribution")}>
      <Donut slices={data.domain_distribution} total={data.donut_total} t={t} />
    </Panel>
  );
}

function ControlCases({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("triage.controlCases")} action={<ViewAll label={t("triage.viewCases")} />}>
      <ul className="flex flex-col gap-1.5">
        {data.control_cases.map((c) => (
          <li key={c.id} className="flex items-center gap-2 text-[0.72rem]">
            <span className="font-mono text-[0.66rem] text-[var(--tessera-green)]">{c.id}</span>
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{c.label}</span>
            <span className="shrink-0 text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("triage.assoc", { n: c.assoc })}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── zone C ───────────────────────────────────────────────────────────────────

function RunningPlaybook({ t, data, className }: { t: T; data: Data; className?: string }) {
  const pb = data.running_playbook;
  return (
    <Panel className={className} title={`${t("exec.running")} — ${pb.name} (${pb.incident})`}>
      <div className="flex flex-col gap-3">
        <ol className="flex items-start justify-between gap-1">
          {pb.steps.map((step, i) => (
            <li
              key={step.key}
              className="flex min-w-0 flex-1 flex-col items-center gap-1 text-center"
            >
              <div className="flex w-full items-center">
                <span
                  className={cn(
                    "h-px flex-1",
                    i === 0 ? "bg-transparent" : "bg-[var(--tessera-border)]",
                  )}
                />
                <span
                  className={cn(
                    "grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[0.62rem] font-semibold",
                    step.state === "done"
                      ? "border-[#1b805f] bg-[#05281f] text-[var(--tessera-green)]"
                      : step.state === "current"
                        ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
                        : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
                  )}
                >
                  {i + 1}
                </span>
                <span
                  className={cn(
                    "h-px flex-1",
                    i === pb.steps.length - 1 ? "bg-transparent" : "bg-[var(--tessera-border)]",
                  )}
                />
              </div>
              <span className="w-full truncate text-[0.6rem] text-[var(--tessera-text)]">
                {step.label}
              </span>
              <span className="w-full truncate text-[0.55rem] tabular-nums text-[var(--tessera-text-muted)]">
                {step.time || "—"}
              </span>
            </li>
          ))}
        </ol>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem]">
          <KV label={t("exec.owner")} value={pb.owner} />
          <KV label={t("exec.role")} value={pb.role} />
          <KV label={t("exec.proofs")} value={String(pb.proofs)} />
          <KV label={t("exec.elapsed")} value={pb.elapsed} mono />
        </div>
      </div>
    </Panel>
  );
}

function ResponseJournal({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      className={className}
      title={t("exec.journal")}
      action={<ViewAll label={t("exec.viewAll")} />}
    >
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("journalCol.time")}</th>
            <th className="px-1.5 py-1 font-medium">{t("journalCol.incident")}</th>
            <th className="px-1.5 py-1 font-medium">{t("journalCol.action")}</th>
            <th className="px-1.5 py-1 font-medium">{t("journalCol.actor")}</th>
          </tr>
        </thead>
        <tbody>
          {data.response_journal.map((r) => (
            <tr
              key={`${r.time}-${r.incident}`}
              className="border-b border-[var(--tessera-border)]/60 last:border-0"
            >
              <td className="px-1.5 py-1 font-mono tabular-nums text-[var(--tessera-text-muted)]">
                {r.time}
              </td>
              <td className="px-1.5 py-1 font-mono text-[#87bfff]">{r.incident}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text)]">{r.action}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{r.actor}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Automations({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      className={className}
      title={t("exec.automations")}
      action={<ViewAll label={t("exec.viewAllAuto")} />}
    >
      <ul className="flex flex-col gap-1.5">
        {data.automations.map((a) => (
          <li
            key={a.rule}
            className="flex flex-col gap-0.5 border-b border-[var(--tessera-border)]/60 pb-1.5 last:border-0 last:pb-0"
          >
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-[0.68rem] text-[var(--tessera-text)]">
                {a.rule}
              </span>
              <AutoStatus status={a.status} t={t} />
            </div>
            <div className="flex items-center gap-2 text-[0.6rem] text-[var(--tessera-text-muted)]">
              <span className="tabular-nums">{a.last}</span>
              <span className="ml-auto">{a.role}</span>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function QuickActions({ t, className }: { t: T; className?: string }) {
  const items = [
    { key: "assignOwner", icon: UserPlus, role: "Operator+" },
    { key: "launchContainment", icon: PlayCircle, role: "Operator+" },
    { key: "freezeRelease", icon: GitBranch, role: "Operator+" },
    { key: "createJira", icon: Ticket, role: "Operator+" },
    { key: "evidencePack", icon: FileSearch, role: "Admin+" },
  ] as const;
  return (
    <Panel className={className} title={t("exec.quickActions")}>
      <ul className="flex flex-col gap-1">
        {items.map((it) => (
          <li key={it.key}>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-left text-[0.68rem] transition-colors hover:bg-[var(--tessera-muted)]"
            >
              <it.icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                {t(`quick.${it.key}`)}
              </span>
              <RoleBadge role={it.role} />
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── zone D ───────────────────────────────────────────────────────────────────

function MttrChart({ t, data, className }: { t: T; data: Data; className?: string }) {
  const s = data.mttr_series;
  return (
    <Panel
      className={className}
      title={t("impact.mttr")}
      action={<ViewAll label={t("impact.viewFull")} />}
    >
      <div className="h-[110px]">
        <StretchChart
          title={t("impact.mttr")}
          lines={[
            { points: s.mtta, color: "#2e72d2" },
            { points: s.mttr, color: "#34d399" },
          ]}
          ticks={s.labels}
        />
      </div>
      <div className="mt-1 flex items-center gap-3 text-[0.6rem] text-[var(--tessera-text-muted)]">
        <Legend color="#2e72d2" label={t("impact.mttaLine")} />
        <Legend color="#34d399" label={t("impact.mttrLine")} />
      </div>
    </Panel>
  );
}

function ResolutionBars({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel className={className} title={t("impact.resolution")}>
      <ul className="flex flex-col gap-2">
        {data.resolution_by_playbook.map((b) => (
          <li key={b.name} className="flex flex-col gap-1 text-[0.68rem]">
            <div className="flex items-center justify-between gap-2">
              <span className="min-w-0 truncate text-[var(--tessera-text)]">{b.name}</span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {b.pct}% · {b.ratio}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${b.pct}%`, background: b.color }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function DomainBars({ t, data, className }: { t: T; data: Data; className?: string }) {
  const max = Math.max(...data.incidents_by_domain.map((d) => d.count), 1);
  return (
    <Panel className={className} title={t("impact.byDomain")}>
      <ul className="flex flex-col gap-2">
        {data.incidents_by_domain.map((d) => (
          <li key={d.key} className="flex items-center gap-2 text-[0.68rem]">
            <span className="w-20 shrink-0 truncate text-[var(--tessera-text)]">
              {t(`domain.${d.key}`)}
            </span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(d.count / max) * 100}%`, background: d.color }}
              />
            </div>
            <span className="w-14 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {d.count} · {d.pct}%
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Postmortems({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      className={className}
      title={t("impact.postmortems")}
      action={<ViewAll label={t("impact.viewAll")} />}
    >
      <ul className="flex flex-col gap-2">
        {data.postmortems.map((p) => (
          <li
            key={p.id}
            className="flex flex-col gap-0.5 border-b border-[var(--tessera-border)]/60 pb-1.5 last:border-0 last:pb-0"
          >
            <div className="flex items-center gap-2 text-[0.7rem]">
              <span className="font-mono text-[0.64rem] text-[#87bfff]">{p.id}</span>
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{p.label}</span>
              <span className="shrink-0 text-[0.6rem] text-emerald-300">{p.resolved}</span>
            </div>
            <p className="truncate text-[0.62rem] text-[var(--tessera-text-muted)]">{p.rca}</p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── footer ───────────────────────────────────────────────────────────────────

function Footer({ t, data }: { t: T; data: Data }) {
  const f = data.footer;
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <Chip icon={Activity} tone="text-red-300" label={t("footer.critical", { n: f.critical })} />
      <Chip icon={Timer} tone="text-amber-300" label={t("footer.atRisk", { n: f.at_risk })} />
      <Chip
        icon={PlayCircle}
        tone="text-[var(--tessera-green)]"
        label={t("footer.playbooks", { n: f.playbooks })}
      />
      <Chip
        icon={FileSearch}
        tone="text-[var(--tessera-green)]"
        label={t("footer.proofs", { n: f.proofs })}
      />
      <Chip icon={Database} label={t("footer.source", { src: f.source })} />
      <Chip icon={RefreshCcw} label={t("footer.sync", { ago: f.sync })} />
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Zone({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="shrink-0 rounded-xl border border-[var(--tessera-border)]/60 bg-[var(--tessera-surface)]/20 p-2.5">
      <h2 className="mb-2 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {label}
      </h2>
      {children}
    </section>
  );
}

function Panel({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="min-w-0 truncate text-[0.8rem] font-semibold text-[var(--tessera-text)]">
          {title}
        </h3>
        {action}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function KpiTile({
  kpi,
  label,
  vs,
}: {
  kpi: Data["kpis"][number];
  label: string;
  vs: string;
}) {
  const up = kpi.delta_label.trim().startsWith("+");
  const good = up === kpi.good_is_up;
  const magnitude = kpi.delta_label.replace(/^[+−-]\s*/, "");
  return (
    <div className="flex h-[104px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="truncate text-[0.7rem] font-medium text-[var(--tessera-text-muted)]">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <span className="whitespace-nowrap text-[1.5rem] font-semibold leading-none text-white">
          {kpi.value}
        </span>
        <MetricSparkline
          className="h-6 min-w-0 flex-1"
          values={kpi.series}
          tone={kpi.good_is_up ? "success" : "danger"}
        />
      </div>
      <div className="mt-auto flex items-center gap-1 whitespace-nowrap text-[0.62rem] font-medium">
        <span className={good ? "text-[var(--tessera-green)]" : "text-red-300"}>
          {up ? "▲" : "▼"} {magnitude}
        </span>
        <span className="text-[var(--tessera-text-muted)]">{vs}</span>
      </div>
    </div>
  );
}

function SevBadge({ severity, t }: { severity: string; t: T }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[0.62rem] font-medium",
        SEV_BADGE[severity],
      )}
    >
      {t(`severity.${severity}`)}
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.6rem] font-medium text-[var(--tessera-text-muted)]">
      {role}
    </span>
  );
}

function AutoStatus({ status, t }: { status: string; t: T }) {
  const cls =
    status === "actif"
      ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
      : status === "dryrun"
        ? "border-amber-500/30 bg-amber-500/15 text-amber-300"
        : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.58rem] font-medium",
        cls,
      )}
    >
      {t(`autoStatus.${status}`)}
    </span>
  );
}

function Donut({
  slices,
  total,
  t,
}: {
  slices: Data["domain_distribution"];
  total: number;
  t: T;
}) {
  const sum = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[84px] w-[84px] shrink-0">
        <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="36"
            cy="36"
            r={R}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="9"
          />
          {slices.map((s) => {
            const frac = s.count / sum;
            const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
            off += frac;
            return (
              <circle
                key={s.key}
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
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-semibold tabular-nums text-white">{total}</span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.66rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
              {t(`domain.${s.key}`)}
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">{s.pct}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--tessera-text-muted)]">{label}</span>
      <span className={cn("truncate text-[var(--tessera-text)]", mono && "font-mono tabular-nums")}>
        {value}
      </span>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-1 w-3 rounded-full" style={{ background: color }} /> {label}
    </span>
  );
}

function ViewAll({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]"
    >
      {label} <ChevronRight className="h-3 w-3" />
    </button>
  );
}

function IconBtn({ icon: Icon }: { icon: typeof Download }) {
  return (
    <button
      type="button"
      className="grid h-9 w-9 place-items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function Sep() {
  return <span className="text-[var(--tessera-border-strong)]">·</span>;
}

function Chip({
  icon: Icon,
  label,
  tone,
}: { icon: typeof Activity; label: string; tone?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
      <Icon className={cn("h-3.5 w-3.5 shrink-0", tone)} />
      <span className="truncate">{label}</span>
    </span>
  );
}
