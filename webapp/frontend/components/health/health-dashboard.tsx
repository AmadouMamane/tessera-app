"use client";

import { useIntFormat } from "@/lib/format-number";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Boxes,
  CalendarClock,
  CircleDollarSign,
  Gauge,
  Heart,
  Lock,
  Radio,
  ServerCog,
  Share2,
  ShieldCheck,
} from "lucide-react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { ZoneBand } from "@/components/cockpit/zone-band";
import { ComponentHistoryPanel } from "@/components/health/component-history";
import { ComponentsPanel } from "@/components/health/components-panel";
import { InstrumentationCoverage } from "@/components/health/instrumentation-coverage";
import { ObservabilityChain } from "@/components/health/observability-chain";
import { ObservabilityVerdict } from "@/components/health/observability-verdict";
import { StoreConsequences } from "@/components/health/store-consequences";
import { ToolLinks } from "@/components/health/tool-links";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import {
  fetchBudget,
  fetchComponents,
  fetchHealth,
  fetchInstrumentationCoverage,
  fetchReadiness,
  fetchTailSampling,
} from "@/lib/api/client";

const POLL_MS = 10_000;

/** A ⓘ for a health card, reading health.explain.<k>.{what,how,source?}. */
function KpiInfo({ title, k }: { title: string; k: string }) {
  const te = useTranslations("health.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

/**
 * The page, in the reading order of its question — *can I know what happened?*
 *
 * The verdict answers it in one line; the KPI row carries THIS page's four numbers (components
 * observed, signals delivered, capabilities underwritten, instrumentation coverage) instead of
 * the process facts that used to sit here; then three zones: the chain and what it underwrites,
 * the time dimension, and the detail. The process facts (alive / ready / version / budget) are
 * one compact card in the detail zone — they answer "is it running", which is a different
 * question, and they duplicated `/api/version` across two of four tiles.
 */
export function HealthDashboard() {
  const t = useTranslations("health");

  const components = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: 15_000,
  });

  const coverage = useQuery({
    queryKey: ["instrumentation-coverage"],
    queryFn: ({ signal }) => fetchInstrumentationCoverage(signal),
    refetchInterval: 60_000,
  });

  const counts = components.data?.counts;
  const chainSignals = Object.entries(components.data?.chain.signals ?? {});
  const signalsServed = chainSignals.filter(([, state]) => state === "served").length;
  const signalsBad = chainSignals.filter(([, state]) => state !== "served");
  const consequences = components.data?.consequences ?? [];
  const capabilitiesServed = consequences.filter((row) => row.state === "served").length;
  const capabilitiesAtRisk = consequences.filter((row) => row.state !== "served");
  const gatesAtRisk = capabilitiesAtRisk.filter((row) => row.gates_agents).length;

  const measured = (coverage.data?.agents ?? []).filter((agent) => agent.covered_pct !== null);
  const fleetPct =
    measured.length > 0
      ? measured.reduce((total, agent) => total + (agent.covered_pct ?? 0), 0) / measured.length
      : null;

  return (
    <div className="flex flex-col gap-2.5">
      {/* The page's answer, first. Everything below is the evidence for it — and a reader who
          only reads one line must get the one that would change what they do next. */}
      <ObservabilityVerdict />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatusCard
          title={t("kpi.components.title")}
          info={<KpiInfo title={t("kpi.components.title")} k="kpiComponents" />}
          icon={<Boxes />}
          loading={components.isPending}
          error={components.error?.message}
          custom={
            counts ? (
              <KpiValue
                value={`${counts.stack_ok}/${counts.stack_total}`}
                tone={
                  counts.stack_fail > 0 ? "danger" : counts.stack_blind > 0 ? "warning" : undefined
                }
                sub={
                  counts.stack_fail === 0 && counts.stack_blind === 0
                    ? t("kpi.components.allClear")
                    : t("kpi.components.degraded", {
                        fail: counts.stack_fail,
                        blind: counts.stack_blind,
                      })
                }
              />
            ) : null
          }
        />
        <StatusCard
          title={t("kpi.signals.title")}
          info={<KpiInfo title={t("kpi.signals.title")} k="kpiSignals" />}
          icon={<Radio />}
          loading={components.isPending}
          error={components.error?.message}
          custom={
            components.data ? (
              <KpiValue
                value={`${signalsServed}/${chainSignals.length}`}
                tone={signalsBad.length > 0 ? "warning" : undefined}
                sub={
                  signalsBad.length === 0
                    ? t("kpi.signals.allServed")
                    : signalsBad.map(([name]) => t(`verdict.signal.${name}`)).join(" · ")
                }
              />
            ) : null
          }
        />
        <StatusCard
          title={t("kpi.capabilities.title")}
          info={<KpiInfo title={t("kpi.capabilities.title")} k="kpiCapabilities" />}
          icon={<ShieldCheck />}
          loading={components.isPending}
          error={components.error?.message}
          custom={
            components.data ? (
              <KpiValue
                value={`${capabilitiesServed}/${consequences.length}`}
                tone={
                  gatesAtRisk > 0 ? "danger" : capabilitiesAtRisk.length > 0 ? "warning" : undefined
                }
                sub={
                  capabilitiesAtRisk.length === 0
                    ? t("kpi.capabilities.allServed")
                    : gatesAtRisk > 0
                      ? t("kpi.capabilities.gatesAtRisk", { n: gatesAtRisk })
                      : t("kpi.capabilities.atRisk", { n: capabilitiesAtRisk.length })
                }
              />
            ) : null
          }
        />
        <StatusCard
          title={t("kpi.coverage.title")}
          info={<KpiInfo title={t("kpi.coverage.title")} k="kpiCoverage" />}
          icon={<Gauge />}
          loading={coverage.isPending}
          error={coverage.error?.message}
          custom={
            coverage.data ? (
              coverage.data.blind ? (
                <KpiValue value="—" tone="warning" sub={t("kpi.coverage.blind")} />
              ) : fleetPct === null ? (
                <KpiValue value="—" sub={t("kpi.coverage.noneMeasured")} />
              ) : (
                <KpiValue
                  value={`${fleetPct.toFixed(0)} %`}
                  tone={fleetPct >= 99 ? undefined : "warning"}
                  sub={t("kpi.coverage.measured", { n: measured.length })}
                />
              )
            ) : null
          }
        />
      </div>

      {/* The chain, then what its silence costs, then the doors into the tools. The order is
          the reading order of the question this page answers — *can I know what happened?* */}
      <ZoneBand label={t("zones.chain")} icon={Share2}>
        <ObservabilityChain />
        <div className="grid gap-2.5 xl:grid-cols-2">
          <StoreConsequences />
          <ToolLinks />
        </div>
      </ZoneBand>

      <ZoneBand
        label={t("zones.time")}
        icon={CalendarClock}
        iconClassName="text-[var(--tessera-fg-info)]"
      >
        <ComponentHistoryPanel />
      </ZoneBand>

      <ZoneBand
        label={t("zones.detail")}
        icon={Boxes}
        iconClassName="text-[var(--tessera-fg-accent)]"
      >
        <ComponentsPanel />
        <div className="grid gap-2.5 xl:grid-cols-2">
          <InstrumentationCoverage />
          <ServiceCard />
        </div>
        <TailSamplingCard />
      </ZoneBand>
    </div>
  );
}

/** One KPI figure with its qualifying sub-line — the number never travels alone. */
function KpiValue({
  value,
  sub,
  tone,
}: {
  value: string;
  sub: string;
  tone?: "danger" | "warning";
}) {
  const ink =
    tone === "danger"
      ? "text-[var(--tessera-fg-danger)]"
      : tone === "warning"
        ? "text-[var(--tessera-fg-warning)]"
        : "text-[var(--foreground)]";
  return (
    <div className="flex flex-col gap-1">
      <span className={`font-serif text-2xl font-semibold ${ink}`}>{value}</span>
      <span className="truncate text-xs text-[var(--muted-foreground)]" title={sub}>
        {sub}
      </span>
    </div>
  );
}

/**
 * The process facts — alive, ready, version, budget — as ONE compact card.
 *
 * They used to be four KPI tiles at the top of the page, with the version printed twice and
 * "€ 0.0000" wearing a tile of its own. They answer *is it running*, which is `fiabilité`'s
 * question; they stay because their drill-downs are real, but as detail, not as the headline.
 */
function ServiceCard() {
  const fmtInt = useIntFormat();
  const t = useTranslations("health");
  const tAuth = useTranslations("auth");
  // Budget/cost is an admin-only surface (ADR 0009): gate the query and the row.
  // superadmin is the highest role and sees everything admin does.
  const role = useSession().data?.user?.role;
  const isAdmin = role === "admin" || role === "superadmin";

  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: POLL_MS,
  });
  const readiness = useQuery({
    queryKey: ["readiness"],
    queryFn: ({ signal }) => fetchReadiness(signal),
    refetchInterval: POLL_MS,
  });
  const budget = useQuery({
    queryKey: ["budget"],
    queryFn: ({ signal }) => fetchBudget(signal),
    refetchInterval: POLL_MS,
    enabled: isAdmin,
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm">
          <ServerCog className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
          <span className="min-w-0 truncate">{t("service.title")}</span>
        </CardTitle>
        <Link
          href="/surveiller/fiabilite-cout"
          className="flex items-center gap-1 text-[0.66rem] text-[var(--muted-foreground)] transition-colors hover:text-[var(--tessera-green)]"
        >
          {t("service.reliability")}
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </CardHeader>
      <CardContent className="pt-1">
        <dl className="flex flex-col gap-1">
          <ServiceRow
            label={t("cards.backend")}
            info={<KpiInfo title={t("cards.backend")} k="backend" />}
          >
            {health.isPending ? (
              <Skeleton className="h-5 w-16" />
            ) : health.error ? (
              <Badge tone="danger">{t("status.down")}</Badge>
            ) : (
              <span className="flex items-center gap-1.5">
                <Badge tone="success">{health.data?.status ?? "ok"}</Badge>
                <Heart className="h-3 w-3 text-[var(--muted-foreground)]" aria-hidden />
              </span>
            )}
          </ServiceRow>
          <ServiceRow
            label={t("cards.readiness")}
            info={<KpiInfo title={t("cards.readiness")} k="readiness" />}
          >
            {readiness.isPending ? (
              <Skeleton className="h-5 w-16" />
            ) : readiness.error ? (
              <Badge tone="danger">{t("status.down")}</Badge>
            ) : (
              <Badge tone="success">{readiness.data?.status ?? "ready"}</Badge>
            )}
          </ServiceRow>
          <ServiceRow
            label={t("cards.version")}
            info={<KpiInfo title={t("cards.version")} k="version" />}
          >
            <span className="flex items-center gap-1.5">
              <span className="font-mono text-xs font-medium">{health.data?.version ?? "—"}</span>
              <Link
                href="/agir/release-control"
                aria-label={t("openSource", { label: t("cards.version") })}
                className="text-[var(--muted-foreground)] transition-colors hover:text-[var(--tessera-green)]"
              >
                <ArrowUpRight className="h-3 w-3" />
              </Link>
            </span>
          </ServiceRow>
          <ServiceRow
            label={t("cards.budget")}
            info={<KpiInfo title={t("cards.budget")} k="budget" />}
          >
            {!isAdmin ? (
              <span className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
                <Lock className="h-3 w-3" />
                {tAuth("adminOnly")}
              </span>
            ) : budget.isPending ? (
              <Skeleton className="h-5 w-24" />
            ) : budget.error ? (
              <Badge tone="danger">{t("status.down")}</Badge>
            ) : budget.data ? (
              <span className="flex items-baseline gap-2">
                <span className="font-mono text-xs font-medium">
                  € {budget.data.estimated_cost_eur.toFixed(2)}
                </span>
                <span className="text-[0.66rem] text-[var(--muted-foreground)]">
                  {fmtInt(budget.data.input_tokens)} in · {fmtInt(budget.data.output_tokens)} out
                </span>
                <CircleDollarSign
                  className="h-3 w-3 self-center text-[var(--muted-foreground)]"
                  aria-hidden
                />
              </span>
            ) : null}
          </ServiceRow>
        </dl>
      </CardContent>
    </Card>
  );
}

function ServiceRow({
  label,
  info,
  children,
}: {
  label: string;
  info: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 border-b border-[var(--tessera-border)]/50 py-1 last:border-0">
      <dt className="flex items-center gap-1 text-[0.72rem] font-medium text-[var(--foreground)]">
        {label}
        {info}
      </dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

/** Tail-based sampling — REAL: analyze_sampling over the captured replay bundles (slow /
 * low-faithfulness turns are always kept; a deterministic base-rate sample of the head is kept
 * for baseline visibility). */
function TailSamplingCard() {
  const t = useTranslations("health");

  const tail = useQuery({
    queryKey: ["tail-sampling"],
    queryFn: ({ signal }) => fetchTailSampling(signal),
    refetchInterval: POLL_MS * 3,
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm">
          <span className="min-w-0 truncate">{t("tail.title")}</span>
          <KpiInfo title={t("tail.title")} k="tailSampling" />
        </CardTitle>
        {tail.data ? (
          <Badge tone={tail.data.tail_retention_rate >= 1 ? "success" : "warning"}>
            {t("tail.guarantee", {
              pct: Math.round(tail.data.tail_retention_rate * 100),
            })}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {tail.isPending ? (
          <Skeleton className="h-12 w-full" />
        ) : tail.error ? (
          <Badge tone="danger">{t("status.down")}</Badge>
        ) : tail.data ? (
          tail.data.n_traces === 0 ? (
            <p className="text-xs text-[var(--muted-foreground)]">{t("tail.empty")}</p>
          ) : (
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <TailStat label={t("tail.traces")} value={`${tail.data.n_traces}`} />
              <TailStat
                label={t("tail.kept")}
                value={`${tail.data.n_kept} (${Math.round(tail.data.retention_rate * 100)}%)`}
              />
              <TailStat
                label={t("tail.tailKept")}
                value={`${tail.data.n_tail - Math.round((1 - tail.data.tail_retention_rate) * tail.data.n_tail)}/${tail.data.n_tail}`}
              />
              <TailStat
                label={t("tail.slow", { ms: Math.round(tail.data.slow_threshold_ms) })}
                value={`${tail.data.n_slow}`}
              />
              <TailStat
                label={t("tail.lowScore", { s: tail.data.score_threshold.toFixed(2) })}
                value={`${tail.data.n_low_score}`}
              />
              <TailStat
                label={t("tail.baseRate")}
                value={`${Math.round(tail.data.base_rate * 100)}%`}
              />
            </dl>
          )
        ) : null}
      </CardContent>
    </Card>
  );
}

function TailStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <dt className="truncate text-[0.66rem] uppercase tracking-wide text-[var(--muted-foreground)]">
        {label}
      </dt>
      <dd className="font-mono text-sm font-medium text-[var(--foreground)]">{value}</dd>
    </div>
  );
}

interface StatusCardProps {
  title: string;
  icon: ReactNode;
  loading: boolean;
  error?: string | undefined;
  custom?: ReactNode;
  /** ⓘ explainer rendered next to the card title. */
  info?: ReactNode;
  /** Real source this card drills into — makes the whole card a link (↗). */
  href?: "/surveiller/fiabilite-cout" | "/agir/release-control";
}

function StatusCard({ title, icon, loading, error, custom, info, href }: StatusCardProps) {
  const t = useTranslations("health");
  return (
    <Card className="group relative overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[var(--shadow-card-elevated)]">
      {/* premium top hairline + corner glow */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold-500/40 to-transparent" />
      <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full bg-gold-500/[0.06] blur-2xl transition-all duration-500 group-hover:bg-gold-500/[0.12]" />
      {/* Whole-card drill-down: an overlay <Link> sibling so the ⓘ never navigates;
          content is pointer-transparent except the ⓘ. */}
      {href ? (
        <Link
          href={href}
          aria-label={t("openSource", { label: title })}
          className="absolute inset-0 z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500/40"
        />
      ) : null}
      <CardHeader
        className={`flex flex-row items-center justify-between space-y-0 pb-2 ${
          href ? "pointer-events-none relative z-20" : ""
        }`}
      >
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <span className="min-w-0 truncate">{title}</span>
          {info ? <span className={href ? "pointer-events-auto" : undefined}>{info}</span> : null}
        </CardTitle>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-navy-800 to-navy-950 text-gold-400 shadow-[inset_0_1px_1px_oklch(0.8_0.066_85/0.2)] ring-1 ring-gold-500/15 transition-transform duration-300 group-hover:scale-105 dark:from-gold-500/15 dark:to-gold-500/5 dark:ring-gold-400/20 [&_svg]:h-4 [&_svg]:w-4">
          {icon}
        </div>
      </CardHeader>
      <CardContent className={`pt-1 ${href ? "pointer-events-none relative z-20" : ""}`}>
        {loading ? (
          <Skeleton className="h-7 w-24" />
        ) : error ? (
          <Badge tone="danger">{t("status.down")}</Badge>
        ) : (
          custom
        )}
      </CardContent>
      {href ? (
        <ArrowUpRight className="pointer-events-none absolute right-2 bottom-2 z-20 h-3.5 w-3.5 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </Card>
  );
}
