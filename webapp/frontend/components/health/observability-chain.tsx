"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Bot,
  Database,
  Eye,
  HardDrive,
  Layers,
  type LucideIcon,
  Radio,
  Server,
  Share2,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import {
  resolveLink,
  useServedFromLoopback,
  verdictTone,
} from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";
import type { ChainEdge, ChainNode, ChainSignal, ComponentsResponse } from "@/lib/api/schemas";

const POLL_MS = 15_000;

/**
 * The observability chain: agent → collector → stores → viewers.
 *
 * This is the block that changes the nature of the page. A flat table shows three red dots; a
 * chain shows one dead node and its two consequences, which is the sentence an operator is
 * trying to assemble anyway. It is also the only shape that can carry the facts a reader gets
 * wrong — metrics reach Prometheus by two routes, so a dead collector does not blind them;
 * business events never touch the collector at all.
 *
 * Every edge carries the file that declares it, shown on hover. The drawing is a claim about
 * the system, and a claim whose evidence a reader cannot reach is decoration (ADR 0026).
 */
export function ObservabilityChain() {
  const t = useTranslations("health.chain");
  const servedFromLoopback = useServedFromLoopback();

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data ? <SignalLegend data={query.data} /> : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-40 w-full" />
        ) : query.error || !query.data ? (
          // A failed read is not an empty chain: say the read failed, never draw a healthy one.
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : (
          <ChainGraph
            data={query.data}
            servedFromLoopback={servedFromLoopback}
            t={t as (key: string, values?: Record<string, string | number>) => string}
          />
        )}
      </CardContent>
    </Card>
  );
}

/** Per signal, whether it still gets from the agent to somewhere it is kept. */
function SignalLegend({ data }: { data: ComponentsResponse }) {
  const t = useTranslations("health.chain");
  const entries = Object.entries(data.chain.signals) as [ChainSignal, string][];
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {entries.map(([signal, state]) => (
        <Badge
          key={signal}
          tone={state === "served" ? "success" : state === "lost" ? "danger" : "warning"}
        >
          {t(`signal.${signal}`)} · {t(`state.${state}`)}
        </Badge>
      ))}
    </div>
  );
}

const STAGE_ORDER = ["emitter", "pipeline", "store", "viewer"] as const;

const NODE_ICON: Record<string, LucideIcon> = {
  agent: Bot,
  "otel-collector": Share2,
  prometheus: BarChart3,
  clickhouse: Database,
  postgres: Database,
  redis: Layers,
  minio: HardDrive,
  "langfuse-db": Database,
  "langfuse-redis": Layers,
  "langfuse-web": Eye,
  "langfuse-worker": Server,
  phoenix: Radio,
  grafana: Activity,
};

const SIGNAL_LINE: Record<ChainSignal, string> = {
  traces: "text-[var(--tessera-fg-accent)]",
  metrics: "text-[var(--tessera-fg-info)]",
  events: "text-[var(--tessera-fg-teal)]",
  state: "text-[var(--muted-foreground)]",
};

/**
 * The chain as four stage columns.
 *
 * Laid out by declared STAGE rather than by a graph solver: the stage is the reading order an
 * operator already has in their head, and a solver would move a node's position whenever an
 * edge changed — a picture that rearranges itself between two polls is unreadable. The cost is
 * that an edge is drawn as an incoming-signal chip on its target rather than as a curve; on a
 * chain this shallow that reads better and survives a phone viewport, which a curve does not.
 */
function ChainGraph({
  data,
  servedFromLoopback,
  t,
}: {
  data: ComponentsResponse;
  servedFromLoopback: boolean;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  const byStage = STAGE_ORDER.map((stage) => ({
    stage,
    nodes: data.chain.nodes.filter((node) => node.stage === stage),
  })).filter((column) => column.nodes.length > 0);

  return (
    <div className="overflow-x-auto">
      <div className="flex min-w-[46rem] items-stretch gap-2">
        {byStage.map((column, index) => (
          <div key={column.stage} className="flex min-w-0 flex-1 items-stretch gap-2">
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <p className="text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                {t(`stage.${column.stage}`)}
              </p>
              {column.nodes.map((node) => (
                <ChainNodeCard
                  key={node.key}
                  node={node}
                  edges={data.chain.edges.filter((edge) => edge.target === node.key)}
                  link={resolveLink(data.links, node.key, servedFromLoopback)}
                  t={t}
                />
              ))}
            </div>
            {index < byStage.length - 1 ? (
              <div
                aria-hidden
                className="mt-5 w-px shrink-0 self-stretch bg-gradient-to-b from-transparent via-[var(--tessera-border)] to-transparent"
              />
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function ChainNodeCard({
  node,
  edges,
  link,
  t,
}: {
  node: ChainNode;
  edges: ChainEdge[];
  link: { url: string; clickable: boolean } | null;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  const Icon = NODE_ICON[node.key] ?? Server;
  const tone = verdictTone(node.verdict);
  const ring =
    tone === "success"
      ? "border-[var(--tessera-border)]"
      : tone === "danger"
        ? "border-[var(--tessera-fg-danger)]/50 bg-[var(--tessera-fg-danger)]/[0.06]"
        : "border-[var(--tessera-fg-warning)]/50 bg-[var(--tessera-fg-warning)]/[0.06]";
  const dot =
    tone === "success"
      ? "bg-[var(--tessera-green)]"
      : tone === "danger"
        ? "bg-[var(--tessera-fg-danger)]"
        : "bg-[var(--tessera-fg-warning)]";

  return (
    <div className={`min-w-0 rounded-lg border px-2 py-1.5 ${ring}`}>
      <div className="flex min-w-0 items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
        <span className="min-w-0 flex-1 truncate text-[0.72rem] font-medium text-[var(--foreground)]">
          {node.key}
        </span>
        {/* The emitter cannot go red here and the reader is told why, rather than left to
            wonder why one node is permanently green. */}
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`}
          title={node.self_evident ? t("selfEvident") : t(`verdictTitle.${node.verdict}`, { n: 0 })}
        />
        {link ? (
          link.clickable ? (
            <a
              href={link.url}
              target="_blank"
              rel="noreferrer"
              title={t("openTool", { url: link.url })}
              className="shrink-0 text-[var(--muted-foreground)] transition-colors hover:text-[var(--tessera-green)]"
            >
              <ArrowUpRight className="h-3 w-3" />
            </a>
          ) : (
            // Shown, not offered. An operator who CAN reach the host still wants the port; a
            // reader who cannot must not be handed a door onto their own loopback.
            <span
              className="shrink-0 text-[0.55rem] text-[var(--muted-foreground)]"
              title={t("onHostOnly", { url: link.url })}
            >
              ⌂
            </span>
          )
        ) : null}
      </div>
      {edges.length > 0 ? (
        <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">
          {edges.map((edge) => (
            <span
              key={`${edge.source}-${edge.signal}`}
              // The declaration travels to the reader: this is where the drawing is checkable.
              title={t("edgeDeclared", {
                source: edge.source,
                signal: t(`signal.${edge.signal}`),
                where: edge.declared_in,
              })}
              className={`text-[0.58rem] ${SIGNAL_LINE[edge.signal]}`}
            >
              ← {edge.source}
              {edge.profile ? ` (${t(`profile.${edge.profile}`)})` : ""}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}
