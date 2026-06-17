"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bot,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  FlaskConical,
  Settings2,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import type { ReactNode } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Skeleton } from "@/components/ui/skeleton";
import { Link, usePathname } from "@/i18n/navigation";
import { type AgentPage, agentPath } from "@/lib/agent-context";
import { fetchAgentSynthese } from "@/lib/api/client";
import type { AgentSynthese as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import type { OverviewTone } from "@/lib/overview";
import { useAgentId } from "@/lib/use-agent-id";

import { AgentSwitcher } from "./agent-switcher";

type T = ReturnType<typeof useTranslations<"agentSynthese">>;

const TABS: ReadonlyArray<{ page: AgentPage; labelKey: string }> = [
  { page: "synthese", labelKey: "item.vueEnsemble" },
  { page: "configurations", labelKey: "item.configurations" },
  { page: "connaissances", labelKey: "item.connaissances" },
  { page: "garde-fous", labelKey: "item.agentGuardrails" },
  { page: "prompts", labelKey: "item.prompts" },
  { page: "evaluations", labelKey: "item.evaluations" },
  { page: "historique", labelKey: "item.historique" },
];

const BAR_TONE: Record<string, string> = {
  violet: "bg-[#8b7cf0]",
  blue: "bg-[#4c8bf5]",
  amber: "bg-[#e0a23a]",
  green: "bg-emerald-500",
  cyan: "bg-cyan-500",
  slate: "bg-slate-500",
};
const KIND_DOT: Record<string, string> = {
  info: "bg-sky-400",
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
  crit: "bg-red-400",
};
const STATUS_BADGE: Record<string, string> = {
  resolu: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  escalade: "border-amber-500/30 bg-amber-500/15 text-amber-300",
};
const STATUS_LABEL: Record<string, string> = {
  resolu: "Résolu",
  escalade: "Escalade",
};
const ALERT_TONE: Record<string, string> = {
  good: "text-emerald-300",
  warn: "text-amber-300",
  crit: "text-red-300",
};

export function AgentSynthese() {
  const t = useTranslations("agentSynthese");
  const tn = useTranslations("nav");
  const pathname = usePathname();
  const agentId = useAgentId();
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const { data } = useQuery({
    queryKey: ["agent-synthese", agentId, temporal.periodKey],
    queryFn: ({ signal }) => fetchAgentSynthese(agentId, temporal.periodKey, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (data === undefined) {
    return <SyntheseSkeleton />;
  }
  if (!data.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {t("unavailable")}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <CommandBar t={t} tn={tn} pathname={pathname} agentId={agentId} />

      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("cmd.realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        onModeChange={temporal.changeMode}
      />

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
        {(data.kpis ?? []).map((k) => (
          <KpiTile key={k.key} kpi={k} />
        ))}
      </div>

      {/* Row 1 */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        <Profile data={data} className="xl:col-span-3" />
        <Capabilities data={data} className="xl:col-span-3" />
        <Topics data={data} className="xl:col-span-2" />
        <Performance data={data} className="xl:col-span-2" />
        <ConfigNow data={data} className="xl:col-span-2" />
      </div>

      {/* Row 2 */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        <Conversations data={data} className="xl:col-span-4" />
        <Activity data={data} className="xl:col-span-2" />
        <Prompts data={data} className="xl:col-span-3" />
        <Channels data={data} className="xl:col-span-3" />
      </div>

      {/* Row 3 */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        <Alerts data={data} className="xl:col-span-5" />
        <QuickConfig data={data} className="xl:col-span-4" />
        <Timeline data={data} className="xl:col-span-3" />
      </div>
    </div>
  );
}

// ── loading skeleton ─────────────────────────────────────────────────────────

const SKELETON_KPIS = ["a", "b", "c", "d", "e", "f", "g"];
const SKELETON_CARDS = ["a", "b", "c", "d"];

function SyntheseSkeleton() {
  return (
    <div className="flex flex-col gap-3 pb-2">
      <Skeleton className="h-9 w-full" />
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
        {SKELETON_KPIS.map((k) => (
          <Skeleton key={k} className="h-[112px] w-full rounded-lg" />
        ))}
      </div>
      <div className="grid gap-2.5 xl:grid-cols-12">
        {SKELETON_CARDS.map((k, i) => (
          <Skeleton
            key={k}
            className={cn("h-44 rounded-lg", i === 0 ? "xl:col-span-4" : "xl:col-span-3")}
          />
        ))}
      </div>
    </div>
  );
}

// ── chrome ─────────────────────────────────────────────────────────────────

function CommandBar({
  t,
  tn,
  pathname,
  agentId,
}: {
  t: T;
  tn: ReturnType<typeof useTranslations<"nav">>;
  pathname: string;
  agentId: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--tessera-border)] pb-1.5">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <AgentSwitcher />
        <nav className="flex min-w-0 flex-wrap items-center gap-1">
          {TABS.map((tab) => {
            const href = agentPath(agentId, tab.page);
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={tab.page}
                href={href}
                className={cn(
                  "-mb-px shrink-0 border-b-2 px-3 py-2 text-[0.8rem] transition-colors",
                  active
                    ? "border-[#6d4aed] font-medium text-[var(--tessera-text)]"
                    : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
                )}
              >
                {tn(tab.labelKey)}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <GhostLink
          icon={FlaskConical}
          label={t("actions.test")}
          href={agentPath(agentId, "evaluations")}
        />
        <Link
          href={agentPath(agentId, "configurations")}
          className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5]"
        >
          <Settings2 className="h-4 w-4" /> {t("actions.configure")}
        </Link>
      </div>
    </div>
  );
}

function GhostLink({
  icon: Icon,
  label,
  href,
}: { icon: typeof FlaskConical; label: string; href: string }) {
  return (
    <Link
      href={href as never}
      className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
    >
      <Icon className="h-4 w-4" /> {label}
    </Link>
  );
}

// ── KPI ────────────────────────────────────────────────────────────────────

function KpiTile({ kpi }: { kpi: NonNullable<Data["kpis"]>[number] }) {
  const tone: OverviewTone = kpi.good ? "success" : "danger";
  return (
    <div className="flex h-[112px] flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">{kpi.label}</p>
      <p className="mt-0.5 text-[1.35rem] font-semibold leading-none tabular-nums text-[var(--tessera-text)]">
        {kpi.value}
      </p>
      <span
        className={cn(
          "mt-1 line-clamp-1 text-[0.6rem] tabular-nums",
          kpi.good ? "text-emerald-400" : "text-red-400",
        )}
      >
        {kpi.delta}
      </span>
      <div className="mt-auto pt-1">
        <MetricSparkline values={kpi.series} tone={tone} height={26} />
      </div>
    </div>
  );
}

// ── cards ──────────────────────────────────────────────────────────────────

function Card({
  title,
  cta,
  ctaHref,
  children,
  className,
}: {
  title?: string;
  cta?: string;
  ctaHref?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      {title ? (
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta ? <CtaLink label={cta} href={ctaHref} /> : null}
    </section>
  );
}

function EmptyRow() {
  const t = useTranslations("agentSynthese");
  return <p className="py-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("empty")}</p>;
}

function CtaLink({ label, href }: { label: string; href?: string }) {
  const classes =
    "mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[#b9a6ff] hover:text-white";
  if (href) {
    return (
      <Link href={href as never} className={classes}>
        {label} <ChevronRight className="h-3.5 w-3.5" />
      </Link>
    );
  }
  return (
    <button type="button" className={classes}>
      {label} <ChevronRight className="h-3.5 w-3.5" />
    </button>
  );
}

function Profile({ data, className }: { data: Data; className?: string }) {
  const p = data.profile;
  if (!p) return null;
  return (
    <Card cta={p.cta} ctaHref={p.ctaHref} className={className}>
      <div className="flex items-center gap-3">
        <Image
          src="/brand/agent-robot.png"
          alt={p.name}
          width={90}
          height={90}
          unoptimized
          className="h-14 w-14 shrink-0 rounded-xl object-cover"
        />
        <div className="min-w-0">
          <p className="truncate text-[0.92rem] font-semibold text-[var(--tessera-text)]">
            {p.name}
          </p>
          <span className="mt-0.5 inline-flex items-center gap-1.5 text-[0.66rem] text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> {p.status}
          </span>
        </div>
      </div>
      <dl className="mt-3 flex flex-col gap-1.5 text-[0.72rem]">
        {p.fields.map((f) => (
          <div key={f.label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{f.label}</dt>
            <dd className="min-w-0 truncate font-medium text-[var(--tessera-text)]">{f.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function Capabilities({ data, className }: { data: Data; className?: string }) {
  const c = data.capabilities;
  if (!c) return null;
  return (
    <Card title={c.title} cta={c.cta} ctaHref={c.ctaHref} className={className}>
      <ul className="flex flex-col gap-2">
        {c.items.map((it) => (
          <li
            key={it}
            className="flex items-center gap-2 text-[0.74rem] text-[var(--tessera-text)]"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            <span className="min-w-0 truncate">{it}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Topics({ data, className }: { data: Data; className?: string }) {
  const tp = data.topics;
  if (!tp) return null;
  return (
    <Card title={tp.title} cta={tp.cta} ctaHref={tp.ctaHref} className={className}>
      <ul className="flex flex-col gap-2.5">
        {tp.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.72rem]">
              <span className="text-[var(--tessera-text)]">{it.label}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.pct}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
              <div
                className={cn("h-full rounded-full", BAR_TONE[it.tone] ?? "bg-slate-500")}
                style={{ width: `${it.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Performance({ data, className }: { data: Data; className?: string }) {
  const pf = data.performance;
  if (!pf) return null;
  return (
    <Card title={pf.title} cta={pf.cta} ctaHref={pf.ctaHref} className={className}>
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {pf.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-[var(--tessera-text-muted)]">{r.label}</span>
            <span className="flex shrink-0 items-center gap-1.5">
              <span className="font-medium tabular-nums text-[var(--tessera-text)]">{r.value}</span>
              <span
                className={cn(
                  "text-[0.6rem] tabular-nums",
                  r.good ? "text-emerald-400" : "text-red-400",
                )}
              >
                {r.delta}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function ConfigNow({ data, className }: { data: Data; className?: string }) {
  const c = data.config;
  if (!c) return null;
  return (
    <Card title={c.title} cta={c.cta} ctaHref={c.ctaHref} className={className}>
      <ul className="flex flex-col gap-2 text-[0.72rem]">
        {c.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span className="text-[var(--tessera-text-muted)]">{r.label}</span>
            <span className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 font-medium text-[var(--tessera-text)]">
              {r.value}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Conversations({ data, className }: { data: Data; className?: string }) {
  const c = data.conversations;
  if (!c) return null;
  return (
    <Card title={c.title} cta={c.cta} ctaHref={c.ctaHref} className={className}>
      {c.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2">
        {c.rows.map((r) => (
          <li
            key={r.title}
            className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)]/50 pb-2 last:border-0 last:pb-0"
          >
            <span className="min-w-0">
              <span className="block truncate text-[0.74rem] font-medium text-[var(--tessera-text)]">
                {r.title}
              </span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {r.user} - {r.time}
              </span>
            </span>
            <span
              className={cn(
                "shrink-0 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium capitalize",
                STATUS_BADGE[r.status] ?? "",
              )}
            >
              {STATUS_LABEL[r.status] ?? r.status}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Activity({ data, className }: { data: Data; className?: string }) {
  const a = data.activity;
  if (!a) return null;
  return (
    <Card title={a.title} className={className}>
      {a.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2.5">
        {a.rows.map((r, i) => (
          <li key={`${r.time}-${i}`} className="flex items-center gap-2 text-[0.72rem]">
            <span
              className={cn(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                KIND_DOT[r.kind] ?? "bg-slate-400",
              )}
            />
            <span className="w-9 shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {r.time}
            </span>
            <span className="min-w-0 truncate text-[var(--tessera-text)]">{r.label}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Prompts({ data, className }: { data: Data; className?: string }) {
  const p = data.prompts;
  if (!p) return null;
  return (
    <Card title={p.title} cta={p.cta} ctaHref={p.ctaHref} className={className}>
      {p.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2">
        {p.rows.map((r) => (
          <li
            key={r.name}
            className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2"
          >
            <span className="min-w-0">
              <span className="flex items-center gap-2 text-[0.74rem] font-medium text-[var(--tessera-text)]">
                {r.name}
                <span className="rounded border border-[var(--tessera-border)] px-1 text-[0.58rem] text-[var(--tessera-text-muted)]">
                  {r.version}
                </span>
              </span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {r.updated}
              </span>
            </span>
            <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.58rem] font-medium capitalize text-emerald-300">
              {r.status}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Channels({ data, className }: { data: Data; className?: string }) {
  const c = data.channels;
  if (!c) return null;
  return (
    <Card title={c.title} className={className}>
      <ul className="flex flex-col gap-2.5">
        {c.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.72rem]">
              <span className="text-[var(--tessera-text)]">{it.label}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.pct}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
              <div
                className={cn("h-full rounded-full", BAR_TONE[it.tone] ?? "bg-slate-500")}
                style={{ width: `${it.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Alerts({ data, className }: { data: Data; className?: string }) {
  const a = data.alerts;
  if (!a) return null;
  return (
    <Card title={a.title} cta={a.cta} ctaHref={a.ctaHref} className={className}>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
        {a.items.map((it) => (
          <div
            key={it.label}
            className="flex flex-col gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <span className="text-[0.62rem] leading-snug text-[var(--tessera-text-muted)]">
              {it.label}
            </span>
            <span
              className={cn(
                "text-[0.82rem] font-semibold tabular-nums",
                ALERT_TONE[it.tone] ?? "text-[var(--tessera-text)]",
              )}
            >
              {it.value}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function QuickConfig({ data, className }: { data: Data; className?: string }) {
  const q = data.quick_config;
  if (!q) return null;
  const icons = [Sparkles, Settings2, CalendarClock, Bot];
  return (
    <Card title={q.title} cta={q.cta} ctaHref={q.ctaHref} className={className}>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? Sparkles;
          return (
            <Link
              key={it.label}
              href={it.href as never}
              className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.72rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 shrink-0 text-[#b9a6ff]" />
              <span className="min-w-0 truncate">{it.label}</span>
            </Link>
          );
        })}
      </div>
    </Card>
  );
}

function Timeline({ data, className }: { data: Data; className?: string }) {
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <Card title={tl.title} cta={tl.cta} ctaHref={tl.ctaHref} className={className}>
      {tl.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2.5">
        {tl.rows.map((r, i) => (
          <li key={`${r.time}-${i}`} className="flex gap-2.5 text-[0.72rem]">
            <span
              className={cn(
                "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                KIND_DOT[r.kind] ?? "bg-slate-400",
              )}
            />
            <span className="min-w-0">
              <span className="text-[var(--tessera-text)]">
                <span className="tabular-nums text-[var(--tessera-text-muted)]">{r.time}</span>{" "}
                {r.label}
              </span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {r.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
