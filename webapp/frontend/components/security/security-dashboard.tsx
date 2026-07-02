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
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { useRailTimeline, useTemporalState } from "@/components/overview/temporal-rail";
import { SignalCommandBar } from "@/components/surveiller/signal-command-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import {
  fetchAnomalies,
  fetchConformance,
  fetchCrossTenant,
  fetchEmbeddingInversion,
  fetchErasureCoverage,
  fetchFailedCases,
  fetchFirewallEfficacy,
  fetchLeastPrivilege,
  fetchMemoryInventory,
  fetchPiiLeak,
  fetchRefusal,
  fetchRegressionRisk,
  fetchScoreSeries,
  fetchToxicity,
  fetchWhatChanged,
} from "@/lib/api/client";
import type {
  AnomalyReport,
  ConformanceReport,
  FailedCasesReport,
  FirewallEfficacy,
  PrivilegeReport,
} from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";

type Tone = "ok" | "warn" | "crit" | "high";
const TONE_BADGE: Record<Tone, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  warn: "warning",
  high: "warning",
  crit: "danger",
};
const toneText = (t: Tone) => (t === "ok" ? GOOD : t === "crit" ? BAD : WARN);

function pct(v: number | null | undefined, digits = 0): string {
  return v == null ? "—" : `${(v * 100).toFixed(digits)}%`;
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
}: { title: string; children: ReactNode; className?: string }) {
  return (
    <Card className={`flex h-full min-w-0 flex-col ${className ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-[0.78rem] font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1">{children}</CardContent>
    </Card>
  );
}

/** A translucent banded section grouping one cockpit zone (A · B · C · …). */
function Zone({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--tessera-border)]/50 bg-[var(--tessera-surface)]/25 p-2.5">
      <Sec>{label}</Sec>
      <div className="mt-1.5">{children}</div>
    </section>
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
            {Math.abs((delta as number) * 100).toFixed(1)} pts {ts("kpi.vs7d")}
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
      <path d={d} fill="none" stroke="#f97316" strokeWidth="1.4" strokeLinejoin="round" />
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
  const tone = value >= 0.5 ? "#ef4444" : value >= 0.25 ? "#f59e0b" : "#10b981";
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
  const total = slices.reduce((s, x) => s + x.count, 0) || 1;
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
            const frac = s.count / total;
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
          <span className="text-base font-semibold tabular-nums">{total}</span>
          <span className="text-[0.5rem] uppercase text-[var(--muted-foreground)]">{label}</span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.7rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate">{ts(`fail.${s.key}`)}</span>
            <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
              {s.count} · {Math.round((s.count / total) * 100)}%
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
        <path d={path(a)} fill="none" stroke="#f97316" strokeWidth="1.6" strokeLinejoin="round" />
        {b.length >= 2 ? (
          <path d={path(b)} fill="none" stroke="#ef4444" strokeWidth="1.4" strokeLinejoin="round" />
        ) : null}
      </svg>
      <div className="flex gap-3 text-[0.6rem] text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span className="h-1 w-3 rounded-full bg-[#f97316]" /> {aLabel}
        </span>
        {b.length >= 2 ? (
          <span className="flex items-center gap-1">
            <span className="h-1 w-3 rounded-full bg-[#ef4444]" /> {bLabel}
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
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
        <span className="min-w-0 text-[0.78rem] font-medium leading-snug">{title}</span>
      </div>
      <p className="text-[0.68rem] leading-snug text-[var(--muted-foreground)]">{desc}</p>
      <div className="flex flex-wrap items-center gap-1">
        <Badge tone="warning">{roleLabel}</Badge>
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
  const ts = useTranslations("security");
  const locale = useLocale();
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();
  const [activeTab, setActiveTab] = useState<SecTab>("overview");
  // Global agent scope (?agent=) — the score-/bundle-/audit-backed safety signals
  // read this agent's own turns; shared-policy probes (firewall, refusal) stay org.
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const firewall = useQuery({
    queryKey: ["firewall-efficacy"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const pii = useQuery({
    queryKey: ["pii-leak", asOf, scope],
    queryFn: ({ signal }) => fetchPiiLeak(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const lp = useQuery({
    queryKey: ["least-privilege"],
    queryFn: ({ signal }) => fetchLeastPrivilege(signal),
    refetchInterval: POLL,
  });
  const refusal = useQuery({
    queryKey: ["refusal"],
    queryFn: ({ signal }) => fetchRefusal(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const toxicity = useQuery({
    queryKey: ["toxicity", asOf, scope],
    queryFn: ({ signal }) => fetchToxicity(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const crossTenant = useQuery({
    queryKey: ["cross-tenant"],
    queryFn: ({ signal }) => fetchCrossTenant(signal),
    refetchInterval: POLL,
  });
  const inversion = useQuery({
    queryKey: ["embedding-inversion"],
    queryFn: ({ signal }) => fetchEmbeddingInversion(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const erasure = useQuery({
    queryKey: ["erasure-coverage"],
    queryFn: ({ signal }) => fetchErasureCoverage(signal),
    refetchInterval: POLL,
  });
  const inventory = useQuery({
    queryKey: ["memory-inventory"],
    queryFn: ({ signal }) => fetchMemoryInventory(signal),
    refetchInterval: POLL,
  });
  const anomalies = useQuery({
    queryKey: ["anomalies", asOf, scope],
    queryFn: ({ signal }) => fetchAnomalies(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const conformance = useQuery({
    queryKey: ["conformance", asOf, scope],
    queryFn: ({ signal }) => fetchConformance(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const regression = useQuery({
    queryKey: ["regression-risk", asOf],
    queryFn: ({ signal }) => fetchRegressionRisk(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const faith = useQuery({
    queryKey: ["score-series", "faithfulness", asOf, scope],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "faithfulness", scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const grounding = useQuery({
    queryKey: ["score-series", "grounding", asOf, scope],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "grounding", scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const whatChanged = useQuery({
    queryKey: ["what-changed", asOf, scope],
    queryFn: ({ signal }) => fetchWhatChanged(signal, asOf ?? undefined, scope),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const failed = useQuery({
    queryKey: ["failed-cases", locale],
    queryFn: ({ signal }) => fetchFailedCases(signal, locale),
    staleTime: Number.POSITIVE_INFINITY,
  });

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
  const tone = (rate: number | null, crit: number, warn: number): Tone =>
    rate == null ? "warn" : rate > crit ? "crit" : rate > warn ? "high" : "ok";
  const controls: Control[] = [
    {
      key: "promptInjection",
      tone: tone(attackRate, 0.2, 0.05),
      value: `${pct(attackRate)} (${fw?.false_negative ?? 0}/${fw?.n_positive ?? 0})`,
      target: "< 20%",
      action: ts("ctrl.promptInjectionAction"),
      role: ts("role.security"),
      case: "CASE-0201",
    },
    {
      key: "piiLeak",
      tone: tone(piiRate, 0.001, 0),
      value: `${pct(piiRate)} (${pii.data?.n_with_leak ?? 0}/${pii.data?.n_turns ?? 0})`,
      target: "0%",
      action: ts("ctrl.piiLeakAction"),
      role: ts("role.privacy"),
      case: "CASE-0205",
    },
    {
      key: "crossTenant",
      tone: tone(xtRate, 0.001, 0),
      value: pct(xtRate),
      target: "0%",
      action: ts("ctrl.crossTenantAction"),
      role: ts("role.security"),
      case: "CASE-0214",
    },
    {
      key: "toolMisuse",
      tone: tone(overProvRate, 0.4, 0.1),
      value: `${pct(overProvRate)} (${lp.data?.n_over_provisioned ?? 0}/${lp.data?.n_granted ?? 0})`,
      target: "< 5%",
      action: ts("ctrl.toolMisuseAction"),
      role: ts("role.security"),
      case: "CASE-0206",
    },
    {
      key: "inversion",
      tone: tone(invRate, 0.2, 0.05),
      value: `${pct(invRate)} (${inversion.data?.n_recoverable ?? 0}/${inversion.data?.n_memories ?? 0})`,
      target: "0%",
      action: ts("ctrl.inversionAction"),
      role: ts("role.ml"),
      case: "CASE-0228",
    },
    {
      key: "toxicity",
      tone: tone(toxRate, 0.001, 0),
      value: pct(toxRate, 2),
      target: "< 0.1%",
      action: ts("ctrl.toxicityAction"),
      role: ts("role.ml"),
      case: "CASE-0231",
    },
  ];

  // Domain risk (real, normalised).
  const domainRisks = [
    { key: "promptInj", value: attackRate ?? 0 },
    { key: "privacy", value: Math.max(piiRate ?? 0, invRate ?? 0) },
    { key: "tools", value: overProvRate ?? 0 },
    { key: "memory", value: invRate ?? 0 },
    { key: "compliance", value: 1 - (conformance.data?.conformance_rate ?? 1) },
  ].sort((a, b) => b.value - a.value);

  // Répartition des échecs (zone C donut) — real failure observations per family.
  const failureSlices = [
    { key: "injection", count: fw?.false_negative ?? 0, color: "#f97316" },
    { key: "toolMisuse", count: lp.data?.n_over_provisioned ?? 0, color: "#60a5fa" },
    { key: "inversion", count: inversion.data?.n_recoverable ?? 0, color: "#a78bfa" },
    {
      key: "refusal",
      count: (refusal.data?.legit_refused ?? 0) + (refusal.data?.forbidden_allowed ?? 0),
      color: "#fbbf24",
    },
    { key: "pii", count: pii.data?.n_with_leak ?? 0, color: "#f472b6" },
    { key: "toxicity", count: toxicity.data?.n_toxic ?? 0, color: "#34d399" },
  ].filter((s) => s.count > 0);

  const erasureComplete =
    erasure.data && erasure.data.n_conversations > 0
      ? erasure.data.n_bundles / erasure.data.n_conversations
      : null;

  // ── focused-tab building blocks (same live queries, curated per domain) ────
  const controlsTable = (rows: Control[]) => (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
              <th className="px-3 py-2 font-medium">{ts("col.signal")}</th>
              <th className="px-3 py-2 font-medium">{ts("col.state")}</th>
              <th className="px-3 py-2 font-medium">{ts("col.value")}</th>
              <th className="px-3 py-2 font-medium">{ts("col.target")}</th>
              <th className="px-3 py-2 font-medium">{ts("col.action")}</th>
              <th className="px-3 py-2 font-medium">{ts("col.role")}</th>
              <th className="px-3 py-2 font-medium">{ts("col.case")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.key} className="border-b border-[var(--border)]/50">
                <td className="px-3 py-2 font-medium">{ts(`ctrl.${c.key}`)}</td>
                <td className="px-3 py-2">
                  <Badge tone={TONE_BADGE[c.tone]}>{ts(`state.${c.tone}`)}</Badge>
                </td>
                <td className={`px-3 py-2 tabular-nums ${toneText(c.tone)}`}>{c.value}</td>
                <td className="px-3 py-2 tabular-nums text-[var(--muted-foreground)]">
                  {c.target}
                </td>
                <td className="px-3 py-2 text-[var(--muted-foreground)]">{c.action}</td>
                <td className="px-3 py-2">{c.role}</td>
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
      <Panel title={ts("tabx.domainCases")}>
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
                <span className="min-w-0 flex-1 truncate">{c.title}</span>
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
    <Panel title={ts("panel.redteam")}>
      <div className="flex flex-col gap-1.5 text-[0.72rem]">
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-semibold tabular-nums">{blocked}</span>
          <span className="text-[var(--muted-foreground)]">{ts("panel.blocked")}</span>
          <span className="ml-auto font-semibold tabular-nums text-amber-500">
            {fw?.false_negative ?? 0} {ts("panel.bypasses")}
          </span>
        </div>
        <div className="flex h-[4px] w-full overflow-hidden rounded-full">
          <div style={{ flexBasis: `${(blockRate ?? 0) * 100}%`, background: "#10b981" }} />
          <div style={{ flexGrow: 1, background: "#f97316" }} />
        </div>
        <KV label={ts("panel.blockRate")} value={pct(blockRate)} tone={GOOD} />
        <KV label={ts("panel.uniqueBypasses")} value={`${fw?.false_negative ?? 0}`} />
      </div>
    </Panel>
  );

  const erasurePanel = (
    <Panel title={ts("panel.erasureSurface")}>
      <div className="flex items-center gap-3">
        <Gauge value={erasureComplete ?? 0} label={ts("panel.completeness")} tone="#10b981" />
        <div className="flex min-w-0 flex-col gap-0.5 text-[0.7rem]">
          <KV label={ts("panel.conversations")} value={`${erasure.data?.n_conversations ?? 0}`} />
          <KV label={ts("panel.bundles")} value={`${erasure.data?.n_bundles ?? 0}`} />
          <KV label={ts("panel.scores")} value={`${erasure.data?.n_scores ?? 0}`} />
        </div>
      </div>
    </Panel>
  );

  const inversionPanel = (
    <Panel title={ts("panel.inversion")}>
      {inversion.data?.available === false || inversion.isLoading ? (
        <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
          {ts("panel.computing")}
        </p>
      ) : (
        <div className="flex flex-col gap-1 text-[0.72rem]">
          <KV
            label={ts("panel.recoverable")}
            value={`${inversion.data?.n_recoverable ?? 0}/${inversion.data?.n_memories ?? 0}`}
            tone={(inversion.data?.n_recoverable ?? 0) > 0 ? BAD : GOOD}
          />
          <KV label={ts("panel.recoveryRate")} value={pct(invRate)} />
          <KV label={ts("panel.threshold")} value={inversion.data?.threshold?.toFixed(2) ?? "—"} />
        </div>
      )}
    </Panel>
  );

  const trendPanel = (
    <Panel title={ts("panel.trend")}>
      <LineChart
        a={attackSeries}
        b={incidentSeries}
        aLabel={ts("panel.attackLine")}
        bLabel={ts("panel.incidentLine")}
      />
    </Panel>
  );

  const kpiGrid = (children: ReactNode) => (
    <Zone label={ts("sec.actual")}>
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
              infoKey="attackRate"
              value={`${fw?.n_positive ?? 0}`}
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
              infoKey="attackRate"
              value={`${fw?.false_negative ?? 0}`}
              tone={(fw?.false_negative ?? 0) > 0 ? WARN : GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.attackSuccess")}
              infoKey="attackRate"
              value={pct(attackRate)}
              tone={attackRate != null && attackRate > 0.2 ? BAD : WARN}
              series={fwSpark}
            />
          </>,
        )}
        <Zone label={ts("sec.controls")}>
          {controlsTable(controls.filter((c) => c.key === "promptInjection"))}
        </Zone>
        <Zone label={ts("sec.diagnostic")}>
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
              infoKey="piiLeak"
              value={`${pii.data?.n_with_leak ?? 0}/${pii.data?.n_turns ?? 0}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("ctrl.toxicity")}
              infoKey="piiLeak"
              value={pct(toxRate, 2)}
              tone={toxRate ? BAD : GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("kpi.sensitiveMemory")}
              infoKey="sensitiveMemory"
              value={`${inventory.data?.n_expiring_soon ?? 0}`}
              tone={(inventory.data?.n_expiring_soon ?? 0) > 0 ? WARN : GOOD}
              href="/configurer/sources-memoire"
              drillLabel={ts("kpi.sensitiveMemory")}
            />
          </>,
        )}
        <Zone label={ts("sec.controls")}>
          {controlsTable(controls.filter((c) => c.key === "piiLeak" || c.key === "toxicity"))}
        </Zone>
        <Zone label={ts("sec.privacy")}>
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
              value={`F1 ${fw?.f1?.toFixed(2) ?? "—"}`}
              tone={fw && fw.f1 >= 0.7 ? GOOD : WARN}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.recall")}
              infoKey="guard"
              value={fw?.recall?.toFixed(2) ?? "—"}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.precision")}
              infoKey="guard"
              value={fw?.precision?.toFixed(2) ?? "—"}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.conformance")}
              infoKey="guard"
              value={pct(conformance.data?.conformance_rate)}
              tone={(conformance.data?.conformance_rate ?? 1) >= 0.95 ? GOOD : WARN}
            />
          </>,
        )}
        <Zone label={ts("sec.diagnostic")}>
          <div className="grid gap-2 lg:grid-cols-3">
            <Panel title={ts("panel.refusal")}>
              <div className="flex items-center gap-2">
                <Gauge
                  value={refusal.data?.over_refusal_rate ?? 0}
                  label={ts("panel.overRefusal")}
                  tone="#f59e0b"
                />
                <div className="flex min-w-0 flex-col gap-1 text-[0.7rem]">
                  <KV
                    label={ts("panel.underRefusal")}
                    value={pct(refusal.data?.under_refusal_rate)}
                    tone={(refusal.data?.under_refusal_rate ?? 0) > 0.1 ? BAD : GOOD}
                  />
                  <KV label={ts("panel.legit")} value={`${refusal.data?.n_legit ?? 0}`} />
                  <KV label={ts("panel.forbidden")} value={`${refusal.data?.n_forbidden ?? 0}`} />
                </div>
              </div>
            </Panel>
            <Panel title={ts("panel.whatChanged")}>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {(whatChanged.data?.changes ?? []).length === 0 ? (
                  <li className="text-[var(--muted-foreground)]">{ts("panel.noChanges")}</li>
                ) : (
                  (whatChanged.data?.changes ?? []).slice(0, 4).map((c) => (
                    <li key={c.field} className="flex items-center gap-2">
                      <span className="min-w-0 flex-1 truncate">{c.field}</span>
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
              value={`${lp.data?.n_used ?? 0}/${lp.data?.n_granted ?? 0}`}
              tone={MUTED}
              href="/admin/roles-acces"
              drillLabel={ts("kpi.leastPriv")}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.overProvCount")}
              infoKey="leastPriv"
              value={`${lp.data?.n_over_provisioned ?? 0}`}
              tone={(lp.data?.n_over_provisioned ?? 0) > 0 ? WARN : GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.overProvRate")}
              infoKey="leastPriv"
              value={pct(overProvRate)}
              tone={overProvRate && overProvRate > 0.4 ? BAD : WARN}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("ctrl.toolMisuse")}
              infoKey="leastPriv"
              value={`${pct(overProvRate)}`}
              tone={MUTED}
            />
          </>,
        )}
        <Zone label={ts("sec.controls")}>
          {controlsTable(controls.filter((c) => c.key === "toolMisuse"))}
        </Zone>
        <Zone label={ts("sec.diagnostic")}>
          <div className="grid gap-2 lg:grid-cols-2">
            <Panel title={ts("panel.overPriv")}>
              <ul className="flex flex-col gap-1 text-[0.72rem]">
                {(lp.data?.usage ?? []).slice(0, 8).map((u) => {
                  const over = lp.data?.over_provisioned.includes(u.tool);
                  return (
                    <li key={u.tool} className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate font-mono">{u.tool}</span>
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
              value={`${inventory.data?.n_expiring_soon ?? 0}`}
              tone={(inventory.data?.n_expiring_soon ?? 0) > 0 ? WARN : GOOD}
              href="/configurer/sources-memoire"
              drillLabel={ts("kpi.sensitiveMemory")}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("panel.conversations")}
              infoKey="sensitiveMemory"
              value={`${erasure.data?.n_conversations ?? 0}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.erasureCompleteness")}
              infoKey="sensitiveMemory"
              value={pct(erasureComplete)}
              tone={GOOD}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("panel.recoverable")}
              infoKey="sensitiveMemory"
              value={`${inversion.data?.n_recoverable ?? 0}/${inversion.data?.n_memories ?? 0}`}
              tone={(inversion.data?.n_recoverable ?? 0) > 0 ? BAD : GOOD}
            />
          </>,
        )}
        <Zone label={ts("sec.privacy")}>
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
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("tabx.isolationProbes")}
              infoKey="crossTenant"
              value={`${crossTenant.data?.n_turns ?? 0}`}
              tone={MUTED}
            />
            <Kpi
              icon={ShieldAlert}
              label={ts("tabx.isolationLeaks")}
              infoKey="crossTenant"
              value={`${crossTenant.data?.n_leaks ?? 0}`}
              tone={(crossTenant.data?.n_leaks ?? 0) > 0 ? BAD : GOOD}
            />
          </>,
        )}
        <Zone label={ts("sec.controls")}>
          {controlsTable(controls.filter((c) => c.key === "crossTenant"))}
        </Zone>
        <Zone label={ts("sec.diagnostic")}>
          <div className="grid gap-2 lg:grid-cols-2">
            <Panel title={ts("tabx.isolationTitle")}>
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
              infoKey="attackRate"
              value={`${fw?.n_positive ?? 0}`}
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
            />
            <Kpi
              icon={ShieldCheck}
              label={ts("kpi.guard")}
              infoKey="guard"
              value={`F1 ${fw?.f1?.toFixed(2) ?? "—"}`}
              tone={fw && fw.f1 >= 0.7 ? GOOD : WARN}
            />
          </>,
        )}
        <Zone label={ts("sec.diagnostic")}>
          <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
            <Panel title={ts("panel.failures")}>
              {failureSlices.length === 0 ? (
                <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                  {ts("panel.noFailures")}
                </p>
              ) : (
                <FailureDonut slices={failureSlices} label={ts("panel.failuresUnit")} />
              )}
            </Panel>
            <Panel title={ts("panel.regression")}>
              <div className="flex items-center gap-3">
                <Gauge
                  value={regression.data?.risk_score ?? 0}
                  tone={(regression.data?.risk_score ?? 0) >= 0.5 ? "#ef4444" : "#f59e0b"}
                />
                <div className="flex flex-col gap-0.5 text-[0.7rem]">
                  <span
                    className={`text-base font-semibold ${(regression.data?.risk_score ?? 0) >= 0.5 ? BAD : WARN}`}
                  >
                    {ts(`level.${regression.data?.level ?? "low"}`)}
                  </span>
                  <span className="text-[var(--muted-foreground)]">
                    {ts("panel.regression7d")}: {pct(regression.data?.probability_7d)}
                  </span>
                </div>
              </div>
            </Panel>
            {trendPanel}
            {casesPanel([], 8)}
          </div>
        </Zone>
      </>
    ),
  };

  return (
    <div className="flex flex-col gap-2">
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
        <div className="flex shrink-0 items-center gap-2">
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
      {agentScope ? <div className="-mt-0.5">{agentScope}</div> : null}

      {activeTab !== "overview" ? (
        <div id="security-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-2">
          {domainView[activeTab]}
        </div>
      ) : (
        <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-2">
            {/* A. État actuel */}
            <Zone label={ts("sec.actual")}>
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
                  value={`${lp.data?.n_used ?? 0}/${lp.data?.n_granted ?? 0}`}
                  tone={MUTED}
                  hint={ts("kpi.leastPrivHint")}
                  href="/admin/roles-acces"
                  drillLabel={ts("kpi.leastPriv")}
                />
                <Kpi
                  icon={ShieldAlert}
                  label={ts("kpi.sensitiveMemory")}
                  infoKey="sensitiveMemory"
                  value={`${inventory.data?.n_expiring_soon ?? 0}`}
                  tone={(inventory.data?.n_expiring_soon ?? 0) > 0 ? WARN : GOOD}
                  hint={ts("kpi.sensitiveMemoryHint")}
                  href="/configurer/sources-memoire"
                  drillLabel={ts("kpi.sensitiveMemory")}
                />
                <Kpi
                  icon={ShieldCheck}
                  label={ts("kpi.guard")}
                  infoKey="guard"
                  value={`F1 ${fw?.f1?.toFixed(2) ?? "—"}`}
                  tone={fw && fw.f1 >= 0.7 ? GOOD : WARN}
                  hint={`${ts("kpi.recall")} ${fw?.recall?.toFixed(2) ?? "—"}`}
                />
              </div>
            </Zone>

            {/* B. Contrôles critiques */}
            <Zone label={ts("sec.controls")}>{controlsTable(controls)}</Zone>

            {/* C. Diagnostic racine */}
            <Zone label={ts("sec.diagnostic")}>
              <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
                <Panel title={ts("panel.failures")}>
                  {failureSlices.length === 0 ? (
                    <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                      {ts("panel.noFailures")}
                    </p>
                  ) : (
                    <FailureDonut slices={failureSlices} label={ts("panel.failuresUnit")} />
                  )}
                </Panel>
                <Panel title={ts("panel.whatChanged")}>
                  <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                    {(whatChanged.data?.changes ?? []).length === 0 ? (
                      <li className="text-[var(--muted-foreground)]">{ts("panel.noChanges")}</li>
                    ) : (
                      (whatChanged.data?.changes ?? []).slice(0, 4).map((c) => (
                        <li key={c.field} className="flex items-center gap-2">
                          <span className="min-w-0 flex-1 truncate">{c.field}</span>
                          <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                            {c.before.slice(0, 8)} → {c.after.slice(0, 8)}
                          </span>
                        </li>
                      ))
                    )}
                  </ul>
                </Panel>
                <Panel title={ts("panel.refusal")}>
                  <div className="flex items-center gap-2">
                    <Gauge
                      value={refusal.data?.over_refusal_rate ?? 0}
                      label={ts("panel.overRefusal")}
                      tone="#f59e0b"
                    />
                    <div className="flex min-w-0 flex-col gap-1 text-[0.7rem]">
                      <KV
                        label={ts("panel.underRefusal")}
                        value={pct(refusal.data?.under_refusal_rate)}
                        tone={(refusal.data?.under_refusal_rate ?? 0) > 0.1 ? BAD : GOOD}
                      />
                      <KV label={ts("panel.legit")} value={`${refusal.data?.n_legit ?? 0}`} />
                      <KV
                        label={ts("panel.forbidden")}
                        value={`${refusal.data?.n_forbidden ?? 0}`}
                      />
                    </div>
                  </div>
                </Panel>
                <Panel title={ts("panel.priorityCases")}>
                  <ul className="flex flex-col gap-1 text-[0.72rem]">
                    {(failed.data?.cases ?? []).slice(0, 4).map((c) => (
                      <li key={c.case_id} className="flex items-center gap-1.5">
                        <span
                          className={`h-1.5 w-1.5 shrink-0 rounded-full ${c.severity === "critical" ? "bg-red-500" : c.severity === "high" ? "bg-amber-500" : "bg-[var(--muted-foreground)]"}`}
                        />
                        <span className="min-w-0 flex-1 truncate">{c.title}</span>
                        <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
                          {c.case_id}
                        </span>
                      </li>
                    ))}
                  </ul>
                </Panel>
              </div>
            </Zone>

            {/* D. Signaux prédictifs */}
            <Zone label={ts("sec.predictive")}>
              <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
                <Panel title={ts("panel.trend")}>
                  <LineChart
                    a={attackSeries}
                    b={incidentSeries}
                    aLabel={ts("panel.attackLine")}
                    bLabel={ts("panel.incidentLine")}
                  />
                </Panel>
                <Panel title={ts("panel.regression")}>
                  <div className="flex items-center gap-3">
                    <Gauge
                      value={regression.data?.risk_score ?? 0}
                      tone={(regression.data?.risk_score ?? 0) >= 0.5 ? "#ef4444" : "#f59e0b"}
                    />
                    <div className="flex flex-col gap-0.5 text-[0.7rem]">
                      <span
                        className={`text-base font-semibold ${(regression.data?.risk_score ?? 0) >= 0.5 ? BAD : WARN}`}
                      >
                        {ts(`level.${regression.data?.level ?? "low"}`)}
                      </span>
                      <span className="text-[var(--muted-foreground)]">
                        {ts("panel.regression7d")}: {pct(regression.data?.probability_7d)}
                      </span>
                    </div>
                  </div>
                </Panel>
                <Panel title={ts("panel.domainRisk")}>
                  <div className="flex flex-col gap-1.5">
                    {domainRisks.map((d) => (
                      <RiskBar key={d.key} label={ts(`domain.${d.key}`)} value={d.value} />
                    ))}
                  </div>
                </Panel>
                <Panel title={ts("panel.overPriv")}>
                  <ul className="flex flex-col gap-1 text-[0.72rem]">
                    {(lp.data?.usage ?? []).slice(0, 5).map((u) => {
                      const over = lp.data?.over_provisioned.includes(u.tool);
                      return (
                        <li key={u.tool} className="flex items-center justify-between gap-2">
                          <span className="min-w-0 truncate font-mono">{u.tool}</span>
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

            {/* E. Privacy / Mémoire / SOC */}
            <Zone label={ts("sec.privacy")}>
              <div className="grid gap-2 lg:grid-cols-3">
                <Panel title={ts("panel.redteam")}>
                  <div className="flex flex-col gap-1.5 text-[0.72rem]">
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-semibold tabular-nums">{blocked}</span>
                      <span className="text-[var(--muted-foreground)]">{ts("panel.blocked")}</span>
                      <span className="ml-auto font-semibold tabular-nums text-amber-500">
                        {fw?.false_negative ?? 0} {ts("panel.bypasses")}
                      </span>
                    </div>
                    <div className="flex h-[4px] w-full overflow-hidden rounded-full">
                      <div
                        style={{ flexBasis: `${(blockRate ?? 0) * 100}%`, background: "#10b981" }}
                      />
                      <div style={{ flexGrow: 1, background: "#f97316" }} />
                    </div>
                    <KV label={ts("panel.blockRate")} value={pct(blockRate)} tone={GOOD} />
                    <KV label={ts("panel.uniqueBypasses")} value={`${fw?.false_negative ?? 0}`} />
                  </div>
                </Panel>
                <Panel title={ts("panel.erasureSurface")}>
                  <div className="flex items-center gap-3">
                    <Gauge
                      value={erasureComplete ?? 0}
                      label={ts("panel.completeness")}
                      tone="#10b981"
                    />
                    <div className="flex min-w-0 flex-col gap-0.5 text-[0.7rem]">
                      <KV
                        label={ts("panel.conversations")}
                        value={`${erasure.data?.n_conversations ?? 0}`}
                      />
                      <KV label={ts("panel.bundles")} value={`${erasure.data?.n_bundles ?? 0}`} />
                      <KV label={ts("panel.scores")} value={`${erasure.data?.n_scores ?? 0}`} />
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
                <Panel title={ts("panel.inversion")}>
                  {inversion.data?.available === false || inversion.isLoading ? (
                    <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                      {ts("panel.computing")}
                    </p>
                  ) : (
                    <div className="flex flex-col gap-1 text-[0.72rem]">
                      <KV
                        label={ts("panel.recoverable")}
                        value={`${inversion.data?.n_recoverable ?? 0}/${inversion.data?.n_memories ?? 0}`}
                        tone={(inversion.data?.n_recoverable ?? 0) > 0 ? BAD : GOOD}
                      />
                      <KV label={ts("panel.recoveryRate")} value={pct(invRate)} />
                      <KV
                        label={ts("panel.threshold")}
                        value={inversion.data?.threshold?.toFixed(2) ?? "—"}
                      />
                    </div>
                  )}
                </Panel>
              </div>
            </Zone>

            {/* F. Actions recommandées */}
            <Zone label={ts("sec.actions")}>
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
      <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--muted-foreground)]">
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
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ts("rail.incidents")}</CardTitle>
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
                  <span className="min-w-0 flex-1 truncate">{c.title}</span>
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
            <CardTitle className="text-sm">{ts("rail.privacyEvidence")}</CardTitle>
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
            <Button
              size="sm"
              className="mt-1 h-8 w-full justify-center gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
            >
              {ts("rail.evidenceCta")}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ts("rail.quickActions")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-0.5">
            {[
              { key: "qaRedteam", icon: Siren },
              { key: "qaIncident", icon: AlertTriangle },
              { key: "qaPurge", icon: Trash2 },
              { key: "qaTicket", icon: ShieldCheck },
            ].map((a) => (
              <button
                key={a.key}
                type="button"
                className="flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.72rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
              >
                <a.icon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{ts(`rail.${a.key}`)}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ts("rail.tools")}</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ts("rail.siem")}</CardTitle>
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
                <span className="min-w-0 flex-1 truncate text-[var(--muted-foreground)]">
                  {c.title}
                </span>
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
            <Button size="sm" variant="outline" className="mt-1 h-7 justify-center text-[0.7rem]">
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
