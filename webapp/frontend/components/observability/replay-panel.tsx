"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Compass,
  EyeOff,
  FlaskConical,
  Gavel,
  Globe,
  Heart,
  HelpCircle,
  Layers3,
  Play,
  ScanSearch,
  ShieldAlert,
  Shuffle,
  Waves,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchCorpusScan,
  fetchProvenance,
  fetchReplays,
  fetchSteganography,
  runAblation,
  runConsistency,
  runCoverage,
  runCrossLingual,
  runEnsemble,
  runReplay,
  runReranking,
  runRobustness,
  runSycophancy,
  runWhy,
} from "@/lib/api/client";
import type {
  AblationReport,
  ConsistencyReport,
  CorpusScanReport,
  CoverageReport,
  CrossLingualReport,
  EnsembleReport,
  ProvenanceReport,
  ReplayBundle,
  ReplayResult,
  RerankContribution,
  RobustnessReport,
  StegoReport,
  SycophancyReport,
  WhyExplanation,
} from "@/lib/api/schemas";

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

  const [consist, setConsist] = useState<Record<string, ConsistencyReport>>({});
  const consistMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runConsistency(bundleId),
    onSuccess: (res, vars) => setConsist((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [robust, setRobust] = useState<Record<string, RobustnessReport>>({});
  const robustMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runRobustness(bundleId),
    onSuccess: (res, vars) => setRobust((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [scans, setScans] = useState<Record<string, CorpusScanReport>>({});
  const scanMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => fetchCorpusScan(bundleId),
    onSuccess: (res, vars) => setScans((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [stego, setStego] = useState<Record<string, StegoReport>>({});
  const stegoMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => fetchSteganography(bundleId),
    onSuccess: (res, vars) => setStego((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [ensemble, setEnsemble] = useState<Record<string, EnsembleReport>>({});
  const ensembleMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runEnsemble(bundleId),
    onSuccess: (res, vars) => setEnsemble((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [coverage, setCoverage] = useState<Record<string, CoverageReport>>({});
  const coverageMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runCoverage(bundleId),
    onSuccess: (res, vars) => setCoverage((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [syco, setSyco] = useState<Record<string, SycophancyReport>>({});
  const sycoMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runSycophancy(bundleId),
    onSuccess: (res, vars) => setSyco((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [xling, setXling] = useState<Record<string, CrossLingualReport>>({});
  const xlingMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runCrossLingual(bundleId),
    onSuccess: (res, vars) => setXling((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [rerank, setRerank] = useState<Record<string, RerankContribution>>({});
  const rerankMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runReranking(bundleId),
    onSuccess: (res, vars) => setRerank((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [ablation, setAblation] = useState<Record<string, AblationReport>>({});
  const ablationMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runAblation(bundleId),
    onSuccess: (res, vars) => setAblation((prev) => ({ ...prev, [vars.bundleId]: res })),
  });

  const [why, setWhy] = useState<Record<string, WhyExplanation>>({});
  const whyMutation = useMutation({
    mutationFn: ({ bundleId }: { bundleId: string }) => runWhy(bundleId),
    onSuccess: (res, vars) => setWhy((prev) => ({ ...prev, [vars.bundleId]: res })),
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
              const cons = consist[b.bundle_id];
              const rob = robust[b.bundle_id];
              const scan = scans[b.bundle_id];
              const steg = stego[b.bundle_id];
              const ens = ensemble[b.bundle_id];
              const cov = coverage[b.bundle_id];
              const syc = syco[b.bundle_id];
              const xl = xling[b.bundle_id];
              const rr = rerank[b.bundle_id];
              const abl = ablation[b.bundle_id];
              const wh = why[b.bundle_id];
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
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          consistMutation.isPending &&
                          consistMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => consistMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Shuffle className="h-3.5 w-3.5" />
                        {t("consistency.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          scanMutation.isPending && scanMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => scanMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <ShieldAlert className="h-3.5 w-3.5" />
                        {t("corpusScan.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          stegoMutation.isPending &&
                          stegoMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => stegoMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <EyeOff className="h-3.5 w-3.5" />
                        {t("stego.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          ensembleMutation.isPending &&
                          ensembleMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => ensembleMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Gavel className="h-3.5 w-3.5" />
                        {t("ensemble.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          coverageMutation.isPending &&
                          coverageMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => coverageMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Compass className="h-3.5 w-3.5" />
                        {t("coverage.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          sycoMutation.isPending && sycoMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => sycoMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Heart className="h-3.5 w-3.5" />
                        {t("sycophancy.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          xlingMutation.isPending &&
                          xlingMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => xlingMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Globe className="h-3.5 w-3.5" />
                        {t("crosslingual.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          rerankMutation.isPending &&
                          rerankMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => rerankMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Layers3 className="h-3.5 w-3.5" />
                        {t("reranking.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          ablationMutation.isPending &&
                          ablationMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => ablationMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <FlaskConical className="h-3.5 w-3.5" />
                        {t("ablation.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          whyMutation.isPending && whyMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => whyMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <HelpCircle className="h-3.5 w-3.5" />
                        {t("why.run")}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="gap-1.5"
                        disabled={
                          robustMutation.isPending &&
                          robustMutation.variables?.bundleId === b.bundle_id
                        }
                        onClick={() => robustMutation.mutate({ bundleId: b.bundle_id })}
                      >
                        <Waves className="h-3.5 w-3.5" />
                        {t("robustness.run")}
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
                  {scan ? <CorpusScanView report={scan} /> : null}
                  {steg ? <StegoView report={steg} /> : null}
                  {ens ? <EnsembleView report={ens} /> : null}
                  {cov ? <CoverageView report={cov} /> : null}
                  {syc ? <SycophancyView report={syc} /> : null}
                  {xl ? <CrossLingualView report={xl} /> : null}
                  {rr ? <RerankingView report={rr} /> : null}
                  {abl ? <AblationView report={abl} /> : null}
                  {wh ? <WhyView report={wh} /> : null}
                  {rob ? <RobustnessView report={rob} /> : null}
                  {cons ? <ConsistencyView report={cons} /> : null}
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

function CorpusScanView({ report }: { report: CorpusScanReport }) {
  const t = useTranslations("observability");
  const clean = report.n_poisoned === 0;
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("corpusScan.title")}</span>
        <Badge tone={clean ? "success" : "danger"}>
          {report.n_poisoned}/{report.n_chunks} {t("corpusScan.poisoned")}
        </Badge>
      </div>
      {clean ? (
        <p className="mt-2 text-xs text-[var(--muted-foreground)]">{t("corpusScan.clean")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1.5">
          {report.findings.map((f, i) => (
            <li key={`${f.index}-${i}`} className="flex items-start gap-2">
              <span aria-hidden className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-red-500" />
              <span className="min-w-0">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("corpusScan.chunk")} #{f.index}
                </span>{" "}
                <span className="text-red-600 dark:text-red-400">{f.snippet}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function WhyView({ report }: { report: WhyExplanation }) {
  const t = useTranslations("observability");
  const confPct = Math.round(report.confidence * 100);
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <HelpCircle className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("why.title")}</span>
        <Badge tone={report.fully_grounded ? "success" : "warning"}>
          {t("why.confidence")} {confPct}%
        </Badge>
      </div>
      <ul className="mt-2 flex flex-col gap-1.5">
        {report.claims.map((c, i) => (
          <li key={`${i}-${c.claim.slice(0, 16)}`} className="flex items-start gap-2">
            <span
              aria-hidden
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                c.supported ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
            <span className="min-w-0">
              <span className={c.supported ? "" : "text-red-600 dark:text-red-400"}>{c.claim}</span>
              {c.source ? (
                <span className="block text-[0.65rem] text-[var(--muted-foreground)]">
                  ← {c.source}
                </span>
              ) : (
                <span className="block text-[0.65rem] text-red-600 dark:text-red-400">
                  {t("why.unsupported")}
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AblationView({ report }: { report: AblationReport }) {
  const t = useTranslations("observability");
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <FlaskConical className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("ablation.title")}</span>
        <span>
          {t("ablation.baseline")}:{" "}
          <span className="font-semibold tabular-nums">{report.baseline.toFixed(2)}</span>
        </span>
      </div>
      <ul className="mt-2 flex flex-col gap-1.5 text-xs">
        {report.layers.map((layer) => (
          <li key={layer.layer} className="flex items-center gap-3">
            <span className="w-24 shrink-0 font-mono text-[var(--muted-foreground)]">
              {t(`ablation.${layer.layer}`)}
            </span>
            <span className="tabular-nums">{layer.score.toFixed(2)}</span>
            <Badge
              tone={layer.worth > 0.05 ? "success" : layer.worth < -0.05 ? "danger" : "neutral"}
            >
              {t("ablation.worth")} {layer.worth >= 0 ? "+" : ""}
              {layer.worth.toFixed(2)}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RerankingView({ report }: { report: RerankContribution }) {
  const t = useTranslations("observability");
  const lexicalPct = Math.round(report.mean_lexical_share * 100);
  const vectorPct = Math.round(report.mean_vector_share * 100);
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Layers3 className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("reranking.title")}</span>
        <Badge tone={report.reranker_lift > 0 ? "success" : "neutral"}>
          {t("reranking.lift")} {report.reranker_lift}
        </Badge>
        {report.top1_changed ? <Badge tone="warning">{t("reranking.top1Changed")}</Badge> : null}
      </div>
      <div className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-[var(--muted)]">
        <div
          className="bg-blue-500"
          style={{ width: `${vectorPct}%` }}
          title={`vector ${vectorPct}%`}
        />
        <div
          className="bg-amber-500"
          style={{ width: `${lexicalPct}%` }}
          title={`lexical ${lexicalPct}%`}
        />
      </div>
      <div className="mt-1 flex gap-4 text-xs text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-blue-500" />
          {t("reranking.vector")} <span className="tabular-nums">{vectorPct}%</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-amber-500" />
          {t("reranking.lexical")} <span className="tabular-nums">{lexicalPct}%</span>
        </span>
      </div>
    </div>
  );
}

function CrossLingualView({ report }: { report: CrossLingualReport }) {
  const t = useTranslations("observability");
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Globe className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("crosslingual.title")}</span>
        <Badge tone={report.consistent ? "success" : "danger"}>
          {report.consistent ? t("crosslingual.consistent") : t("crosslingual.divergent")}
        </Badge>
        <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
          {t("crosslingual.min")} {Math.round(report.min_similarity * 100)}%
        </span>
      </div>
      <ul className="mt-2 flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        {Object.entries(report.answers).map(([lang, answer]) => (
          <li key={lang} className="flex items-start gap-2">
            <span className="w-8 shrink-0 uppercase">{lang}</span>
            <span className="min-w-0 break-words">{answer}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SycophancyView({ report }: { report: SycophancyReport }) {
  const t = useTranslations("observability");
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Heart className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("sycophancy.title")}</span>
        <Badge tone={report.sycophantic ? "danger" : "success"}>
          {report.sycophantic ? t("sycophancy.flagged") : t("sycophancy.ok")}
        </Badge>
        <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
          {report.score.toFixed(2)}
        </span>
        <span className="text-xs text-[var(--muted-foreground)]">{report.judge_model}</span>
      </div>
      {report.rationale ? <p className="mt-1 text-xs">{report.rationale}</p> : null}
    </div>
  );
}

function CoverageView({ report }: { report: CoverageReport }) {
  const t = useTranslations("observability");
  const pct = Math.round(report.max_similarity * 100);
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Compass className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("coverage.title")}</span>
        <Badge tone={report.covered ? "success" : "danger"}>
          {report.covered ? t("coverage.covered") : t("coverage.gap")}
        </Badge>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("coverage.best")}: <span className="tabular-nums">{pct}%</span> · {report.n_chunks}{" "}
          {t("coverage.chunks")}
        </span>
      </div>
    </div>
  );
}

function EnsembleView({ report }: { report: EnsembleReport }) {
  const t = useTranslations("observability");
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Gavel className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span>
          {t("ensemble.mean")}:{" "}
          <span className="font-semibold tabular-nums">{report.mean_score.toFixed(2)}</span>
        </span>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("ensemble.spread")}: {report.max_spread.toFixed(2)}
        </span>
        <Badge tone={report.disagreement ? "danger" : "success"}>
          {report.disagreement ? t("ensemble.hardCase") : t("ensemble.agree")}
        </Badge>
      </div>
      <ul className="mt-2 flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        {report.scores.map((s) => (
          <li key={s.model} className="flex items-center gap-3">
            <span className="w-28 shrink-0 font-mono">{s.model}</span>
            <span className="tabular-nums">{s.score.toFixed(2)}</span>
            <span className="min-w-0 truncate">{s.rationale}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StegoView({ report }: { report: StegoReport }) {
  const t = useTranslations("observability");
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <EyeOff className="h-4 w-4 text-[var(--muted-foreground)]" />
        <span className="text-xs text-[var(--muted-foreground)]">{t("stego.title")}</span>
        <Badge tone={report.clean ? "success" : "danger"}>
          {report.clean ? t("stego.clean") : `${report.n_hidden} ${t("stego.hidden")}`}
        </Badge>
        {Object.entries(report.categories).map(([cat, count]) => (
          <span key={cat} className="text-xs text-[var(--muted-foreground)]">
            {cat}: <span className="tabular-nums">{count}</span>
          </span>
        ))}
      </div>
      {report.decoded_tags ? (
        <p className="mt-2 text-xs">
          <span className="text-[var(--muted-foreground)]">{t("stego.decoded")}:</span>{" "}
          <span className="font-mono text-red-600 dark:text-red-400">{report.decoded_tags}</span>
        </p>
      ) : null}
    </div>
  );
}

function RobustnessView({ report }: { report: RobustnessReport }) {
  const t = useTranslations("observability");
  const tone =
    report.min_faithfulness >= 0.7
      ? "success"
      : report.min_faithfulness >= 0.5
        ? "warning"
        : "danger";
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-4">
        <span>
          {t("robustness.baseline")}:{" "}
          <span className="font-semibold tabular-nums">
            {report.baseline_faithfulness.toFixed(2)}
          </span>
        </span>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("robustness.similarity")}: {Math.round(report.mean_similarity * 100)}%
        </span>
        <Badge tone={tone}>
          {t("robustness.minFaith")} {report.min_faithfulness.toFixed(2)}
        </Badge>
      </div>
      <ul className="mt-2 flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        {report.results.map((r) => (
          <li key={r.kind} className="flex items-center gap-3">
            <span className="w-20 shrink-0">{r.kind}</span>
            <span className="tabular-nums">sim {Math.round(r.similarity * 100)}%</span>
            <span className="tabular-nums">faith {r.faithfulness.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ConsistencyView({ report }: { report: ConsistencyReport }) {
  const t = useTranslations("observability");
  const pct = Math.round(report.uncertainty * 100);
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="flex items-center gap-2">
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("consistency.uncertainty")}
        </span>
        <Badge tone={pct <= 20 ? "success" : pct <= 50 ? "warning" : "danger"}>{pct}%</Badge>
        <span className="text-xs text-[var(--muted-foreground)]">
          {report.samples} {t("consistency.samples")}
        </span>
      </div>
      <ul className="mt-2 flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
        {report.answers.map((a, i) => (
          <li key={`${i}-${a.slice(0, 16)}`} className="break-words">
            • {a}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProvenanceView({ report }: { report: ProvenanceReport }) {
  const t = useTranslations("observability");
  const pct = Math.round(report.grounded_fraction * 100);
  return (
    <div className="mt-3 rounded-md bg-[var(--muted)]/40 p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--muted-foreground)]">{t("provenance.grounded")}</span>
        <Badge tone={pct >= 80 ? "success" : pct >= 50 ? "warning" : "danger"}>{pct}%</Badge>
        {report.utilization ? (
          <span className="text-xs text-[var(--muted-foreground)]">
            · {t("provenance.chunksUsed")} {report.utilization.used_chunks}/
            {report.utilization.n_chunks} · {t("provenance.deadContext")}{" "}
            {report.utilization.dead_chunks}
          </span>
        ) : null}
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
