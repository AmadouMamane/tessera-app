"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Clapperboard,
  FileText,
  Flag,
  MessageSquare,
  Search,
  ShieldCheck,
  SkipBack,
  SkipForward,
  Workflow,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useState } from "react";

import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchReplays, fetchTrajectory } from "@/lib/api/client";
import type { TrajectoryStep } from "@/lib/api/schemas";

function stepIcon(kind: string): ReactNode {
  switch (kind) {
    case "input":
      return <MessageSquare className="h-4 w-4" />;
    case "guard":
      return <ShieldCheck className="h-4 w-4" />;
    case "retrieval":
      return <Search className="h-4 w-4" />;
    case "node":
      return <Workflow className="h-4 w-4" />;
    case "answer":
      return <Flag className="h-4 w-4" />;
    default:
      return <FileText className="h-4 w-4" />;
  }
}

function statusTone(status: string): "success" | "warning" | "neutral" {
  if (status === "ok") return "success";
  if (status === "warn") return "warning";
  return "neutral";
}

export function SessionTheater() {
  const t = useTranslations("observability");
  const [bundleId, setBundleId] = useState<string | null>(null);
  const [cursor, setCursor] = useState(0);

  const replays = useQuery({
    queryKey: ["replays"],
    queryFn: ({ signal }) => fetchReplays(signal),
    refetchInterval: 10_000,
  });

  // Default to the most recent captured turn once bundles arrive.
  const bundles = replays.data ? [...replays.data.bundles].reverse() : [];
  const selectedId = bundleId ?? bundles[0]?.bundle_id ?? null;

  const trajectory = useQuery({
    queryKey: ["trajectory", selectedId],
    queryFn: ({ signal }) =>
      selectedId ? fetchTrajectory(selectedId, signal) : Promise.reject(new Error("no bundle")),
    enabled: selectedId != null,
  });

  // Reset the playhead whenever the selected turn changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on turn change
  useEffect(() => {
    setCursor(0);
  }, [selectedId]);

  const steps: TrajectoryStep[] = trajectory.data?.steps ?? [];
  const current = steps[Math.min(cursor, steps.length - 1)];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Clapperboard className="h-4 w-4 text-[var(--tessera-fg-info)]" />
            {t("theater.title")}
          </span>
          {bundles.length > 0 ? (
            <select
              value={selectedId ?? ""}
              onChange={(e) => setBundleId(e.target.value)}
              className="max-w-[60%] rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              {bundles.map((b) => (
                <option key={b.bundle_id} value={b.bundle_id}>
                  {b.language.toUpperCase()} · {b.question.slice(0, 48)}
                </option>
              ))}
            </select>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {replays.isError && replays.data === undefined ? (
          <QueryErrorState
            compact
            onRetry={() => replays.refetch()}
            retrying={replays.isFetching}
          />
        ) : trajectory.isError && trajectory.data === undefined ? (
          <QueryErrorState
            compact
            onRetry={() => trajectory.refetch()}
            retrying={trajectory.isFetching}
          />
        ) : bundles.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {t("theater.empty")}
          </p>
        ) : steps.length === 0 || !current ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {t("theater.loading")}
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                variant="outline"
                disabled={cursor === 0}
                onClick={() => setCursor((c) => Math.max(0, c - 1))}
              >
                <SkipBack className="h-3.5 w-3.5" />
              </Button>
              <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
                {cursor + 1} / {steps.length}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={cursor >= steps.length - 1}
                onClick={() => setCursor((c) => Math.min(steps.length - 1, c + 1))}
              >
                <SkipForward className="h-3.5 w-3.5" />
              </Button>
              {trajectory.data ? (
                <span className="ml-auto text-xs text-[var(--muted-foreground)]">
                  {trajectory.data.model} · {Math.round(trajectory.data.total_ms)} ms ·{" "}
                  {t("theater.score")} {trajectory.data.score.toFixed(2)}
                </span>
              ) : null}
            </div>

            <div className="grid gap-4 sm:grid-cols-[180px_1fr]">
              <ol className="flex flex-col gap-1">
                {steps.map((s, i) => (
                  <li key={s.index}>
                    <button
                      type="button"
                      onClick={() => setCursor(i)}
                      className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors ${
                        i === cursor
                          ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                          : "text-[var(--muted-foreground)] hover:bg-[var(--muted)]/50"
                      }`}
                    >
                      {stepIcon(s.kind)}
                      <span className="min-w-0 truncate">{s.title}</span>
                    </button>
                  </li>
                ))}
              </ol>

              <div className="rounded-lg border border-[var(--border)] p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  {stepIcon(current.kind)}
                  <span className="font-medium">{current.title}</span>
                  <Badge tone={statusTone(current.status)}>{current.kind}</Badge>
                  {current.duration_ms > 0 ? (
                    <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
                      {Math.round(current.duration_ms)} ms
                    </span>
                  ) : null}
                </div>
                <p className="whitespace-pre-wrap break-words text-sm text-[var(--foreground)]">
                  {current.detail}
                </p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
