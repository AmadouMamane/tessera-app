"use client";

import * as Popover from "@radix-ui/react-popover";
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
import type { ReactNode } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { resolveLink, verdictTone } from "@/components/health/observability-shared";
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
 * Every edge carries the file that declares it. It used to live in a hover `title` — the one
 * affordance a touch screen does not have and a reader never finds — so the citations now open
 * on CLICK: every node and every signal badge is a popover naming its edges and the file that
 * wires each one (ADR 0026: a claim whose evidence a reader cannot reach is decoration).
 */
export function ObservabilityChain() {
  const t = useTranslations("health.chain");

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm">
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
          <QueryErrorState
            compact
            onRetry={() => void query.refetch()}
            retrying={query.isRefetching}
          />
        ) : (
          <ChainGraph data={query.data} />
        )}
      </CardContent>
    </Card>
  );
}

/** Shared popover chrome, on the tooltip surface the ⓘ uses — one look for "evidence opens". */
function ChainPopover({ trigger, children }: { trigger: ReactNode; children: ReactNode }) {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>{trigger}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          sideOffset={6}
          collisionPadding={12}
          className="z-50 w-80 rounded-xs border border-[var(--tessera-tooltip-border)] bg-[var(--tessera-tooltip-bg)] p-3 text-left shadow-[0_2px_6px_rgba(0,0,0,0.4)] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
        >
          {children}
          <Popover.Arrow className="fill-[var(--tessera-tooltip-border)]" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** One edge, with its citation in the open — the line the whole drawing rests on. */
function EdgeLine({ edge }: { edge: ChainEdge }) {
  const t = useTranslations("health.chain");
  return (
    <li className="text-[0.7rem] leading-snug text-[var(--tessera-tooltip-fg-muted)]">
      <span className="text-[var(--tessera-tooltip-fg)]">
        {edge.source} → {edge.target}
      </span>
      {" · "}
      {t(`signal.${edge.signal}`)}
      {edge.profile ? ` (${t(`profile.${edge.profile}`)})` : ""}
      <span className="block truncate font-mono text-[0.62rem]" title={edge.declared_in}>
        {edge.declared_in}
      </span>
    </li>
  );
}

/** Per signal, whether it still gets from the agent to somewhere it is kept — click for the path. */
function SignalLegend({ data }: { data: ComponentsResponse }) {
  const t = useTranslations("health.chain");
  const entries = Object.entries(data.chain.signals) as [ChainSignal, string][];
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {entries.map(([signal, state]) => (
        <ChainPopover
          key={signal}
          trigger={
            <button
              type="button"
              aria-label={t("signalPath", { signal: t(`signal.${signal}`) })}
              className="cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            >
              <Badge
                tone={state === "served" ? "success" : state === "lost" ? "danger" : "warning"}
              >
                {t(`signal.${signal}`)} · {t(`state.${state}`)}
              </Badge>
            </button>
          }
        >
          <p className="font-semibold text-[var(--tessera-tooltip-fg)] text-xs">
            {t("signalPath", { signal: t(`signal.${signal}`) })}
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {data.chain.edges
              .filter((edge) => edge.signal === signal)
              .map((edge) => (
                <EdgeLine key={`${edge.source}-${edge.target}`} edge={edge} />
              ))}
          </ul>
        </ChainPopover>
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
 * The emitter column centres its lone node so the drawing reads as a fan-out from it rather
 * than as a stray card over a void.
 */
function ChainGraph({ data }: { data: ComponentsResponse }) {
  const t = useTranslations("health.chain");
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
              <div
                className={`flex min-w-0 flex-1 flex-col gap-1.5 ${
                  column.stage === "emitter" ? "justify-center pb-4" : ""
                }`}
              >
                {column.nodes.map((node) => (
                  <ChainNodeCard
                    key={node.key}
                    node={node}
                    edges={data.chain.edges}
                    link={resolveLink(data.links, node.key)}
                  />
                ))}
              </div>
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
}: {
  node: ChainNode;
  edges: ChainEdge[];
  link: { url: string; hostLocal: boolean } | null;
}) {
  const t = useTranslations("health.chain");
  const Icon = NODE_ICON[node.key] ?? Server;
  const tone = verdictTone(node.verdict);
  const incoming = edges.filter((edge) => edge.target === node.key);
  const outgoing = edges.filter((edge) => edge.source === node.key);
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
        <ChainPopover
          trigger={
            <button
              type="button"
              aria-label={t("openNode", { node: node.key })}
              className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            >
              <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
              <span className="min-w-0 flex-1 truncate text-[0.72rem] font-medium text-[var(--foreground)]">
                {node.key}
              </span>
              {/* The emitter cannot go red here and the reader is told why, rather than left
                  to wonder why one node is permanently green. */}
              <span
                className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`}
                title={
                  node.self_evident ? t("selfEvident") : t(`verdictTitle.${node.verdict}`, { n: 0 })
                }
              />
            </button>
          }
        >
          <p className="flex items-center justify-between gap-2 font-semibold text-[var(--tessera-tooltip-fg)] text-xs">
            {node.key}
            <span className="font-normal text-[0.62rem] uppercase tracking-wide text-[var(--tessera-tooltip-fg-muted)]">
              {t(`stage.${node.stage}`)}
            </span>
          </p>
          <p className="mt-0.5 text-[0.7rem] text-[var(--tessera-tooltip-fg-muted)]">
            {node.self_evident
              ? t("selfEvident")
              : `${t("verdictLine")} : ${t(`nodeState.${node.verdict}`)}`}
            {node.carries.length > 0
              ? ` · ${t("carries", {
                  list: node.carries.map((signal) => t(`signal.${signal}`)).join(", "),
                })}`
              : ""}
          </p>
          {incoming.length + outgoing.length > 0 ? (
            <>
              <p className="mt-2 border-t border-[var(--tessera-tooltip-border)] pt-2 font-medium text-[0.58rem] text-[var(--tessera-tooltip-fg-muted)] uppercase tracking-wide">
                {t("declaredEdges")}
              </p>
              <ul className="mt-1 flex max-h-48 flex-col gap-1 overflow-y-auto">
                {[...incoming, ...outgoing].map((edge) => (
                  <EdgeLine key={`${edge.source}-${edge.target}-${edge.signal}`} edge={edge} />
                ))}
              </ul>
            </>
          ) : null}
        </ChainPopover>
        {link ? (
          // Always a link. Whether the reader is at the deployment host is not knowable from
          // here, and withholding a door that would have opened is its own dishonesty; what IS
          // known — that the address is host-local — is said in the tooltip and on the card.
          <a
            href={link.url}
            target="_blank"
            rel="noreferrer"
            title={
              link.hostLocal ? t("onHostOnly", { url: link.url }) : t("openTool", { url: link.url })
            }
            className="shrink-0 text-[var(--muted-foreground)] transition-colors hover:text-[var(--tessera-green)]"
          >
            <ArrowUpRight className="h-3 w-3" />
          </a>
        ) : null}
      </div>
      {incoming.length > 0 ? (
        <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">
          {incoming.map((edge) => (
            <span
              key={`${edge.source}-${edge.signal}`}
              // The declaration also travels on hover for mouse readers; the popover above is
              // where it is reachable for everyone else.
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
