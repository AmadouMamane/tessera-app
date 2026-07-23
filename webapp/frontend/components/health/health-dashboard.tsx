"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowUpRight, CircleDollarSign, Heart, Lock, ServerCog } from "lucide-react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { fetchBudget, fetchHealth, fetchReadiness, fetchTailSampling } from "@/lib/api/client";

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

export function HealthDashboard() {
  const t = useTranslations("health");
  const tAuth = useTranslations("auth");
  // Budget/cost is an admin-only surface (ADR 0009): gate the query and the card.
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

  const tail = useQuery({
    queryKey: ["tail-sampling"],
    queryFn: ({ signal }) => fetchTailSampling(signal),
    refetchInterval: POLL_MS * 3,
  });

  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatusCard
          title={t("cards.backend")}
          info={<KpiInfo title={t("cards.backend")} k="backend" />}
          icon={<ServerCog />}
          loading={health.isPending}
          error={health.error?.message}
          status={health.data?.status}
          helper={health.data?.version ? `v${health.data.version}` : undefined}
        />
        <StatusCard
          title={t("cards.readiness")}
          info={<KpiInfo title={t("cards.readiness")} k="readiness" />}
          icon={<Heart />}
          loading={readiness.isPending}
          error={readiness.error?.message}
          status={readiness.data?.status}
        />
        <StatusCard
          title={t("cards.budget")}
          info={<KpiInfo title={t("cards.budget")} k="budget" />}
          href="/surveiller/fiabilite-cout"
          icon={<CircleDollarSign />}
          locked={!isAdmin}
          lockedLabel={tAuth("adminOnly")}
          loading={isAdmin && budget.isPending}
          error={budget.error?.message}
          custom={
            budget.data ? (
              <div className="flex flex-col gap-1">
                <span className="font-serif text-2xl font-semibold">
                  € {budget.data.estimated_cost_eur.toFixed(4)}
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  {budget.data.input_tokens.toLocaleString()} in ·{" "}
                  {budget.data.output_tokens.toLocaleString()} out
                </span>
              </div>
            ) : null
          }
        />
        <StatusCard
          title={t("cards.version")}
          info={<KpiInfo title={t("cards.version")} k="version" />}
          href="/agir/release-control"
          icon={<Activity />}
          loading={health.isPending}
          error={health.error?.message}
          custom={
            health.data ? (
              <span className="font-mono text-base font-medium">{health.data.version}</span>
            ) : null
          }
        />
      </div>

      {/* Tail-based sampling — REAL: analyze_sampling over the captured replay
        bundles (slow / low-faithfulness turns are always kept; a deterministic
        base-rate sample of the head is kept for baseline visibility). */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
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
    </div>
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
  status?: string;
  helper?: string;
  custom?: ReactNode;
  locked?: boolean;
  lockedLabel?: string;
  /** ⓘ explainer rendered next to the card title. */
  info?: ReactNode;
  /** Real source this card drills into — makes the whole card a link (↗). */
  href?: string;
}

function StatusCard({
  title,
  icon,
  loading,
  error,
  status,
  helper,
  custom,
  locked,
  lockedLabel,
  info,
  href,
}: StatusCardProps) {
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
        {locked ? (
          <span className="flex items-center gap-1.5 text-sm text-[var(--muted-foreground)]">
            <Lock className="h-3.5 w-3.5" />
            {lockedLabel}
          </span>
        ) : loading ? (
          <Skeleton className="h-7 w-24" />
        ) : error ? (
          <Badge tone="danger">{t("status.down")}</Badge>
        ) : custom ? (
          custom
        ) : (
          <div className="flex items-center gap-2">
            <Badge tone="success">{status ?? "ok"}</Badge>
            {helper ? (
              <span className="text-xs text-[var(--muted-foreground)]">{helper}</span>
            ) : null}
          </div>
        )}
      </CardContent>
      {href ? (
        <ArrowUpRight className="pointer-events-none absolute right-2 bottom-2 z-20 h-3.5 w-3.5 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </Card>
  );
}
