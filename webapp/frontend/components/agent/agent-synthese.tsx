"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity as ActivityIcon,
  Bot,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  Clock3,
  History,
  Info,
  RotateCcw,
  Settings2,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { useAsOf } from "@/components/agir/agir-rail";
import { AsOfPickerChip } from "@/components/cockpit/asof-picker-chip";
import { CardInfo } from "@/components/cockpit/card-info";
import { CHIP_ACTIVE, CHIP_BASE, SelectChip } from "@/components/cockpit/rail-chip";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { useTemporalState } from "@/components/overview/temporal-rail";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchAgentSynthese } from "@/lib/api/client";
import type { AgentSynthese as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import type { OverviewTone } from "@/lib/overview";
import { useAgentId } from "@/lib/use-agent-id";

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
const BADGE_STYLE: Record<string, string> = {
  Question: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  Réponse: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  "Handoff entrant": "border-violet-500/30 bg-violet-500/15 text-violet-300",
  "Handoff sortant": "border-amber-500/30 bg-amber-500/15 text-amber-300",
  "Garde-fou": "border-red-500/30 bg-red-500/15 text-red-300",
  Outil: "border-cyan-500/30 bg-cyan-500/15 text-cyan-300",
};
const STATUS_BADGE: Record<string, string> = {
  resolu: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  escalade: "border-amber-500/30 bg-amber-500/15 text-amber-300",
};
const STATUS_LABEL: Record<string, string> = { resolu: "Résolu", escalade: "Escalade" };
const ALERT_TONE: Record<string, string> = {
  warn: "border-amber-500/30 bg-amber-500/10",
  crit: "border-red-500/30 bg-red-500/10",
};
const ALERT_BADGE: Record<string, string> = {
  warn: "border-amber-500/40 bg-amber-500/15 text-amber-300",
  crit: "border-red-500/40 bg-red-500/15 text-red-300",
};

export function AgentSynthese() {
  const t = useTranslations("agentSynthese");
  const agentId = useAgentId();
  const temporal = useTemporalState();
  const asOf = useAsOf();
  const { data } = useQuery({
    queryKey: ["agent-synthese", agentId, temporal.periodKey, asOf ?? null],
    queryFn: ({ signal }) => fetchAgentSynthese(agentId, temporal.periodKey, asOf, signal),
    staleTime: 30_000,
    refetchInterval: asOf ? false : 30_000,
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
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <AgentRail temporal={temporal} asOf={asOf} agentName={data.context?.name ?? "l'agent"} />

      <div className="grid gap-2.5 xl:grid-cols-12">
        {/* Left region: KPI strip + two card rows */}
        <div className="flex flex-col gap-2.5 xl:col-span-9">
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
            {(data.kpis ?? []).map((k) => (
              <KpiTile key={k.key} kpi={k} />
            ))}
          </div>

          <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-12">
            <Profile data={data} className="xl:col-span-3" />
            <Capabilities data={data} className="xl:col-span-3" />
            <Repartition data={data} className="xl:col-span-3" />
            <Performance data={data} className="xl:col-span-3" />
          </div>

          <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-12">
            <Prompts data={data} className="xl:col-span-3" />
            <Conversations data={data} className="xl:col-span-5" />
            <Activity data={data} className="xl:col-span-4" />
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-2.5 xl:col-span-3">
          <Context data={data} />
          <OpAlerts data={data} />
          <QuickAccess data={data} />
        </div>
      </div>
    </div>
  );
}

// ── AT-01 rail (Live · Période · Voir à date) ────────────────────────────────
// "Voir à date" was removed in registre v1.5 because the backend had no as-of
// instant — a displayed mode the page cannot honour is a lie. It returns
// (v1.11) only because the content now honours it: the backend takes `at` and
// re-reads transcript / CSAT / journal over the window ending at T. Knowledge
// counts, prompts, registry identity and the chain badge stay live — the As-of
// micro-line says exactly that (scoped claim, same rule as the AGIR rail). The
// rail wears the shared SR-01 chip grammar (rail-chip + AsOfPickerChip): no
// status colours for a reading, no OS-drawn datetime panel on the strip.

const PERIODS = ["h24", "d7", "d30"] as const;

function AgentRail({
  temporal,
  asOf,
  agentName,
}: {
  temporal: ReturnType<typeof useTemporalState>;
  asOf: string | null;
  agentName: string;
}) {
  const t = useTranslations("agentSynthese");
  const ta = useTranslations("agirRail");
  const to = useTranslations("overview.time");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const setAsof = (value: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("asof", value);
    } else {
      params.delete("asof");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  const ReadingIcon = asOf ? History : ActivityIcon;
  return (
    <section className="sr01-strip rounded-2xl backdrop-blur-md">
      <div className="sr01-command-row flex flex-wrap items-center gap-2 px-3 py-2">
        {/* Lecture — the reading, always visible (champagne indicator chip, the
            SR-01 primary-reading grammar — never a status colour). */}
        <span className={cn(CHIP_BASE, CHIP_ACTIVE, "cursor-default")}>
          <ReadingIcon className="h-3.5 w-3.5 shrink-0 text-gold-600 dark:text-gold-400" />
          {to("reading")}
          <span className="font-semibold text-[var(--tessera-text)]">
            {asOf ? ta("asofBadge") : ta("liveBadge")}
          </span>
        </span>
        <SelectChip
          icon={Clock3}
          label={to("period")}
          value={temporal.periodKey}
          onChange={temporal.setPeriodKey}
          options={PERIODS.map((p) => ({ value: p, label: to(p) }))}
        />
        <AsOfPickerChip value={asOf} onChange={setAsof} />
      </div>

      {/* Contextual micro-line — the exact scoped claim of the active reading,
          and the single "Revenir au direct" (outline, SR-01 grammar). */}
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 border-t border-[rgba(96,194,242,0.1)] px-3 py-1.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
        {asOf ? (
          <span className="min-w-0">
            <span className="font-medium text-[var(--tessera-text)]">
              {ta("asofBadge")} · {new Date(asOf).toLocaleString()}
            </span>
            <span> — {t("railAsofScope", { agent: agentName })}</span>
          </span>
        ) : (
          <span className="font-medium text-[var(--tessera-text)]">
            {t("railLiveScope", { agent: agentName })}
          </span>
        )}
        {asOf ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto h-7 gap-1.5 px-2.5 text-xs"
            onClick={() => setAsof(null)}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {ta("backToLive")}
          </Button>
        ) : null}
      </div>
    </section>
  );
}

// ── loading skeleton ─────────────────────────────────────────────────────────

const SKELETON_KPIS = ["a", "b", "c", "d", "e", "f", "g"];
const SKELETON_CARDS = ["a", "b", "c", "d"];

function SyntheseSkeleton() {
  return (
    <div className="flex flex-col gap-2.5 pb-2">
      <Skeleton className="h-[88px] w-full rounded-lg" />
      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex flex-col gap-2.5 xl:col-span-9">
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-7">
            {SKELETON_KPIS.map((k) => (
              <Skeleton key={k} className="h-[112px] w-full rounded-lg" />
            ))}
          </div>
          <div className="grid gap-2.5 xl:grid-cols-12">
            {SKELETON_CARDS.map((k) => (
              <Skeleton key={k} className="h-44 rounded-lg xl:col-span-3" />
            ))}
          </div>
        </div>
        <Skeleton className="h-[480px] rounded-lg xl:col-span-3" />
      </div>
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function KpiTile({ kpi }: { kpi: NonNullable<Data["kpis"]>[number] }) {
  const tone: OverviewTone = kpi.good ? "success" : "danger";
  // The ⓘ pastille only renders when an explanation is authored for this KPI; mirror
  // that same honest-empty check so the tooltip only advertises "click for more" when
  // there is actually an ⓘ to click.
  const te = useTranslations("agentSynthese.explain");
  const hasInfo = te.has(`kpi.${kpi.key}.what`);
  // Whole-tile hover reveals the verbose name (label is kept terse so it never
  // ellipsises). A real Radix Tooltip, not native `title=`: the native delay is
  // browser-fixed (~1 s) and untunable, whereas this inherits the app-wide 200 ms
  // provider (with skipDelay, so sweeping across the dense strip never flickers). The
  // tooltip also SIGNPOSTS the ⓘ, so the hover promotes the click instead of pre-empting it.
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex min-h-[112px] flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
          <div className="flex items-center gap-1">
            <p className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">{kpi.label}</p>
            <CardInfo ns="agentSynthese" k={`kpi.${kpi.key}`} title={kpi.full ?? kpi.label} />
          </div>
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
          <div className="mt-auto pt-1.5">
            <MetricSparkline values={kpi.series} tone={tone} height={20} />
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top">
        <p className="font-medium">{kpi.full ?? kpi.label}</p>
        {hasInfo ? (
          <p className="mt-1 text-[0.66rem] opacity-70">
            Cliquez sur <Info className="inline h-3 w-3 align-middle" aria-hidden /> pour en savoir
            plus
          </p>
        ) : null}
      </TooltipContent>
    </Tooltip>
  );
}

function Card({
  title,
  subtitle,
  info,
  cta,
  ctaHref,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  info?: ReactNode;
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
        <div className="mb-2 flex flex-col gap-0.5">
          <div className="flex items-center gap-1">
            <h2 className="text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
            {info}
          </div>
          {subtitle ? (
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{subtitle}</p>
          ) : null}
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta ? <CtaLink label={cta} href={ctaHref} /> : null}
    </section>
  );
}

function EmptyRow({ label }: { label?: string }) {
  const t = useTranslations("agentSynthese");
  return (
    <p className="py-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{label ?? t("empty")}</p>
  );
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

// ── left region cards ─────────────────────────────────────────────────────────

function Profile({ data, className }: { data: Data; className?: string }) {
  const p = data.profile;
  if (!p) return null;
  return (
    <Card
      title="Aperçu de l'agent"
      info={<CardInfo ns="agentSynthese" k="profile" title="Aperçu de l'agent" />}
      cta={p.cta}
      ctaHref={p.ctaHref}
      className={className}
    >
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
          <p
            title={p.name}
            className="truncate text-[0.92rem] font-semibold text-[var(--tessera-text)]"
          >
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
            <dd title={f.value} className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
              {f.value}
            </dd>
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
    <Card
      title={c.title}
      info={<CardInfo ns="agentSynthese" k="capabilities" title={c.title} />}
      cta={c.cta}
      ctaHref={c.ctaHref}
      className={className}
    >
      <ul className="flex flex-col gap-2">
        {c.items.map((it) => (
          <li
            key={it}
            className="flex items-center gap-2 text-[0.74rem] text-[var(--tessera-text)]"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            <span title={it} className="min-w-0 truncate">
              {it}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Repartition({ data, className }: { data: Data; className?: string }) {
  const r = data.repartition;
  if (!r) return null;
  return (
    <Card
      title={r.title}
      subtitle={r.subtitle}
      info={<CardInfo ns="agentSynthese" k="repartition" title={r.title} />}
      className={className}
    >
      {r.items.length === 0 ? <EmptyRow label="Aucun événement de routage." /> : null}
      <ul className="flex flex-col gap-2.5">
        {r.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.72rem]">
              <span title={it.label} className="min-w-0 truncate text-[var(--tessera-text)]">
                {it.label}
              </span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.pct}%</span>
            </div>
            <div className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
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
    <Card
      title={pf.title}
      info={<CardInfo ns="agentSynthese" k="performance" title={pf.title} />}
      cta={pf.cta}
      ctaHref={pf.ctaHref}
      className={className}
    >
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {pf.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span title={r.label} className="min-w-0 truncate text-[var(--tessera-text-muted)]">
              {r.label}
            </span>
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

function Conversations({ data, className }: { data: Data; className?: string }) {
  const c = data.conversations;
  if (!c) return null;
  return (
    <Card
      title={c.title}
      info={<CardInfo ns="agentSynthese" k="conversations" title={c.title} />}
      cta={c.cta}
      ctaHref={c.ctaHref}
      className={className}
    >
      {c.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2">
        {c.rows.map((r, i) => (
          <li
            key={`${r.title}-${r.user}-${r.time}-${i}`}
            className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)]/50 pb-2 last:border-0 last:pb-0"
          >
            <span className="min-w-0">
              <Truncate
                full={r.title}
                className="text-[0.74rem] font-medium text-[var(--tessera-text)]"
              >
                {r.title}
              </Truncate>
              <Truncate
                full={`${r.user} - ${r.time}`}
                className="text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
                {r.user} - {r.time}
              </Truncate>
            </span>
            <span
              className={cn(
                "shrink-0 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
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
    <Card
      title={a.title}
      info={<CardInfo ns="agentSynthese" k="activity" title={a.title} />}
      cta={a.cta}
      ctaHref={a.ctaHref}
      className={className}
    >
      {a.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2.5">
        {a.rows.map((r, i) => (
          <li key={`${r.time}-${i}`} className="flex items-start gap-2 text-[0.72rem]">
            <span
              className={cn(
                "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                KIND_DOT[r.kind] ?? "bg-slate-400",
              )}
            />
            <span className="w-9 shrink-0 pt-px tabular-nums text-[var(--tessera-text-muted)]">
              {r.time}
            </span>
            <span className="min-w-0 flex-1">
              <span title={r.label} className="block truncate text-[var(--tessera-text)]">
                {r.label}
              </span>
              <span
                title={r.detail}
                className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
                {r.detail}
              </span>
            </span>
            <span
              className={cn(
                "shrink-0 rounded-full border px-1.5 py-0.5 text-[0.55rem] font-medium",
                BADGE_STYLE[r.badge] ??
                  "border-[var(--tessera-border)] text-[var(--tessera-text-muted)]",
              )}
            >
              {r.badge}
            </span>
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
    <Card
      title={p.title}
      info={<CardInfo ns="agentSynthese" k="prompts" title={p.title} />}
      cta={p.cta}
      ctaHref={p.ctaHref}
      className={className}
    >
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
              <span
                title={r.updated}
                className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
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

// ── right column ──────────────────────────────────────────────────────────────

function Context({ data }: { data: Data }) {
  const c = data.context;
  if (!c) return null;
  return (
    <Card
      title="Contexte de l'agent"
      info={<CardInfo ns="agentSynthese" k="context" title="Contexte de l'agent" />}
      cta={c.cta}
      ctaHref={c.ctaHref}
    >
      <div className="flex items-center gap-3">
        <Image
          src="/brand/agent-robot.png"
          alt={c.name}
          width={80}
          height={80}
          unoptimized
          className="h-12 w-12 shrink-0 rounded-xl object-cover"
        />
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-[0.92rem] font-semibold text-[var(--tessera-text)]">
            <span title={c.name} className="truncate">
              {c.name}
            </span>
            <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.55rem] font-medium capitalize text-emerald-300">
              {c.status}
            </span>
          </p>
          <span
            title={`ID : ${c.agentId}`}
            className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]"
          >
            ID : {c.agentId}
          </span>
        </div>
      </div>
      <p className="mt-2.5 text-[0.7rem] leading-snug text-[var(--tessera-text-muted)]">
        {c.description}
      </p>
      <dl className="mt-3 flex flex-col gap-1.5 text-[0.72rem]">
        {c.fields.map((f) => (
          <div key={f.label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{f.label}</dt>
            <dd title={f.value} className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
              {f.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function OpAlerts({ data }: { data: Data }) {
  const a = data.opAlerts;
  if (!a) return null;
  return (
    <Card
      title={a.title}
      info={<CardInfo ns="agentSynthese" k="opAlerts" title={a.title} />}
      cta={a.cta}
      ctaHref={a.ctaHref}
    >
      {a.items.length === 0 ? (
        <div className="flex items-center gap-2 rounded-md border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5 text-[0.72rem] text-emerald-300">
          <CheckCircle2 className="h-4 w-4 shrink-0" /> Aucune alerte
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {a.items.map((it) => (
            <li
              key={it.label}
              className={cn(
                "flex items-start justify-between gap-2 rounded-md border px-2.5 py-2",
                ALERT_TONE[it.tone] ?? "border-[var(--tessera-border)]",
              )}
            >
              <span className="min-w-0">
                <span
                  title={it.label}
                  className="block truncate text-[0.72rem] font-medium text-[var(--tessera-text)]"
                >
                  {it.label}
                </span>
                <span
                  title={it.detail}
                  className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]"
                >
                  {it.detail}
                </span>
              </span>
              <span
                className={cn(
                  "shrink-0 rounded-full border px-1.5 py-0.5 text-[0.55rem] font-medium",
                  ALERT_BADGE[it.tone] ?? "",
                )}
              >
                {it.badge}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function QuickAccess({ data }: { data: Data }) {
  const q = data.quickAccess;
  if (!q) return null;
  const icons = [Sparkles, Settings2, Bot, CalendarClock];
  return (
    <Card title={q.title} info={<CardInfo ns="agentSynthese" k="quickAccess" title={q.title} />}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? Sparkles;
          return (
            <Link
              key={it.label}
              href={it.href as never}
              className="flex flex-col gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2.5 text-left hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 text-[#b9a6ff]" />
              <span
                title={it.label}
                className="truncate text-[0.74rem] font-medium text-[var(--tessera-text)]"
              >
                {it.label}
              </span>
              <span
                title={it.sublabel}
                className="truncate text-[0.6rem] text-[var(--tessera-text-muted)]"
              >
                {it.sublabel}
              </span>
            </Link>
          );
        })}
      </div>
    </Card>
  );
}
