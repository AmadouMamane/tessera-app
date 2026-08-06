"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, ExternalLink, Home } from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { useServedFromLoopback, verdictTone } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";

const POLL_MS = 15_000;

/**
 * The tools that are running, and the doors into them.
 *
 * Grafana, Prometheus, Langfuse, Phoenix and MinIO all run beside this page, and the page linked
 * nowhere. An operator diagnosing a red component had to remember five port numbers.
 *
 * A link is only offered when it can actually be opened FROM HERE. The published addresses are
 * loopback (`127.0.0.1:13000` is Grafana on the deployment host), which is true for a reader
 * sitting on that host and false for everyone else: on `tessera.example.com` the same link
 * reaches whatever happens to run on the reader's own port 13000. So the URL is always shown —
 * an operator who can reach the host wants the port — and it becomes clickable only when this
 * page is itself being served from loopback. A dashboard that promises closed doors is worse
 * than one that promises nothing.
 *
 * Each door also carries the component's live verdict, because the second-most useless link on a
 * monitoring page is one into a tool that is down.
 */
export function ToolLinks() {
  const t = useTranslations("health.tools");
  const servedFromLoopback = useServedFromLoopback();

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  const links = query.data?.links ?? [];
  const verdicts = new Map(
    (query.data?.components ?? [])
      .filter((component) => component.group === "stack")
      .map((component) => [component.name, component.verdict]),
  );

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <ExternalLink className="h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data && links.length > 0 && !servedFromLoopback ? (
          <Badge tone="neutral">
            <Home className="h-3 w-3" />
            {t("hostOnly")}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-12 w-full" />
        ) : query.error || !query.data ? (
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : links.length === 0 ? (
          // Configured to publish nothing is a legitimate deployment, and it must read as that
          // rather than as a broken card.
          <p className="text-xs text-[var(--muted-foreground)]">{t("none")}</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {links.map((link) => (
              <ToolDoor
                key={link.key}
                name={link.key}
                url={link.url}
                verdict={verdicts.get(link.key) ?? "blind"}
                clickable={!link.loopback || servedFromLoopback}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const DOOR = "flex min-w-0 items-center gap-1.5 rounded-md border px-2 py-1 text-[0.7rem]";

/** One door: the tool's name, its port, its live verdict — and whether it opens from here. */
function ToolDoor({
  name,
  url,
  verdict,
  clickable,
}: {
  name: string;
  url: string;
  verdict: string;
  clickable: boolean;
}) {
  const t = useTranslations("health.tools");
  const tone = verdictTone(verdict);
  const dot =
    tone === "success"
      ? "bg-[var(--tessera-green)]"
      : tone === "danger"
        ? "bg-[var(--tessera-fg-danger)]"
        : "bg-[var(--tessera-fg-warning)]";
  // The port is what an operator actually needs to remember; the hostname is the fallback for a
  // URL that carries none. Parsing is guarded because a mis-set env var must not blank the card.
  let port = url;
  try {
    const parsed = new URL(url);
    port = parsed.port || parsed.hostname;
  } catch {
    port = url;
  }
  const body = (
    <>
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      <span className="truncate">{name}</span>
      <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
        {port}
      </span>
      {clickable ? <ArrowUpRight className="h-3 w-3 shrink-0" /> : null}
    </>
  );

  if (!clickable) {
    return (
      <span
        title={t("hostOnlyTitle", { url })}
        className={`${DOOR} border-[var(--tessera-border)] text-[var(--muted-foreground)]`}
      >
        {body}
      </span>
    );
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer"
      title={url}
      className={`${DOOR} border-[var(--tessera-border)] text-[var(--foreground)] transition-colors hover:border-[var(--tessera-green)]/50 hover:text-[var(--tessera-green)]`}
    >
      {body}
    </a>
  );
}
