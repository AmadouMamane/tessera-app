"use client";

import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Gauge, LineChart, Scale, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { ReplayPanel } from "@/components/observability/replay-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchCalibration, fetchEvalScores, fetchFirewallEfficacy } from "@/lib/api/client";
import type { Calibration, EvalScore, FirewallEfficacy } from "@/lib/api/schemas";

const POLL_MS = 5_000;
const PHOENIX_URL = process.env.NEXT_PUBLIC_PHOENIX_URL ?? "http://localhost:16006";
const LANGFUSE_URL = process.env.NEXT_PUBLIC_LANGFUSE_URL ?? "http://localhost:3900";

function scoreTone(score: number): string {
  if (score >= 0.8) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 0.5) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function ObservabilityDashboard() {
  const t = useTranslations("observability");

  const scores = useQuery({
    queryKey: ["eval-scores"],
    queryFn: ({ signal }) => fetchEvalScores(signal),
    refetchInterval: POLL_MS,
  });

  // Calibration is computed server-side (slow, judge over a gold set) and cached,
  // so fetch it once rather than polling.
  const calibration = useQuery({
    queryKey: ["calibration"],
    queryFn: ({ signal }) => fetchCalibration(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const firewall = useQuery({
    queryKey: ["firewall-efficacy"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  // Newest first for display.
  const rows: EvalScore[] = scores.data ? [...scores.data.scores].reverse() : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <BackendCard
          title="Arize Phoenix"
          subtitle={t("phoenix")}
          href={PHOENIX_URL}
          icon={<LineChart className="h-5 w-5 text-blue-500" />}
        />
        <BackendCard
          title="Langfuse"
          subtitle={t("langfuse")}
          href={LANGFUSE_URL}
          icon={<Gauge className="h-5 w-5 text-blue-500" />}
        />
      </div>

      <CalibrationCard data={calibration.data} loading={calibration.isLoading} />

      <FirewallEfficacyCard data={firewall.data} loading={firewall.isLoading} />

      <ReplayPanel />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("scores.title")}
            <Badge tone="neutral">{t("scores.metric")}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {scores.isLoading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
              {t("scores.empty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="py-2 pr-4 font-medium">{t("scores.time")}</th>
                    <th className="py-2 pr-4 font-medium">{t("scores.metricCol")}</th>
                    <th className="py-2 pr-4 font-medium">{t("scores.score")}</th>
                    <th className="py-2 pr-4 font-medium">{t("scores.language")}</th>
                    <th className="py-2 font-medium">{t("scores.judge")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s, i) => (
                    <tr key={`${s.scored_at}-${i}`} className="border-b border-[var(--border)]/50">
                      <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                        {new Date(s.scored_at).toLocaleTimeString()}
                      </td>
                      <td className="py-2 pr-4">{s.metric}</td>
                      <td className={`py-2 pr-4 font-semibold tabular-nums ${scoreTone(s.score)}`}>
                        {s.score.toFixed(2)}
                      </td>
                      <td className="py-2 pr-4 uppercase">{s.language}</td>
                      <td className="py-2 text-[var(--muted-foreground)]">{s.judge_model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BackendCard({
  title,
  subtitle,
  href,
  icon,
}: {
  title: string;
  subtitle: string;
  href: string;
  icon: ReactNode;
}) {
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" className="group">
      <Card className="h-full transition-colors hover:border-blue-500/50">
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2">
              {icon}
              {title}
            </span>
            <ExternalLink className="h-4 w-4 text-[var(--muted-foreground)] transition-colors group-hover:text-blue-500" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[var(--muted-foreground)]">{subtitle}</p>
        </CardContent>
      </Card>
    </a>
  );
}

function CalibrationCard({ data, loading }: { data: Calibration | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Scale className="h-4 w-4 text-blue-500" />
          {t("calibration.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-12 w-full" />
        ) : !data?.available ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("calibration.unavailable")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <Metric label={t("calibration.kappa")} value={(data.kappa ?? 0).toFixed(2)} />
            <Metric
              label={t("calibration.agreement")}
              value={`${Math.round((data.agreement ?? 0) * 100)}%`}
            />
            <Metric
              label={t("calibration.verbosity")}
              value={(data.verbosity_corr ?? 0).toFixed(2)}
            />
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("calibration.lenient")}
              </span>
              <Badge tone={data.lenient ? "warning" : "success"}>
                {data.lenient ? t("calibration.lenientYes") : t("calibration.lenientNo")}
              </Badge>
            </div>
            <Metric label={t("calibration.judge")} value={data.judge_model ?? "—"} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FirewallEfficacyCard({
  data,
  loading,
}: {
  data: FirewallEfficacy | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldCheck className="h-4 w-4 text-blue-500" />
          {t("firewall.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <Metric label={t("firewall.precision")} value={data.precision.toFixed(2)} />
            <Metric label={t("firewall.recall")} value={data.recall.toFixed(2)} />
            <Metric label={t("firewall.f1")} value={data.f1.toFixed(2)} />
            <Metric
              label={t("firewall.caught")}
              value={`${data.true_positive}/${data.n_positive}`}
            />
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("firewall.falsePositive")}
              </span>
              <Badge tone={data.false_positive === 0 ? "success" : "warning"}>
                {data.false_positive}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </div>
  );
}
