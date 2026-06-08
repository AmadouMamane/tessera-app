"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchReplays, runReplay } from "@/lib/api/client";
import type { ReplayBundle, ReplayResult } from "@/lib/api/schemas";

// Locally-available Ollama models to replay against (smallest first).
const MODELS = ["llama3.2:3b", "mistral:7b", "gemma3:27b", "llama3.3:70b"] as const;

export function ReplayPanel() {
  const t = useTranslations("observability");
  const [model, setModel] = useState<string>(MODELS[0]);
  const [results, setResults] = useState<Record<string, ReplayResult>>({});

  const replays = useQuery({
    queryKey: ["replays"],
    queryFn: ({ signal }) => fetchReplays(signal),
    refetchInterval: 10_000,
  });

  const mutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runReplay(bundleId, model),
    onSuccess: (res) => setResults((prev) => ({ ...prev, [res.bundle_id]: res })),
  });

  const bundles: ReplayBundle[] = replays.data ? [...replays.data.bundles].reverse() : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>{t("replay.title")}</span>
          <label className="flex items-center gap-2 text-xs font-normal text-[var(--muted-foreground)]">
            {t("replay.model")}
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {replays.isLoading ? (
          <Skeleton className="h-12 w-full" />
        ) : bundles.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {t("replay.empty")}
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {bundles.map((b) => {
              const res = results[b.bundle_id];
              const pending = mutation.isPending && mutation.variables?.bundleId === b.bundle_id;
              return (
                <li key={b.bundle_id} className="rounded-lg border border-[var(--border)] p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm">{b.question}</p>
                      <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
                        {b.language.toUpperCase()} · {t("replay.original")}{" "}
                        <span className="tabular-nums">{b.original_score.toFixed(2)}</span> ·{" "}
                        {b.original_model}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      className="gap-1.5"
                      disabled={pending}
                      onClick={() => mutation.mutate({ bundleId: b.bundle_id })}
                    >
                      <Play className="h-3.5 w-3.5" />
                      {pending ? t("replay.running") : t("replay.run")}
                    </Button>
                  </div>
                  {res ? <ReplayResultView res={res} /> : null}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ReplayResultView({ res }: { res: ReplayResult }) {
  const t = useTranslations("observability");
  const improved = res.score_delta >= 0;
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-4">
        <span className="text-xs text-[var(--muted-foreground)]">{res.candidate_model}</span>
        <span>
          {t("replay.candidate")}:{" "}
          <span className="font-semibold tabular-nums">{res.candidate_score.toFixed(2)}</span>
        </span>
        <Badge tone={improved ? "success" : "danger"}>
          {improved ? "+" : ""}
          {res.score_delta.toFixed(2)}
        </Badge>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("replay.similarity")}: {Math.round(res.similarity * 100)}%
        </span>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-[var(--foreground)]">{res.candidate_answer}</p>
    </div>
  );
}
