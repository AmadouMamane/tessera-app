"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  ChevronRight,
  Database,
  FileCode2,
  FileSearch,
  GitCompare,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { SyntheticNotice } from "@/components/cockpit/synthetic-notice";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchPoliciesOverview } from "@/lib/api/client";
import type { PoliciesOverview as PoliciesData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useUrlBackedView } from "@/lib/use-url-backed-view";

const VSTATUS: Record<string, string> = {
  draft: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  approved: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  active: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  canary: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  archived:
    "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
};
const VDOT: Record<string, string> = {
  draft: "bg-[var(--tessera-text-muted)]",
  approved: "bg-sky-400",
  active: "bg-emerald-400",
  canary: "bg-amber-400",
  archived: "bg-[var(--tessera-text-muted)]",
};
const ACTION_BADGE: Record<string, string> = {
  deny: "border-red-500/30 bg-red-500/15 text-red-300",
  allow: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  warn: "border-amber-500/30 bg-amber-500/15 text-amber-300",
};
const TONE_TEXT: Record<string, string> = {
  ok: "text-[var(--tessera-fg-success)]",
  warn: "text-[var(--tessera-fg-warning)]",
  bad: "text-[var(--tessera-fg-danger)]",
  neutral: "text-[var(--tessera-text-muted)]",
};
const TABS = [
  "overview",
  "activePolicies",
  "history",
  "runtimeGuardrails",
  "impactSimulator",
  "approvals",
] as const;
type Tab = (typeof TABS)[number];

const LINK_ROUTES: Record<string, Route> = {
  audit_journal: "/prouver/audit-logs",
  export_siem: "/configurer/integrations",
  evidence_pack: "/prouver/evidence-store",
  release_control: "/agir/release-control",
};

// Honest per-KPI drill-down: only where a real per-item source exists. The rule
// count aggregates the compiled guard policy -> the guardrail catalogue; the 24h
// violations are ledger deny decisions -> the audit journal. The fixture KPIs
// (false positives / pending versions / exceptions) have no source -> no link.
const KPI_HREF: Record<string, Route | undefined> = {
  active_policies: "/configurer/garde-fous",
  blocking_guardrails: "/configurer/garde-fous",
  violations_blocked: "/prouver/audit-logs",
};

type T = ReturnType<typeof useTranslations<"policies">>;
type Data = PoliciesData;

export function PoliciesOverview() {
  const t = useTranslations("policies");
  const locale = useLocale();
  const [activeTab, setActiveTab] = useUrlBackedView(TABS, "overview");
  const { data } = useQuery({
    queryKey: ["policies-overview", locale],
    queryFn: ({ signal }) => fetchPoliciesOverview(locale, signal),
    staleTime: 60_000,
  });

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} active={activeTab} onSelect={setActiveTab} />
      <VersionRail t={t} data={data} />

      <div id="policies-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-3">
        {activeTab === "activePolicies" ? (
          <ActivePolicies t={t} data={data} onViewAll={() => setActiveTab("history")} />
        ) : null}
        {activeTab === "history" ? (
          <div className="grid gap-3 xl:grid-cols-12">
            <VersionHistory t={t} data={data} className="xl:col-span-6" />
            <DiffYaml t={t} data={data} className="xl:col-span-6" />
          </div>
        ) : null}
        {activeTab === "runtimeGuardrails" ? (
          <div className="grid gap-3 xl:grid-cols-12">
            <Guardrails t={t} data={data} className="xl:col-span-5" />
            <ActivePolicies
              t={t}
              data={data}
              className="xl:col-span-7"
              onViewAll={() => setActiveTab("activePolicies")}
            />
          </div>
        ) : null}
        {activeTab === "impactSimulator" ? (
          <div className="flex min-w-0 flex-col gap-2">
            <SyntheticNotice signalId="policy_versioning" compact />
            <Impact t={t} data={data} />
          </div>
        ) : null}
        {activeTab === "approvals" ? (
          <div className="flex min-w-0 flex-col gap-2">
            <SyntheticNotice signalId="policy_versioning" compact />
            <PoliciesRail t={t} data={data} full />
          </div>
        ) : null}
      </div>

      {activeTab !== "overview" ? null : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {data.kpis.map((kpi) => (
              <KpiTile
                key={kpi.key}
                kpi={kpi}
                label={t(`kpi.${kpi.key}`)}
                vs={t("delta.vsHier")}
                info={<PolInfo k={kpi.key} title={t(`kpi.${kpi.key}`)} />}
                href={KPI_HREF[kpi.key]}
                drillLabel={t(`kpi.${kpi.key}`)}
              />
            ))}
          </div>

          <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_316px]">
            <div className="flex min-w-0 flex-col gap-3">
              <div className="grid gap-3 xl:grid-cols-12">
                <ActivePolicies
                  t={t}
                  data={data}
                  className="xl:col-span-7"
                  onViewAll={() => setActiveTab("activePolicies")}
                />
                <VersionHistory t={t} data={data} className="xl:col-span-5" />
              </div>
              <div className="grid gap-3 xl:grid-cols-12">
                <DiffYaml t={t} data={data} className="xl:col-span-5" />
                <Guardrails t={t} data={data} className="xl:col-span-3" />
                <Impact t={t} data={data} className="xl:col-span-4" flagged />
              </div>
            </div>

            <PoliciesRail t={t} data={data} />
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
}: {
  t: T;
  active: Tab;
  onSelect: (tab: Tab) => void;
}) {
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
            aria-controls="policies-tabpanel"
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
          variant="outline"
          onClick={() => onSelect("history")}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <GitCompare className="h-4 w-4" /> {t("actions.compareVersions")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onSelect("history")}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <FileCode2 className="h-4 w-4" /> {t("actions.diffYaml")}
        </Button>
        <Button
          asChild
          size="sm"
          className="h-9 gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/60 px-3 text-xs text-[var(--tessera-fg-accent)] hover:bg-[#4c3fb0]/80"
        >
          <Link href="/agir/release-control">
            <ShieldCheck className="h-4 w-4" /> {t("actions.requestApproval")}
          </Link>
        </Button>
      </div>
    </section>
  );
}

function VersionRail({ t, data }: { t: T; data: Data }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--tessera-text-muted)]">
        <span>
          {t("version.active")}{" "}
          <span className="font-semibold text-[var(--tessera-fg-success)]">
            {data.active_version}
          </span>
        </span>
        <PolInfo k="versionRail" title={t("version.active")} />
      </span>
      <ol className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {data.version_timeline.map((v, i) => (
          <li key={v.version} className="flex items-center gap-1">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[0.62rem] font-medium",
                VSTATUS[v.status],
              )}
              title={v.date}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", VDOT[v.status])} />
              {v.version}
            </span>
            {i < data.version_timeline.length - 1 ? (
              <span className="h-px w-3 shrink-0 bg-[var(--tessera-border)]" />
            ) : null}
          </li>
        ))}
      </ol>
      <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
        {t("version.compareTo")}{" "}
        <span className="font-medium text-[var(--tessera-text)]">{data.compare_to}</span>
      </span>
    </section>
  );
}

// ── zone A / B ───────────────────────────────────────────────────────────────

function ActivePolicies({
  t,
  data,
  className,
  onViewAll,
}: {
  t: T;
  data: Data;
  className?: string;
  onViewAll?: () => void;
}) {
  const cols = [
    "id",
    "name",
    "type",
    "action",
    "scope",
    "version",
    "changedBy",
    "approvedBy",
    "status",
  ] as const;
  return (
    <Panel
      title={t("zone.activePolicies")}
      className={className}
      info={<PolInfo k="zoneActivePolicies" title={t("zone.activePolicies")} />}
      action={<ViewAll label={t("viewAll.policies")} onClick={onViewAll} />}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-1.5 py-1.5 font-medium">
                  {t(`col.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.active_policies.map((p) => (
              <tr key={p.id} className="border-b border-[var(--tessera-border)]/60 last:border-0">
                <td className="px-1.5 py-1.5 font-mono text-[0.64rem] text-[var(--tessera-fg-info)]">
                  {p.id}
                </td>
                <td className="max-w-[140px] truncate px-1.5 py-1.5 text-[var(--tessera-text)]">
                  {p.name}
                </td>
                <td className="px-1.5 py-1.5">
                  <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                    {t(`type.${p.type}`)}
                  </Badge>
                </td>
                <td className="px-1.5 py-1.5">
                  <Badge className={ACTION_BADGE[p.action]}>{t(`action.${p.action}`)}</Badge>
                </td>
                <td className="px-1.5 py-1.5 text-[var(--tessera-text-muted)]">{p.scope}</td>
                <td className="px-1.5 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {p.version}
                </td>
                <td className="px-1.5 py-1.5 text-[var(--tessera-text-muted)]">{p.changed_by}</td>
                <td className="px-1.5 py-1.5 text-[var(--tessera-text-muted)]">{p.approved_by}</td>
                <td className="px-1.5 py-1.5">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1",
                      p.status === "active"
                        ? "text-[var(--tessera-fg-success)]"
                        : "text-[var(--tessera-text-muted)]",
                    )}
                  >
                    <span
                      className={cn("h-1.5 w-1.5 rounded-full", VDOT[p.status] ?? VDOT.draft)}
                    />{" "}
                    {t(`pStatus.${p.status}`)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function VersionHistory({ t, data, className }: { t: T; data: Data; className?: string }) {
  const cols = ["version", "datetime", "author", "approver", "status"] as const;
  return (
    <Panel
      title={t("zone.history")}
      className={className}
      info={<PolInfo k="zoneHistory" title={t("zone.history")} />}
      action={<ViewAll label={t("viewAll.history")} />}
    >
      <table className="w-full border-collapse text-left text-[0.72rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-1.5 py-1.5 font-medium">
                {t(`hCol.${c}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.version_history.map((v) => (
            <tr
              key={v.version}
              className="border-b border-[var(--tessera-border)]/60 last:border-0"
            >
              <td className="px-1.5 py-1.5 font-mono text-[0.64rem] text-[var(--tessera-text)]">
                {v.version}
              </td>
              <td className="whitespace-nowrap px-1.5 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                {v.datetime}
              </td>
              <td className="px-1.5 py-1.5 text-[var(--tessera-text-muted)]">{v.author}</td>
              <td className="px-1.5 py-1.5 text-[var(--tessera-text-muted)]">{v.approver}</td>
              <td className="px-1.5 py-1.5">
                <Badge className={VSTATUS[v.status]}>{t(`vStatus.${v.status}`)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {t("version.compareLabel", { active: data.active_version, compare: data.compare_to })}
      </p>
    </Panel>
  );
}

// ── zone C / D / E ───────────────────────────────────────────────────────────

function DiffYaml({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={`${t("zone.diff")} (${data.diff.title})`}
      className={className}
      info={<PolInfo k="zoneDiff" title={t("zone.diff")} />}
    >
      <pre className="overflow-x-auto rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2 font-mono text-[0.64rem] leading-relaxed">
        {data.diff.lines.map((l, i) => (
          <div
            key={`${i}-${l.text}`}
            className={cn(
              "px-1",
              l.type === "added" && "bg-emerald-500/10 text-emerald-300",
              l.type === "removed" && "bg-red-500/10 text-red-300",
              l.type === "context" && "text-[var(--tessera-text-muted)]",
            )}
          >
            {l.type === "added" ? "+ " : l.type === "removed" ? "- " : "  "}
            {l.text}
          </div>
        ))}
      </pre>
    </Panel>
  );
}

function Guardrails({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("zone.guardrails")}
      className={className}
      info={<PolInfo k="zoneGuardrails" title={t("zone.guardrails")} />}
    >
      <ul className="flex flex-col gap-2">
        {data.guardrails.map((g) => (
          <li key={g.key} className="flex flex-col gap-0.5 text-[0.66rem]">
            <div className="flex items-center justify-between gap-1.5">
              <span className="flex min-w-0 items-center gap-1">
                <Truncate className="min-w-0 text-[var(--tessera-text)]">
                  {t(`gr.${g.key}`)}
                </Truncate>
                <PolInfo k={g.key} title={t(`gr.${g.key}`)} />
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {g.value}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--tessera-bg)]">
              <div className="h-full rounded-full bg-[#2e72d2]" style={{ width: `${g.pct}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Impact({
  t,
  data,
  className,
  flagged,
}: {
  t: T;
  data: Data;
  className?: string;
  flagged?: boolean;
}) {
  return (
    <Panel
      title={t("zone.impact")}
      className={className}
      info={<PolInfo k="zoneImpact" title={t("zone.impact")} />}
    >
      {flagged ? <SyntheticNotice signalId="policy_versioning" compact /> : null}
      <table className="w-full border-collapse text-left text-[0.68rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("impactCol.metric")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("impactCol.baseline")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("impactCol.candidate")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("impactCol.impact")}</th>
          </tr>
        </thead>
        <tbody>
          {data.impact.map((r) => (
            <tr key={r.metric} className="border-b border-[var(--tessera-border)]/60 last:border-0">
              <td className="px-1.5 py-1.5 text-[var(--tessera-text)]">{r.metric}</td>
              <td className="px-1.5 py-1.5 text-right tabular-nums text-[var(--tessera-text-muted)]">
                {r.baseline}
              </td>
              <td className="px-1.5 py-1.5 text-right tabular-nums text-[var(--tessera-text)]">
                {r.candidate}
              </td>
              <td
                className={cn(
                  "px-1.5 py-1.5 text-right tabular-nums font-medium",
                  TONE_TEXT[r.tone],
                )}
              >
                {r.delta}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// ── right rail ───────────────────────────────────────────────────────────────

function PoliciesRail({ t, data, full }: { t: T; data: Data; full?: boolean }) {
  const d = data.version_detail;
  const linkIcons: Record<string, typeof FileSearch> = {
    audit_journal: FileSearch,
    export_siem: Database,
    evidence_pack: FileSearch,
    release_control: GitCompare,
  };
  return (
    <aside className={full ? "grid min-w-0 gap-3 lg:grid-cols-3" : "flex min-w-0 flex-col gap-3"}>
      <Panel
        title={`${t("zone.detail")} · ${d.version}`}
        info={<PolInfo k="zoneDetail" title={t("zone.detail")} />}
      >
        <dl className="flex flex-col gap-1.5 text-[0.7rem]">
          <KV label={t("version.effectiveFrom")} value={d.effective_from} />
          <KV label={t("version.commit")} value={d.commit} mono />
          <KV label={t("version.author")} value={d.author} />
          <KV label={t("version.approver")} value={d.approver} />
          <KV label={t("version.scope")} value={d.scope} />
        </dl>
      </Panel>

      <Panel
        title={t("zone.sensitive")}
        info={<PolInfo k="zoneSensitive" title={t("zone.sensitive")} />}
      >
        <SyntheticNotice signalId="policy_versioning" compact />
        <ul className="flex flex-col gap-1">
          {data.sensitive_actions.map((a) => (
            <li key={a.key}>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md border border-red-500/25 bg-red-500/5 px-2 py-1.5 text-left text-[0.68rem] transition-colors hover:bg-red-500/10"
              >
                <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-danger)]" />
                <Truncate className="min-w-0 flex-1 text-[var(--tessera-text)]">
                  {t(`sensitive.${a.key}`, {
                    v: a.key === "rollback" ? data.compare_to : data.active_version,
                  })}
                </Truncate>
                <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                  {a.role}
                </Badge>
              </button>
            </li>
          ))}
          <li className="mt-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]">
            {t("sensitive.reservedOps")}
          </li>
        </ul>
      </Panel>

      <Panel title={t("zone.links")}>
        <ul className="flex flex-col gap-1">
          {data.quick_links.map((link) => {
            const Icon = linkIcons[link] ?? FileSearch;
            return (
              <li key={link}>
                <Link
                  href={LINK_ROUTES[link] ?? "/prouver/audit-logs"}
                  className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.68rem] text-[var(--tessera-fg-info)] transition-colors hover:bg-[var(--tessera-muted)]"
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  <Truncate className="min-w-0 flex-1">{t(`links.${link}`)}</Truncate>
                </Link>
              </li>
            );
          })}
        </ul>
      </Panel>
    </aside>
  );
}

function Footer({ t, data }: { t: T; data: Data }) {
  const f = data.footer;
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <Chip icon={Database} label={t("footer.source", { src: f.source })} />
      <Chip
        icon={ShieldCheck}
        tone="text-[var(--tessera-green)]"
        label={t("footer.chain", { txt: f.chain })}
      />
      <Chip icon={Activity} label={data.version_detail.commit} />
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

/** ⓘ grounded in policies.explain.<k> (what / how computed / source). */
function PolInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("policies.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
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
      data-slot="card"
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5">
          <h3 className="min-w-0 truncate text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
            {title}
          </h3>
          {info ? <span className="shrink-0">{info}</span> : null}
        </div>
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
  info,
  href,
  drillLabel,
}: {
  kpi: Data["kpis"][number];
  label: string;
  vs: string;
  info?: ReactNode;
  href?: Route;
  drillLabel?: string;
}) {
  const up = kpi.delta_label.trim().startsWith("+");
  const neutral = kpi.delta_label.trim() === "0";
  const good = up === kpi.good_is_up;
  const magnitude = kpi.delta_label.replace(/^[+-]\s*/, "");
  return (
    <div
      data-slot="card"
      className={cn(
        "group relative flex h-[104px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        href && "transition-colors hover:border-[#2e72d2]/50",
      )}
    >
      {href ? (
        <Link
          href={href}
          aria-label={drillLabel}
          className="absolute inset-0 z-10 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2e72d2]/40"
        />
      ) : null}
      <div className={cn("flex items-center gap-1.5", href && "pointer-events-none relative z-20")}>
        <Truncate
          as="p"
          full={label}
          className="min-w-0 flex-1 text-[0.7rem] font-medium text-[var(--tessera-text-muted)]"
        >
          {label}
        </Truncate>
        {info ? <span className={href ? "pointer-events-auto" : undefined}>{info}</span> : null}
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="whitespace-nowrap text-[1.4rem] font-semibold leading-none text-[var(--tessera-text-strong)]">
          {kpi.value}
        </span>
        <MetricSparkline
          className="h-6 min-w-0 flex-1"
          values={kpi.series}
          tone={kpi.good_is_up ? "success" : "danger"}
        />
      </div>
      <div className="mt-auto flex items-center gap-1 whitespace-nowrap text-[0.62rem] font-medium">
        <span
          className={
            neutral
              ? "text-[var(--tessera-text-muted)]"
              : good
                ? "text-[var(--tessera-green)]"
                : "text-[var(--tessera-fg-danger)]"
          }
        >
          {neutral ? "" : up ? "▲ " : "▼ "}
          {magnitude}
        </span>
        <span className="text-[var(--tessera-text-muted)]">{vs}</span>
      </div>
      {href ? (
        <ArrowUpRight className="pointer-events-none absolute right-2 bottom-2 z-20 h-3 w-3 text-[var(--tessera-text-muted)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </div>
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

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd
        className={cn(
          "min-w-0 truncate text-right text-[var(--tessera-text)]",
          mono && "font-mono text-[0.64rem]",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function ViewAll({ label, onClick }: { label: string; onClick?: () => void }) {
  if (!onClick) return null;
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium text-[var(--tessera-fg-info)] hover:text-[var(--tessera-fg-info)]"
    >
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
      <Truncate full={label}>{label}</Truncate>
    </span>
  );
}
