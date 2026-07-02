"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  CheckCircle2,
  ChevronRight,
  Database,
  Download,
  KeyRound,
  Plug,
  Save,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { fetchParametersOverview } from "@/lib/api/client";
import type { ParametersOverview as ParametersData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const PARAM_STATUS: Record<string, string> = {
  active: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  draft: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  deprecated: "border-red-500/30 bg-red-500/15 text-red-300",
};
const CAT_ICON: Record<string, typeof ShieldCheck> = {
  security_policies: ShieldCheck,
  data_retention: Database,
  models_ai: Sparkles,
  authentication: KeyRound,
  notifications: Bell,
  integrations: Plug,
};
const TABS = [
  "overview",
  "general",
  "security",
  "data",
  "models",
  "access",
  "notifications",
  "integrations",
  "audit",
  "system",
] as const;

type T = ReturnType<typeof useTranslations<"parameters">>;
type Data = ParametersData;

/** ⓘ for a parameters KPI/section, reading parameters.explain.<k>.{what,how,source?}. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("parameters.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

export function ParametersOverview() {
  const t = useTranslations("parameters");
  const locale = useLocale();
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]>("overview");
  const { data } = useQuery({
    queryKey: ["parameters-overview", locale],
    queryFn: ({ signal }) => fetchParametersOverview(locale, signal),
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
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} activeTab={activeTab} onSelect={setActiveTab} />
      <ConfigVersionBar t={t} data={data} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((kpi) => (
          <CompactKpi
            key={kpi.key}
            kpi={kpi}
            label={t(`kpi.${kpi.key}`)}
            info={<ExplainInfo k={kpi.key} title={t(`kpi.${kpi.key}`)} />}
          />
        ))}
      </div>

      {activeTab === "overview" ? (
        <div
          id="parameters-tabpanel"
          role="tabpanel"
          aria-labelledby="parameters-tab-overview"
          className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_320px]"
        >
          <div className="flex min-w-0 flex-col gap-3">
            <QuickConfig t={t} data={data} />
            <RecentParams t={t} data={data} />
            <ModelsConfigured t={t} data={data} />
            <UsagePolicies t={t} data={data} />
          </div>
          <aside className="flex min-w-0 flex-col gap-3">
            <ConfigState t={t} data={data} />
            <Compliance t={t} data={data} />
            <Backup t={t} data={data} />
          </aside>
        </div>
      ) : (
        <CategoryView t={t} data={data} tab={activeTab} />
      )}

      <Footer t={t} data={data} />
    </div>
  );
}

/** A single config category (one of the CommandBar tabs): its real settings +
 *  the sections relevant to it. Categories with no real source (Notifications)
 *  render an honest empty state, never fabricated content. */
function CategoryView({ t, data, tab }: { t: T; data: Data; tab: (typeof TABS)[number] }) {
  let extra: ReactNode = null;
  if (tab === "models") extra = <ModelsConfigured t={t} data={data} />;
  else if (tab === "security")
    extra = (
      <>
        <UsagePolicies t={t} data={data} />
        <Compliance t={t} data={data} />
      </>
    );
  else if (tab === "audit") extra = <Compliance t={t} data={data} />;
  else if (tab === "system")
    extra = (
      <>
        <ConfigState t={t} data={data} />
        <Backup t={t} data={data} />
      </>
    );
  else if (tab === "general") extra = <QuickConfig t={t} data={data} />;
  return (
    <div
      id="parameters-tabpanel"
      role="tabpanel"
      aria-labelledby={`parameters-tab-${tab}`}
      className="flex min-w-0 flex-col gap-3"
    >
      <RecentParams t={t} data={data} category={tab} title={t(`tabs.${tab}`)} />
      {extra}
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({
  t,
  activeTab,
  onSelect,
}: {
  t: T;
  activeTab: (typeof TABS)[number];
  onSelect: (tab: (typeof TABS)[number]) => void;
}) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div
        role="tablist"
        aria-label={t("title")}
        className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5"
      >
        {TABS.map((tab) => {
          const active = tab === activeTab;
          return (
            <button
              key={tab}
              type="button"
              role="tab"
              id={`parameters-tab-${tab}`}
              aria-selected={active}
              aria-controls="parameters-tabpanel"
              onClick={() => onSelect(tab)}
              className={cn(
                "h-8 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors",
                active
                  ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
                  : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {t(`tabs.${tab}`)}
            </button>
          );
        })}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <Download className="h-4 w-4" /> {t("actions.export")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <UploadCloud className="h-4 w-4" /> {t("actions.import")}
        </Button>
        <Button
          size="sm"
          className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
        >
          <Save className="h-4 w-4" /> {t("actions.save")}
        </Button>
      </div>
    </section>
  );
}

function ConfigVersionBar({ t, data }: { t: T; data: Data }) {
  const c = data.config_version;
  return (
    <section className="flex min-h-[48px] shrink-0 flex-wrap items-center gap-x-5 gap-y-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="text-[var(--tessera-text-muted)]">
        {t("version.active")}{" "}
        <span className="font-mono font-semibold text-[var(--tessera-text)]">{c.version}</span>
      </span>
      <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/15 px-1.5 py-0.5 text-[0.62rem] text-emerald-300">
        {c.env}
      </span>
      <Sep />
      <KvInline label={t("version.activeSince")} value={c.active_since} />
      <Sep />
      <KvInline label={t("version.modifiedBy")} value={c.modified_by} />
      <Sep />
      <span className="inline-flex items-center gap-1 text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" /> {c.validation}
      </span>
      <span className="ml-auto text-[var(--tessera-text-muted)]">
        {t("version.nextReview")}:{" "}
        <span className="text-[var(--tessera-text)]">{c.next_review}</span>
      </span>
    </section>
  );
}

function CompactKpi({
  kpi,
  label,
  info,
}: { kpi: Data["kpis"][number]; label: string; info?: ReactNode }) {
  return (
    <div className="flex h-[96px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 text-[0.66rem] font-medium text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
      </p>
      <p className="mt-0.5 text-[1.4rem] font-semibold leading-none text-white">{kpi.value}</p>
      <p className="mt-0.5 truncate text-[0.58rem] text-[var(--tessera-text-muted)]">{kpi.sub}</p>
      <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
    </div>
  );
}

// ── left column ──────────────────────────────────────────────────────────────

function QuickConfig({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("quick.title")} action={<ViewAll label={t("quick.customize")} />}>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {data.categories.map((c) => {
          const Icon = CAT_ICON[c.key] ?? ShieldCheck;
          return (
            <div
              key={c.key}
              className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
            >
              <div className="flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5 shrink-0 text-[#87bfff]" />
                <span className="truncate text-[0.74rem] font-medium text-[var(--tessera-text)]">
                  {t(`cat.${c.key}`)}
                </span>
              </div>
              <p className="line-clamp-2 text-[0.6rem] leading-tight text-[var(--tessera-text-muted)]">
                {c.desc}
              </p>
              <button
                type="button"
                className="mt-auto self-start text-[0.62rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]"
              >
                {t("quick.configure")} →
              </button>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function RecentParams({
  t,
  data,
  category,
  title,
}: { t: T; data: Data; category?: string; title?: string }) {
  const cols = ["name", "category", "value", "modifiedBy", "date", "status"] as const;
  const rows = category
    ? data.recent_params.filter((p) => p.category === category)
    : data.recent_params;
  return (
    <Panel
      title={title ?? t("recent.title")}
      action={<ViewAll label={t("drill.audit")} href="/prouver/audit-logs" />}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                  {t(`col.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={cols.length}
                  className="px-2 py-5 text-center text-[var(--tessera-text-muted)]"
                >
                  {t("recent.empty")}
                </td>
              </tr>
            ) : (
              rows.map((p) => (
                <tr
                  key={p.name}
                  className="border-b border-[var(--tessera-border)]/60 last:border-0"
                >
                  <td className="px-2 py-1.5 font-mono text-[0.66rem] text-[var(--tessera-text)]">
                    {p.name}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {t(`tabs.${p.category}`)}
                  </td>
                  <td className="px-2 py-1.5 font-mono text-[0.66rem] text-[#87bfff]">{p.value}</td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{p.modified_by}</td>
                  <td className="whitespace-nowrap px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {p.date}
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={PARAM_STATUS[p.status]}>{t(`paramStatus.${p.status}`)}</Badge>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function UsagePolicies({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("usage.title")}>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {data.usage_policies.map((p) => (
          <li
            key={p.name}
            className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.68rem]"
          >
            <span className="min-w-0 truncate text-[var(--tessera-text)]">{p.name}</span>
            <span className="shrink-0 font-mono text-[0.62rem] text-[#87bfff]">{p.value}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

const MODEL_STATUS: Record<string, string> = {
  active: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  available:
    "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
};

function ModelsConfigured({ t, data }: { t: T; data: Data }) {
  const models = data.models_configured;
  const cols = ["colName", "colProvider", "colRole", "colStatus"] as const;
  return (
    <Panel
      title={t("models.title", { n: models.length })}
      action={<ViewAll label={t("models.manage")} href="/configurer/modeles" />}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                  {t(`models.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={m.name} className="border-b border-[var(--tessera-border)]/60 last:border-0">
                <td className="px-2 py-1.5 font-mono text-[0.66rem] text-[var(--tessera-text)]">
                  {m.name}
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{m.provider}</td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                  {t(`models.${m.role}`)}
                </td>
                <td className="px-2 py-1.5">
                  <Badge className={MODEL_STATUS[m.status]}>{t(`models.${m.status}`)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ── right column ─────────────────────────────────────────────────────────────

function ConfigState({ t, data }: { t: T; data: Data }) {
  const cs = data.config_state;
  const sum = cs.slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <Panel
      title={t("state.title")}
      info={<ExplainInfo k="configState" title={t("state.title")} />}
      action={<ViewAll label={t("state.viewDetail")} />}
    >
      <div className="flex items-center gap-3">
        <div className="relative h-[92px] w-[92px] shrink-0">
          <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle
              cx="36"
              cy="36"
              r={R}
              fill="none"
              stroke="var(--tessera-border)"
              strokeWidth="9"
            />
            {cs.slices.map((s) => {
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
            <span className="text-base font-semibold tabular-nums text-white">{cs.total}</span>
            <span className="text-[0.46rem] uppercase text-[var(--tessera-text-muted)]">Total</span>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.64rem]">
          {cs.slices.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                {t(`state.${s.key}`)}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {s.pct}% ({s.count})
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function Compliance({ t, data }: { t: T; data: Data }) {
  return (
    <Panel
      title={t("compliance.title")}
      action={<ViewAll label={t("compliance.viewAll")} href="/surveiller/conformite" />}
    >
      <ul className="flex flex-col gap-1.5">
        {data.compliance.map((c) => (
          <li key={c.key} className="flex items-center gap-2 text-[0.7rem]">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
              {t(`compliance.${c.key}`)}
            </span>
            <span className="shrink-0 text-emerald-300">{t("compliance.conform")}</span>
            <button type="button" className="shrink-0 text-[#87bfff]">
              {t("compliance.view")}
            </button>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Backup({ t, data }: { t: T; data: Data }) {
  const b = data.backup;
  const rows: [string, string][] = [
    [t("backup.last"), b.last_backup],
    [t("backup.frequency"), b.frequency],
    [t("backup.retention"), b.retention],
    [t("backup.size"), b.size],
  ];
  return (
    <Panel title={t("backup.title")}>
      <dl className="flex flex-col gap-1.5 text-[0.7rem]">
        {rows.map(([k, v]) => (
          <KV key={k} label={k} value={v} />
        ))}
      </dl>
    </Panel>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Panel({
  title,
  info,
  action,
  children,
}: { title: string; info?: ReactNode; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex min-w-0 items-center gap-1 text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
          <span className="min-w-0 truncate">{title}</span>
          {info}
        </h3>
        {action}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
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

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0 truncate text-right text-[var(--tessera-text)]">{value}</dd>
    </div>
  );
}

function KvInline({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-[var(--tessera-text-muted)]">
      {label}: <span className="text-[var(--tessera-text)]">{value}</span>
    </span>
  );
}

function Sep() {
  return <span className="hidden text-[var(--tessera-border-strong)] sm:inline">·</span>;
}

function ViewAll({ label, href }: { label: string; href?: Route }) {
  const cls =
    "flex shrink-0 items-center gap-0.5 text-[0.64rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]";
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

function Footer({ t, data }: { t: T; data: Data }) {
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span>{t("footer.version", { v: data.footer.version })}</span>
      <span>{t("footer.source", { src: data.footer.source })}</span>
    </footer>
  );
}
