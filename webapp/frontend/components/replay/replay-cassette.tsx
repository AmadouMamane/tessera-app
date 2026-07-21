"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  CircleDot,
  Clapperboard,
  CornerDownRight,
  Play,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { Truncate } from "@/components/ui/truncate";
import { fetchReplays, runReplay } from "@/lib/api/client";
import type { ReplayBundle, ReplayResult } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { type CassetteSpan, buildCassetteTrace } from "@/lib/replay-cassette";

// XT-01 (registre des rails) — the execution-trace cassette lens. The selected
// cassette derives from the URL (`?bundle=<id>`, deep-linkable), never from
// local state, and the active mode is always displayed: Live (latest captures)
// or Replay (a selected cassette — a historical execution, read as recorded).
// Every section is a projection of the persisted S2 record; what was not
// captured says "non capturé", never a fabricated value.

// Locally-available Ollama models to replay against (smallest first) — same
// candidate list as the historical replay panel; the backend refuses unknowns.
const MODELS = ["llama3.2:3b", "mistral:7b", "gemma3:27b", "llama3.3:70b"] as const;

function fmtMs(ms: number): string {
  if (ms < 1) return "< 1 ms";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)} ms`;
}

export function ReplayCassettes({ asof }: { asof: string | null }) {
  const t = useTranslations("replay");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selectedId = searchParams.get("bundle");

  const replays = useQuery({
    queryKey: ["replays"],
    queryFn: ({ signal }) => fetchReplays(signal),
    refetchInterval: 30_000,
  });

  const select = (bundleId: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (bundleId) {
      params.set("bundle", bundleId);
    } else {
      params.delete("bundle");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  // Newest first: the API returns bundles oldest→newest.
  const bundles = [...(replays.data?.bundles ?? [])].reverse();
  const selected = selectedId ? (bundles.find((b) => b.bundle_id === selectedId) ?? null) : null;

  return (
    <section className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[0.66rem] font-medium",
            selectedId
              ? "border-[#7c5cf5]/60 bg-[#7c5cf5]/10 text-[#c9b8ff]"
              : "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
          )}
          data-testid="cassette-mode"
        >
          {selectedId ? <Clapperboard className="h-3 w-3" /> : <CircleDot className="h-3 w-3" />}
          {selectedId ? t("cassette.modeReplay") : t("cassette.modeLive")}
        </span>
        {selected ? (
          <span className="min-w-0 truncate text-[0.68rem] text-[var(--tessera-text)]">
            {new Date(selected.captured_at).toLocaleString()}
          </span>
        ) : null}
        <MetricInfo
          title={t("cassette.title")}
          what={t("explain.cassettes.what")}
          how={t("explain.cassettes.how")}
          source={t("explain.cassettes.source")}
        />
      </div>

      <div className="grid min-w-0 gap-3 xl:grid-cols-12">
        <CassetteList
          t={t}
          bundles={bundles}
          selectedId={selectedId}
          onSelect={select}
          loaded={replays.data !== undefined}
          className="xl:col-span-4"
        />
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-8">
          {selectedId && replays.data !== undefined && selected === null ? (
            <Panel title={t("cassette.title")}>
              <p className="text-xs text-[var(--tessera-text-muted)]">
                {t("cassette.notFound", { id: selectedId })}
              </p>
            </Panel>
          ) : null}
          {selected ? <CassetteDetail t={t} bundle={selected} asof={asof} /> : null}
          {!selectedId && replays.data !== undefined ? (
            <Panel title={t("cassette.title")}>
              <p className="text-xs text-[var(--tessera-text-muted)]">{t("cassette.pick")}</p>
            </Panel>
          ) : null}
        </div>
      </div>
    </section>
  );
}

type T = ReturnType<typeof useTranslations<"replay">>;

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="text-[0.72rem] font-medium text-[var(--tessera-text)]">{title}</h3>
      {children}
    </section>
  );
}

function CassetteList({
  t,
  bundles,
  selectedId,
  onSelect,
  loaded,
  className,
}: {
  t: T;
  bundles: ReplayBundle[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  loaded: boolean;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="border-b border-[var(--tessera-border)] px-3 py-2 text-[0.72rem] font-medium text-[var(--tessera-text)]">
        {t("cassette.listTitle", { count: bundles.length })}
      </div>
      {loaded && bundles.length === 0 ? (
        <p className="px-3 py-8 text-center text-[0.7rem] text-[var(--tessera-text-muted)]">
          {t("cassette.empty")}
        </p>
      ) : (
        <ul className="max-h-[520px] overflow-y-auto">
          {bundles.map((b) => (
            <li key={b.bundle_id}>
              <button
                type="button"
                onClick={() => onSelect(b.bundle_id === selectedId ? null : b.bundle_id)}
                aria-pressed={b.bundle_id === selectedId}
                className={cn(
                  "group flex w-full items-center gap-2 border-b border-[var(--tessera-border)] px-3 py-2 text-left transition-colors last:border-b-0",
                  b.bundle_id === selectedId
                    ? "bg-[#7c5cf5]/10"
                    : "hover:bg-[var(--tessera-muted)]",
                )}
              >
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <Truncate full={b.question} className="text-[0.7rem] text-[var(--tessera-text)]">
                    {b.question}
                  </Truncate>
                  <span className="flex flex-wrap items-center gap-x-2 text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
                    <span>{new Date(b.captured_at).toLocaleString()}</span>
                    {b.agent_id ? <span>{b.agent_id}</span> : null}
                    <span>{b.original_model}</span>
                    <span>{b.original_score.toFixed(2)}</span>
                  </span>
                </div>
                <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)] group-hover:text-[var(--tessera-text)]" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CassetteDetail({ t, bundle, asof }: { t: T; bundle: ReplayBundle; asof: string | null }) {
  const trace = buildCassetteTrace(bundle);
  return (
    <>
      <Panel title={t("cassette.turnTitle")}>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[0.68rem] sm:grid-cols-3">
          <MetaRow label={t("cassette.metaModel")} value={bundle.original_model} />
          <MetaRow label={t("cassette.metaScore")} value={bundle.original_score.toFixed(2)} />
          <MetaRow label={t("cassette.metaLanguage")} value={bundle.language} />
          <MetaRow label={t("cassette.metaAgent")} value={bundle.agent_id ?? "—"} />
          <MetaRow
            label={t("cassette.metaSampling")}
            value={
              bundle.sampling && Object.keys(bundle.sampling).length > 0
                ? Object.entries(bundle.sampling)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(" · ")
                : t("cassette.notCaptured")
            }
          />
          <MetaRow
            label={t("cassette.metaMaxTokens")}
            value={
              bundle.max_output_tokens !== null && bundle.max_output_tokens !== undefined
                ? String(bundle.max_output_tokens)
                : t("cassette.notCaptured")
            }
          />
        </dl>
        <div className="flex flex-col gap-1 text-[0.7rem]">
          <span className="text-[var(--tessera-text-muted)]">{t("cassette.question")}</span>
          <p className="whitespace-pre-wrap text-[var(--tessera-text)]">{bundle.question}</p>
          <span className="mt-1 text-[var(--tessera-text-muted)]">{t("cassette.answer")}</span>
          <p className="max-h-40 overflow-y-auto whitespace-pre-wrap text-[var(--tessera-text)]">
            {bundle.original_answer}
          </p>
        </div>
      </Panel>

      <Panel title={t("cassette.traceTitle")}>
        {trace === null ? (
          <p className="text-xs text-[var(--tessera-text-muted)]">{t("cassette.traceEmpty")}</p>
        ) : (
          <>
            {!trace.positioned ? (
              <p className="text-[0.66rem] text-amber-300">{t("cassette.traceUnpositioned")}</p>
            ) : null}
            <div className="flex flex-col gap-1.5">
              {trace.spans.map((span) => (
                <CassetteSpanRow key={span.key} span={span} total={trace.total_ms} t={t} />
              ))}
            </div>
            {trace.orphan_tools.length > 0 ? (
              <div className="flex flex-col gap-1 border-t border-[var(--tessera-border)] pt-2">
                <span className="text-[0.64rem] text-[var(--tessera-text-muted)]">
                  {t("cassette.orphanTools")}
                </span>
                {trace.orphan_tools.map((tool) => (
                  <ToolRow key={tool.name} tool={tool} />
                ))}
              </div>
            ) : null}
            {trace.total_ms !== null ? (
              <p className="text-[0.64rem] text-[var(--tessera-text-muted)]">
                {t("cassette.traceTotal")}{" "}
                <span className="tabular-nums">{fmtMs(trace.total_ms)}</span>
              </p>
            ) : null}
          </>
        )}
      </Panel>

      <Panel title={t("cassette.promptTitle")}>
        {bundle.prompt_messages && bundle.prompt_messages.length > 0 ? (
          <div className="flex max-h-72 flex-col gap-2 overflow-y-auto">
            {bundle.prompt_messages.map((m, i) => (
              <div
                key={`${m.role}-${i}`}
                className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2"
              >
                <span className="text-[0.62rem] font-medium uppercase text-[#c9b8ff]">
                  {m.role}
                </span>
                <p className="mt-1 whitespace-pre-wrap text-[0.68rem] leading-relaxed text-[var(--tessera-text)]">
                  {m.content}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-[var(--tessera-text-muted)]">
            {t("cassette.promptNotCaptured")}
          </p>
        )}
      </Panel>

      <ReplayAction t={t} bundle={bundle} asof={asof} />
    </>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0">
        <Truncate full={value} className="text-[var(--tessera-text)]">
          {value}
        </Truncate>
      </dd>
    </div>
  );
}

function CassetteSpanRow({
  span,
  total,
  t,
}: {
  span: CassetteSpan;
  total: number | null;
  t: T;
}) {
  const positioned = span.start_ms !== null && total !== null && total > 0;
  const left = positioned ? Math.min(((span.start_ms ?? 0) / (total ?? 1)) * 100, 99) : 0;
  const subMs = span.duration_ms < 1;
  const width = positioned
    ? subMs
      ? 0.8
      : Math.max((span.duration_ms / (total ?? 1)) * 100, 1)
    : 100;
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2 text-[0.7rem]">
        <Truncate full={span.key} className="text-[var(--tessera-text)]">
          {span.key}
        </Truncate>
        <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
          {fmtMs(span.duration_ms)}
        </span>
      </div>
      {positioned ? (
        <div className="h-[4px] w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
          <div
            className="h-full rounded-full bg-[#7c5cf5]"
            style={{
              marginLeft: `${left}%`,
              width: `${width}%`,
              minWidth: subMs ? "3px" : undefined,
            }}
          />
        </div>
      ) : null}
      {span.tools.map((tool) => (
        <ToolRow key={tool.name} tool={tool} nested label={t("cassette.toolCall")} />
      ))}
    </div>
  );
}

function ToolRow({
  tool,
  nested = false,
  label,
}: {
  tool: { name: string; succeeded: boolean; duration_ms: number };
  nested?: boolean;
  label?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text)]",
        nested && "pl-4",
      )}
    >
      {nested ? (
        <CornerDownRight className="h-3 w-3 shrink-0 text-[var(--tessera-text-muted)]" />
      ) : null}
      {tool.succeeded ? (
        <Check className="h-3 w-3 shrink-0 text-emerald-400" />
      ) : (
        <AlertTriangle className="h-3 w-3 shrink-0 text-red-400" />
      )}
      <span className="min-w-0 truncate">{tool.name}</span>
      {label ? <span className="text-[var(--tessera-text-muted)]">{label}</span> : null}
      <span className="ml-auto shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
        {fmtMs(tool.duration_ms)}
      </span>
    </div>
  );
}

function ReplayAction({ t, bundle, asof }: { t: T; bundle: ReplayBundle; asof: string | null }) {
  const [model, setModel] = useState<string>(MODELS[0]);
  const [result, setResult] = useState<ReplayResult | null>(null);
  const mutation = useMutation({
    mutationFn: () => runReplay(bundle.bundle_id, model),
    onSuccess: setResult,
  });
  // One does not act in the past: while the page reads As-of T, the replay
  // mutation is frozen (registre des rails §6 — AGIR composition).
  const frozen = asof !== null;
  return (
    <Panel title={t("cassette.replayTitle")}>
      <div className="flex flex-wrap items-center gap-2">
        <label className="inline-flex items-center gap-1.5 text-[0.68rem] text-[var(--tessera-text-muted)]">
          {t("cassette.candidateModel")}
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.66rem] text-[var(--tessera-text)]"
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={frozen || mutation.isPending}
          onClick={() => mutation.mutate()}
          className="inline-flex h-7 items-center gap-1.5 rounded-md border border-[#7c5cf5]/60 bg-[#7c5cf5]/10 px-2.5 text-[0.68rem] font-medium text-[#c9b8ff] transition-colors hover:bg-[#7c5cf5]/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Play className="h-3 w-3" />
          {mutation.isPending ? t("cassette.replayRunning") : t("cassette.replayRun")}
        </button>
        {frozen ? (
          <span className="text-[0.64rem] text-amber-300">{t("cassette.replayFrozen")}</span>
        ) : null}
        {mutation.isError ? (
          <span className="text-[0.64rem] text-red-400">{t("cassette.replayFailed")}</span>
        ) : null}
      </div>
      {result ? (
        <div className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2 text-[0.68rem]">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 tabular-nums">
            <span className="text-[var(--tessera-text-muted)]">{result.candidate_model}</span>
            <span
              className={cn(
                "font-medium",
                result.score_delta >= 0 ? "text-emerald-300" : "text-red-400",
              )}
            >
              Δ {result.score_delta >= 0 ? "+" : ""}
              {result.score_delta.toFixed(2)}
            </span>
            <span className="text-[var(--tessera-text-muted)]">
              {t("cassette.similarity")} {(result.similarity * 100).toFixed(0)}%
            </span>
          </div>
          <p className="max-h-32 overflow-y-auto whitespace-pre-wrap text-[var(--tessera-text)]">
            {result.candidate_answer}
          </p>
        </div>
      ) : null}
    </Panel>
  );
}
