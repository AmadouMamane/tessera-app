"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  type LucideIcon,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Snowflake,
  Trash2,
} from "lucide-react";
import type { Route } from "next";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { downloadBlob } from "@/components/agent/agent-subtab-shared";
import { AuthorityLabel } from "@/components/cockpit/authority-label";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { ProvenanceNotice } from "@/components/cockpit/provenance-notice";
import { useRailTimeline, useTemporalState } from "@/components/overview/temporal-rail";
import { SignalCommandBar } from "@/components/surveiller/signal-command-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { isAccessDenied } from "@/lib/api/access";
import {
  fetchBatch,
  fetchMemoryInventory,
  fetchOverviewSnapshot,
  fetchScoreSeries,
} from "@/lib/api/client";
import {
  AnomalyReportSchema,
  ConformanceReportSchema,
  CrossTenantReportSchema,
  ErasureCoverageSchema,
  FailedCasesReportSchema,
  FirewallEfficacySchema,
  InversionReportSchema,
  PIILeakSummarySchema,
  PrivilegeReportSchema,
  RedTeamResponseSchema,
  RefusalReportSchema,
  RegressionRiskSchema,
  ToxicityReportSchema,
  WhatChangedSchema,
} from "@/lib/api/schemas";
import type {
  AnomalyReport,
  ConformanceReport,
  FailedCasesReport,
  FirewallEfficacy,
  PrivilegeReport,
} from "@/lib/api/schemas";
import { type ControlId, type ControlReading, readControls } from "@/lib/control-registry";
import { useDecimalFormat, usePercentFormat } from "@/lib/format-number";
import { panelOf, signalOf } from "@/lib/overview-snapshot";
import { useWindowStore } from "@/lib/stores/window-store";
import { showNumber, toneFor } from "@/lib/unread-is-not-zero";
import { useUrlBackedView } from "@/lib/use-url-backed-view";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";

/**
 * The third answer, and the one this screen was missing.
 *
 * Ten tiles here read `(x ?? 0) > 0 ? BAD : GOOD`. On a query that does not answer — 401, 403,
 * backend down — `x` is `undefined`, `?? 0` makes it zero, and the SECURITY dashboard prints a
 * green **0 cross-tenant leaks**: the most reassuring sentence on the page, emitted by knowing
 * nothing at all. Green is a claim; absence of a reading does not earn it (ADR 0026).
 *
 * `failed-read-is-not-an-empty-result` could not catch them, and says so in its own docstring:
 * its granularity is the FILE, and one `isAccessDenied` four hundred lines up cleared all ten.
 */
const TONE_BAD = { bad: BAD, good: GOOD, unread: MUTED };
const TONE_WARN = { bad: WARN, good: GOOD, unread: MUTED };

type Tone = "ok" | "warn" | "crit" | "high";
const TONE_BADGE: Record<Tone, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  warn: "warning",
  high: "warning",
  crit: "danger",
};
const toneText = (t: Tone) => (t === "ok" ? GOOD : t === "crit" ? BAD : WARN);

/**
 * A ratio as a percentage, in the reader's language.
 *
 * `${(v * 100).toFixed(d)}%` was wrong twice outside English, and the second is the one nobody
 * catches: the separator, and the SPACE before the sign — French and German write `73,1 %`,
 * English `73.1%`. Gluing "%" on by hand can only produce one of the two.
 *
 * Three formatters rather than one built per call: `usePercentFormat` memoises on its digit
 * count, and a hook cannot be called inside the returned closure.
 */
function usePct(): (v: number | null | undefined, digits?: number) => string {
  const zero = usePercentFormat(0);
  const one = usePercentFormat(1);
  const two = usePercentFormat(2);
  return (v, digits = 0) => (digits >= 2 ? two : digits === 1 ? one : zero)(v);
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Sec({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
      {children}
    </h2>
  );
}

function Panel({
  title,
  children,
  className,
  info,
}: { title: string; children: ReactNode; className?: string; info?: ReactNode }) {
  return (
    <Card className={`flex h-full min-w-0 flex-col ${className ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-[0.78rem] font-medium">
          <span className="min-w-0 truncate">{title}</span>
          {info ? <span className="ml-auto shrink-0">{info}</span> : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1">{children}</CardContent>
    </Card>
  );
}

/** A translucent banded section grouping one cockpit zone (A · B · C · …). */
function Zone({ label, children, info }: { label: string; children: ReactNode; info?: ReactNode }) {
  return (
    <section
      data-slot="card"
      className="rounded-xl border border-[var(--tessera-border)]/50 bg-[var(--tessera-surface)]/25 p-2.5"
    >
      <div className="flex items-center gap-1.5">
        <Sec>{label}</Sec>
        {info ? <span className="shrink-0">{info}</span> : null}
      </div>
      <div className="mt-1.5">{children}</div>
    </section>
  );
}

/**
 * ⓘ for a section / zone / panel title, grounded in security.explain.<k>
 * (what / how computed / source). Mirrors the KPI-tile affordance so every
 * heading is self-explaining, not just the metric tiles.
 */
function SecInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("security.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
  hint,
  series,
  delta,
  deltaUpIsGood,
  infoKey,
  href,
  drillLabel,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: string;
  hint?: string;
  series?: number[];
  delta?: number | null;
  deltaUpIsGood?: boolean;
  /** Key under security.explain — renders a ⓘ "what is this / how computed". */
  infoKey?: string;
  /** Whole-tile drill-down to the real source (overlay ↗). */
  href?: string;
  drillLabel?: string;
}) {
  const dec1 = useDecimalFormat(1);
  const ts = useTranslations("security");
  const te = useTranslations("security.explain");
  const showDelta = delta != null && Math.abs(delta) >= 0.005;
  const up = (delta ?? 0) > 0;
  const deltaGood = up === (deltaUpIsGood ?? true);
  return (
    <Card
      className={`group relative flex flex-col gap-1 p-3 ${
        href ? "transition-colors hover:border-blue-400/40" : ""
      }`}
    >
      {href ? (
        <Link
          href={href}
          aria-label={drillLabel}
          className="absolute inset-0 z-10 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/40"
        />
      ) : null}
      <div
        className={`flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] ${
          href ? "pointer-events-none relative z-20" : ""
        }`}
      >
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
        {infoKey ? (
          <span className={href ? "pointer-events-auto ml-auto" : "ml-auto"}>
            <MetricInfo
              title={label}
              what={te(`${infoKey}.what`)}
              how={te(`${infoKey}.how`)}
              source={te.has(`${infoKey}.source`) ? te(`${infoKey}.source`) : undefined}
            />
          </span>
        ) : null}
      </div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
      </div>
      {showDelta ? (
        <div
          className={`flex items-center gap-1 text-[0.65rem] tabular-nums ${deltaGood ? GOOD : BAD}`}
        >
          <span>{up ? "↗" : "↘"}</span>
          <span>
            {dec1(Math.abs((delta as number) * 100))} pts {ts("kpi.vs7d")}
          </span>
        </div>
      ) : null}
      {series && series.length > 1 ? <Spark values={series} /> : null}
      {hint ? (
        <div className="truncate text-[0.65rem] text-[var(--muted-foreground)]">{hint}</div>
      ) : null}
      {href ? (
        <ArrowUpRight className="pointer-events-none absolute right-2 bottom-2 z-20 h-3 w-3 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </Card>
  );
}

/** Tiny sparkline. */
function Spark({ values }: { values: number[] }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 100;
  const H = 22;
  const d = values
    .map(
      (v, i) =>
        `${i === 0 ? "M" : "L"}${((i / (values.length - 1)) * W).toFixed(1)},${(H - ((v - min) / span) * H).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-5 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={d}
        fill="none"
        stroke="var(--tessera-fg-warning)"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Half-circle gauge with a centred percentage. */
function Gauge({ value, label, tone }: { value: number; label?: string; tone: string }) {
  const clamped = Math.max(0, Math.min(1, value));
  const R = 32;
  const C = Math.PI * R; // half-circle circumference
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 80 46" className="h-[60px] w-[104px]" aria-hidden="true">
        <path
          d="M8 40 A32 32 0 0 1 72 40"
          fill="none"
          stroke="var(--tessera-border)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path
          d="M8 40 A32 32 0 0 1 72 40"
          fill="none"
          stroke={tone}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${clamped * C} ${C}`}
        />
        <text
          x="40"
          y="38"
          textAnchor="middle"
          className="fill-[var(--foreground)] text-[14px] font-semibold"
        >
          {Math.round(clamped * 100)}%
        </text>
      </svg>
      {label ? (
        <span className="text-[0.65rem] text-[var(--muted-foreground)]">{label}</span>
      ) : null}
    </div>
  );
}

/** Horizontal risk bar row. */
function RiskBar({ label, value, sub }: { label: string; value: number; sub?: string }) {
  const pct = usePct();
  const tone =
    value >= 0.5
      ? "var(--tessera-fg-danger)"
      : value >= 0.25
        ? "var(--tessera-fg-warning)"
        : "var(--tessera-fg-success)";
  return (
    <div className="flex items-center gap-2 text-[0.72rem]">
      <span className="w-24 shrink-0 truncate">{label}</span>
      <div className="h-[4px] flex-1 overflow-hidden rounded-sm bg-[var(--tessera-border)]">
        <div
          className="h-full rounded-sm"
          style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, background: tone }}
        />
      </div>
      <span className="w-12 shrink-0 text-right tabular-nums" style={{ color: tone }}>
        {sub ?? pct(value)}
      </span>
    </div>
  );
}

/** Donut of failure families (zone C "Répartition des échecs"). */
function FailureDonut({
  slices,
  label,
}: {
  slices: { key: string; count: number; color: string }[];
  label: string;
}) {
  const ts = useTranslations("security");
  const measuredTotal = slices.reduce((sum, slice) => sum + slice.count, 0);
  const denominator = measuredTotal || 1;
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
            const frac = s.count / denominator;
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
        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
          <span className="max-w-[49px] truncate text-base font-semibold leading-none tabular-nums">
            {measuredTotal}
          </span>
          <span className="line-clamp-2 max-w-[49px] break-words text-center text-[0.5rem] uppercase leading-tight text-[var(--muted-foreground)]">
            {label}
          </span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.68rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex flex-col gap-0.5">
            <span className="flex min-w-0 items-center gap-1">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 truncate">{ts(`fail.${s.key}`)}</span>
            </span>
            <span className="pl-2.5 tabular-nums text-[var(--muted-foreground)]">
              {s.count} · {Math.round((s.count / denominator) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Two-line trend chart over the score-series window (zone D). */
function LineChart({
  a,
  b,
  aLabel,
  bLabel,
}: {
  a: number[];
  b: number[];
  aLabel: string;
  bLabel: string;
}) {
  const all = [...a, ...b];
  if (all.length < 2)
    return <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>;
  const max = Math.max(0.01, ...all);
  const W = 220;
  const H = 60;
  const path = (s: number[]) =>
    s.length < 2
      ? ""
      : s
          .map(
            (v, i) =>
              `${i === 0 ? "M" : "L"}${((i / (s.length - 1)) * W).toFixed(1)},${(H - 4 - (v / max) * (H - 8)).toFixed(1)}`,
          )
          .join(" ");
  return (
    <div className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-16 w-full"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d={path(a)}
          fill="none"
          stroke="var(--tessera-fg-warning)"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        {b.length >= 2 ? (
          <path
            d={path(b)}
            fill="none"
            stroke="var(--tessera-fg-danger)"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
        ) : null}
      </svg>
      <div className="flex gap-3 text-[0.6rem] text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span className="h-1 w-3 rounded-full bg-[var(--tessera-fg-warning)]" /> {aLabel}
        </span>
        {b.length >= 2 ? (
          <span className="flex items-center gap-1">
            <span className="h-1 w-3 rounded-full bg-[var(--tessera-fg-danger)]" /> {bLabel}
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ── action card (zone F) ─────────────────────────────────────────────────────

function ActionCard({
  icon: Icon,
  title,
  desc,
  roleLabel,
  cta,
  href,
}: {
  icon: LucideIcon;
  title: string;
  desc: string;
  roleLabel: string;
  cta: string;
  href: Route;
}) {
  const ts = useTranslations("security");
  return (
    <Card className="flex h-full min-w-0 flex-col gap-2 p-3">
      <div className="flex items-start gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-[var(--tessera-fg-warning)]" />
        <span className="min-w-0 text-[0.78rem] font-medium leading-snug">{title}</span>
      </div>
      <p className="text-[0.68rem] leading-snug text-[var(--muted-foreground)]">{desc}</p>
      <div className="flex flex-wrap items-center gap-1">
        <Badge tone="warning">
          <AuthorityLabel authority={roleLabel} />
        </Badge>
        <Badge tone="danger">{ts("dualControl")}</Badge>
      </div>
      <Button
        asChild
        size="sm"
        variant="outline"
        className="mt-auto h-7 justify-center text-[0.7rem]"
      >
        <Link href={href}>{cta}</Link>
      </Button>
    </Card>
  );
}

// ── main dashboard ───────────────────────────────────────────────────────────

const POLL = 30_000;

/**
 * The safety signals that ARE snapshot signals (`_READS` registry): ONE `/observability/snapshot`
 * round-trip serves all five instead of five separate card fetches. They share this page's scope
 * (`?agent=`), as-of and poll cadence, so folding them changes no refresh timing — only transport.
 * Each card `select`s its own slice, validated by the same schema its route used (byte-identical,
 * honest-empty on absence). The non-snapshot probes keep their own fetches.
 */
const SEC_SNAPSHOT_SIGNALS = [
  "pii_leak",
  "toxicity",
  "anomalies",
  "conformance",
  "what_changed",
] as const;

// The eight individual public safety-card reads, fetched in ONE `/observability/batch` request
// instead of eight tunnel round-trips. Each panel is byte-identical to its own endpoint. The
// subject-scoped memory inventory and the per-metric score-series stay on their own fetches.
const SEC_BATCH_KEYS = [
  "firewall-efficacy",
  "least-privilege",
  "refusal",
  "redteam",
  "cross-tenant",
  "embedding-inversion",
  "erasure-coverage",
  "regression-risk",
  "failed-cases",
] as const;

// The 8 normative sub-views (32-1..32-8): overview stays comprehensive; the seven
// focused tabs are curated REAL views over the same live security signals.
const SEC_TABS = [
  "overview",
  "promptInjection",
  "pii",
  "guard",
  "tools",
  "memory",
  "isolation",
  "redteam",
] as const;
type SecTab = (typeof SEC_TABS)[number];

export function SecurityDashboard({ agentScope }: { agentScope?: ReactNode }) {
  const pct = usePct();
  const dec2 = useDecimalFormat(2);
  const ts = useTranslations("security");
  // The supporting line under a control value, localised from the SAME catalogue the other
  // two surfaces read — the counts used to be pasted in as `(3/25)` beside every value.
  const tcd = useTranslations("overview.controlDetail");
  const locale = useLocale();
  const formatter = useFormatter();
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();
  const [activeTab, setActiveTab] = useUrlBackedView(SEC_TABS, "overview");
  // Global agent scope (?agent=) — the score-/bundle-/audit-backed safety signals
  // read this agent's own turns; shared-policy probes (firewall, refusal) stay org.
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));
  // The window length, from the header's period selector. The fixed-corpus probes on this
  // page ignore it by construction and SAY so (their capability declares no TIME dimension);
  // the turn-derived ones — PII, toxicity, tool validity, and since 2026-08-04 cross-tenant
  // and least-privilege — honour it. Those last two were in the first group by accident of
  // their handlers taking no scope, never because their samples lacked timestamps.
  const period = useWindowStore((st) => st.period);

  // One batched read for the eight individual public safety signals (was eight fetches).
  const secBatch = useQuery({
    queryKey: ["sec-batch", asOf, locale, period],
    queryFn: ({ signal }) =>
      fetchBatch(signal, SEC_BATCH_KEYS, { at: asOf ?? undefined, lang: locale, days: period }),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const firewall = panelOf(secBatch, "firewall-efficacy", FirewallEfficacySchema);
  // One batched snapshot for the five snapshot-eligible safety signals (was five fetches).
  const secSnap = useQuery({
    queryKey: ["sec-snapshot", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchOverviewSnapshot(signal, asOf ?? undefined, scope, SEC_SNAPSHOT_SIGNALS, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const pii = signalOf(secSnap, "pii_leak", PIILeakSummarySchema);
  const toxicity = signalOf(secSnap, "toxicity", ToxicityReportSchema);
  const anomalies = signalOf(secSnap, "anomalies", AnomalyReportSchema);
  const conformance = signalOf(secSnap, "conformance", ConformanceReportSchema);
  const whatChanged = signalOf(secSnap, "what_changed", WhatChangedSchema);
  const lp = panelOf(secBatch, "least-privilege", PrivilegeReportSchema);
  const refusal = panelOf(secBatch, "refusal", RefusalReportSchema);
  // Newest last, as the endpoint documents. `undefined` when the campaign has never run —
  // which the panel must render as "never run", not as a reassuring 0 % success rate.
  const redteamHistory = panelOf(secBatch, "redteam", RedTeamResponseSchema);
  const lastRedteam = redteamHistory.data?.snapshots.at(-1);
  const crossTenant = panelOf(secBatch, "cross-tenant", CrossTenantReportSchema);
  const inversion = panelOf(secBatch, "embedding-inversion", InversionReportSchema);
  const erasure = panelOf(secBatch, "erasure-coverage", ErasureCoverageSchema);
  const inventory = useQuery({
    queryKey: ["memory-inventory"],
    queryFn: ({ signal }) => fetchMemoryInventory(signal),
    refetchInterval: POLL,
    // A refusal is not a transient failure — retrying it just hammers the gate.
    retry: (_count, error) => !isAccessDenied(error),
  });
  // The memory inventory is subject-scoped (GDPR): it carries the stored memories' text and
  // their subject ids, so the agent now requires a verified operator (audit 2026-07-12, F-4).
  // An anonymous visitor of the public demo is refused here — and MUST be told so. Rendering
  // `?? 0` for a refused caller would print a confident "0 sensitive memories expiring", which
  // is not an honest empty: it is a fact about the world asserted from a fact about the caller.
  const inventoryDenied = isAccessDenied(inventory.error);
  const inventoryExpiring = inventoryDenied
    ? ts("accessDenied")
    : `${showNumber(inventory.data?.n_expiring_soon)}`;
  const regression = panelOf(secBatch, "regression-risk", RegressionRiskSchema);
  const faith = useQuery({
    queryKey: ["score-series", "faithfulness", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchScoreSeries(signal, asOf ?? undefined, "faithfulness", scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const grounding = useQuery({
    queryKey: ["score-series", "grounding", asOf, scope, period],
    queryFn: ({ signal }) =>
      fetchScoreSeries(signal, asOf ?? undefined, "grounding", scope, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const failed = panelOf(secBatch, "failed-cases", FailedCasesReportSchema);

  const fw = firewall.data;
  const attackRate = fw && fw.n_positive > 0 ? fw.false_negative / fw.n_positive : null;
  const blocked = fw ? `${fw.true_positive}/${fw.n_positive}` : "—";
  const blockRate = fw && fw.n_positive > 0 ? fw.true_positive / fw.n_positive : null;
  const piiRate = pii.data?.leak_rate ?? null;
  const toxRate = toxicity.data?.toxicity_rate ?? null;
  const xtRate = crossTenant.data?.leak_rate ?? null;
  const invRate = inversion.data?.recovery_rate ?? null;
  const overProvRate =
    lp.data && lp.data.n_granted > 0 ? lp.data.n_over_provisioned / lp.data.n_granted : null;

  // Real 30-day risk trend from the durable score series (1 − metric mean).
  const attackSeries =
    faith.data?.buckets.filter((b) => b.mean != null).map((b) => 1 - (b.mean as number)) ?? [];
  const incidentSeries =
    grounding.data?.buckets.filter((b) => b.mean != null).map((b) => 1 - (b.mean as number)) ?? [];
  const fwSpark = attackSeries;
  const sparkDelta = (s: number[]): number | null =>
    s.length >= 2 ? (s.at(-1) as number) - (s[0] as number) : null;

  // Zone B — critical controls, all real.
  type Control = {
    key: string;
    tone: Tone;
    value: string;
    target: string;
    action: string;
    role: string;
    case: string;
  };
  /**
   * This page's vocabulary for a control state.
   *
   * `high` is a tone this table has and the other two do not, so the mapping is one-way and
   * lossy in one direction only: the registry's `warn` becomes `high` here. That is a
   * presentation choice about a shared verdict, not a second verdict — the state itself is
   * computed once, from the value shown against the bar shown.
   */
  const toneOf = (reading: ControlReading): Tone =>
    reading.noData
      ? "warn"
      : reading.state.key === "fail"
        ? "crit"
        : reading.state.key === "warn"
          ? "high"
          : "ok";
  // Case refs come from the real failed-harness cases of the control's domain —
  // never an invented "CASE-02xx" id (same rule as the SIEM card in the rail).
  const caseRef = (cats: string[]): string => {
    const ids = (failed.data?.cases ?? [])
      .filter((c) => cats.some((k) => c.category.includes(k)))
      .map((c) => c.case_id);
    const first = ids[0];
    if (!first) return "—";
    return ids.length === 1 ? first : `${first} +${ids.length - 1}`;
  };
  /**
   * The six controls this page shows, read from `lib/control-registry.ts`.
   *
   * This surface was the THIRD independent copy of the same derivations, and the one that made
   * the cost visible: it rendered `1 − recall` (24 %) as "Prompt injection" while
   * `overview-dashboard` rendered `recall` (76 %) and `signals-table` rendered `f1` (86 %) —
   * three numbers from one `FirewallEfficacy` report, each under a label naming firewall
   * effectiveness, none of them saying which of the three it was. All three are still visible;
   * each now says which view it is, and the bars come from one place.
   *
   * The `?? 0` that used to fill each value is gone with them: an unread probe rendered `0 %`,
   * which reads as "nothing recoverable" — the best possible result — for a measurement that
   * did not happen. It now reads `—` (ADR 0026: a witness that cannot see may not report ok).
   */
  const secControls: readonly {
    readonly id: ControlId;
    readonly key: string;
    readonly action: string;
    readonly role: string;
    readonly cats: string[];
  }[] = [
    {
      id: "injectionBypass",
      key: "promptInjection",
      action: "ctrl.promptInjectionAction",
      role: "role.security",
      cats: ["prompt_injection"],
    },
    {
      id: "pii",
      key: "piiLeak",
      action: "ctrl.piiLeakAction",
      role: "role.privacy",
      cats: ["pii"],
    },
    {
      id: "crossTenant",
      key: "crossTenant",
      action: "ctrl.crossTenantAction",
      role: "role.security",
      cats: ["cross_tenant", "tenant"],
    },
    {
      id: "leastPrivilege",
      key: "toolMisuse",
      action: "ctrl.toolMisuseAction",
      role: "role.security",
      cats: ["tool"],
    },
    {
      id: "embeddingInversion",
      key: "inversion",
      action: "ctrl.inversionAction",
      role: "role.ml",
      cats: ["memory"],
    },
    {
      id: "toxicity",
      key: "toxicity",
      action: "ctrl.toxicityAction",
      role: "role.ml",
      cats: ["toxicity"],
    },
  ];

  const readings = new Map(
    readControls(
      {
        firewall: fw ?? undefined,
        pii: pii.data,
        toxicity: toxicity.data,
        crossTenant: crossTenant.data,
        privilege: lp.data,
        inversion: inversion.data,
      },
      secControls.map((c) => c.id),
      locale,
    ).map((r) => [r.id, r]),
  );

  const controls: Control[] = secControls.flatMap((spec) => {
    const reading = readings.get(spec.id);
    if (!reading) return [];
    return [
      {
        key: spec.key,
        tone: toneOf(reading),
        value: reading.detail
          ? `${reading.value} (${tcd(reading.detail.key, reading.detail.values)})`
          : reading.value,
        target: reading.target,
        action: ts(spec.action),
        role: ts(spec.role),
        case: caseRef(spec.cats),
      },
    ];
  });

  // Domain risk, normalised. NOT uniformly real: `invRate` is the embedding-inversion probe,
  // which runs over `DEMO_MEMORIES` — a built-in corpus of five invented sentences. It reaches
  // two of these five bars (`privacy` via the max, and `memory` outright), so the panel carries
  // the synthetic notice rather than presenting all five as equally measured. The comment here
  // used to read "(real, normalised)" flatly, which is how a fixture becomes a finding.
  const domainRisks = [
    { key: "promptInj", value: attackRate ?? 0 },
    { key: "privacy", value: Math.max(piiRate ?? 0, invRate ?? 0) },
    { key: "tools", value: overProvRate ?? 0 },
    { key: "memory", value: invRate ?? 0 },
    { key: "compliance", value: 1 - (conformance.data?.conformance_rate ?? 1) },
  ].sort((a, b) => b.value - a.value);

  // Répartition des échecs (zone C donut) — failure observations per family.
  //
  // One of these families is NOT an observation. `inversion` counts recoverable memories from
  // the demonstration corpus, so the donut pooled a fixture with five real counts and the
  // header called the whole thing real. Removing the slice would be worse — the risk it
  // demonstrates is genuine and the operator should see it — so it stays, the panel says which
  // part is a demonstration, and the comment stops claiming what it cannot.
  const failureSlices = [
    // Failure FAMILIES — identity, not severity: every slice here is already a failure,
    // so the categorical ramp separates them and the legend says which is which.
    { key: "injection", count: fw?.false_negative ?? 0, color: "var(--tessera-cat-1)" },
    { key: "toolMisuse", count: lp.data?.n_over_provisioned ?? 0, color: "var(--tessera-cat-2)" },
    { key: "inversion", count: inversion.data?.n_recoverable ?? 0, color: "var(--tessera-cat-3)" },
    {
      key: "refusal",
      count: (refusal.data?.legit_refused ?? 0) + (refusal.data?.forbidden_allowed ?? 0),
      color: "var(--tessera-cat-4)",
    },
    { key: "pii", count: pii.data?.n_with_leak ?? 0, color: "var(--tessera-cat-5)" },
    { key: "toxicity", count: toxicity.data?.n_toxic ?? 0, color: "var(--tessera-cat-6)" },
  ].filter((s) => s.count > 0);

  const erasureComplete =
    erasure.data && erasure.data.n_conversations > 0
      ? erasure.data.n_bundles / erasure.data.n_conversations
      : null;

  // ── focused-tab building blocks (same live queries, curated per domain) ────
  const controlsTable = (rows: Control[]) => (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        {/* House table mould (data-premium-table: type scale, sticky first column, hover
            states) + small-caps header — this was the fleet's last text-sm data table;
            every sibling cockpit entity table already wears the marker (operator ask
            2026-08-25). Column sizing below is untouched: the mould sets type, not widths. */}
        <table data-premium-table="true" className="w-full">
          <thead>
            <tr className="border-b border-[var(--border)] text-left uppercase text-[var(--muted-foreground)]">
              {/* One column absorbs the card's leftover width; every other column is sized by
                its own content, which means it must not WRAP that content. Both halves are
                needed: with only the first, the auto layout spread the slack over five of
                these seven columns (gutters of 51, 26, 37, 30, 67 px under identical `px-3`);
                with only the second, «≤ 0.10%» and «100% (3/3)» broke across two lines in
                columns 69 px wide. Measured in `e2e/table-rhythm.spec.ts`. The identity
                column is nowrap-content-sized like the value columns (an earlier
                `min-w-[11rem]` made it a second slack absorber once the mould's smaller
                type freed 36 px inside it — two absorbers is exactly the spread the rule
                refuses). */}
              <th className="px-3 py-2 font-medium whitespace-nowrap">{ts("col.signal")}</th>
              <th className="px-3 py-2 font-medium whitespace-nowrap">{ts("col.state")}</th>
              <th className="px-3 py-2 font-medium whitespace-nowrap">{ts("col.value")}</th>
              <th className="px-3 py-2 font-medium whitespace-nowrap">{ts("col.target")}</th>
              {/* The slack column — the one holding a sentence, not the one holding a link. */}
              <th className="w-full px-3 py-2 font-medium">{ts("col.action")}</th>
              <th className="px-3 py-2 font-medium whitespace-nowrap">{ts("col.role")}</th>
              <th className="px-3 py-2 font-medium whitespace-nowrap">{ts("col.case")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.key} className="border-b border-[var(--border)]/50">
                <td className="px-3 py-2 font-medium whitespace-nowrap">{ts(`ctrl.${c.key}`)}</td>
                <td className="px-3 py-2">
                  <Badge tone={TONE_BADGE[c.tone]}>{ts(`state.${c.tone}`)}</Badge>
                </td>
                <td className={`px-3 py-2 tabular-nums whitespace-nowrap ${toneText(c.tone)}`}>
                  {c.value}
                </td>
                <td className="px-3 py-2 tabular-nums whitespace-nowrap text-[var(--muted-foreground)]">
                  {c.target}
                </td>
                {/* The one column that MAY wrap: it holds a sentence. */}
                <td className="px-3 py-2 text-[var(--muted-foreground)]">{c.action}</td>
                <td className="px-3 py-2 whitespace-nowrap">{c.role}</td>
                <td className="px-3 py-2 font-mono text-[0.7rem] text-[var(--tessera-green)]">
                  {c.case}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );

  // Real failed harness cases for one domain ([] = all domains).
  const domainCases = (cats: string[]) =>
    (failed.data?.cases ?? []).filter(
      (c) => cats.length === 0 || cats.some((k) => c.category.includes(k)),
    );
  const casesPanel = (cats: string[], max = 6) => {
    const rows = domainCases(cats);
    return (
      <Panel
        title={ts("tabx.domainCases")}
        info={<SecInfo k="domainCases" title={ts("tabx.domainCases")} />}
      >
        {rows.length === 0 ? (
          <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">
            {ts("tabx.noCases")}
          </p>
        ) : (
          <ul className="flex flex-col gap-1 text-[0.72rem]">
            {rows.slice(0, max).map((c) => (
              <li key={`${c.case_id}.${c.language}`} className="flex items-center gap-1.5">
                <span
                  className={`h-1.5 w-1.5 shrink-0 rounded-full ${c.severity === "critical" ? "bg-red-500" : c.severity === "high" ? "bg-amber-500" : "bg-[var(--muted-foreground)]"}`}
                />
                <Truncate className="min-w-0 flex-1">{c.title}</Truncate>
                <span className="shrink-0 font-mono text-[0.6rem] uppercase text-[var(--muted-foreground)]">
                  {c.language}
                </span>
                <span className="shrink-0 font-mono text-[0.6rem] text-[var(--tessera-green)]">
                  {c.case_id}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    );
  };

  const redteamPanel = (
    <Panel title={ts("panel.redteam")} info={<SecInfo k="redteam" title={ts("panel.redteam")} />}>
      <div className="flex flex-col gap-1.5 text-[0.72rem]">
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-semibold tabular-nums">{blocked}</span>
          <span className="text-[var(--muted-foreground)]">{ts("panel.blocked")}</span>
          <span className="ml-auto font-semibold tabular-nums text-[var(--tessera-fg-warning)]">
            {showNumber(fw?.false_negative)} {ts("panel.bypasses")}
          </span>
        </div>
        <div className="flex h-[4px] w-full overflow-hidden rounded-full">
          <div
            style={{
              flexBasis: `${(blockRate ?? 0) * 100}%`,
              background: "var(--tessera-fg-success)",
            }}
          />
          <div style={{ flexGrow: 1, background: "var(--tessera-fg-warning)" }} />
        </div>
        <KV label={ts("panel.blockRate")} value={pct(blockRate)} tone={GOOD} />
        <KV label={ts("panel.uniqueBypasses")} value={`${showNumber(fw?.false_negative)}`} />
        {/* The recorded campaign history. The numbers above are the FIXED-CORPUS efficacy
            probe, recomputed on every read; these are the runs somebody actually triggered.
            Until 2026-08-04 the endpoint that serves them had no consumer at all and the
            snapshots lived in one worker's memory, so "repeated runs form a drift series" —
            the module's own premise — was true of nothing anyone could see. A campaign that
            has never run must SAY so: a 0 % success rate here would be the most reassuring
            possible way to report that the guard was never attacked. */}
        {lastRedteam ? (
          <KV
            label={ts("panel.redteamLastRun")}
            value={`${pct(lastRedteam.attack_success_rate)} · ${formatter.dateTime(new Date(lastRedteam.ran_at), { dateStyle: "short", timeStyle: "short" })}`}
            tone={lastRedteam.n_bypassed > 0 ? WARN : GOOD}
          />
        ) : (
          <KV label={ts("panel.redteamLastRun")} value={ts("panel.redteamNeverRun")} tone={MUTED} />
        )}
      </div>
    </Panel>
  );

  const erasurePanel = (
    <Panel
      title={ts("panel.erasureSurface")}
      info={<SecInfo k="erasureSurface" title={ts("panel.erasureSurface")} />}
    >
      <div className="flex items-center gap-3">
        <Gauge
          value={erasureComplete ?? 0}
          label={ts("panel.completeness")}
          tone="var(--tessera-fg-success)"
        />
        <div className="flex min-w-0 flex-col gap-0.5 text-[0.7rem]">
          <KV
            label={ts("panel.conversations")}
            value={`${showNumber(erasure.data?.n_conversations)}`}
          />
          <KV label={ts("panel.bundles")} value={`${showNumber(erasure.data?.n_bundles)}`} />
          <KV label={ts("panel.scores")} value={`${showNumber(erasure.data?.n_scores)}`} />
        </div>
      </div>
    </Panel>
  );

  const inversionPanel = (
    <Panel
      title={ts("panel.inversion")}
      info={<SecInfo k="inversion" title={ts("panel.inversion")} />}
    >
      {/* This page carried NO synthetic notice at all, and this panel is why it needed one.
          `embedding_inversion.py` assesses `DEMO_MEMORIES` — five invented sentences —
          "so the dashboard always shows a concrete number". The maths is real, the memories
          are not, and the panel read "Inversion embedding · Critique · 100 %" as if measured.
          The notice renders from the capability registry, which said `synthetic: false` here
          while `capabilities.py` said true; a test now refuses that disagreement. */}
      <ProvenanceNotice signalId="embedding_inversion" compact />
      {inversion.data?.available === false || inversion.isLoading ? (
        <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
          {ts("panel.computing")}
        </p>
      ) : (
        <div className="flex flex-col gap-1 text-[0.72rem]">
          <KV
            label={ts("panel.recoverable")}
            value={`${showNumber(inversion.data?.n_recoverable)}/${showNumber(inversion.data?.n_memories)}`}
            tone={toneFor(inversion.data?.n_recoverable, (n) => n > 0, TONE_BAD)}
          />
          <KV label={ts("panel.recoveryRate")} value={pct(invRate)} />
          <KV label={ts("panel.threshold")} value={dec2(inversion.data?.threshold)} />
        </div>
      )}
    </Panel>
  );

  /**
   * The regression risk, or the honest absence of it — defined once, mounted in both layouts.
   *
   * `{ts(`level.${regression.data?.level ?? "low"}`)}` printed the word **« faible »** when the
   * probe had not answered: not a colour this time but a verdict in words, and the most
   * comforting of the four. The gauge under it was pinned at 0 by the same `?? 0`. A risk nobody
   * measured is not a low risk.
   */
  const riskScore = regression.data?.risk_score;
  const regressionBody =
    riskScore === null || riskScore === undefined ? (
      <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
        {ts("panel.regressionUnread")}
      </p>
    ) : (
      <div className="flex items-center gap-3">
        <Gauge
          value={riskScore}
          tone={riskScore >= 0.5 ? "var(--tessera-fg-danger)" : "var(--tessera-fg-warning)"}
        />
        <div className="flex flex-col gap-0.5 text-[0.7rem]">
          <span className={`text-base font-semibold ${riskScore >= 0.5 ? BAD : WARN}`}>
            {ts(`level.${regression.data?.level ?? "low"}`)}
          </span>
          <span className="text-[var(--muted-foreground)]">
            {ts("panel.regression7d")}: {pct(regression.data?.probability_7d)}
          </span>
        </div>
      </div>
    );

  const trendPanel = (
    <Panel title={ts("panel.trend")} info={<SecInfo k="trend" title={ts("panel.trend")} />}>
      <LineChart
        a={attackSeries}
        b={incidentSeries}
        aLabel={ts("panel.attackLine")}
        bLabel={ts("panel.incidentLine")}
      />
    </Panel>
  );

  const kpiGrid = (children: ReactNode) => (
    <Zone label={ts("sec.actual")} info={<SecInfo k="zoneActual" title={ts("sec.actual")} />}>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">{children}</div>
    </Zone>
  );

  // The seven focused domain views (normatives 32-2..32-8), every value live.
  const domainView: Record<Exclude<SecTab, "overview">, ReactNode> = {
    promptInjection: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.probes")}
              infoKey="probes"
              value={`${showNumber(fw?.n_positive)}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.blocked")}
              infoKey="blocked"
              value={blocked}
              tone={GOOD}
              series={fwSpark.map((v) => 1 - v)}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.escaped")}
              infoKey="escaped"
              value={`${showNumber(fw?.false_negative)}`}
              tone={toneFor(fw?.false_negative, (n) => n > 0, TONE_WARN)}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.attackSuccess")}
              infoKey="attackRate"
              value={pct(attackRate)}
              tone={attackRate != null && attackRate > 0.2 ? BAD : WARN}
              series={fwSpark}
              href="/surveiller/qualite-ia"
              drillLabel={ts("tabx.attackSuccess")}
            />
          </>,
        )}
        <Zone
          label={ts("sec.controls")}
          info={<SecInfo k="zoneControls" title={ts("sec.controls")} />}
        >
          {controlsTable(controls.filter((c) => c.key === "promptInjection"))}
        </Zone>
        <Zone
          label={ts("sec.diagnostic")}
          info={<SecInfo k="zoneDiagnostic" title={ts("sec.diagnostic")} />}
        >
          <div className="grid gap-2 lg:grid-cols-3">
            {trendPanel}
            {redteamPanel}
            {casesPanel(["prompt_injection"])}
          </div>
        </Zone>
      </>
    ),
    pii: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.piiLeak")}
              infoKey="piiLeak"
              value={pct(piiRate)}
              tone={piiRate ? BAD : GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.piiTurns")}
              infoKey="piiTurns"
              value={`${showNumber(pii.data?.n_with_leak)}/${showNumber(pii.data?.n_turns)}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("ctrl.toxicity")}
              infoKey="toxicity"
              value={pct(toxRate, 2)}
              tone={toxRate ? BAD : GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("kpi.sensitiveMemory")}
              infoKey="sensitiveMemory"
              value={inventoryExpiring}
              tone={
                inventoryDenied
                  ? WARN
                  : toneFor(inventory.data?.n_expiring_soon, (n) => n > 0, TONE_WARN)
              }
              href="/configurer/sources-memoire"
              drillLabel={ts("kpi.sensitiveMemory")}
            />
          </>,
        )}
        <Zone
          label={ts("sec.controls")}
          info={<SecInfo k="zoneControls" title={ts("sec.controls")} />}
        >
          {controlsTable(controls.filter((c) => c.key === "piiLeak" || c.key === "toxicity"))}
        </Zone>
        <Zone
          label={ts("sec.privacy")}
          info={<SecInfo k="zonePrivacy" title={ts("sec.privacy")} />}
        >
          <div className="grid gap-2 lg:grid-cols-3">
            {erasurePanel}
            {inversionPanel}
            {casesPanel(["pii"])}
          </div>
        </Zone>
      </>
    ),
    guard: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.guard")}
              infoKey="guard"
              value={`F1 ${dec2(fw?.f1)}`}
              tone={fw && fw.f1 >= 0.7 ? GOOD : WARN}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.recall")}
              infoKey="recall"
              value={dec2(fw?.recall)}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.precision")}
              infoKey="precision"
              value={dec2(fw?.precision)}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.conformance")}
              infoKey="conformance"
              value={pct(conformance.data?.conformance_rate)}
              tone={(conformance.data?.conformance_rate ?? 1) >= 0.95 ? GOOD : WARN}
              href="/surveiller/conformite"
              drillLabel={ts("tabx.conformance")}
            />
          </>,
        )}
        <Zone
          label={ts("sec.diagnostic")}
          info={<SecInfo k="zoneDiagnostic" title={ts("sec.diagnostic")} />}
        >
          <div className="grid gap-2 lg:grid-cols-3">
            <Panel
              title={ts("panel.refusal")}
              info={<SecInfo k="refusal" title={ts("panel.refusal")} />}
            >
              <div className="flex items-center gap-2">
                <Gauge
                  value={refusal.data?.over_refusal_rate ?? 0}
                  label={ts("panel.overRefusal")}
                  tone="var(--tessera-fg-warning)"
                />
                <div className="flex min-w-0 flex-col gap-1 text-[0.7rem]">
                  <KV
                    label={ts("panel.underRefusal")}
                    value={pct(refusal.data?.under_refusal_rate)}
                    tone={toneFor(refusal.data?.under_refusal_rate, (r) => r > 0.1, TONE_BAD)}
                  />
                  <KV label={ts("panel.legit")} value={`${showNumber(refusal.data?.n_legit)}`} />
                  <KV
                    label={ts("panel.forbidden")}
                    value={`${showNumber(refusal.data?.n_forbidden)}`}
                  />
                </div>
              </div>
            </Panel>
            <Panel
              title={ts("panel.whatChanged")}
              info={<SecInfo k="whatChanged" title={ts("panel.whatChanged")} />}
            >
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {(whatChanged.data?.changes ?? []).length === 0 ? (
                  <li className="text-[var(--muted-foreground)]">{ts("panel.noChanges")}</li>
                ) : (
                  (whatChanged.data?.changes ?? []).slice(0, 4).map((c) => (
                    <li key={c.field} className="flex items-center gap-2">
                      <Truncate className="min-w-0 flex-1">{c.field}</Truncate>
                      <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                        {c.before.slice(0, 8)} → {c.after.slice(0, 8)}
                      </span>
                    </li>
                  ))
                )}
              </ul>
            </Panel>
            <Panel title={ts("tabx.guardLinks")}>
              <div className="flex flex-col gap-1.5 text-[0.72rem]">
                <Link
                  href="/configurer/politiques"
                  className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] px-2 py-1.5 hover:border-[var(--tessera-green)] hover:text-[var(--tessera-green)]"
                >
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
                  {ts("tabx.linkPolicies")}
                </Link>
                <Link
                  href="/configurer/garde-fous"
                  className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] px-2 py-1.5 hover:border-[var(--tessera-green)] hover:text-[var(--tessera-green)]"
                >
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
                  {ts("tabx.linkGuardrails")}
                </Link>
                <Link
                  href="/prouver/audit-logs"
                  className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] px-2 py-1.5 hover:border-[var(--tessera-green)] hover:text-[var(--tessera-green)]"
                >
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0" />
                  {ts("tabx.linkAudit")}
                </Link>
              </div>
            </Panel>
          </div>
        </Zone>
      </>
    ),
    tools: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.leastPriv")}
              infoKey="leastPriv"
              value={`${showNumber(lp.data?.n_used)}/${showNumber(lp.data?.n_granted)}`}
              tone={MUTED}
              href="/admin/roles-acces"
              drillLabel={ts("kpi.leastPriv")}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.overProvCount")}
              infoKey="overProvCount"
              value={`${showNumber(lp.data?.n_over_provisioned)}`}
              tone={toneFor(lp.data?.n_over_provisioned, (n) => n > 0, TONE_WARN)}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.overProvRate")}
              infoKey="overProvRate"
              value={pct(overProvRate)}
              tone={overProvRate && overProvRate > 0.4 ? BAD : WARN}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("ctrl.toolMisuse")}
              infoKey="toolMisuse"
              value={`${pct(overProvRate)}`}
              tone={MUTED}
            />
          </>,
        )}
        <Zone
          label={ts("sec.controls")}
          info={<SecInfo k="zoneControls" title={ts("sec.controls")} />}
        >
          {controlsTable(controls.filter((c) => c.key === "toolMisuse"))}
        </Zone>
        <Zone
          label={ts("sec.diagnostic")}
          info={<SecInfo k="zoneDiagnostic" title={ts("sec.diagnostic")} />}
        >
          <div className="grid gap-2 lg:grid-cols-2">
            <Panel
              title={ts("panel.overPriv")}
              info={<SecInfo k="overPriv" title={ts("panel.overPriv")} />}
            >
              <ul className="flex flex-col gap-1 text-[0.72rem]">
                {(lp.data?.usage ?? []).slice(0, 8).map((u) => {
                  const over = lp.data?.over_provisioned.includes(u.tool);
                  return (
                    <li key={u.tool} className="flex items-center justify-between gap-2">
                      <Truncate className="min-w-0 font-mono">{u.tool}</Truncate>
                      <Badge tone={over ? "warning" : "success"}>
                        {over ? ts("overProvisioned") : `${u.used}`}
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            </Panel>
            {casesPanel(["tool"])}
          </div>
        </Zone>
      </>
    ),
    memory: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={ShieldAlert}
              label={ts("kpi.sensitiveMemory")}
              infoKey="sensitiveMemory"
              value={inventoryExpiring}
              tone={
                inventoryDenied
                  ? WARN
                  : toneFor(inventory.data?.n_expiring_soon, (n) => n > 0, TONE_WARN)
              }
              href="/configurer/sources-memoire"
              drillLabel={ts("kpi.sensitiveMemory")}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("panel.conversations")}
              infoKey="conversations"
              value={`${showNumber(erasure.data?.n_conversations)}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.erasureCompleteness")}
              infoKey="erasure"
              value={pct(erasureComplete)}
              tone={GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("panel.recoverable")}
              infoKey="inversion"
              value={`${showNumber(inversion.data?.n_recoverable)}/${showNumber(inversion.data?.n_memories)}`}
              tone={toneFor(inversion.data?.n_recoverable, (n) => n > 0, TONE_BAD)}
            />
          </>,
        )}
        <Zone
          label={ts("sec.privacy")}
          info={<SecInfo k="zonePrivacy" title={ts("sec.privacy")} />}
        >
          <div className="grid gap-2 lg:grid-cols-3">
            {erasurePanel}
            {inversionPanel}
            {casesPanel(["memory", "pii"])}
          </div>
        </Zone>
      </>
    ),
    isolation: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={ShieldCheck}
              label={ts("ctrl.crossTenant")}
              infoKey="crossTenant"
              value={pct(xtRate)}
              tone={xtRate ? BAD : GOOD}
              href="/admin/profil-systeme"
              drillLabel={ts("ctrl.crossTenant")}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.isolationProbes")}
              infoKey="isolationProbes"
              value={`${showNumber(crossTenant.data?.n_turns)}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.isolationLeaks")}
              infoKey="isolationLeaks"
              value={`${showNumber(crossTenant.data?.n_leaks)}`}
              tone={toneFor(crossTenant.data?.n_leaks, (n) => n > 0, TONE_BAD)}
            />
          </>,
        )}
        <Zone
          label={ts("sec.controls")}
          info={<SecInfo k="zoneControls" title={ts("sec.controls")} />}
        >
          {controlsTable(controls.filter((c) => c.key === "crossTenant"))}
        </Zone>
        <Zone
          label={ts("sec.diagnostic")}
          info={<SecInfo k="zoneDiagnostic" title={ts("sec.diagnostic")} />}
        >
          <div className="grid gap-2 lg:grid-cols-2">
            <Panel
              title={ts("tabx.isolationTitle")}
              info={<SecInfo k="isolationFacts" title={ts("tabx.isolationTitle")} />}
            >
              <ul className="flex flex-col gap-1.5 text-[0.72rem] text-[var(--muted-foreground)]">
                <li>{ts("tabx.isolationFactEnv")}</li>
                <li>{ts("tabx.isolationFactSchema")}</li>
                <li>{ts("tabx.isolationFactState")}</li>
              </ul>
              <Link
                href="/admin/profil-systeme"
                className="mt-2 inline-flex items-center gap-1 text-[0.7rem] text-[var(--tessera-green)] hover:underline"
              >
                {ts("tabx.linkSystem")} <ArrowUpRight className="h-3 w-3" />
              </Link>
            </Panel>
            {casesPanel(["cross_tenant", "tenant"])}
          </div>
        </Zone>
      </>
    ),
    redteam: (
      <>
        {kpiGrid(
          <>
            <Kpi
              icon={Siren}
              label={ts("tabx.probes")}
              infoKey="probes"
              value={`${showNumber(fw?.n_positive)}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.blocked")}
              infoKey="blocked"
              value={blocked}
              tone={GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.attackSuccess")}
              infoKey="attackRate"
              value={pct(attackRate)}
              tone={attackRate != null && attackRate > 0.2 ? BAD : WARN}
              series={fwSpark}
              href="/surveiller/qualite-ia"
              drillLabel={ts("tabx.attackSuccess")}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.guard")}
              infoKey="guard"
              value={`F1 ${dec2(fw?.f1)}`}
              tone={fw && fw.f1 >= 0.7 ? GOOD : WARN}
            />
          </>,
        )}
        <Zone
          label={ts("sec.diagnostic")}
          info={<SecInfo k="zoneDiagnostic" title={ts("sec.diagnostic")} />}
        >
          <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
            <Panel
              title={ts("panel.failures")}
              info={<SecInfo k="failures" title={ts("panel.failures")} />}
            >
              {/* One of the six slices (`inversion`) counts the demonstration corpus. */}
              <ProvenanceNotice signalId="embedding_inversion" compact />
              {failureSlices.length === 0 ? (
                <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                  {ts("panel.noFailures")}
                </p>
              ) : (
                <FailureDonut slices={failureSlices} label={ts("panel.failuresUnit")} />
              )}
            </Panel>
            <Panel
              title={ts("panel.regression")}
              info={<SecInfo k="regression" title={ts("panel.regression")} />}
            >
              {regressionBody}
            </Panel>
            {trendPanel}
            {casesPanel([], 8)}
          </div>
        </Zone>
      </>
    ),
  };

  return (
    <div className="flex flex-col gap-2.5">
      {/* The temporal rail LEADS — directly beneath the SLO breach alert the page renders
          above the dashboard (user feedback) — then the chrome, then the agent scope. */}
      <SignalCommandBar
        temporal={temporal}
        timeline={railTimeline.data}
        liveStatus={ts("status.realtime")}
      />
      {/* chrome */}
      <div className="flex items-center justify-between gap-3 border-b border-[var(--tessera-border)] pb-1.5">
        <div
          role="tablist"
          aria-label={ts("tabs.overview")}
          className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5"
        >
          {SEC_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={tab === activeTab}
              aria-controls="security-tabpanel"
              onClick={() => setActiveTab(tab)}
              className={`h-8 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors ${
                tab === activeTab
                  ? "border-[#007a55] bg-[#0b3d2e] text-[#d6f0e3]"
                  : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
              }`}
            >
              {ts(`tabs.${tab}`)}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            asChild
            size="sm"
            className="h-8 gap-2 border border-[#007a55] bg-[#005c42] text-xs text-[#d6f0e3] hover:bg-[#006d4e]"
          >
            <Link href="/surveiller/qualite-ia">
              <Siren className="h-3.5 w-3.5" /> {ts("cta.redteam")}
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline" className="h-8 gap-2 text-xs">
            <Link href="/prouver/evidence-store">
              <ShieldCheck className="h-3.5 w-3.5" /> {ts("cta.report")}
            </Link>
          </Button>
        </div>
      </div>

      {/* Agent-scope context (Vue par agent) sits BELOW the rail, so the rail stays
          directly under the SLO alert. */}
      {agentScope ? <div>{agentScope}</div> : null}

      {activeTab !== "overview" ? (
        <div id="security-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-2.5">
          {domainView[activeTab]}
        </div>
      ) : (
        <div className="grid gap-2.5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-2.5">
            {/* État actuel */}
            <Zone
              label={ts("sec.actual")}
              info={<SecInfo k="zoneActual" title={ts("sec.actual")} />}
            >
              <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
                <Kpi
                  icon={ShieldAlert}
                  label={ts("kpi.attackRate")}
                  infoKey="attackRate"
                  value={pct(attackRate)}
                  tone={attackRate != null && attackRate > 0.2 ? BAD : WARN}
                  series={fwSpark}
                  delta={sparkDelta(attackSeries)}
                  deltaUpIsGood={false}
                />
                <Kpi
                  icon={ShieldCheck}
                  label={ts("kpi.blocked")}
                  infoKey="blocked"
                  value={blocked}
                  tone={GOOD}
                  series={fwSpark.map((v) => 1 - v)}
                  delta={sparkDelta(incidentSeries.map((v) => -v))}
                  deltaUpIsGood
                />
                <Kpi
                  icon={ShieldCheck}
                  label={ts("kpi.piiLeak")}
                  infoKey="piiLeak"
                  value={pct(piiRate)}
                  tone={piiRate ? BAD : GOOD}
                />
                <Kpi
                  icon={ShieldCheck}
                  label={ts("kpi.leastPriv")}
                  infoKey="leastPriv"
                  value={`${showNumber(lp.data?.n_used)}/${showNumber(lp.data?.n_granted)}`}
                  tone={MUTED}
                  hint={ts("kpi.leastPrivHint")}
                  href="/admin/roles-acces"
                  drillLabel={ts("kpi.leastPriv")}
                />
                <Kpi
                  icon={ShieldAlert}
                  label={ts("kpi.sensitiveMemory")}
                  infoKey="sensitiveMemory"
                  value={inventoryExpiring}
                  tone={
                    inventoryDenied
                      ? WARN
                      : toneFor(inventory.data?.n_expiring_soon, (n) => n > 0, TONE_WARN)
                  }
                  hint={ts("kpi.sensitiveMemoryHint")}
                  href="/configurer/sources-memoire"
                  drillLabel={ts("kpi.sensitiveMemory")}
                />
                <Kpi
                  icon={ShieldCheck}
                  label={ts("kpi.guard")}
                  infoKey="guard"
                  value={`F1 ${dec2(fw?.f1)}`}
                  tone={fw && fw.f1 >= 0.7 ? GOOD : WARN}
                  hint={`${ts("kpi.recall")} ${dec2(fw?.recall)}`}
                />
              </div>
            </Zone>

            {/* Contrôles critiques */}
            <Zone
              label={ts("sec.controls")}
              info={<SecInfo k="zoneControls" title={ts("sec.controls")} />}
            >
              {controlsTable(controls)}
            </Zone>

            {/* Diagnostic racine */}
            <Zone
              label={ts("sec.diagnostic")}
              info={<SecInfo k="zoneDiagnostic" title={ts("sec.diagnostic")} />}
            >
              <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
                <Panel
                  title={ts("panel.failures")}
                  info={<SecInfo k="failures" title={ts("panel.failures")} />}
                >
                  <ProvenanceNotice signalId="embedding_inversion" compact />
                  {failureSlices.length === 0 ? (
                    <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                      {ts("panel.noFailures")}
                    </p>
                  ) : (
                    <FailureDonut slices={failureSlices} label={ts("panel.failuresUnit")} />
                  )}
                </Panel>
                <Panel
                  title={ts("panel.whatChanged")}
                  info={<SecInfo k="whatChanged" title={ts("panel.whatChanged")} />}
                >
                  <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                    {(whatChanged.data?.changes ?? []).length === 0 ? (
                      <li className="text-[var(--muted-foreground)]">{ts("panel.noChanges")}</li>
                    ) : (
                      (whatChanged.data?.changes ?? []).slice(0, 4).map((c) => (
                        <li key={c.field} className="flex items-center gap-2">
                          <Truncate className="min-w-0 flex-1">{c.field}</Truncate>
                          <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                            {c.before.slice(0, 8)} → {c.after.slice(0, 8)}
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                </Panel>
                <Panel
                  title={ts("panel.refusal")}
                  info={<SecInfo k="refusal" title={ts("panel.refusal")} />}
                >
                  <div className="flex items-center gap-2">
                    <Gauge
                      value={refusal.data?.over_refusal_rate ?? 0}
                      label={ts("panel.overRefusal")}
                      tone="var(--tessera-fg-warning)"
                    />
                    <div className="flex min-w-0 flex-col gap-1 text-[0.7rem]">
                      <KV
                        label={ts("panel.underRefusal")}
                        value={pct(refusal.data?.under_refusal_rate)}
                        tone={toneFor(refusal.data?.under_refusal_rate, (r) => r > 0.1, TONE_BAD)}
                      />
                      <KV
                        label={ts("panel.legit")}
                        value={`${showNumber(refusal.data?.n_legit)}`}
                      />
                      <KV
                        label={ts("panel.forbidden")}
                        value={`${showNumber(refusal.data?.n_forbidden)}`}
                      />
                    </div>
                  </div>
                </Panel>
                <Panel
                  title={ts("panel.priorityCases")}
                  info={<SecInfo k="priorityCases" title={ts("panel.priorityCases")} />}
                >
                  <ul className="flex flex-col gap-1 text-[0.72rem]">
                    {(failed.data?.cases ?? []).slice(0, 4).map((c) => (
                      <li key={c.case_id} className="flex items-center gap-1.5">
                        <span
                          className={`h-1.5 w-1.5 shrink-0 rounded-full ${c.severity === "critical" ? "bg-red-500" : c.severity === "high" ? "bg-amber-500" : "bg-[var(--muted-foreground)]"}`}
                        />
                        <Truncate className="min-w-0 flex-1">{c.title}</Truncate>
                        <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                          {c.case_id}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              </div>
            </Zone>

            {/* Signaux prédictifs */}
            <Zone
              label={ts("sec.predictive")}
              info={<SecInfo k="zonePredictive" title={ts("sec.predictive")} />}
            >
              <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
                <Panel
                  title={ts("panel.trend")}
                  info={<SecInfo k="trend" title={ts("panel.trend")} />}
                >
                  <LineChart
                    a={attackSeries}
                    b={incidentSeries}
                    aLabel={ts("panel.attackLine")}
                    bLabel={ts("panel.incidentLine")}
                  />
                </Panel>
                <Panel
                  title={ts("panel.regression")}
                  info={<SecInfo k="regression" title={ts("panel.regression")} />}
                >
                  {regressionBody}
                </Panel>
                <Panel
                  title={ts("panel.domainRisk")}
                  info={<SecInfo k="domainRisk" title={ts("panel.domainRisk")} />}
                >
                  {/* `privacy` and `memory` both read the demonstration corpus. */}
                  <ProvenanceNotice signalId="embedding_inversion" compact />
                  <div className="flex flex-col gap-1.5">
                    {domainRisks.map((d) => (
                      <RiskBar key={d.key} label={ts(`domain.${d.key}`)} value={d.value} />
                    ))}
                  </div>
                </Panel>
                <Panel
                  title={ts("panel.overPriv")}
                  info={<SecInfo k="overPriv" title={ts("panel.overPriv")} />}
                >
                  <ul className="flex flex-col gap-1 text-[0.72rem]">
                    {(lp.data?.usage ?? []).slice(0, 5).map((u) => {
                      const over = lp.data?.over_provisioned.includes(u.tool);
                      return (
                        <li key={u.tool} className="flex items-center justify-between gap-2">
                          <Truncate className="min-w-0 font-mono">{u.tool}</Truncate>
                          <Badge tone={over ? "warning" : "success"}>
                            {over ? ts("overProvisioned") : `${u.used}`}
                          </Badge>
                        </li>
                      );
                    })}
                  </ul>
                </Panel>
              </div>
            </Zone>

            {/* Privacy / Mémoire / SOC */}
            <Zone
              label={ts("sec.privacy")}
              info={<SecInfo k="zonePrivacy" title={ts("sec.privacy")} />}
            >
              <div className="grid gap-2 lg:grid-cols-3">
                <Panel
                  title={ts("panel.redteam")}
                  info={<SecInfo k="redteam" title={ts("panel.redteam")} />}
                >
                  <div className="flex flex-col gap-1.5 text-[0.72rem]">
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-semibold tabular-nums">{blocked}</span>
                      <span className="text-[var(--muted-foreground)]">{ts("panel.blocked")}</span>
                      <span className="ml-auto font-semibold tabular-nums text-[var(--tessera-fg-warning)]">
                        {showNumber(fw?.false_negative)} {ts("panel.bypasses")}
                      </span>
                    </div>
                    <div className="flex h-[4px] w-full overflow-hidden rounded-full">
                      <div
                        style={{
                          flexBasis: `${(blockRate ?? 0) * 100}%`,
                          background: "var(--tessera-fg-success)",
                        }}
                      />
                      <div style={{ flexGrow: 1, background: "var(--tessera-fg-warning)" }} />
                    </div>
                    <KV label={ts("panel.blockRate")} value={pct(blockRate)} tone={GOOD} />
                    <KV
                      label={ts("panel.uniqueBypasses")}
                      value={`${showNumber(fw?.false_negative)}`}
                    />
                  </div>
                </Panel>
                <Panel
                  title={ts("panel.erasureSurface")}
                  info={<SecInfo k="erasureSurface" title={ts("panel.erasureSurface")} />}
                >
                  <div className="flex items-center gap-3">
                    <Gauge
                      value={erasureComplete ?? 0}
                      label={ts("panel.completeness")}
                      tone="var(--tessera-fg-success)"
                    />
                    <div className="flex min-w-0 flex-col gap-0.5 text-[0.7rem]">
                      <KV
                        label={ts("panel.conversations")}
                        value={`${showNumber(erasure.data?.n_conversations)}`}
                      />
                      <KV
                        label={ts("panel.bundles")}
                        value={`${showNumber(erasure.data?.n_bundles)}`}
                      />
                      <KV
                        label={ts("panel.scores")}
                        value={`${showNumber(erasure.data?.n_scores)}`}
                      />
                    </div>
                  </div>
                  <Button
                    asChild
                    size="sm"
                    variant="outline"
                    className="mt-2 h-7 w-full justify-center text-[0.7rem]"
                  >
                    <Link href="/configurer/sources-memoire">{ts("panel.purgeCta")}</Link>
                  </Button>
                </Panel>
                <Panel
                  title={ts("panel.inversion")}
                  info={<SecInfo k="inversion" title={ts("panel.inversion")} />}
                >
                  {inversion.data?.available === false || inversion.isLoading ? (
                    <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                      {ts("panel.computing")}
                    </p>
                  ) : (
                    <div className="flex flex-col gap-1 text-[0.72rem]">
                      <KV
                        label={ts("panel.recoverable")}
                        value={`${showNumber(inversion.data?.n_recoverable)}/${showNumber(inversion.data?.n_memories)}`}
                        tone={toneFor(inversion.data?.n_recoverable, (n) => n > 0, TONE_BAD)}
                      />
                      <KV label={ts("panel.recoveryRate")} value={pct(invRate)} />
                      <KV label={ts("panel.threshold")} value={dec2(inversion.data?.threshold)} />
                    </div>
                  )}
                </Panel>
              </div>
            </Zone>

            {/* Actions recommandées */}
            <Zone
              label={ts("sec.actions")}
              info={<SecInfo k="zoneActions" title={ts("sec.actions")} />}
            >
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <ActionCard
                  icon={Siren}
                  title={ts("act.redteamTitle")}
                  desc={ts("act.redteamDesc")}
                  roleLabel={ts("role.security")}
                  cta={ts("act.redteamCta")}
                  href="/surveiller/qualite-ia"
                />
                <ActionCard
                  icon={Snowflake}
                  title={ts("act.freezeTitle")}
                  desc={ts("act.freezeDesc")}
                  roleLabel="Admin+"
                  cta={ts("act.freezeCta")}
                  href="/agir/release-control"
                />
                <ActionCard
                  icon={ShieldAlert}
                  title={ts("act.playbookTitle")}
                  desc={ts("act.playbookDesc")}
                  roleLabel={ts("role.security")}
                  cta={ts("act.playbookCta")}
                  href="/agir/incidents-playbooks"
                />
                <ActionCard
                  icon={Trash2}
                  title={ts("act.purgeTitle")}
                  desc={ts("act.purgeDesc")}
                  roleLabel={ts("role.privacy")}
                  cta={ts("act.purgeCta")}
                  href="/configurer/sources-memoire"
                />
              </div>
            </Zone>
          </div>

          <SecurityRail
            firewall={fw}
            conformance={conformance.data}
            lp={lp.data}
            anomalies={anomalies.data}
            failed={failed.data}
          />
        </div>
      )}

      {/* footer status */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--muted-foreground)]">
        <Chip icon={Radio} label={ts("status.realtime")} tone="text-[var(--tessera-green)]" />
        <Chip icon={ShieldCheck} label={ts("status.chain")} tone="text-[var(--tessera-green)]" />
        <Chip icon={AlertTriangle} label={ts("status.signals", { n: 200 })} />
      </div>
    </div>
  );
}

function KV({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <span className={`tabular-nums ${tone ?? ""}`}>{value}</span>
    </div>
  );
}

function Chip({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
      <Icon className={`h-3.5 w-3.5 shrink-0 ${tone ?? ""}`} />
      <span className="truncate">{label}</span>
    </span>
  );
}

// ── right rail ───────────────────────────────────────────────────────────────

function SecurityRail({
  firewall,
  conformance,
  lp,
  anomalies,
  failed,
}: {
  firewall: FirewallEfficacy | undefined;
  conformance: ConformanceReport | undefined;
  lp: PrivilegeReport | undefined;
  anomalies: AnomalyReport | undefined;
  failed: FailedCasesReport | undefined;
}) {
  const ts = useTranslations("security");
  const incidents = (failed?.cases ?? []).slice(0, 5);
  const onExportIncidents = () =>
    downloadBlob(
      "tessera-security-incidents.json",
      "application/json",
      JSON.stringify(failed?.cases ?? [], null, 2),
    );
  const gates: { label: string; pass: boolean | "watch" }[] = [
    { label: ts("gate.security"), pass: firewall ? firewall.precision >= 0.9 : "watch" },
    { label: ts("gate.privacy"), pass: true },
    { label: ts("gate.compliance"), pass: (conformance?.conformance_rate ?? 1) >= 0.9 },
    { label: ts("gate.audit"), pass: "watch" },
  ];
  const sevDot = (s: string) =>
    s === "critical"
      ? "bg-red-500"
      : s === "high"
        ? "bg-amber-500"
        : "bg-[var(--muted-foreground)]";

  return (
    <aside className="flex min-w-0 flex-col gap-2.5">
      <div className="flex flex-col gap-2.5 xl:sticky xl:top-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {ts("rail.incidents")}
              <span className="ml-auto shrink-0">
                <SecInfo k="railIncidents" title={ts("rail.incidents")} />
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {incidents.length === 0 ? (
              <p className="text-[0.7rem] text-[var(--muted-foreground)]">
                {ts("rail.noIncidents")}
              </p>
            ) : (
              incidents.map((c) => (
                <div key={c.case_id} className="flex items-center gap-1.5 text-[0.72rem]">
                  <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${sevDot(c.severity)}`} />
                  <Truncate className="min-w-0 flex-1">{c.title}</Truncate>
                  <Badge
                    tone={
                      c.severity === "critical"
                        ? "danger"
                        : c.severity === "high"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {ts(
                      `state.${c.severity === "critical" ? "crit" : c.severity === "high" ? "high" : "warn"}`,
                    )}
                  </Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {ts("rail.privacyEvidence")}
              <span className="ml-auto shrink-0">
                <SecInfo k="railGates" title={ts("rail.privacyEvidence")} />
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {gates.map((g) => (
              <div key={g.label} className="flex items-center justify-between gap-2 text-[0.72rem]">
                <span className="text-[var(--muted-foreground)]">{g.label}</span>
                <Badge
                  tone={g.pass === true ? "success" : g.pass === "watch" ? "warning" : "danger"}
                >
                  {g.pass === true ? "PASS" : g.pass === "watch" ? "WATCH" : "FAIL"}
                </Badge>
              </div>
            ))}
            <Link
              href="/prouver/evidence-store"
              className="mt-1 inline-flex h-8 w-full items-center justify-center gap-2 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[var(--tessera-fg-accent)] transition-colors hover:bg-[#4c3fb0]/60"
            >
              {ts("rail.evidenceCta")}
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ts("rail.quickActions")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-0.5">
            {(
              [
                { key: "qaRedteam", icon: Siren, href: "/surveiller/qualite-ia" },
                { key: "qaIncident", icon: AlertTriangle, href: "/agir/incidents-playbooks" },
                { key: "qaPurge", icon: Trash2 },
                { key: "qaTicket", icon: ShieldCheck, href: "/surveiller/conformite" },
              ] as { key: string; icon: LucideIcon; href?: Route }[]
            ).map((a) =>
              a.href ? (
                <Link
                  key={a.key}
                  href={a.href}
                  className="flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.72rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
                >
                  <a.icon className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{ts(`rail.${a.key}`)}</span>
                </Link>
              ) : (
                // GDPR purge has no endpoint yet — honest disabled state, never a silent no-op.
                <button
                  key={a.key}
                  type="button"
                  disabled
                  title={ts("rail.notWired")}
                  className="flex cursor-not-allowed items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.72rem] text-[var(--muted-foreground)] opacity-60"
                >
                  <a.icon className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{ts(`rail.${a.key}`)}</span>
                </button>
              ),
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {ts("rail.tools")}
              <span className="ml-auto shrink-0">
                <SecInfo k="railTools" title={ts("rail.tools")} />
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-[0.7rem]">
                <thead>
                  <tr className="text-left text-[var(--muted-foreground)]">
                    <th className="pb-1 font-medium">{ts("rail.tool")}</th>
                    <th className="pb-1 text-right font-medium">{ts("rail.used")}</th>
                    <th className="pb-1 text-right font-medium">{ts("rail.risk")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(lp?.usage ?? []).slice(0, 5).map((u) => {
                    const over = lp?.over_provisioned.includes(u.tool);
                    return (
                      <tr key={u.tool}>
                        <td className="py-0.5 font-mono">{u.tool}</td>
                        <td className="py-0.5 text-right tabular-nums">{u.used}</td>
                        <td className={`py-0.5 text-right ${over ? WARN : GOOD}`}>
                          {over ? ts("state.high") : ts("state.ok")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {ts("rail.siem")}
              <span className="ml-auto shrink-0">
                <SecInfo k="railSiem" title={ts("rail.siem")} />
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            {incidents.slice(0, 3).map((c) => (
              <div
                key={c.case_id}
                className="flex items-center justify-between gap-2 text-[0.7rem]"
              >
                {/* Real case id + real severity (was a fabricated "CASE-02xx" id and a
                  hardcoded "High" badge — honest data only: never invent an id/severity). */}
                <span className="shrink-0 font-mono text-[var(--tessera-green)]">{c.case_id}</span>
                <Truncate className="min-w-0 flex-1 text-[var(--muted-foreground)]">
                  {c.title}
                </Truncate>
                <Badge
                  tone={
                    c.severity === "critical"
                      ? "danger"
                      : c.severity === "high"
                        ? "warning"
                        : "neutral"
                  }
                >
                  {ts(
                    `state.${c.severity === "critical" ? "crit" : c.severity === "high" ? "high" : "warn"}`,
                  )}
                </Badge>
              </div>
            ))}
            <Button
              size="sm"
              variant="outline"
              onClick={onExportIncidents}
              className="mt-1 h-7 justify-center text-[0.7rem]"
            >
              {ts("rail.exportSiem")}
            </Button>
            {anomalies?.n_anomalous ? (
              <p className="text-[0.62rem] text-[var(--muted-foreground)]">
                {ts("rail.anomalies", { n: anomalies.n_anomalous })}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </aside>
  );
}
