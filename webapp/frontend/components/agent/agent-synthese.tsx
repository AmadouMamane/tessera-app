"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  Bot,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Flag,
  Radio,
  Settings2,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import type { ReactNode } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { useTemporalState } from "@/components/overview/temporal-rail";
import { Skeleton } from "@/components/ui/skeleton";
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
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <AgentRail temporal={temporal} agentName={data.context?.name ?? "l'agent"} />

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

// ── AT-01 rail (4 labelled segments + mode banner) ───────────────────────────

const PERIOD_OPTIONS: { key: string; label: string }[] = [
  { key: "h24", label: "24h" },
  { key: "d7", label: "7 jours" },
  { key: "d30", label: "30 jours" },
];

function AgentRail({
  temporal,
  agentName,
}: {
  temporal: ReturnType<typeof useTemporalState>;
  agentName: string;
}) {
  const live = temporal.mode === "live";
  const selectedIso =
    temporal.selectedAt != null
      ? new Date(temporal.selectedAt - new Date().getTimezoneOffset() * 60000)
          .toISOString()
          .slice(0, 16)
      : "";
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Segment icon={Radio} label="Mode">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 font-semibold",
              live ? "text-emerald-300" : "text-[#f0a23a]",
            )}
          >
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                live ? "bg-emerald-400 shadow-[0_0_8px_rgba(0,200,120,0.85)]" : "bg-[#f0a23a]",
              )}
            />
            {live ? "Live · En direct" : "État à date"}
          </span>
        </Segment>

        <Segment icon={Clock3} label="Période">
          <select
            value={temporal.periodKey}
            onChange={(e) => {
              temporal.setPeriodKey(e.target.value);
              temporal.setSelectedAt(null);
            }}
            className="cursor-pointer rounded bg-transparent font-semibold text-[var(--tessera-text)] outline-none"
          >
            {PERIOD_OPTIONS.map((p) => (
              <option key={p.key} value={p.key} className="bg-[var(--tessera-surface)]">
                {p.label}
              </option>
            ))}
          </select>
        </Segment>

        <Segment icon={Flag} label="Voir à date">
          <input
            type="datetime-local"
            value={selectedIso}
            onChange={(e) => {
              const v = e.target.value;
              if (!v) {
                temporal.changeMode("live");
                return;
              }
              temporal.changeMode("history");
              temporal.setSelectedAt(new Date(v).getTime());
            }}
            aria-label="Voir à date"
            className="cursor-pointer rounded bg-transparent font-semibold text-[var(--tessera-text)] outline-none [color-scheme:dark]"
          />
        </Segment>

        <Segment icon={ArrowLeftRight} label="Comparaison">
          <span className="font-semibold text-[var(--tessera-text-muted)]">Aucune comparaison</span>
        </Segment>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#1f3a5f]/60 bg-[#0e1f33]/40 px-3 py-2">
        <span className="text-xs text-[var(--tessera-text-muted)]">
          {live ? (
            <>
              <b className="font-semibold text-sky-300">Mode : Live</b> — Vous consultez les données
              en direct de {agentName}.
            </>
          ) : (
            <>
              <b className="font-semibold text-[#f0a23a]">Mode : État à date</b> — données
              reconstituées au point sélectionné.
            </>
          )}
        </span>
        <button
          type="button"
          onClick={() => temporal.changeMode(live ? "history" : "live")}
          className={cn(
            "flex h-8 items-center gap-1.5 rounded-md border px-3 text-xs",
            live
              ? "border-[#9a5f18] text-[#f0a23a] hover:bg-[#3e260c]/35"
              : "border-emerald-600/60 text-emerald-300 hover:bg-emerald-900/20",
          )}
        >
          {live ? (
            <>
              <CalendarClock className="h-4 w-4" /> État à date
            </>
          ) : (
            <>
              <Radio className="h-4 w-4" /> Revenir au direct
            </>
          )}
        </button>
      </div>
    </section>
  );
}

function Segment({
  icon: Icon,
  label,
  children,
}: { icon: typeof Clock3; label: string; children: ReactNode }) {
  return (
    <span className="flex h-9 items-center gap-2 whitespace-nowrap rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)]">
      <Icon className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
      <span className="uppercase tracking-wide text-[0.6rem]">{label}</span>
      {children}
    </span>
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

function Card({
  title,
  subtitle,
  cta,
  ctaHref,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
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
          <h2 className="text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
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
    <Card title="Aperçu de l'agent" cta={p.cta} ctaHref={p.ctaHref} className={className}>
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

function Repartition({ data, className }: { data: Data; className?: string }) {
  const r = data.repartition;
  if (!r) return null;
  return (
    <Card title={r.title} subtitle={r.subtitle} className={className}>
      {r.items.length === 0 ? <EmptyRow label="Aucun événement de routage." /> : null}
      <ul className="flex flex-col gap-2.5">
        {r.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.72rem]">
              <span className="min-w-0 truncate text-[var(--tessera-text)]">{it.label}</span>
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

function Conversations({ data, className }: { data: Data; className?: string }) {
  const c = data.conversations;
  if (!c) return null;
  return (
    <Card title={c.title} cta={c.cta} ctaHref={c.ctaHref} className={className}>
      {c.rows.length === 0 ? <EmptyRow /> : null}
      <ul className="flex flex-col gap-2">
        {c.rows.map((r, i) => (
          <li
            key={`${r.title}-${r.user}-${r.time}-${i}`}
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
    <Card title={a.title} cta={a.cta} ctaHref={a.ctaHref} className={className}>
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
              <span className="block truncate text-[var(--tessera-text)]">{r.label}</span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {r.detail}
              </span>
            </span>
            <span
              className={cn(
                "shrink-0 rounded-full border px-1.5 py-0.5 text-[0.55rem] font-medium",
                BADGE_STYLE[r.badge] ?? "border-[var(--tessera-border)] text-[var(--tessera-text-muted)]",
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

// ── right column ──────────────────────────────────────────────────────────────

function Context({ data }: { data: Data }) {
  const c = data.context;
  if (!c) return null;
  return (
    <Card title="Contexte de l'agent" cta={c.cta} ctaHref={c.ctaHref}>
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
            <span className="truncate">{c.name}</span>
            <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.55rem] font-medium capitalize text-emerald-300">
              {c.status}
            </span>
          </p>
          <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
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
            <dd className="min-w-0 truncate font-medium text-[var(--tessera-text)]">{f.value}</dd>
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
    <Card title={a.title} cta={a.cta} ctaHref={a.ctaHref}>
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
                <span className="block truncate text-[0.72rem] font-medium text-[var(--tessera-text)]">
                  {it.label}
                </span>
                <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
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
    <Card title={q.title}>
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
              <span className="truncate text-[0.74rem] font-medium text-[var(--tessera-text)]">
                {it.label}
              </span>
              <span className="truncate text-[0.6rem] text-[var(--tessera-text-muted)]">
                {it.sublabel}
              </span>
            </Link>
          );
        })}
      </div>
    </Card>
  );
}
