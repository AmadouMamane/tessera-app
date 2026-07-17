"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ChevronRight,
  Clock3,
  Database,
  Download,
  FileSearch,
  GitCompare,
  Plus,
  RefreshCcw,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useState } from "react";

import { downloadBlob } from "@/components/agent/agent-subtab-shared";
import { AgirRail, useAsOf } from "@/components/agir/agir-rail";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { SyntheticNotice } from "@/components/cockpit/synthetic-notice";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { fetchReplayShadowOverview } from "@/lib/api/client";
import type { ReplayShadowOverview } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const SEV_TEXT: Record<string, string> = {
  critique: "text-red-300",
  eleve: "text-amber-300",
  moyen: "text-yellow-300",
  faible: "text-sky-300",
};
const STATUS_BADGE: Record<string, string> = {
  rejouee: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  termine: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  encours: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  error: "border-red-500/30 bg-red-500/15 text-red-300",
};

const TABS = [
  "overview",
  "sessions",
  "shadow",
  "comparisons",
  "baselines",
  "diffs",
  "evals",
  "exports",
] as const;
type Tab = (typeof TABS)[number];

type T = ReturnType<typeof useTranslations<"replay">>;
type Data = ReplayShadowOverview;

/** ⓘ for a replay metric/section, reading replay.explain.<k>.{what,how,source?}.
 * Renders nothing when no explanation exists for the key (e.g. unmapped KPI). */
function Info({ k, title }: { k: string; title: string }) {
  const te = useTranslations("replay.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te.has(`${k}.how`) ? te(`${k}.how`) : undefined}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

export function ReplayOverview() {
  const t = useTranslations("replay");
  const locale = useLocale();
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  // AGIR composition (registre §6): As-of reads the folded captures/diffs at T.
  const asof = useAsOf();
  const { data } = useQuery({
    queryKey: ["replay-shadow-overview", locale, asof],
    queryFn: ({ signal }) => fetchReplayShadowOverview(locale, asof, signal),
    staleTime: 30_000,
    refetchInterval: asof ? false : 30_000,
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
      <CommandBar t={t} active={activeTab} onSelect={setActiveTab} />
      {/* AGIR / Replay is XT-01's home (registre): the rail keeps the legitimate
          execution-replay cassette (début · précédent · play/pause · suivant · fin).
          SURVEILLER surfaces stay on the default "signal" event navigation. */}
      {/* Registre §6/§8 — AGIR composes As-of + Live: captures, executions and
          run diffs fold to T server-side. */}
      <AgirRail />

      <div id="replay-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-3">
        {activeTab === "sessions" ? (
          <div className="grid gap-3 xl:grid-cols-12">
            <RecentSessions t={t} data={data} className="xl:col-span-7" />
            <TrafficChart t={t} data={data} className="xl:col-span-5" />
          </div>
        ) : null}
        {activeTab === "shadow" ? (
          <div className="flex min-w-0 flex-col gap-2">
            <SyntheticNotice signalId="shadow_traffic" compact />
            <Panel title={t("tabs.shadow")}>
              <p className="text-xs leading-relaxed text-[var(--tessera-text-muted)]">
                {t("tabx.shadowExplain")}
              </p>
            </Panel>
          </div>
        ) : null}
        {activeTab === "comparisons" ? (
          <div className="grid gap-3 xl:grid-cols-12">
            <Comparisons t={t} data={data} className="xl:col-span-6" />
            <Regressions t={t} data={data} className="xl:col-span-6" />
          </div>
        ) : null}
        {activeTab === "baselines" ? <BaselinesPanel t={t} data={data} /> : null}
        {activeTab === "diffs" ? (
          <div className="grid gap-3 xl:grid-cols-12">
            <TopDeviations t={t} data={data} className="xl:col-span-8" />
            <Panel
              title={t("panel.devByType")}
              info={<Info k="panel.devByType" title={t("panel.devByType")} />}
              className="xl:col-span-2"
            >
              <Donut
                slices={data.deviation_by_type}
                total={data.deviation_total}
                caption={t("legend.critical")}
                labelOf={(k) => t(`type.${k}`)}
              />
            </Panel>
            <Panel
              title={t("panel.severity")}
              info={<Info k="panel.severity" title={t("panel.severity")} />}
              className="xl:col-span-2"
            >
              <Donut
                slices={data.deviation_severity}
                total={data.deviation_total}
                caption={t("legend.critical")}
                labelOf={(k) => t(`severity.${k}`)}
              />
            </Panel>
          </div>
        ) : null}
        {activeTab === "evals" ? (
          <div className="grid gap-3 xl:grid-cols-12">
            <EvalsByCategory t={t} data={data} className="xl:col-span-4" />
            <Comparisons t={t} data={data} className="xl:col-span-8" />
          </div>
        ) : null}
        {activeTab === "exports" ? (
          <div className="flex min-w-0 flex-col gap-2">
            <SyntheticNotice signalId="shadow_traffic" compact />
            <ProofsExports t={t} data={data} />
          </div>
        ) : null}
      </div>

      {activeTab !== "overview" ? null : (
        <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_312px]">
          <div className="flex min-w-0 flex-col gap-3">
            {/* A · État actuel */}
            <Zone label={t("zone.actual")} info={<Info k="zone.actual" title={t("zone.actual")} />}>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
                {data.kpis.map((kpi) => (
                  <KpiTile
                    key={kpi.key}
                    kpi={kpi}
                    label={t(`kpi.${kpi.key}`)}
                    vs={t("delta.vs7d")}
                    info={<Info k={`kpi.${kpi.key}`} title={t(`kpi.${kpi.key}`)} />}
                  />
                ))}
              </div>
            </Zone>

            {/* B · Diagnostic des écarts */}
            <Zone
              label={t("zone.diagnostic")}
              info={<Info k="zone.diagnostic" title={t("zone.diagnostic")} />}
            >
              <div className="grid gap-3 xl:grid-cols-12">
                <TrafficChart t={t} data={data} className="xl:col-span-4" />
                <Panel
                  title={t("panel.devByType")}
                  info={<Info k="panel.devByType" title={t("panel.devByType")} />}
                  className="xl:col-span-2"
                >
                  <Donut
                    slices={data.deviation_by_type}
                    total={data.deviation_total}
                    caption={t("legend.critical")}
                    labelOf={(k) => t(`type.${k}`)}
                  />
                </Panel>
                <Panel
                  title={t("panel.severity")}
                  info={<Info k="panel.severity" title={t("panel.severity")} />}
                  className="xl:col-span-2"
                >
                  <Donut
                    slices={data.deviation_severity}
                    total={data.deviation_total}
                    caption={t("legend.critical")}
                    labelOf={(k) => t(`severity.${k}`)}
                  />
                </Panel>
                <RecentSessions
                  t={t}
                  data={data}
                  className="xl:col-span-4"
                  onViewAll={() => setActiveTab("sessions")}
                />
              </div>
            </Zone>

            {/* C · Écarts & comparaisons */}
            <Zone
              label={t("zone.comparisons")}
              info={<Info k="zone.comparisons" title={t("zone.comparisons")} />}
            >
              <div className="grid gap-3 xl:grid-cols-12">
                <TopDeviations
                  t={t}
                  data={data}
                  className="xl:col-span-6"
                  onViewAll={() => setActiveTab("diffs")}
                />
                <Comparisons
                  t={t}
                  data={data}
                  className="xl:col-span-3"
                  onViewAll={() => setActiveTab("comparisons")}
                />
                <Regressions t={t} data={data} className="xl:col-span-3" />
              </div>
            </Zone>

            {/* D · Distribution & preuves */}
            <Zone
              label={t("zone.distribution")}
              info={<Info k="zone.distribution" title={t("zone.distribution")} />}
            >
              <div className="grid gap-3 xl:grid-cols-12">
                <Panel
                  title={t("panel.byService")}
                  info={<Info k="panel.byService" title={t("panel.byService")} />}
                  className="xl:col-span-3"
                >
                  <Donut
                    slices={data.by_service}
                    total={data.requests_total}
                    caption={t("kpi.requests").toLowerCase()}
                    labelOf={(k) => (t.has(`service.${k}`) ? t(`service.${k}`) : k)}
                    showCount
                  />
                </Panel>
                <Panel
                  title={t("panel.byModel")}
                  info={<Info k="panel.byModel" title={t("panel.byModel")} />}
                  className="xl:col-span-3"
                >
                  <Donut
                    slices={data.by_model}
                    total={data.requests_total}
                    caption={t("kpi.requests").toLowerCase()}
                    labelOf={(k) => (t.has(`model.${k}`) ? t(`model.${k}`) : k)}
                    showCount
                  />
                </Panel>
                <EvalsByCategory
                  t={t}
                  data={data}
                  className="xl:col-span-2"
                  onViewAll={() => setActiveTab("evals")}
                />
                <ProofsExports
                  t={t}
                  data={data}
                  className="xl:col-span-2"
                  onViewAll={() => setActiveTab("exports")}
                />
                <QuickActions t={t} data={data} className="xl:col-span-2" />
              </div>
            </Zone>
          </div>

          <ReplayRail t={t} data={data} />
        </div>
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
            aria-controls="replay-tabpanel"
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
      <Button
        size="sm"
        variant="outline"
        onClick={() => onSelect("comparisons")}
        className="h-9 shrink-0 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
      >
        <GitCompare className="h-4 w-4" /> {t("rail.compareBaseline")}
      </Button>
    </section>
  );
}

function BaselinesPanel({ t, data }: { t: T; data: Data }) {
  return (
    <Panel
      title={t("tabx.baselinesTitle")}
      info={<Info k="panel.baselines" title={t("tabx.baselinesTitle")} />}
    >
      {data.baselines.length === 0 ? (
        <p className="py-6 text-center text-xs text-[var(--tessera-text-muted)]">
          {t("tabx.baselinesEmpty")}
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.baselines.map((b) => (
            <li
              key={b.value}
              className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-xs"
            >
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{b.label}</span>
              <span className="shrink-0 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                {b.value}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ── zone B ───────────────────────────────────────────────────────────────────

function TrafficChart({ t, data, className }: { t: T; data: Data; className?: string }) {
  const tr = data.replay_traffic;
  const niceMax = (v: number, step: number) => Math.max(step, Math.ceil(v / step) * step);
  const reqMax = niceMax(Math.max(...tr.requests, 1), 4);
  const tokMax = niceMax(Math.max(...tr.tokens, 1), 4);
  const fracs = [1, 0.75, 0.5, 0.25, 0];
  const W = 240;
  const H = 112;
  const top = 6;
  const n = tr.requests.length;
  const bw = (W / n) * 0.46;
  const y = (v: number, max: number) => top + (1 - v / max) * (H - top);
  const line = tr.tokens.map((v, i) => `${((i + 0.5) / n) * W},${y(v, tokMax)}`).join(" ");
  return (
    <Panel
      title={t("panel.traffic")}
      info={<Info k="panel.traffic" title={t("panel.traffic")} />}
      className={className}
    >
      <div className="flex flex-col gap-1">
        <div className="flex gap-1">
          <div className="flex w-7 flex-col justify-between py-[5px] text-right text-[0.5rem] tabular-nums text-[var(--tessera-text-muted)]">
            {fracs.map((f) => (
              <span key={f}>{Math.round(f * reqMax)}</span>
            ))}
          </div>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            className="h-[120px] min-w-0 flex-1"
            aria-hidden="true"
          >
            {fracs.map((f) => (
              <line
                key={f}
                x1="0"
                x2={W}
                y1={top + f * (H - top)}
                y2={top + f * (H - top)}
                stroke="var(--tessera-border)"
                strokeWidth="1"
                vectorEffect="non-scaling-stroke"
                opacity="0.5"
              />
            ))}
            {tr.requests.map((v, i) => {
              const yy = y(v, reqMax);
              return (
                <rect
                  // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length daily series never reorders
                  key={i}
                  x={((i + 0.5) / n) * W - bw / 2}
                  y={yy}
                  width={bw}
                  height={H - yy}
                  rx="1.5"
                  fill="#2e72d2"
                  opacity="0.8"
                />
              );
            })}
            <polyline
              points={line}
              fill="none"
              stroke="#34d399"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div className="flex w-7 flex-col justify-between py-[5px] text-left text-[0.5rem] tabular-nums text-[var(--tessera-text-muted)]">
            {fracs.map((f) => (
              <span key={f}>{Math.round(f * tokMax)}</span>
            ))}
          </div>
        </div>
        <div className="flex justify-between pl-8 pr-8 text-[0.55rem] tabular-nums text-[var(--tessera-text-muted)]">
          {tr.labels.map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
        <div className="flex items-center gap-3 pl-8 text-[0.6rem] text-[var(--tessera-text-muted)]">
          <Legend color="#2e72d2" label={t("legend.requests")} />
          <Legend color="#34d399" label={t("legend.tokens")} />
        </div>
      </div>
    </Panel>
  );
}

function RecentSessions({
  t,
  data,
  className,
  onViewAll,
}: { t: T; data: Data; className?: string; onViewAll?: () => void }) {
  return (
    <Panel
      title={t("panel.recentSessions")}
      info={<Info k="panel.recentSessions" title={t("panel.recentSessions")} />}
      className={className}
      action={<ViewAll label={t("viewAll.all")} onClick={onViewAll} />}
    >
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("col.id")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.service")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.model")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.status")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.origin")}</th>
          </tr>
        </thead>
        <tbody>
          {data.recent_sessions.map((s) => (
            <tr key={s.id} className="border-b border-[var(--tessera-border)]/60 last:border-0">
              <td className="px-1.5 py-1 font-mono text-[#87bfff]">{s.id}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text)]">{s.service}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{s.model}</td>
              <td className="px-1.5 py-1">
                <StatusBadge status={s.status} t={t} />
              </td>
              <td className="px-1.5 py-1 tabular-nums text-[var(--tessera-text-muted)]">
                {s.origin}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// ── zone C ───────────────────────────────────────────────────────────────────

function TopDeviations({
  t,
  data,
  className,
  onViewAll,
}: { t: T; data: Data; className?: string; onViewAll?: () => void }) {
  return (
    <Panel
      title={t("panel.topDeviations")}
      info={<Info k="panel.topDeviations" title={t("panel.topDeviations")} />}
      className={className}
      action={<ViewAll label={t("viewAll.deviations")} onClick={onViewAll} />}
    >
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("col.id")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.service")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.type")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.baseline")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.severity")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("col.delta")}</th>
          </tr>
        </thead>
        <tbody>
          {data.top_deviations.map((d) => (
            <tr
              key={`${d.id}-${d.type}`}
              className="border-b border-[var(--tessera-border)]/60 last:border-0"
            >
              <td className="px-1.5 py-1 font-mono text-[#87bfff]">{d.id}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text)]">{d.service}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">
                {t(`type.${d.type}`)}
              </td>
              <td className="px-1.5 py-1 font-mono text-[0.64rem] text-[var(--tessera-text-muted)]">
                {d.baseline}
              </td>
              <td className={cn("px-1.5 py-1 font-medium", SEV_TEXT[d.severity])}>
                {t(`severity.${d.severity}`)}
              </td>
              <td className="px-1.5 py-1 text-right font-mono tabular-nums text-red-300">
                {d.delta}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Comparisons({
  t,
  data,
  className,
  onViewAll,
}: { t: T; data: Data; className?: string; onViewAll?: () => void }) {
  return (
    <Panel
      title={t("panel.comparisons")}
      info={<Info k="panel.comparisons" title={t("panel.comparisons")} />}
      className={className}
      action={<ViewAll label={t("viewAll.comparisons")} onClick={onViewAll} />}
    >
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("col.comparison")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("col.sessions")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("col.deviations")}</th>
          </tr>
        </thead>
        <tbody>
          {data.recent_comparisons.map((c) => (
            <tr key={c.label} className="border-b border-[var(--tessera-border)]/60 last:border-0">
              <td className="px-1.5 py-1 font-mono text-[0.64rem] text-[var(--tessera-text)]">
                {c.label}
              </td>
              <td className="px-1.5 py-1 text-right tabular-nums text-[var(--tessera-text-muted)]">
                {c.sessions}
              </td>
              <td className="px-1.5 py-1 text-right tabular-nums text-amber-300">{c.deviations}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Regressions({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("panel.regressions")}
      info={<Info k="panel.regressions" title={t("panel.regressions")} />}
      className={className}
      action={
        <Link
          href="/surveiller/fiabilite-cout"
          className="inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap text-[0.62rem] text-[var(--tessera-green)] hover:underline"
        >
          {t("viewAll.regressions")}
          <ChevronRight className="h-3 w-3" />
        </Link>
      }
    >
      <ul className="flex flex-col gap-1.5">
        {data.top_regressions.map((r) => (
          <li key={r.service} className="flex items-center gap-2 text-[0.7rem]">
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{r.service}</span>
            <span className="font-mono tabular-nums text-red-300">{r.delta}</span>
            <MetricSparkline className="h-4 w-12" values={r.spark} tone="danger" />
            <span className="w-7 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {r.critical}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── zone D ───────────────────────────────────────────────────────────────────

function EvalsByCategory({
  t,
  data,
  className,
  onViewAll,
}: { t: T; data: Data; className?: string; onViewAll?: () => void }) {
  const max = Math.max(...data.evals_by_category.map((c) => c.pct), 1);
  return (
    <Panel
      title={t("panel.evalsByCat")}
      info={<Info k="panel.evalsByCat" title={t("panel.evalsByCat")} />}
      className={className}
      action={<ViewAll label={t("viewAll.categories")} onClick={onViewAll} />}
    >
      <ul className="flex flex-col gap-2">
        {data.evals_by_category.map((c) => (
          <li key={c.key} className="flex items-center gap-2 text-[0.68rem]">
            <span className="w-24 shrink-0 truncate text-[var(--tessera-text)]">
              {t(`type.${c.key}`)}
            </span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(c.pct / max) * 100}%`, background: c.color }}
              />
            </div>
            <span className="w-12 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {c.count} · {c.pct}%
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function ProofsExports({
  t,
  data,
  className,
  onViewAll,
}: { t: T; data: Data; className?: string; onViewAll?: () => void }) {
  // Export subsystem — flagged demonstration (shadow_traffic).
  const p = data.proofs_exports;
  const rows: [string, string][] = [
    [t("proofs.generated"), p.generated],
    [t("proofs.available"), p.available],
    [t("proofs.downloaded"), p.downloaded],
    [t("proofs.totalSize"), p.total_size],
    [t("proofs.lastExport"), p.last_export],
  ];
  return (
    <Panel
      title={t("panel.proofsExports")}
      info={<Info k="panel.proofsExports" title={t("panel.proofsExports")} />}
      className={className}
      action={<ViewAll label={t("exportBtn.all")} onClick={onViewAll} />}
    >
      <SyntheticNotice signalId="shadow_traffic" compact />
      <dl className="flex flex-col gap-1.5 text-[0.7rem]">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{k}</dt>
            <dd className="tabular-nums text-[var(--tessera-text)]">{v}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function QuickActions({ t, data, className }: { t: T; data: Data; className?: string }) {
  const tc = useTranslations("common");
  const items = [
    { key: "replaySession", icon: RefreshCcw },
    { key: "compareBaseline", icon: GitCompare },
    { key: "createBaseline", icon: Plus },
    { key: "exportResults", icon: Download, export: true },
    { key: "scheduleReplay", icon: Clock3 },
    { key: "viewLog", icon: FileSearch, href: "/prouver/audit-logs" },
  ] as const;
  return (
    <Panel title={t("panel.quickActions")} className={className}>
      <ul className="flex flex-col gap-1">
        {items.map((it) => (
          <li key={it.key}>
            <RailButton
              icon={it.icon}
              label={t(`quick.${it.key}`)}
              href={"href" in it ? it.href : undefined}
              onClick={
                "export" in it
                  ? () =>
                      downloadBlob(
                        "tessera-replay.json",
                        "application/json",
                        JSON.stringify(data, null, 2),
                      )
                  : undefined
              }
              disabledTitle={tc("notWired")}
            />
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── right rail ───────────────────────────────────────────────────────────────

function ReplayRail({ t, data }: { t: T; data: Data }) {
  const tc = useTranslations("common");
  return (
    <aside className="flex min-w-0 flex-col gap-3">
      <Panel title={t("rail.compareBaseline")}>
        <div className="flex flex-col gap-2">
          <Select options={data.baselines.map((b) => b.label)} disabled title={tc("notWired")} />
          <Select
            options={[t("rail.allServices"), ...data.services]}
            disabled
            title={tc("notWired")}
          />
          <span title={tc("notWired")}>
            <Button
              size="sm"
              disabled
              className="h-9 w-full justify-center gap-2 border border-[#2e72d2] bg-[#1b4f8a] text-xs text-[#d8eaff] hover:bg-[#22609f]"
            >
              <RefreshCcw className="h-4 w-4" /> {t("rail.replayNow")}
            </Button>
          </span>
        </div>
      </Panel>

      <Panel title={t("rail.shortcuts")}>
        <div className="flex flex-wrap gap-1.5">
          {[t("rail.now"), "24h", "7j", "30j", t("rail.custom")].map((s, i) => (
            <button
              key={s}
              type="button"
              className={cn(
                "h-7 rounded-md border px-2.5 text-[0.66rem] font-medium transition-colors",
                i === 2
                  ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
                  : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </Panel>

      <Panel
        title={t("rail.activity")}
        info={<Info k="panel.activity" title={t("rail.activity")} />}
        action={<ViewAll label={t("rail.viewJournal")} href="/prouver/audit-logs" />}
      >
        <ul className="flex flex-col gap-1.5">
          {data.activity_feed.map((a) => (
            <li key={`${a.id}-${a.time}`} className="flex items-center gap-2 text-[0.7rem]">
              <span
                className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  a.status === "error"
                    ? "bg-red-400"
                    : a.status === "termine"
                      ? "bg-emerald-400"
                      : "bg-sky-400",
                )}
              />
              <span className="font-mono text-[0.66rem] text-[#87bfff]">{a.id}</span>
              <span className="ml-auto tabular-nums text-[var(--tessera-text-muted)]">
                {a.time}
              </span>
              <StatusBadge status={a.status} t={t} />
            </li>
          ))}
        </ul>
      </Panel>
    </aside>
  );
}

// ── footer ───────────────────────────────────────────────────────────────────

function Footer({ t, data }: { t: T; data: Data }) {
  const f = data.footer;
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <Chip
        icon={Activity}
        tone="text-[var(--tessera-green)]"
        label={t("footer.environment", { env: f.environment })}
      />
      <Chip icon={GitCompare} label={t("footer.services", { n: f.services })} />
      <Chip icon={Users} label={t("footer.activeUsers", { n: f.active_users })} />
      <Chip
        icon={ShieldCheck}
        tone="text-[var(--tessera-green)]"
        label={t("footer.confidence", { level: f.confidence })}
      />
      <Chip icon={ShieldCheck} tone="text-[var(--tessera-green)]" label={t("footer.chain")} />
      <Chip icon={Database} label={t("footer.source", { src: f.source })} />
      <Chip icon={ShieldCheck} tone="text-[var(--tessera-green)]" label={t("footer.soc")} />
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Zone({ label, info, children }: { label: string; info?: ReactNode; children: ReactNode }) {
  return (
    <section className="shrink-0 rounded-xl border border-[var(--tessera-border)]/60 bg-[var(--tessera-surface)]/20 p-2.5">
      <h2 className="mb-2 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {label}
        {info}
      </h2>
      {children}
    </section>
  );
}

function Panel({
  title,
  info,
  action,
  children,
  className,
}: {
  title: string;
  info?: ReactNode;
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
        <h3 className="flex min-w-0 items-center gap-1 text-[0.8rem] font-semibold text-[var(--tessera-text)]">
          <span className="min-w-0 truncate">{title}</span>
          {info}
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
  info,
}: {
  kpi: Data["kpis"][number];
  label: string;
  vs: string;
  info?: ReactNode;
}) {
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
  slices: Data["deviation_by_type"];
  total: number | string;
  caption: string;
  labelOf: (key: string) => string;
  showCount?: boolean;
}) {
  const sum = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 39;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[104px] w-[104px] shrink-0">
        <svg viewBox="0 0 104 104" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="52"
            cy="52"
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
                cx="52"
                cy="52"
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
        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden text-center">
          <span className="max-w-[52px] truncate text-sm font-semibold leading-none tabular-nums text-white">
            {total}
          </span>
          <span className="line-clamp-2 max-w-[52px] break-words px-1 text-[0.46rem] uppercase leading-tight text-[var(--tessera-text-muted)]">
            {caption}
          </span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex flex-col gap-0.5">
            <span className="flex min-w-0 items-center gap-1">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 truncate text-[var(--tessera-text)]">{labelOf(s.key)}</span>
            </span>
            <span className="pl-2.5 tabular-nums text-[var(--tessera-text-muted)]">
              {showCount ? `${s.count.toLocaleString("fr-FR")} · ` : ""}
              {s.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StatusBadge({ status, t }: { status: string; t: T }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.58rem] font-medium",
        STATUS_BADGE[status],
      )}
    >
      {t(`status.${status}`)}
    </span>
  );
}

function Select({
  options,
  disabled,
  title,
}: { options: string[]; disabled?: boolean; title?: string }) {
  return (
    <div className="relative" title={title}>
      <select
        disabled={disabled}
        className={cn(
          "h-9 w-full appearance-none rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 pr-8 text-xs text-[var(--tessera-text)] outline-none",
          disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
        )}
      >
        {options.map((o) => (
          <option key={o} className="bg-[var(--tessera-surface)]">
            {o}
          </option>
        ))}
      </select>
      <ChevronRight className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 rotate-90 text-[var(--tessera-text-muted)]" />
    </div>
  );
}

function RailButton({
  icon: Icon,
  label,
  href,
  onClick,
  disabledTitle,
}: {
  icon: typeof Download;
  label: string;
  href?: Route;
  onClick?: () => void;
  disabledTitle?: string;
}) {
  const cls =
    "flex w-full items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-left text-[0.68rem] transition-colors";
  const inner = (
    <>
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
      <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{label}</span>
    </>
  );
  if (href) {
    return (
      <Link href={href} className={cn(cls, "hover:bg-[var(--tessera-muted)]")}>
        {inner}
      </Link>
    );
  }
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(cls, "hover:bg-[var(--tessera-muted)]")}
      >
        {inner}
      </button>
    );
  }
  return (
    <button
      type="button"
      disabled
      title={disabledTitle}
      className={cn(cls, "cursor-not-allowed opacity-50")}
    >
      {inner}
    </button>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-1 w-3 rounded-full" style={{ background: color }} /> {label}
    </span>
  );
}

function ViewAll({ label, href, onClick }: { label: string; href?: Route; onClick?: () => void }) {
  const cls =
    "flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]";
  if (href) {
    return (
      <Link href={href} className={cls}>
        {label} <ChevronRight className="h-3 w-3" />
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls}>
        {label} <ChevronRight className="h-3 w-3" />
      </button>
    );
  }
  return null;
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
