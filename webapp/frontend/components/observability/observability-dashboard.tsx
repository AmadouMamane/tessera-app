"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  DatabaseZap,
  ExternalLink,
  FilePlus2,
  Gauge,
  Link2,
  LockKeyhole,
  Radar,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  type CommitEvidencePayload,
  commitEvidenceBundle,
  fetchObservabilityStatus,
} from "@/lib/api/client";
import type { ObservabilityStatus } from "@/lib/api/schemas";

const POLL_MS = 10_000;
const LOADING_KEYS = ["profile", "completeness", "exporters", "llmops"] as const;

export function ObservabilityDashboard() {
  const t = useTranslations("observability");
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["observability-status"],
    queryFn: ({ signal }) => fetchObservabilityStatus(signal),
    refetchInterval: POLL_MS,
  });
  const commit = useMutation({
    mutationFn: () => commitEvidenceBundle(buildSyntheticEvidencePayload()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["observability-status"] }),
  });

  if (status.isPending) {
    return <LoadingGrid />;
  }

  if (status.error || !status.data) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 py-8 text-sm text-[var(--muted-foreground)]">
          <AlertTriangle className="h-4 w-4 text-warning-500" />
          {status.error?.message ?? t("error")}
        </CardContent>
      </Card>
    );
  }

  const data = status.data;
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatusTile
          title={t("cards.profile")}
          icon={<Radar />}
          value={data.profile}
          badge={data.status}
          tone={data.status === "ok" ? "success" : "warning"}
          detail={`${data.assurance.current_level} / ${data.assurance.target_level}`}
        />
        <ScoreTile
          title={t("cards.completeness")}
          icon={<Gauge />}
          value={data.assurance.completeness}
          badge={data.assurance.proof_slo_status}
        />
        <StatusTile
          title={t("cards.exporters")}
          icon={<DatabaseZap />}
          value={data.exporters.primary_backend}
          badge={
            data.exporters.collector_required && !data.exporters.collector_configured
              ? t("status.degraded")
              : t("status.ok")
          }
          tone={
            data.exporters.collector_required && !data.exporters.collector_configured
              ? "warning"
              : "success"
          }
          detail={data.exporters.evidence_signing_enabled ? t("signed") : t("unsigned")}
        />
        <StatusTile
          title={t("cards.llmops")}
          icon={<Activity />}
          value={data.llmops.project}
          badge={data.llmops.status}
          tone={data.llmops.status === "degraded" ? "warning" : "info"}
          detail={`${data.llmops.ingestion_mode} / ${data.llmops.host ?? "OpenTelemetry"}`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.15fr]">
        <AssurancePanel data={data} />
        <TracePanel data={data} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <OperatorLinksPanel data={data} />
        <EvidencePanel
          data={data}
          onCommit={() => commit.mutate()}
          committing={commit.isPending}
          commitResult={commit.data?.evidence_id}
          commitError={commit.error?.message}
        />
      </div>
    </div>
  );
}

function buildSyntheticEvidencePayload(): CommitEvidencePayload {
  return {
    conversation_id: crypto.randomUUID(),
    turn_id: crypto.randomUUID(),
    model: "dashboard_synthetic",
    language: "fr",
    attributes: {
      language: "fr",
      model: "dashboard_synthetic",
      citation_count: 0,
      retrieval_hit_count: 0,
    },
  };
}

function LoadingGrid() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {LOADING_KEYS.map((key) => (
        <Card key={key}>
          <CardHeader>
            <Skeleton className="h-4 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-36" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

interface StatusTileProps {
  title: string;
  icon: ReactNode;
  value: string;
  badge: string;
  tone: BadgeProps["tone"];
  detail?: string;
}

function StatusTile({ title, icon, value, badge, tone, detail }: StatusTileProps) {
  return (
    <Card className="min-h-36">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <CardTitle className="text-xs font-medium uppercase text-[var(--muted-foreground)]">
          {title}
        </CardTitle>
        <div className="rounded-md bg-[var(--secondary)] p-2 text-[var(--muted-foreground)] [&_svg]:h-4 [&_svg]:w-4">
          {icon}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <span className="break-words font-mono text-lg font-semibold">{value}</span>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={tone}>{badge}</Badge>
          {detail ? <span className="text-xs text-[var(--muted-foreground)]">{detail}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

interface ScoreTileProps {
  title: string;
  icon: ReactNode;
  value: number;
  badge: string;
}

function ScoreTile({ title, icon, value, badge }: ScoreTileProps) {
  const tone: BadgeProps["tone"] = value >= 0.9 ? "success" : value >= 0.65 ? "warning" : "danger";
  return (
    <Card className="min-h-36">
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <CardTitle className="text-xs font-medium uppercase text-[var(--muted-foreground)]">
          {title}
        </CardTitle>
        <div className="rounded-md bg-[var(--secondary)] p-2 text-[var(--muted-foreground)] [&_svg]:h-4 [&_svg]:w-4">
          {icon}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <span className="font-serif text-3xl font-semibold">{Math.round(value * 100)}%</span>
        <div className="h-2 overflow-hidden rounded-full bg-[var(--secondary)]">
          <div className="h-full bg-blue-500" style={{ width: `${Math.round(value * 100)}%` }} />
        </div>
        <Badge tone={tone}>{badge}</Badge>
      </CardContent>
    </Card>
  );
}

function AssurancePanel({ data }: { data: ObservabilityStatus }) {
  const t = useTranslations("observability");
  const rows = [
    {
      label: t("controls.privacy"),
      ok: !data.exporters.raw_prompts_export && !data.exporters.pii_export,
    },
    {
      label: t("controls.collector"),
      ok: !data.exporters.collector_required || data.exporters.collector_configured,
    },
    { label: t("controls.evidence"), ok: data.exporters.evidence_enabled },
    {
      label: t("controls.langfuse"),
      ok: !data.llmops.enabled || data.llmops.configured,
    },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("assurance")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Metric label={t("allowed")} value={String(data.allowed_attribute_count)} />
          <Metric label={t("forbidden")} value={String(data.forbidden_attribute_count)} />
          <Metric
            label={t("proofConsensus")}
            value={`${Math.round(data.assurance.proof_consensus * 100)}%`}
          />
          <Metric label={t("prompt")} value={`${data.prompt_family}:${data.prompt_version}`} />
        </div>
        <div className="flex flex-col gap-2">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2 text-sm"
            >
              <span>{row.label}</span>
              {row.ok ? (
                <CheckCircle2 className="h-4 w-4 text-success-500" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-warning-500" />
              )}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {data.warnings.length ? (
            data.warnings.map((warning) => (
              <Badge key={warning} tone="warning">
                {warning}
              </Badge>
            ))
          ) : (
            <Badge tone="success">{t("noWarnings")}</Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function TracePanel({ data }: { data: ObservabilityStatus }) {
  const t = useTranslations("observability");
  const summary = data.trace_summary;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("traces.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Metric label={t("traces.recent")} value={String(summary.recent_count)} />
          <Metric label={t("traces.traceable")} value={String(summary.traceable_count)} />
          <Metric label={t("traces.complete")} value={String(summary.complete_count)} />
          <Metric label={t("traces.degraded")} value={String(summary.degraded_count)} />
        </div>
        <div className="rounded-md border border-[var(--border)] px-3 py-2 text-sm">
          <p className="text-xs text-[var(--muted-foreground)]">{t("traces.latest")}</p>
          {summary.latest_trace_id ? (
            <a
              href={summary.latest_trace_url ?? undefined}
              target={summary.latest_trace_url ? "_blank" : undefined}
              rel="noreferrer"
              className="mt-1 inline-flex max-w-full items-center gap-1 font-mono text-xs text-blue-600 hover:underline dark:text-blue-400"
            >
              <span className="truncate">{summary.latest_trace_id}</span>
              {summary.latest_trace_url ? <ExternalLink className="h-3 w-3 shrink-0" /> : null}
            </a>
          ) : (
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">{t("traces.none")}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {summary.gap_codes.length ? (
            summary.gap_codes.map((gap) => (
              <Badge key={gap} tone="warning">
                {gap}
              </Badge>
            ))
          ) : (
            <Badge tone="success">{t("traces.noGaps")}</Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function OperatorLinksPanel({ data }: { data: ObservabilityStatus }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("links.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2">
        {data.operator_links.map((link) => {
          const active = Boolean(link.url);
          const content = (
            <>
              <span key="label" className="min-w-0">
                <span className="block truncate font-medium">{link.label}</span>
                <span className="block truncate text-xs text-[var(--muted-foreground)]">
                  {t(`links.roles.${link.role}`)}
                </span>
              </span>
              <span key="status" className="flex items-center gap-2">
                <Badge
                  tone={
                    link.status === "configured"
                      ? "success"
                      : link.status === "disabled" || link.status === "linked"
                        ? "info"
                        : "warning"
                  }
                >
                  {t(`links.status.${link.status}`)}
                </Badge>
                {active ? <ExternalLink className="h-3.5 w-3.5" /> : null}
              </span>
            </>
          );
          const className =
            "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-md border border-[var(--border)] px-3 py-2 text-sm transition-colors";
          return active ? (
            <a
              key={link.key}
              href={link.url ?? "#"}
              target="_blank"
              rel="noreferrer"
              className={`${className} hover:border-blue-500/40 hover:bg-blue-500/5`}
            >
              {content}
            </a>
          ) : (
            <div key={link.key} className={`${className} bg-[var(--muted)]/20`}>
              {content}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function EvidencePanel({
  data,
  onCommit,
  committing,
  commitResult,
  commitError,
}: {
  data: ObservabilityStatus;
  onCommit: () => void;
  committing: boolean;
  commitResult?: string;
  commitError?: string;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>{t("evidence")}</CardTitle>
        <Button size="sm" variant="outline" onClick={onCommit} disabled={committing}>
          <FilePlus2 />
          {committing ? t("committing") : t("commit")}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {commitResult ? (
          <Badge tone="success">
            <Link2 className="h-3 w-3" />
            {commitResult}
          </Badge>
        ) : null}
        {commitError ? <Badge tone="danger">{commitError}</Badge> : null}
        {data.recent_evidence.length ? (
          <div className="overflow-hidden rounded-md border border-[var(--border)]">
            {data.recent_evidence.map((item) => (
              <div
                key={item.evidence_id ?? item.turn_id}
                className="grid grid-cols-[1fr_auto] gap-3 border-b border-[var(--border)] px-3 py-2 text-sm last:border-b-0"
              >
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs">{item.evidence_id}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">{item.created_at}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={item.proof_quality === "complete" ? "success" : "warning"}>
                    {item.proof_quality}
                  </Badge>
                  <span className="font-mono text-xs text-[var(--muted-foreground)]">
                    {item.proof_consensus}
                  </span>
                  {item.trace_url ? (
                    <a
                      href={item.trace_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 hover:underline dark:text-blue-400"
                    >
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  ) : null}
                </div>
                <p className="col-span-2 font-mono text-[0.68rem] text-[var(--muted-foreground)]">
                  {t("traces.trace")} {item.trace_id ?? t("traces.none")}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-md border border-dashed border-[var(--border)] px-3 py-5 text-sm text-[var(--muted-foreground)]">
            <LockKeyhole className="h-4 w-4" />
            {t("emptyEvidence")}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] px-3 py-2">
      <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
      <p className="truncate font-mono text-sm font-medium">{value}</p>
    </div>
  );
}
