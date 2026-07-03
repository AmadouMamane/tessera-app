"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSearch,
  FlaskConical,
  GitBranch,
  PauseCircle,
  PlayCircle,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { StretchChart } from "@/components/cockpit/stretch-chart";
import { SyntheticNotice } from "@/components/cockpit/synthetic-notice";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import {
  fetchAutomationsOverview,
  mutateAutomationRuleState,
  mutateAutomationsEvaluate,
} from "@/lib/api/client";
import type { AutomationsOverview as AutomationsData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const SEV_BADGE: Record<string, string> = {
  critique: "border-red-500/30 bg-red-500/15 text-red-300",
  eleve: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  moyen: "border-yellow-500/30 bg-yellow-500/15 text-yellow-300",
  faible: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const RESULT_BADGE: Record<string, string> = {
  success: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  fail: "border-red-500/30 bg-red-500/15 text-red-300",
  blocked: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  approb: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};

const TABS = ["overview", "rules", "executions", "queue", "approvals", "audit"] as const;
type Tab = (typeof TABS)[number];

type T = ReturnType<typeof useTranslations<"automations">>;
type Data = AutomationsData;

export function AutomationsOverview() {
  const t = useTranslations("automations");
  const locale = useLocale();
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["automations-overview", locale],
    queryFn: ({ signal }) => fetchAutomationsOverview(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const evaluate = useMutation({
    mutationFn: () => mutateAutomationsEvaluate(locale),
    onSuccess: (fresh) => qc.setQueryData(["automations-overview", locale], fresh),
  });
  const toggleRule = useMutation({
    mutationFn: mutateAutomationRuleState,
    onSuccess: (fresh) => qc.setQueryData(["automations-overview", locale], fresh),
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
      <CommandBar
        t={t}
        active={activeTab}
        onSelect={setActiveTab}
        onEvaluate={() => evaluate.mutate()}
        evaluating={evaluate.isPending}
        data={data}
      />
      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("rail.realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        windowEnd={temporal.windowEnd}
        onPickDate={temporal.pickDate}
        onModeChange={temporal.changeMode}
      />

      <div id="automations-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-3">
        {activeTab === "rules" ? (
          <Zone
            label={t("zone.catalogue")}
            info={<KpiInfo k="zone.catalogue" title={t("zone.catalogue")} />}
          >
            <Catalogue
              t={t}
              data={data}
              onToggle={(id, enabled) => toggleRule.mutate({ rule_id: id, enabled, lang: locale })}
              toggling={toggleRule.isPending}
            />
          </Zone>
        ) : null}
        {activeTab === "executions" ? (
          <>
            <Zone
              label={t("zone.journal")}
              info={<KpiInfo k="zone.journal" title={t("zone.journal")} />}
            >
              <Journal t={t} data={data} />
            </Zone>
            <div className="grid gap-3 xl:grid-cols-2">
              <Performance t={t} data={data} />
              <Zone
                label={t("zone.pipeline")}
                info={<KpiInfo k="zone.pipeline" title={t("zone.pipeline")} />}
              >
                <Pipeline t={t} data={data} />
              </Zone>
            </div>
          </>
        ) : null}
        {activeTab === "queue" || activeTab === "approvals" ? (
          <div className="flex min-w-0 flex-col gap-2">
            <SyntheticNotice signalId="automation_workflow" compact />
            <div className="grid gap-3 xl:grid-cols-2">
              <Approvals t={t} data={data} />
              <Savings t={t} data={data} />
            </div>
          </div>
        ) : null}
        {activeTab === "audit" ? (
          <Zone
            label={t("zone.journal")}
            info={<KpiInfo k="zone.journal" title={t("zone.journal")} />}
          >
            <Journal t={t} data={data} />
            <div className="mt-2">
              <Link
                href="/prouver/audit-logs"
                className="inline-flex items-center gap-1 text-[0.7rem] text-[var(--tessera-green)] hover:underline"
              >
                {t("tabx.auditLink")}
              </Link>
            </div>
          </Zone>
        ) : null}
      </div>

      {activeTab !== "overview" ? null : (
        <>
          <Zone
            label={t("zone.actual")}
            info={<KpiInfo k="zone.actual" title={t("zone.actual")} />}
          >
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
              {data.kpis.map((kpi) => (
                <KpiTile
                  key={kpi.key}
                  kpi={kpi}
                  label={t(`kpi.${kpi.key}`)}
                  vs={t("delta.vsHier")}
                  info={<KpiInfo k={kpi.key} title={t(`kpi.${kpi.key}`)} />}
                />
              ))}
            </div>
          </Zone>

          <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_316px]">
            <div className="flex min-w-0 flex-col gap-3">
              <Zone
                label={t("zone.catalogue")}
                info={<KpiInfo k="zone.catalogue" title={t("zone.catalogue")} />}
              >
                <Catalogue
                  t={t}
                  data={data}
                  onToggle={(id, enabled) =>
                    toggleRule.mutate({ rule_id: id, enabled, lang: locale })
                  }
                  toggling={toggleRule.isPending}
                />
              </Zone>
              <Zone
                label={t("zone.pipeline")}
                info={<KpiInfo k="zone.pipeline" title={t("zone.pipeline")} />}
              >
                <Pipeline t={t} data={data} />
              </Zone>
              <div className="grid gap-3 xl:grid-cols-2">
                <Zone
                  label={t("zone.distribution")}
                  info={<KpiInfo k="zone.distribution" title={t("zone.distribution")} />}
                >
                  <Panel title="">
                    <Donut
                      slices={data.by_type}
                      total={data.by_type_total}
                      caption="automations"
                      labelOf={(k) => t(`type.${k}`)}
                      showCount
                    />
                  </Panel>
                </Zone>
                <Zone label={t("zone.env")} info={<KpiInfo k="zone.env" title={t("zone.env")} />}>
                  <EnvBars t={t} data={data} />
                </Zone>
              </div>
              <Zone
                label={t("zone.journal")}
                info={<KpiInfo k="zone.journal" title={t("zone.journal")} />}
              >
                <Journal t={t} data={data} />
              </Zone>
            </div>

            <AutomationsRail t={t} data={data} />
          </div>

          {/* Bottom band: approvals · guardrails · performance · savings · context */}
          <div className="grid gap-3 xl:grid-cols-12">
            <Approvals t={t} data={data} className="xl:col-span-3" />
            <Guardrails t={t} data={data} className="xl:col-span-2" />
            <Performance t={t} data={data} className="xl:col-span-3" />
            <Savings t={t} data={data} className="xl:col-span-2" />
            <ContextPanel t={t} data={data} className="xl:col-span-2" />
          </div>
        </>
      )}

      <Footer t={t} data={data} />
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({
  t,
  active,
  onSelect,
  onEvaluate,
  evaluating,
  data,
}: {
  t: T;
  active: Tab;
  onSelect: (tab: Tab) => void;
  onEvaluate: () => void;
  evaluating: boolean;
  data: Data;
}) {
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "automations-overview.json";
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div
        role="tablist"
        aria-label={t("tabs.overview")}
        className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5"
      >
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={tab === active}
            aria-controls="automations-tabpanel"
            onClick={() => onSelect(tab)}
            className={cn(
              "h-8 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors",
              tab === active
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
          onClick={onEvaluate}
          disabled={evaluating}
          className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
        >
          <FlaskConical className="h-4 w-4" />{" "}
          {evaluating ? t("tabx.evaluating") : t("tabx.evaluateNow")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={exportJson}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <Download className="h-4 w-4" /> {t("actions.export")}
        </Button>
        <Button
          asChild
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <Link href="/prouver/evidence-store">
            <FileSearch className="h-4 w-4" /> {t("actions.evidencePack")}
          </Link>
        </Button>
      </div>
    </section>
  );
}

// ── catalogue ────────────────────────────────────────────────────────────────

function Catalogue({
  t,
  data,
  onToggle,
  toggling,
}: {
  t: T;
  data: Data;
  onToggle: (id: string, enabled: boolean) => void;
  toggling: boolean;
}) {
  const cols = [
    "name",
    "trigger",
    "action",
    "scope",
    "mode",
    "lastRun",
    "success",
    "role",
    "status",
  ] as const;
  return (
    <Panel title="">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                  {t(`col.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.catalogue.map((row) => (
              <tr key={row.id} className="border-b border-[var(--tessera-border)]/60 last:border-0">
                <td className="max-w-[240px] px-2 py-1.5 font-medium text-[var(--tessera-text)]">
                  <span className="flex min-w-0 items-center gap-1">
                    <span className="min-w-0 truncate">{row.name}</span>
                    <KpiInfo k={`rule.${row.id}`} title={row.name} />
                  </span>
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{row.trigger}</td>
                <td className="px-2 py-1.5 text-[var(--tessera-text)]">{row.action}</td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{row.scope}</td>
                <td className="px-2 py-1.5">
                  <Badge
                    className={
                      row.mode === "auto"
                        ? "border-sky-500/30 bg-sky-500/15 text-sky-300"
                        : "border-amber-500/30 bg-amber-500/15 text-amber-300"
                    }
                  >
                    {t(`mode.${row.mode}`)}
                  </Badge>
                </td>
                <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[0.66rem] text-[var(--tessera-text-muted)]">
                  {row.last_run}
                </td>
                <td className="px-2 py-1.5 tabular-nums text-emerald-300">{row.success}</td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{row.role}</td>
                <td className="px-2 py-1.5">
                  <button
                    type="button"
                    role="switch"
                    aria-checked={row.status === "active"}
                    aria-label={`${row.name} — ${t(`status.${row.status}`)}`}
                    disabled={toggling}
                    onClick={() => onToggle(row.id, row.status !== "active")}
                    className="inline-flex items-center gap-1.5 rounded-md border border-transparent px-1.5 py-0.5 text-[0.7rem] transition-colors hover:border-[var(--tessera-border)] hover:bg-[var(--tessera-muted)] disabled:opacity-60"
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        row.status === "active" ? "bg-emerald-400" : "bg-amber-400",
                      )}
                    />
                    {t(`status.${row.status}`)}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ── pipeline funnel ──────────────────────────────────────────────────────────

function Pipeline({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title="">
      <div className="flex flex-col gap-2">
        <ol className="flex items-stretch gap-1">
          {data.pipeline.map((step, i) => (
            <li key={step.key} className="flex min-w-0 flex-1 items-center gap-1">
              <div className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-2 text-center">
                <span className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">
                  {t(`pipeline.${step.key}`)}
                </span>
                <span className="text-[0.95rem] font-semibold tabular-nums text-white">
                  {step.count}
                </span>
                <span className="text-[0.6rem] tabular-nums text-[#87bfff]">{step.pct}%</span>
              </div>
              {i < data.pipeline.length - 1 ? (
                <ChevronRight className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
              ) : null}
            </li>
          ))}
        </ol>
        <p className="text-[0.7rem] text-[var(--tessera-text-muted)]">
          {t("pipeline.completion")} :{" "}
          <span className="font-semibold text-[var(--tessera-green)]">{data.completion}</span>
        </p>
      </div>
    </Panel>
  );
}

function EnvBars({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.by_env.map((e) => e.count), 1);
  return (
    <Panel title="">
      <div className="flex h-[120px] items-end justify-around gap-3">
        {data.by_env.map((e) => (
          <div key={e.key} className="flex h-full flex-1 flex-col items-center justify-end gap-1">
            <span className="text-[0.7rem] font-semibold tabular-nums text-white">{e.count}</span>
            <div
              className="w-full max-w-[42px] rounded-t-sm"
              style={{ height: `${(e.count / max) * 100}%`, background: e.color }}
            />
            <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">
              {t(`env.${e.key}`)}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Journal({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title="" action={<ViewAll label={t("viewAll.journal")} href="/prouver/audit-logs" />}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.7rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="px-1.5 py-1 font-medium">{t("jCol.time")}</th>
              <th className="px-1.5 py-1 font-medium">{t("jCol.automation")}</th>
              <th className="px-1.5 py-1 font-medium">{t("jCol.trigger")}</th>
              <th className="px-1.5 py-1 font-medium">{t("jCol.actor")}</th>
              <th className="px-1.5 py-1 font-medium">{t("jCol.evidence")}</th>
              <th className="px-1.5 py-1 font-medium">{t("jCol.duration")}</th>
              <th className="px-1.5 py-1 font-medium">{t("jCol.result")}</th>
            </tr>
          </thead>
          <tbody>
            {data.journal.map((r, i) => (
              <tr
                key={`${r.time}-${r.automation}-${i}`}
                className="border-b border-[var(--tessera-border)]/60 last:border-0"
              >
                <td className="whitespace-nowrap px-1.5 py-1 font-mono tabular-nums text-[var(--tessera-text-muted)]">
                  {r.time}
                </td>
                <td className="max-w-[200px] truncate px-1.5 py-1 text-[var(--tessera-text)]">
                  {r.automation}
                </td>
                <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{r.trigger}</td>
                <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{r.actor}</td>
                <td className="px-1.5 py-1 font-mono text-[0.62rem] text-[#87bfff]">
                  {r.evidence}
                </td>
                <td className="px-1.5 py-1 tabular-nums text-[var(--tessera-text-muted)]">
                  {r.duration}
                </td>
                <td className="px-1.5 py-1">
                  <Badge className={RESULT_BADGE[r.result]}>{t(`result.${r.result}`)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ── right rail ───────────────────────────────────────────────────────────────

function AutomationsRail({ t, data }: { t: T; data: Data }) {
  const g = data.governance;
  return (
    <aside className="flex min-w-0 flex-col gap-3">
      <Panel
        title={t("panel.recentIncidents")}
        info={<KpiInfo k="panel.recentIncidents" title={t("panel.recentIncidents")} />}
        action={<ViewAll label={t("viewAll.all")} href="/prouver/audit-logs" />}
      >
        <ul className="flex flex-col gap-1.5">
          {data.recent_incidents.map((inc, i) => (
            <li key={`${inc.id}-${i}`} className="flex items-center gap-2 text-[0.72rem]">
              <Badge className={SEV_BADGE[inc.severity]}>{t(`severity.${inc.severity}`)}</Badge>
              <span className="font-mono text-[0.64rem] text-[#87bfff]">{inc.id}</span>
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                {inc.label}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {inc.time}
              </span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title={t("panel.quickActions")}>
        <div className="grid grid-cols-2 gap-1.5">
          {[
            { key: "activate", icon: PlayCircle },
            { key: "suspend", icon: PauseCircle },
            { key: "openJournal", icon: ScrollText },
            { key: "viewApprovals", icon: CheckCircle2 },
          ].map((q) => (
            <button
              key={q.key}
              type="button"
              className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-left text-[0.66rem] transition-colors hover:bg-[var(--tessera-muted)]"
            >
              <q.icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                {t(`quick.${q.key}`)}
              </span>
            </button>
          ))}
        </div>
      </Panel>

      <Panel
        title={t("zone.governance").replace(/^G · /, "")}
        info={<KpiInfo k="zone.governance" title={t("zone.governance").replace(/^G · /, "")} />}
      >
        <div className="flex flex-col gap-2 text-[0.7rem]">
          <span className="inline-flex w-fit items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.62rem] text-emerald-300">
            <ShieldCheck className="h-3 w-3" /> {t("gov.dualControl")}
          </span>
          <div>
            <p className="mb-1 text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {t("gov.rolesByMode")}
            </p>
            <ul className="flex flex-col gap-1">
              {g.roles.map((r, i) => (
                <li key={`${r.mode}-${i}`} className="flex items-start gap-2">
                  <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                    {/* r.mode here is a role-authority tier (Admin / Compliance+ /
                        Operator+), not the auto/approb execution mode — render the
                        backend label directly (it is not localized). */}
                    {r.mode}
                  </Badge>
                  <span className="min-w-0 flex-1 text-[0.66rem] text-[var(--tessera-text)]">
                    {r.scope}
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div className="border-t border-[var(--tessera-border)] pt-1.5">
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">
              {t("gov.defaultScope")}
            </p>
            <p className="text-[0.66rem] text-[var(--tessera-text)]">{g.default_scope}</p>
          </div>
          <span className="inline-flex items-center gap-1.5 text-[0.64rem] text-[var(--tessera-green)]">
            <ShieldCheck className="h-3 w-3" /> {t("gov.chain")}
          </span>
        </div>
      </Panel>
    </aside>
  );
}

// ── bottom band ──────────────────────────────────────────────────────────────

function Approvals({ t, data, className }: { t: T; data: Data; className?: string }) {
  // Approval queue — flagged demonstration (automation_workflow subsystem).
  return (
    <Panel
      title={t("zone.approvals").replace(/^H · /, "")}
      className={className}
      info={<KpiInfo k="zone.approvals" title={t("zone.approvals").replace(/^H · /, "")} />}
      action={<ViewAll label={t("viewAll.all")} />}
    >
      <SyntheticNotice signalId="automation_workflow" compact />
      {data.approvals.length === 0 ? (
        <p className="py-4 text-center text-[0.68rem] text-[var(--tessera-text-muted)]">
          {t("tabx.noApprovals")}
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.approvals.map((a) => (
            <li key={a.name} className="flex items-center gap-2 text-[0.7rem]">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[var(--tessera-text)]">{a.name}</p>
                <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">
                  {t("approve.since", { t: a.since })}
                </p>
              </div>
              <Button
                size="sm"
                className="h-7 shrink-0 border border-[#007a55] bg-[#005c42] px-2.5 text-[0.66rem] text-[#d6f0e3] hover:bg-[#006d4e]"
              >
                {t("approve.cta")}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Guardrails({ t, data, className }: { t: T; data: Data; className?: string }) {
  const max = Math.max(...data.guardrails.map((g) => g.count), 1);
  return (
    <Panel
      title={t("zone.guardrails").replace(/^I · /, "")}
      className={className}
      info={<KpiInfo k="zone.guardrails" title={t("zone.guardrails").replace(/^I · /, "")} />}
      action={<ViewAll label={t("viewAll.guardrails")} href="/configurer/garde-fous" />}
    >
      <ul className="flex flex-col gap-2">
        {data.guardrails.map((g) => (
          <li key={g.key} className="flex flex-col gap-0.5 text-[0.66rem]">
            <div className="flex items-center justify-between gap-1.5">
              <span className="min-w-0 truncate text-[var(--tessera-text)]">
                {t(`gr.${g.key}`)}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {g.count} · {g.pct}%
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full bg-[#2e72d2]"
                style={{ width: `${(g.count / max) * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Performance({ t, data, className }: { t: T; data: Data; className?: string }) {
  const p = data.performance;
  return (
    <Panel
      title={t("zone.performance").replace(/^J · /, "")}
      className={className}
      info={<KpiInfo k="zone.performance" title={t("zone.performance").replace(/^J · /, "")} />}
      action={<ViewAll label={t("viewAll.performance")} />}
    >
      <div className="h-[100px]">
        <StretchChart
          title={t("zone.performance")}
          lines={[
            { points: p.success, color: "#34d399" },
            { points: p.average, color: "#60a5fa" },
          ]}
          ticks={p.labels}
        />
      </div>
      <div className="mt-1 flex gap-3 text-[0.6rem] text-[var(--tessera-text-muted)]">
        <Legend color="#34d399" label={t("perf.success")} />
        <Legend color="#60a5fa" label={t("perf.average")} />
      </div>
    </Panel>
  );
}

function Savings({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("zone.savings").replace(/^K · /, "")}
      className={className}
      info={<KpiInfo k="zone.savings" title={t("zone.savings").replace(/^K · /, "")} />}
    >
      <SyntheticNotice signalId="automation_workflow" compact />
      <dl className="flex flex-col gap-2">
        {data.savings.map((s) => (
          <div key={s.key} className="flex items-center justify-between gap-2">
            <dt className="text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t(`savings.${s.key}`)}
            </dt>
            <dd className="flex items-baseline gap-1.5">
              <span className="text-[0.82rem] font-semibold tabular-nums text-white">
                {s.value}
              </span>
              <span className="text-[0.6rem] font-medium text-[var(--tessera-green)]">
                {s.delta}
              </span>
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function ContextPanel({ t, data, className }: { t: T; data: Data; className?: string }) {
  const c = data.context;
  const rows: [string, string][] = [
    [t("ctx.version"), c.version],
    [t("ctx.modified"), c.last_modified],
    [t("ctx.author"), c.author],
    [t("ctx.branch"), c.branch],
    [t("ctx.scope"), c.scope],
  ];
  return (
    <Panel
      title={t("zone.context").replace(/^L · /, "")}
      className={className}
      info={<KpiInfo k="zone.context" title={t("zone.context").replace(/^L · /, "")} />}
      action={<ViewAll label={t("ctx.history")} />}
    >
      <dl className="flex flex-col gap-1 text-[0.68rem]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{k}</dt>
            <dd className="truncate font-mono text-[0.64rem] text-[var(--tessera-text)]">{v}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function Footer({ t, data }: { t: T; data: Data }) {
  const f = data.footer;
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <Chip icon={GitBranch} label={t("footer.source", { src: f.source })} />
      <Chip
        icon={ShieldCheck}
        tone="text-[var(--tessera-green)]"
        label={t("footer.certified", { txt: f.certified })}
      />
      <Chip icon={Activity} label={t("gov.chain")} />
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

/** ⓘ for an automations KPI/zone, reading automations.explain.<k>.{what,how,source?}. */
function KpiInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("automations.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

function Zone({
  label,
  info,
  children,
}: {
  label: string;
  info?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="shrink-0 rounded-xl border border-[var(--tessera-border)]/60 bg-[var(--tessera-surface)]/20 p-2.5">
      <h2 className="mb-2 flex items-center gap-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
      </h2>
      {children}
    </section>
  );
}

function Panel({
  title,
  action,
  info,
  children,
  className,
}: {
  title: string;
  action?: ReactNode;
  info?: ReactNode;
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
      {title || action || info ? (
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="flex min-w-0 items-center gap-1 text-[0.8rem] font-semibold text-[var(--tessera-text)]">
            <span className="min-w-0 truncate">{title}</span>
            {info}
          </h3>
          {action}
        </div>
      ) : null}
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function KpiTile({
  kpi,
  label,
  vs,
  info,
}: { kpi: Data["kpis"][number]; label: string; vs: string; info?: ReactNode }) {
  const up = kpi.delta_label.trim().startsWith("+");
  const good = up === kpi.good_is_up;
  const magnitude = kpi.delta_label.replace(/^[+-]\s*/, "");
  return (
    <div className="flex h-[104px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 text-[0.7rem] font-medium text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
      </p>
      <div className="mt-1 flex items-center gap-2">
        <span className="whitespace-nowrap text-[1.4rem] font-semibold leading-none text-white">
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

function Donut({
  slices,
  total,
  caption,
  labelOf,
  showCount,
}: {
  slices: Data["by_type"];
  total: number;
  caption: string;
  labelOf: (key: string) => string;
  showCount?: boolean;
}) {
  const sum = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[88px] w-[88px] shrink-0">
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
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-base font-semibold tabular-nums text-white">{total}</span>
          <span className="text-[0.46rem] uppercase text-[var(--tessera-text-muted)]">
            {caption}
          </span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
              {labelOf(s.key)}
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {showCount ? `${s.count} · ` : ""}
              {s.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.58rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-1 w-3 rounded-full" style={{ background: color }} /> {label}
    </span>
  );
}

function ViewAll({ label, href }: { label: string; href?: Route }) {
  const cls =
    "flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]";
  if (href) {
    return (
      <Link href={href} className={cls}>
        {label} <ChevronRight className="h-3 w-3" />
      </Link>
    );
  }
  return (
    <button type="button" className={cls}>
      {label} <ChevronRight className="h-3 w-3" />
    </button>
  );
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
