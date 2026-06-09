"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Crosshair,
  ExternalLink,
  Gauge,
  Languages,
  LineChart,
  Lock,
  Scale,
  ShieldCheck,
  Target,
  Wrench,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { ReplayPanel } from "@/components/observability/replay-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchCalibration,
  fetchEvalScores,
  fetchFirewallEfficacy,
  fetchPiiLeak,
  fetchRedteam,
  fetchRouting,
  fetchSessions,
  fetchToolValidity,
  runRedteam,
} from "@/lib/api/client";
import type {
  Calibration,
  EvalScore,
  FirewallEfficacy,
  PIILeakSummary,
  RedTeamResponse,
  RoutingReport,
  SessionReport,
  ToolValidity,
} from "@/lib/api/schemas";

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

  const tools = useQuery({
    queryKey: ["tool-validity"],
    queryFn: ({ signal }) => fetchToolValidity(signal),
    refetchInterval: 15_000,
  });

  const routing = useQuery({
    queryKey: ["routing"],
    queryFn: ({ signal }) => fetchRouting(signal),
    refetchInterval: 15_000,
  });

  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: ({ signal }) => fetchSessions(signal),
    refetchInterval: 15_000,
  });

  const piiLeak = useQuery({
    queryKey: ["pii-leak"],
    queryFn: ({ signal }) => fetchPiiLeak(signal),
    refetchInterval: 15_000,
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

      <RedTeamCard />

      <PiiLeakCard data={piiLeak.data} loading={piiLeak.isLoading} />

      <ToolValidityCard data={tools.data} loading={tools.isLoading} />

      <RoutingCard data={routing.data} loading={routing.isLoading} />

      <SessionCard data={sessions.data} loading={sessions.isLoading} />

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

function RedTeamCard() {
  const t = useTranslations("observability");
  const query = useQuery({
    queryKey: ["redteam"],
    queryFn: ({ signal }) => fetchRedteam(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const mutation = useMutation({
    mutationFn: () => runRedteam(),
    onSuccess: (res: RedTeamResponse) => query.refetch().then(() => res),
  });

  const data = mutation.data ?? query.data;
  const snapshots = data?.snapshots ?? [];
  const latest = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
  const pct = latest ? Math.round(latest.attack_success_rate * 100) : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Crosshair className="h-4 w-4 text-blue-500" />
            {t("redteam.title")}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? t("redteam.running") : t("redteam.run")}
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!latest ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("redteam.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("redteam.successRate")}
                </span>
                <Badge tone={pct === 0 ? "success" : pct <= 20 ? "warning" : "danger"}>
                  {pct}%
                </Badge>
              </div>
              <Metric
                label={t("redteam.blocked")}
                value={`${latest.n_blocked}/${latest.n_attacks}`}
              />
              <Metric label={t("redteam.bypassed")} value={String(latest.n_bypassed)} />
              {snapshots.length > 1 ? (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {t("redteam.drift")}
                  </span>
                  <span className="flex items-center gap-1 font-mono text-xs tabular-nums">
                    {snapshots.slice(-8).map((s, i) => (
                      <span key={`${s.ran_at}-${i}`}>
                        {Math.round(s.attack_success_rate * 100)}
                      </span>
                    ))}
                  </span>
                </div>
              ) : null}
            </div>
            {latest.bypassed_samples.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
                {latest.bypassed_samples.map((s, i) => (
                  <li key={`${i}-${s.slice(0, 16)}`} className="flex items-start gap-2">
                    <span
                      aria-hidden
                      className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-amber-500"
                    />
                    <span className="min-w-0 break-words">{s}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PiiLeakCard({ data, loading }: { data: PIILeakSummary | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.leak_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Lock className="h-4 w-4 text-blue-500" />
          {t("piiLeak.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("piiLeak.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("piiLeak.rate")}</span>
              <Badge tone={pct === 0 ? "success" : pct <= 10 ? "warning" : "danger"}>{pct}%</Badge>
            </div>
            <Metric label={t("piiLeak.turns")} value={String(data.n_turns)} />
            <Metric label={t("piiLeak.leaked")} value={String(data.total_leaked)} />
            {data.examples.length > 0 ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("piiLeak.examples")}
                </span>
                <span className="font-mono text-xs text-red-600 dark:text-red-400">
                  {data.examples.join(", ")}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ToolValidityCard({
  data,
  loading,
}: {
  data: ToolValidity | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.validity_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Wrench className="h-4 w-4 text-blue-500" />
          {t("tools.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.total === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("tools.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("tools.validity")}</span>
              <Badge tone={pct >= 90 ? "success" : pct >= 70 ? "warning" : "danger"}>{pct}%</Badge>
            </div>
            <Metric label={t("tools.allowed")} value={String(data.allowed)} />
            <Metric label={t("tools.denied")} value={String(data.denied)} />
            <Metric label={t("tools.argFailures")} value={String(data.arg_failures)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RoutingCard({ data, loading }: { data: RoutingReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const mis = data ? Math.round(data.mismatch_rate * 100) : 0;
  const cs = data ? Math.round(data.code_switch_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Languages className="h-4 w-4 text-blue-500" />
          {t("routing.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("routing.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("routing.mismatch")}
              </span>
              <Badge tone={mis === 0 ? "success" : mis <= 20 ? "warning" : "danger"}>{mis}%</Badge>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("routing.codeSwitch")}
              </span>
              <Badge tone={cs === 0 ? "neutral" : "warning"}>{cs}%</Badge>
            </div>
            <Metric label={t("routing.turns")} value={String(data.n)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SessionCard({ data, loading }: { data: SessionReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Target className="h-4 w-4 text-blue-500" />
          {t("sessions.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_sessions === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("sessions.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <Metric label={t("sessions.sessions")} value={String(data.n_sessions)} />
            <Metric
              label={t("sessions.turnsPerSession")}
              value={data.mean_turns_per_session.toFixed(1)}
            />
            <Metric
              label={t("sessions.singleTurn")}
              value={`${Math.round(data.single_turn_rate * 100)}%`}
            />
            <Metric label={t("sessions.meanScore")} value={data.mean_score.toFixed(2)} />
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
