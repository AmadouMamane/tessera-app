"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Play, ScanSearch } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchProvenance, fetchReplays, runReplay } from "@/lib/api/client";
import type { ProvenanceReport, ReplayBundle, ReplayResult } from "@/lib/api/schemas";

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

  const [provs, setProvs] = useState<Record<string, ProvenanceReport>>({});
  const provMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => fetchProvenance(bundleId),
    onSuccess: (res, vars) => setProvs((prev) => ({ ...prev, [vars.bundleId]: res })),
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
              const prov = provs[b.bundle_id];
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
                      {b.lineage ? (
                        <p className="mt-0.5 text-[0.65rem] text-[var(--muted-foreground)]/80">
                          {t("lineage.prompt")} {b.lineage.prompt_version} · {t("lineage.policy")}{" "}
                          {b.lineage.guard_policy_version} · {b.lineage.doc_sources.length}{" "}
                          {t("lineage.docs")}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          provMutation.isPending && provMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => provMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <ScanSearch className="h-3.5 w-3.5" />
                        {t("provenance.run")}
                      </Button>
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
                  </div>
                  {b.latency_ms ? <LatencyWaterfall timings={b.latency_ms} /> : null}
                  {prov ? <ProvenanceView report={prov} /> : null}
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

const LATENCY_COLORS = [
  "bg-blue-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-violet-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-lime-500",
];

function LatencyWaterfall({ timings }: { timings: Record<string, number> }) {
  const t = useTranslations("observability");
  const entries = Object.entries(timings).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, ms]) => sum + ms, 0);
  if (total <= 0) {
    return null;
  }
  return (
    <div className="mt-2">
      <div className="mb-1 flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
        <span>{t("latency.title")}</span>
        <span className="tabular-nums">{Math.round(total)} ms</span>
      </div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-[var(--muted)]">
        {entries.map(([name, ms], i) => (
          <div
            key={name}
            className={LATENCY_COLORS[i % LATENCY_COLORS.length]}
            style={{ width: `${(ms / total) * 100}%` }}
            title={`${name}: ${Math.round(ms)} ms`}
          />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[0.65rem] text-[var(--muted-foreground)]">
        {entries.map(([name, ms], i) => (
          <span key={name} className="flex items-center gap-1">
            <span className={`h-2 w-2 rounded-full ${LATENCY_COLORS[i % LATENCY_COLORS.length]}`} />
            {name} <span className="tabular-nums">{Math.round(ms)}ms</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function ProvenanceView({ report }: { report: ProvenanceReport }) {
  const t = useTranslations("observability");
  const pct = Math.round(report.grounded_fraction * 100);
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs text-[var(--muted-foreground)]">{t("provenance.grounded")}</span>
        <Badge tone={pct >= 80 ? "success" : pct >= 50 ? "warning" : "danger"}>{pct}%</Badge>
      </div>
      <ul className="flex flex-col gap-1.5">
        {report.claims.map((c, i) => (
          <li key={`${i}-${c.text.slice(0, 16)}`} className="flex items-start gap-2">
            <span
              aria-hidden
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                c.supported ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
            <span className="min-w-0">
              <span className={c.supported ? "" : "text-red-600 dark:text-red-400"}>{c.text}</span>{" "}
              <span className="text-xs text-[var(--muted-foreground)] tabular-nums">
                ({c.support.toFixed(2)})
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
