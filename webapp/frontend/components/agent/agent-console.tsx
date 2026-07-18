"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Check,
  ChevronRight,
  Cpu,
  Database,
  Download,
  MessageSquare,
  MessageSquareOff,
  Paperclip,
  Pencil,
  Plus,
  RotateCcw,
  SendHorizontal,
  Shield,
  ShieldCheck,
  Tag,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useSession } from "next-auth/react";
import { useLocale } from "next-intl";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import {
  type AgentInvokeBody,
  fetchAgentConsole,
  fetchConsoleFeedback,
  fetchSandboxConfig,
  invokeAgentTurn,
  saveConsoleFeedback,
} from "@/lib/api/client";
import type {
  AgentInvokeOutcome,
  ChatCitation,
  ChatDebug,
  ChatEndEvent,
  ChatTrace,
  AgentConsole as Data,
} from "@/lib/api/schemas";
import type { SandboxConfig } from "@/lib/api/schemas";
import { streamChat } from "@/lib/api/sse";
import { cn } from "@/lib/cn";
import { CHAT_MODELS, getStoredModel, isModelAllowedForRole } from "@/lib/models";
import { fieldsFromSchema } from "@/lib/schema-form";
import { useAgentId } from "@/lib/use-agent-id";

import { AgentCrossLinks } from "./agent-cross-links";
import { SchemaForm } from "./schema-form";

type Rating = "up" | "down";

type T = ReturnType<typeof useTranslations<"agentConsole">>;

const FIELD_ICONS: LucideIcon[] = [Cpu, Tag, Database, Shield, Activity];

// Console inspector tabs are stable French keys (the panel gating matches them);
// these are the localized display labels per locale.
const TAB_LABEL: Record<string, Record<string, string>> = {
  fr: {
    Sources: "Sources",
    Outils: "Outils",
    "Garde-fous": "Garde-fous",
    Évaluation: "Évaluation",
    Debug: "Debug",
  },
  de: {
    Sources: "Quellen",
    Outils: "Tools",
    "Garde-fous": "Guardrails",
    Évaluation: "Bewertung",
    Debug: "Debug",
  },
  en: {
    Sources: "Sources",
    Outils: "Tools",
    "Garde-fous": "Guardrails",
    Évaluation: "Evaluation",
    Debug: "Debug",
  },
};

const SCORE_TONE: Record<string, string> = {
  good: "text-emerald-300",
  warn: "text-amber-300",
  crit: "text-red-300",
};
const STATUS_TONE: Record<string, string> = {
  good: "text-emerald-400",
  warn: "text-amber-300",
  crit: "text-red-400",
};
const BADGE_TONE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  warn: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
};

type LiveMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  latency?: string;
  citations?: ChatCitation[];
  debug?: ChatDebug;
  error?: boolean;
};

function getSubjectId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const key = "tessera.debugSubjectId";
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(key, id);
  }
  return id;
}

function formatTime(ts: number): string {
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(ts));
}

export function AgentConsole() {
  const t = useTranslations("agentConsole");
  const locale = useLocale() as "fr" | "de" | "en";
  const abortRef = useRef<AbortController | null>(null);
  const streamStartedAt = useRef<number>(0);
  const [messages, setMessages] = useState<LiveMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [liveDebug, setLiveDebug] = useState<ChatDebug | null>(null);
  // Sandbox playground overrides (env Sandbox): model / system prompt / guards.
  const role = useSession().data?.user?.role ?? null;
  const [model, setModel] = useState<string>(() => getStoredModel());
  const [promptOverride, setPromptOverride] = useState<string | null>(null);
  const [guardDisabled, setGuardDisabled] = useState<string[]>([]);
  const { data: sandbox } = useQuery({
    queryKey: ["sandbox-config", locale],
    queryFn: ({ signal }) => fetchSandboxConfig(locale, signal),
    staleTime: 300_000,
  });
  // Never hold a gated model the current role can't run (it would 403 at the
  // proxy with no answer): coerce back to the first runnable model.
  useEffect(() => {
    if (!isModelAllowedForRole(model, role)) {
      const ok = CHAT_MODELS.find((m) => isModelAllowedForRole(m.id, role));
      if (ok) setModel(ok.id);
    }
  }, [model, role]);
  const qc = useQueryClient();
  // ADR 0019 §I2 — the console is scoped to the agent in the route: the payload's shape
  // (interactive vs honest-empty) is decided by THIS agent's declared invocation binding.
  const agentId = useAgentId();
  const { data } = useQuery({
    queryKey: ["agent-console", locale, agentId],
    queryFn: ({ signal }) => fetchAgentConsole(locale, agentId, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  // Durable operator feedback (thumbs up/down) for the live conversation turns.
  const { data: feedback } = useQuery({
    queryKey: ["agent-console-feedback", conversationId],
    queryFn: ({ signal }) => fetchConsoleFeedback(conversationId ?? "", signal),
    enabled: Boolean(conversationId),
  });
  const rate = useMutation({
    mutationFn: ({ turn, rating }: { turn: number; rating: Rating }) =>
      saveConsoleFeedback(conversationId ?? "", turn, rating),
    onSuccess: (fresh) => qc.setQueryData(["agent-console-feedback", conversationId], fresh),
  });
  const ratings = feedback?.ratings ?? {};

  useEffect(() => () => abortRef.current?.abort(), []);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming) return;
      const history = messages.map((message) => ({
        role: message.role,
        content: message.content,
      }));
      setInput("");
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: "user", content: trimmed, createdAt: Date.now() },
      ]);
      setIsStreaming(true);
      streamStartedAt.current = performance.now();
      const controller = new AbortController();
      abortRef.current = controller;

      let assistantId: string | null = null;
      const ensureAssistant = () => {
        if (assistantId) return assistantId;
        assistantId = crypto.randomUUID();
        setMessages((current) => [
          ...current,
          {
            id: assistantId ?? crypto.randomUUID(),
            role: "assistant",
            content: "",
            createdAt: Date.now(),
          },
        ]);
        return assistantId;
      };

      const finalize = (envelope: ChatEndEvent) => {
        const id = ensureAssistant();
        const latency = `${((performance.now() - streamStartedAt.current) / 1000).toFixed(1)}s`;
        setConversationId(envelope.conversation_id);
        setLiveDebug(envelope.debug ?? null);
        setMessages((current) =>
          current.map((message) =>
            message.id === id
              ? {
                  ...message,
                  content: envelope.final_response,
                  latency,
                  citations: envelope.citations,
                  debug: envelope.debug,
                }
              : message,
          ),
        );
      };

      try {
        await streamChat(
          {
            message: trimmed,
            conversation_id: conversationId ?? undefined,
            subject_id: getSubjectId(),
            language: locale,
            history: history.length > 0 ? history : undefined,
            model,
            system_prompt_override: promptOverride ?? undefined,
            guard_overrides: guardDisabled.length > 0 ? guardDisabled : undefined,
          },
          {
            signal: controller.signal,
            // Signal the cockpit console surface so the BFF can — only for a
            // verified operator session — route on cockpit-embedded (ADR 0010
            // Phase B). A hint, not a privilege: no operator session, no change.
            surface: "console",
            onStart: ({ conversation_id }) => setConversationId(conversation_id),
            onToken: (token) => {
              const id = ensureAssistant();
              setMessages((current) =>
                current.map((message) =>
                  message.id === id ? { ...message, content: message.content + token } : message,
                ),
              );
            },
            onEnd: finalize,
            onError: (message) => {
              const id = ensureAssistant();
              setMessages((current) =>
                current.map((item) =>
                  item.id === id ? { ...item, content: message, error: true } : item,
                ),
              );
            },
          },
        );
      } catch (error) {
        if (!controller.signal.aborted) {
          const id = ensureAssistant();
          const message = error instanceof Error ? error.message : String(error);
          setMessages((current) =>
            current.map((item) =>
              item.id === id ? { ...item, content: message, error: true } : item,
            ),
          );
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setIsStreaming(false);
      }
    },
    [conversationId, guardDisabled, isStreaming, locale, messages, model, promptOverride],
  );

  const resetSession = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setConversationId(null);
    setLiveDebug(null);
    setInput("");
    setIsStreaming(false);
  }, []);

  const lastUserText = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "user") return messages[i]?.content ?? "";
    }
    return "";
  }, [messages]);

  const replayLastTurn = useCallback(() => {
    if (lastUserText) void sendMessage(lastUserText);
  }, [lastUserText, sendMessage]);

  const exportSession = useCallback(() => {
    const blob = new Blob([JSON.stringify({ conversationId, messages }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `tessera-console-${conversationId ?? "session"}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }, [conversationId, messages]);

  const onFooterAction = useCallback(
    (key: string) => {
      if (key === "replay") replayLastTurn();
      else if (key === "export") exportSession();
      else if (key === "close") resetSession();
    },
    [replayLastTurn, exportSession, resetSession],
  );

  const onRate = useCallback(
    (turn: number, rating: Rating) => {
      if (conversationId) rate.mutate({ turn, rating });
    },
    [conversationId, rate],
  );

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  // ADR 0019 §I2 — honest-empty gate. A publish-only agent (declared binding: none)
  // exposes no test invocation: render the observe-only state pointing at its runs and
  // evals, never a broken chat over config it does not own. Only trip when we positively
  // know it is non-invocable (an absent block means an old payload → keep the interactive
  // console, the pre-ADR behaviour).
  if (data.invocation && !data.invocation.invocable) {
    return <ConsoleHonestEmpty empty={data.empty} title={data.title} subtitle={data.subtitle} />;
  }

  // ADR 0019 §I3 — an http-binding agent is a foreign runtime invoked over its declared
  // endpoint: a request/response test bench, not the in-process SSE console. Generated from
  // the declaration, no per-agent code.
  if (data.invocation?.binding === "http") {
    return <HttpConsole data={data} agentId={agentId} />;
  }

  const liveSession = conversationId
    ? `sess_${conversationId.slice(0, 8)}`
    : data.context?.session_id;
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      {/* Operator-context strip — honestly reflects the surface this turn runs
          on (ADR 0010 Phase B). With a verified operator session the console
          reaches the operator fleet (recouvrement) on the cockpit surface;
          otherwise it stays on the customer surface. No secret is shown. */}
      <p
        className={cn(
          "rounded-md border px-2.5 py-1 text-[0.7rem]",
          role
            ? "border-[var(--tessera-border-strong)] bg-[var(--tessera-surface-2)] text-[var(--tessera-text)]"
            : "border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--tessera-text-muted)]",
        )}
      >
        {role ? t("operatorContext.operator", { role }) : t("operatorContext.visitor")}
      </p>

      {/* Sandbox config bar — env Sandbox playground: choose model / edit the
          system prompt / toggle guard categories for the next turns. Overrides
          are per-turn (never persisted). "Nouvelle session" stays top-right. */}
      <SandboxControls
        sandbox={sandbox}
        role={role}
        model={model}
        onModel={setModel}
        promptOverride={promptOverride}
        onPromptOverride={setPromptOverride}
        guardDisabled={guardDisabled}
        onGuardDisabled={setGuardDisabled}
        onNewSession={resetSession}
        newSessionLabel={data.actions?.new_session ?? t("newSession")}
      />

      {/* Three panes share a viewport-bounded height on xl and scroll
          internally, so the conversation no longer towers over the summary /
          trace columns as turns accumulate. */}
      <div className="grid items-start gap-3 xl:grid-cols-12">
        <div className="flex min-h-0 min-w-0 flex-col gap-3 xl:col-span-6 xl:max-w-[840px]">
          <ChatCard
            data={data}
            input={input}
            isStreaming={isStreaming}
            messages={messages}
            ratings={ratings}
            onAbort={() => abortRef.current?.abort()}
            onFooterAction={onFooterAction}
            onInputChange={setInput}
            onRate={onRate}
            onReset={resetSession}
            onSubmit={sendMessage}
          />
        </div>

        {/* Central "Résumé de la réponse" — context strip + response panels.
            Live debug swaps the pre-turn config panels for the real turn data. */}
        <div className="flex min-h-0 min-w-0 flex-col gap-3 xl:col-span-3">
          <ResponseSummary data={data} debug={liveDebug} sessionId={liveSession} t={t} />
        </div>

        {/* XT-01 — the page's temporal rail, a persistent waterfall column. */}
        <div className="flex min-h-0 min-w-0 flex-col gap-3 xl:col-span-3">
          <TraceColumn debug={liveDebug} sessionId={liveSession} t={t} />
        </div>
      </div>

      {/* "Liens utiles" — see-also navigation, placed at the foot of the
          interactive console so the sandbox bar + conversation lead. */}
      <AgentCrossLinks page="console" />
    </div>
  );
}

// ── honest-empty console (ADR 0019 §I2) ─────────────────────────────────────

/** The observe-only state for a publish-only agent (declared binding: none): it exposes
 *  no test invocation, so instead of a broken chat we show the honest-empty copy from the
 *  backend and route the operator to the surfaces that DO observe it (runs / evals via the
 *  cross-links). No per-agent code — the shape is decided entirely by the declaration. */
function ConsoleHonestEmpty({
  empty,
  title,
  subtitle,
}: {
  empty?: { title: string; detail: string };
  title?: string;
  subtitle?: string;
}) {
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <div className="flex min-h-[54vh] items-center justify-center">
        <div className="w-full max-w-2xl rounded-lg border border-dashed border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-6 py-12 text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)]">
            <MessageSquareOff className="h-5 w-5 text-[var(--tessera-text-muted)]" aria-hidden />
          </div>
          <p className="text-sm font-semibold">{empty?.title ?? title}</p>
          <p className="mx-auto mt-1.5 max-w-md text-[0.8rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {empty?.detail ?? subtitle}
          </p>
        </div>
      </div>
      <AgentCrossLinks page="console" />
    </div>
  );
}

// ── http console (ADR 0019 §I3) ─────────────────────────────────────────────

/** Request/response test bench for an http-binding agent: send a turn to the endpoint the
 *  agent declares (through the audited, operator-authed invoke seam) and observe the
 *  TurnResult. No streaming, no sandbox/debug tabs — a foreign runtime owns its own guard
 *  and telemetry; this surface only proves the turn contract over the declared transport. */
function HttpConsole({ data, agentId }: { data: Data; agentId: string }) {
  const t = useTranslations();
  const [message, setMessage] = useState("");
  const [outcome, setOutcome] = useState<AgentInvokeOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const http = data.http_console;
  const cap = data.capability_console;
  const capabilities = data.capabilities ?? [];
  const endpoint = data.invocation?.endpoint ?? null;
  const invoke = useMutation({
    mutationFn: (body: AgentInvokeBody) => invokeAgentTurn(agentId, body),
    onSuccess: (o) => {
      setOutcome(o);
      setError(null);
    },
    onError: (e) => {
      setError(e instanceof Error ? e.message : "invocation failed");
      setOutcome(null);
    },
  });
  const send = () => {
    const msg = message.trim();
    if (msg && !invoke.isPending) invoke.mutate({ message: msg });
  };
  const reply =
    outcome?.result && typeof outcome.result.visibleReply === "string"
      ? (outcome.result.visibleReply as string)
      : null;
  const green = outcome?.verdict === "green";

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <header className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-base font-semibold">{data.title}</h1>
          <span className="inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-1.5 py-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <Cpu className="h-3 w-3" aria-hidden /> HTTP
          </span>
          {endpoint ? (
            <code className="rounded bg-[var(--tessera-surface-2)] px-1.5 py-0.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
              {endpoint}
            </code>
          ) : null}
        </div>
        <p className="max-w-2xl text-[0.8rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {data.subtitle}
        </p>
      </header>

      <div className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
        {cap?.free_text_label ? (
          <p className="text-[0.65rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {cap.free_text_label}
          </p>
        ) : null}
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
          placeholder={http?.placeholder}
          rows={3}
          className="w-full resize-y rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-sm text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-border-strong)]"
        />
        <div className="flex justify-end">
          <button
            type="button"
            onClick={send}
            disabled={invoke.isPending || !message.trim()}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface-2)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            <SendHorizontal className="h-4 w-4" aria-hidden />
            {http?.send_label}
          </button>
        </div>
      </div>

      {capabilities.length > 0 && cap ? (
        <section className="flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
          <div className="flex flex-col gap-0.5">
            <h2 className="text-[0.8rem] font-semibold">{cap.section_label}</h2>
            <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{cap.hint}</p>
          </div>
          {capabilities.map((capability) => (
            <div
              key={capability.id}
              className="flex flex-col gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
            >
              <h3 className="text-[0.78rem] font-medium">{t(capability.label_key)}</h3>
              <SchemaForm
                fields={fieldsFromSchema(capability.schema)}
                submitLabel={cap.submit_label}
                requiredLabel={cap.required_label}
                pending={invoke.isPending}
                onSubmit={(params) =>
                  invoke.mutate({ action: { capability_id: capability.id, params } })
                }
              />
            </div>
          ))}
        </section>
      ) : null}

      {error ? (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-2.5 py-1.5 text-[0.8rem] text-red-300">
          {error}
        </p>
      ) : null}

      {outcome ? (
        <div className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
          <div className="flex items-center gap-2 text-[0.8rem]">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[0.7rem] font-medium",
                green ? BADGE_TONE.good : BADGE_TONE.crit,
              )}
            >
              <span
                className={cn("h-1.5 w-1.5 rounded-full", green ? "bg-emerald-400" : "bg-red-400")}
              />
              {green ? http?.verdict_ok : http?.verdict_failed}
            </span>
            {outcome.status_code != null ? (
              <span className="text-[var(--tessera-text-muted)]">HTTP {outcome.status_code}</span>
            ) : null}
            <span className="text-[var(--tessera-text-muted)]">
              {Math.round(outcome.duration_ms)} ms
            </span>
          </div>

          {reply ? (
            <div>
              <p className="mb-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {http?.reply_label}
              </p>
              <p className="whitespace-pre-wrap text-sm">{reply}</p>
            </div>
          ) : null}

          {outcome.error ? <p className="text-[0.8rem] text-red-300">{outcome.error}</p> : null}
          {outcome.conformance.length > 0 ? (
            <ul className="list-inside list-disc text-[0.75rem] text-amber-300">
              {outcome.conformance.map((v) => (
                <li key={v}>{v}</li>
              ))}
            </ul>
          ) : null}

          {outcome.result ? (
            <details className="text-[0.75rem]">
              <summary className="cursor-pointer text-[var(--tessera-text-muted)]">
                {http?.result_label}
              </summary>
              <pre className="mt-1 max-h-72 overflow-auto rounded-md bg-[var(--tessera-bg)] p-2 text-[0.7rem]">
                {JSON.stringify(outcome.result, null, 2)}
              </pre>
            </details>
          ) : null}
        </div>
      ) : null}

      <AgentCrossLinks page="console" />
    </div>
  );
}

// ── sandbox config bar ──────────────────────────────────────────────────────

/** env Sandbox playground controls: pick the model, edit the system prompt, and
 *  toggle guard categories. Each is a per-turn override (never persisted) sent on
 *  the next message. Prompt + guard categories are prefilled from the live
 *  /observability/sandbox-config (the real YAML bundle + runtime policy). */
function SandboxControls({
  sandbox,
  role,
  model,
  onModel,
  promptOverride,
  onPromptOverride,
  guardDisabled,
  onGuardDisabled,
  onNewSession,
  newSessionLabel,
}: {
  sandbox: SandboxConfig | undefined;
  role: string | null;
  model: string;
  onModel: (id: string) => void;
  promptOverride: string | null;
  onPromptOverride: (value: string | null) => void;
  guardDisabled: string[];
  onGuardDisabled: (next: string[]) => void;
  onNewSession: () => void;
  newSessionLabel: string;
}) {
  const [editing, setEditing] = useState(false);
  const cats = sandbox?.guard_categories ?? [];
  const basePrompt = sandbox?.system_prompt ?? "";
  const promptDirty = promptOverride !== null && promptOverride !== basePrompt;

  function toggleGuard(key: string) {
    onGuardDisabled(
      guardDisabled.includes(key)
        ? guardDisabled.filter((k) => k !== key)
        : [...guardDisabled, key],
    );
  }

  return (
    <section className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[0.7rem]">
        <span className="inline-flex items-center rounded-md border border-[#d98b1f]/40 bg-[#3a2a14]/40 px-2 py-0.5 text-[0.6rem] font-medium uppercase tracking-wide text-[#f4c76a]">
          env Sandbox
        </span>

        <label className="inline-flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          <span className="text-[var(--tessera-text-muted)]">Modèle</span>
          <select
            value={model}
            onChange={(e) => onModel(e.target.value)}
            className="rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface-2)] px-2 py-1 text-[0.7rem] text-[var(--tessera-text)]"
          >
            {CHAT_MODELS.map((m) => {
              const allowed = isModelAllowedForRole(m.id, role);
              return (
                <option key={m.id} value={m.id} disabled={!allowed}>
                  {m.label}
                  {allowed ? "" : " — super-admin"}
                </option>
              );
            })}
          </select>
        </label>

        <span className="inline-flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              if (promptOverride === null) onPromptOverride(basePrompt);
              setEditing((e) => !e);
            }}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[0.7rem] transition-colors hover:bg-[var(--tessera-muted)]",
              promptDirty
                ? "border-[#d98b1f]/55 bg-[#3a2a14]/40 text-[#f4c76a]"
                : "border-[var(--tessera-border-strong)] bg-[var(--tessera-surface-2)] text-[var(--tessera-text)]",
            )}
          >
            <Pencil className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
            Prompt système{promptDirty ? " · modifié" : ""}
          </button>
          {promptDirty ? (
            <button
              type="button"
              onClick={() => {
                onPromptOverride(null);
                setEditing(false);
              }}
              className="text-[0.66rem] text-[var(--tessera-text-muted)] underline hover:text-[var(--tessera-text)]"
            >
              réinitialiser
            </button>
          ) : null}
        </span>

        <span className="inline-flex flex-wrap items-center gap-1.5">
          <Shield className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          <span className="text-[var(--tessera-text-muted)]">Garde-fous</span>
          {cats.map((c) => {
            const on = !guardDisabled.includes(c.key);
            return (
              <button
                key={c.key}
                type="button"
                onClick={() => toggleGuard(c.key)}
                title={`${c.detail} (${c.count} motifs)`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[0.66rem] transition-colors",
                  on
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] text-[var(--tessera-text-muted)] line-through",
                )}
              >
                {on ? <ShieldCheck className="h-3 w-3" /> : <Shield className="h-3 w-3" />}
                {c.label}
              </button>
            );
          })}
        </span>

        <button
          type="button"
          onClick={onNewSession}
          className="ml-auto flex h-8 items-center gap-1.5 rounded-md border border-[#d98b1f]/55 bg-[linear-gradient(180deg,#3a2a14,#21180d)] px-3 text-[0.72rem] font-medium text-[#f4c76a] hover:border-[#f4c76a]/65"
        >
          <Plus className="h-3.5 w-3.5" /> {newSessionLabel}
        </button>
      </div>

      {editing ? (
        <div className="flex flex-col gap-1">
          <textarea
            value={promptOverride ?? basePrompt}
            onChange={(e) => onPromptOverride(e.target.value)}
            rows={8}
            spellCheck={false}
            className="w-full resize-y rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg)] px-3 py-2 font-mono text-[0.68rem] leading-relaxed text-[var(--tessera-text)]"
          />
          <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">
            Override appliqué aux prochains messages de cette session — non persisté.
          </p>
        </div>
      ) : null}
    </section>
  );
}

// ── chat ─────────────────────────────────────────────────────────────────────

function ChatCard({
  data,
  input,
  isStreaming,
  messages,
  ratings,
  onAbort,
  onFooterAction,
  onInputChange,
  onRate,
  onReset,
  onSubmit,
}: {
  data: Data;
  input: string;
  isStreaming: boolean;
  messages: LiveMessage[];
  ratings: Record<string, string>;
  onAbort: () => void;
  onFooterAction: (key: string) => void;
  onInputChange: (value: string) => void;
  onRate: (turn: number, rating: Rating) => void;
  onReset: () => void;
  onSubmit: (value: string) => void;
}) {
  const t = useTranslations("agentConsole");
  const a = data.actions;
  const f = data.footer;
  const hasLiveMessages = messages.length > 0;
  let assistantTurn = -1;
  // Keep the latest turn in view as tokens stream / turns accumulate.
  const scrollRef = useRef<HTMLDivElement>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: must re-run on every messages change to follow streaming output
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);
  return (
    <section className="flex min-h-0 min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] h-[calc(100dvh-21rem)]">
      <div className="flex items-start gap-3 border-b border-[var(--tessera-border)] p-3.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#d98b1f]/45 bg-[#d98b1f]/12 text-[#f4c76a]">
          <MessageSquare className="h-4.5 w-4.5" />
        </span>
        <div className="min-w-0">
          <h2 className="text-[0.95rem] font-semibold text-[var(--tessera-text)]">{data.title}</h2>
          <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{data.subtitle}</p>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="flex min-h-[300px] flex-1 flex-col gap-4 overflow-y-auto p-3.5"
      >
        {hasLiveMessages ? (
          messages.map((message) => {
            if (message.role === "user") {
              return (
                <UserMsg
                  key={message.id}
                  time={formatTime(message.createdAt)}
                  text={message.content}
                />
              );
            }
            assistantTurn += 1;
            const turn = assistantTurn;
            return (
              <LiveAssistantMsg
                key={message.id}
                message={message}
                rating={ratings[String(turn)] as Rating | undefined}
                onRate={(rating) => onRate(turn, rating)}
              />
            );
          })
        ) : (
          <EmptyConversation t={t} />
        )}
      </div>

      <div className="border-t border-[var(--tessera-border)] p-3.5">
        <form
          className="flex items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2.5"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit(input);
          }}
        >
          <Paperclip className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
          <input
            value={input}
            disabled={isStreaming}
            placeholder={a?.input_placeholder}
            onChange={(event) => onInputChange(event.target.value)}
            className="h-8 min-w-0 flex-1 bg-transparent text-[0.78rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)] disabled:opacity-60"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={onAbort}
              className="h-8 rounded-md border border-red-500/35 px-3 text-[0.7rem] text-red-300"
            >
              {t("stop")}
            </button>
          ) : (
            <button
              type="submit"
              className="grid h-9 w-9 place-items-center rounded-full border border-[#d98b1f]/55 bg-[linear-gradient(180deg,#f4c76a,#b87923)] text-[#08111d] shadow-[0_0_18px_rgba(244,199,106,0.2)]"
              aria-label={t("send")}
            >
              <SendHorizontal className="h-4 w-4" />
            </button>
          )}
        </form>
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onReset}
            className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
          >
            <RotateCcw className="mr-1 inline h-3.5 w-3.5" />
            {t("newSession")}
          </button>
          {(a?.footer_actions ?? []).map((action) => {
            const cls =
              "inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]";
            if (action.key === "compare") {
              return (
                <Link key={action.key} href="/prouver/etat-a-date" className={cls}>
                  {action.label}
                </Link>
              );
            }
            return (
              <button
                key={action.key}
                type="button"
                onClick={() => onFooterAction(action.key)}
                className={cls}
              >
                {action.key === "export" ? <Download className="h-3.5 w-3.5" /> : null}
                {action.label}
              </button>
            );
          })}
        </div>
      </div>

      {f ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
          <span>{f.started}</span>
          <span className="inline-flex items-center gap-1.5 text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Live
          </span>
          <span>Contexte : {f.context}</span>
          <span className="inline-flex items-center gap-1">
            Langue : <span className="text-[var(--tessera-text)]">{f.language}</span>
          </span>
        </div>
      ) : null}
    </section>
  );
}

function UserMsg({ time, text }: { time: string; text: string }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
        <span className="font-medium text-[var(--tessera-text)]">Vous</span> {time}
      </span>
      <p className="max-w-[85%] rounded-xl rounded-tr-sm border border-cyan-400/25 bg-cyan-400/[0.08] px-3 py-2 text-[0.78rem] leading-relaxed text-[var(--tessera-text)]">
        {text}
      </p>
    </div>
  );
}

/** Honest empty state — the console starts with no turn; the seeded example
 *  transcript was removed. Real turns are produced live by the operator. */
function EmptyConversation({ t }: { t: T }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
        <MessageSquare className="h-5 w-5" />
      </span>
      <p className="text-[0.8rem] font-medium text-[var(--tessera-text)]">{t("emptyTitle")}</p>
      <p className="max-w-[36ch] text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {t("emptyBody")}
      </p>
    </div>
  );
}

function FeedbackButtons({
  rating,
  onRate,
}: {
  rating?: Rating;
  onRate: (rating: Rating) => void;
}) {
  return (
    <div className="flex items-center gap-3 text-[0.66rem] text-[var(--tessera-text-muted)]">
      <button
        type="button"
        aria-pressed={rating === "up"}
        onClick={() => onRate("up")}
        className={cn(
          "inline-flex items-center gap-1 hover:text-emerald-300",
          rating === "up" && "font-medium text-emerald-300",
        )}
      >
        <ThumbsUp className="h-3.5 w-3.5" /> Utile
      </button>
      <button
        type="button"
        aria-pressed={rating === "down"}
        onClick={() => onRate("down")}
        className={cn(
          "inline-flex items-center gap-1 hover:text-red-300",
          rating === "down" && "font-medium text-red-300",
        )}
      >
        <ThumbsDown className="h-3.5 w-3.5" /> Pas utile
      </button>
    </div>
  );
}

function LiveAssistantMsg({
  message,
  rating,
  onRate,
}: {
  message: LiveMessage;
  rating?: Rating;
  onRate: (rating: Rating) => void;
}) {
  const t = useTranslations("agentConsole");
  const sources = message.debug?.sources?.rows.length ?? message.citations?.length ?? 0;
  const tools = message.debug?.tools?.rows.length ?? 0;
  const guardrails = message.debug?.guardrails?.rows.length ?? 0;
  return (
    <div className="flex flex-col gap-2">
      <span className="inline-flex items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <span
          className={cn(
            "flex h-4 w-4 items-center justify-center rounded-full",
            message.error ? "bg-red-500/20 text-red-300" : "bg-emerald-500/20 text-emerald-400",
          )}
        >
          <ShieldCheck className="h-3 w-3" />
        </span>
        <span className="font-medium text-[var(--tessera-text)]">Assistant</span>{" "}
        {formatTime(message.createdAt)}
        {message.latency ? <span>- {message.latency}</span> : null}
      </span>
      <div
        className={cn(
          "whitespace-pre-wrap rounded-xl rounded-tl-sm border px-3.5 py-3 text-[0.78rem] leading-relaxed text-[var(--tessera-text)]",
          message.error
            ? "border-red-500/35 bg-red-500/10 text-red-200"
            : "border-[var(--tessera-border)] bg-[var(--tessera-bg)]",
        )}
      >
        {message.content || t("generating")}
        {!message.error && message.content ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
              Sources ({sources})
            </span>
            <span className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
              Outils ({tools})
            </span>
            <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[0.64rem] text-amber-300">
              Garde-fous ({guardrails})
            </span>
            {typeof message.debug?.tokens === "number" ? (
              <span className="ml-auto text-[0.64rem] text-[var(--tessera-text-muted)]">
                {message.debug.tokens} tokens
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      {!message.error && message.content ? (
        <FeedbackButtons rating={rating} onRate={onRate} />
      ) : null}
    </div>
  );
}

// ── XT-01 — persistent execution-trace waterfall (normative 05) ─────────────

const SPAN_STATUS_TONE: Record<string, string> = {
  ok: "text-emerald-400",
  warn: "text-amber-300",
  crit: "text-red-400",
};
const SPAN_BAR_TONE: Record<string, string> = {
  ok: "bg-emerald-400/70",
  warn: "bg-amber-300/80",
  crit: "bg-red-400/80",
};

function fmtMs(ms: number): string {
  if (ms < 1) return "< 1 ms";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)} ms`;
}

/** The execution-trace waterfall column. Spans are the *real* per-node timings
 *  from the live SSE debug envelope — positioned by their measured start offset
 *  so the bars cascade. There is a single view: a real span tree (parent/child
 *  nesting) is not captured yet, so no redundant second view is offered. Renders
 *  an honest empty state before the operator runs a turn. */
function TraceColumn({
  debug,
  sessionId,
  t,
}: {
  debug: ChatDebug | null;
  sessionId?: string;
  t: T;
}) {
  const trace = debug?.trace;

  const exportJsonl = useCallback(() => {
    if (!trace) return;
    const lines = trace.spans.map((s) => JSON.stringify(s)).join("\n");
    const blob = new Blob([lines], { type: "application/x-ndjson" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `tessera-trace-${sessionId ?? "session"}.jsonl`;
    link.click();
    URL.revokeObjectURL(url);
  }, [trace, sessionId]);

  return (
    <section className="flex min-h-0 min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] h-[460px] overflow-y-auto">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)] px-3.5 py-2.5">
        <span className="inline-flex items-center gap-2 text-[0.72rem] font-medium text-[#e0a23a]">
          <Activity className="h-4 w-4" /> {t("traceTitle")}
        </span>
      </div>

      {trace ? (
        <>
          <div className="flex flex-col gap-1.5 p-3.5">
            {trace.spans.map((span) => (
              <TraceSpan key={span.key} span={span} total={trace.total_ms} />
            ))}
          </div>
          <div className="mt-auto flex items-center justify-between gap-2 border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
            <span>
              {t("traceTotal")} <span className="tabular-nums">{fmtMs(trace.total_ms)}</span> ·{" "}
              <span className="tabular-nums">{trace.count}</span> {t("traceSpans")}
            </span>
            <button
              type="button"
              onClick={exportJsonl}
              className="inline-flex items-center gap-1 text-[#f4c76a] hover:text-white"
            >
              <Download className="h-3.5 w-3.5" /> {t("traceExport")}
            </button>
          </div>
          {sessionId ? (
            <div className="border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.62rem] text-[var(--tessera-text-muted)]">
              {t("idSession")}: <span className="tabular-nums">{sessionId}</span>
            </div>
          ) : null}
        </>
      ) : (
        <p className="px-3.5 py-10 text-center text-[0.72rem] text-[var(--tessera-text-muted)]">
          {t("traceEmpty")}
        </p>
      )}
    </section>
  );
}

function TraceSpan({
  span,
  total,
}: {
  span: ChatTrace["spans"][number];
  total: number;
}) {
  const denom = total > 0 ? total : 1;
  const left = Math.min((span.start_ms / denom) * 100, 99);
  // Sub-ms spans render as a small point rather than a fabricated wide bar.
  const subMs = span.duration_ms < 1;
  const width = subMs ? 0.8 : Math.max((span.duration_ms / denom) * 100, 1);
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2 text-[0.7rem]">
        <span className="inline-flex min-w-0 items-center gap-1.5">
          <span className={cn("shrink-0", SPAN_STATUS_TONE[span.status] ?? SPAN_STATUS_TONE.ok)}>
            {span.status === "ok" ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5" />
            )}
          </span>
          <span className="truncate text-[var(--tessera-text)]">{span.label}</span>
        </span>
        <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
          {fmtMs(span.duration_ms)}
        </span>
      </div>
      <div className="h-[4px] w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
        <div
          className={cn("h-full rounded-full", SPAN_BAR_TONE[span.status] ?? SPAN_BAR_TONE.ok)}
          style={{
            marginLeft: `${left}%`,
            width: `${width}%`,
            minWidth: subMs ? "3px" : undefined,
          }}
        />
      </div>
    </div>
  );
}

// ── central "Résumé de la réponse" column ──────────────────────────────────

/** Context strip atop the response summary (relocated from the old full-width
 *  status bar). Real config: env Sandbox · model · prompt/sources/guard stamps. */
function ContextStrip({ ctx }: { ctx: NonNullable<Data["context"]> }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-[var(--tessera-border)] px-3.5 py-2.5 text-[0.68rem]">
      {ctx.fields.map((f, i) => {
        const Icon: LucideIcon = FIELD_ICONS[i % FIELD_ICONS.length] ?? Cpu;
        return (
          <span key={f.label} className="inline-flex items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
            <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
            <span className="font-medium text-[var(--tessera-text)]">{f.value}</span>
          </span>
        );
      })}
    </div>
  );
}

function ResponseSummary({
  data,
  debug,
  sessionId,
  t,
}: {
  data: Data;
  debug: ChatDebug | null;
  sessionId?: string;
  t: T;
}) {
  const locale = useLocale();
  const baseTabs = data.tabs ?? ["Sources", "Outils", "Garde-fous", "Évaluation"];
  // The Debug tab surfaces the live turn's full internals (prompt, memory,
  // routing, usage, reviewer split, language, draft-vs-final, effective config).
  const tabs = baseTabs.includes("Debug") ? baseTabs : [...baseTabs, "Debug"];
  const [active, setActive] = useState(tabs[0] ?? "Sources");
  // Tabs are stable keys (panel gating below matches these exact strings); map
  // them to localized display labels without changing the gating contract.
  const tabLabel = (tab: string): string => TAB_LABEL[locale]?.[tab] ?? tab;
  // Response-specific signals come from the live turn only (no static fallback);
  // config panels (tools/guardrails) fall back to the real loaded policy pre-turn.
  const quality = debug?.quality;
  const sources = debug?.sources;
  const tools = debug?.tools ?? data.tools;
  const guardrails = debug?.guardrails ?? data.guardrails;
  return (
    <section className="flex min-h-0 min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] h-[460px] overflow-y-auto">
      {data.context ? <ContextStrip ctx={data.context} /> : null}
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-2.5">
        <h2 className="text-[0.82rem] font-semibold text-[var(--tessera-text)]">
          {t("summaryTitle")}
        </h2>
      </div>

      {/* Response quality — live-derived & distinct after a turn; honest awaiting
          state before (no per-turn quality to show yet). */}
      {quality ? (
        <Quality q={quality} />
      ) : (
        <Awaiting className="border-b border-[var(--tessera-border)]" text={t("qualityAwaiting")} />
      )}

      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {tabs.map((tab) => {
          const on = tab === active;
          return (
            <button
              key={tab}
              type="button"
              onClick={() => setActive(tab)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
                on
                  ? "border-[#e0a23a] font-medium text-[#e0a23a]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tabLabel(tab)}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col">
        {active === "Sources" ? (
          sources ? (
            <SourcesPanel s={sources} />
          ) : (
            <Awaiting text={t("sourcesAwaiting")} />
          )
        ) : null}
        {active === "Outils" && tools ? <ToolsPanel tl={tools} /> : null}
        {active === "Garde-fous" && guardrails ? <GuardrailsPanel g={guardrails} /> : null}
        {active === "Évaluation" ? <EvaluationPanel ev={data.evaluation} /> : null}
        {active === "Debug" ? <DebugPanel debug={debug} t={t} /> : null}
      </div>

      {sessionId ? (
        <div className="mt-auto border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
          {t("idSession")}: <span className="tabular-nums">{sessionId}</span>
        </div>
      ) : null}
    </section>
  );
}

/** Honest awaiting / empty placeholder for a response-specific panel. */
function Awaiting({ text, className }: { text: string; className?: string }) {
  return (
    <p
      className={cn(
        "px-3.5 py-5 text-center text-[0.7rem] text-[var(--tessera-text-muted)]",
        className,
      )}
    >
      {text}
    </p>
  );
}

function PanelHead({
  title,
  cta,
  href,
}: {
  title: string;
  cta?: string;
  href?: string;
}) {
  const cls = "inline-flex items-center gap-0.5 text-[0.64rem] text-[#f4c76a] hover:text-white";
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-[0.74rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
      {cta && href ? (
        <Link href={href} className={cls}>
          {cta} <ChevronRight className="h-3 w-3" />
        </Link>
      ) : null}
    </div>
  );
}

function Quality({ q }: { q: NonNullable<ChatDebug["quality"]> }) {
  return (
    <div className="p-3.5">
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h3 className="text-[0.74rem] font-semibold text-[var(--tessera-text)]">{q.title}</h3>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            BADGE_TONE[q.badge_tone] ?? BADGE_TONE.good,
          )}
        >
          {q.badge}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2.5 min-[1480px]:grid-cols-4">
        {q.rows.map((r) => (
          <div
            key={r.label}
            className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{r.label}</p>
            <p className="mt-1 tabular-nums">
              <span className={cn("text-[1.05rem] font-semibold", SCORE_TONE[r.tone])}>
                {r.value}
              </span>
              <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{r.scale}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function SourcesPanel({ s }: { s: NonNullable<ChatDebug["sources"]> }) {
  const agentId = useAgentId();
  return (
    <div className="p-3.5">
      <PanelHead title={s.title} cta={s.cta} href={agentPath(agentId, "connaissances")} />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {s.rows.map((r, i) => (
          <li key={`${r.label}-${i}`} className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-[var(--tessera-text)]">{r.label}</span>
            <span className="shrink-0 text-[0.64rem] text-[var(--tessera-text-muted)]">
              {r.scope}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ToolsPanel({ tl }: { tl: NonNullable<Data["tools"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={tl.title} />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {tl.rows.map((r) => (
          <li key={r.name} className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate font-mono text-[0.68rem] text-[var(--tessera-text)]">
              {r.name}
            </span>
            <span className="flex shrink-0 items-center gap-3">
              <span className={cn("text-[0.66rem] font-medium", STATUS_TONE[r.tone])}>
                {r.status}
              </span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{r.latency}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GuardrailsPanel({ g }: { g: NonNullable<Data["guardrails"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={g.title} />
      <ul className="flex flex-col gap-2">
        {g.rows.map((r) => (
          <li key={r.name} className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2 text-[0.72rem]">
              <span className="font-medium text-[var(--tessera-text)]">{r.name}</span>
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
                  BADGE_TONE[r.tone] ?? BADGE_TONE.warn,
                )}
              >
                {r.status}
              </span>
            </div>
            <p className="text-[0.64rem] text-[var(--tessera-text-muted)]">{r.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** "Évaluation automatique" — latest real eval-run metrics (not per-turn). Honest
 *  empty value ("—") when a metric has no recorded score; links to Évaluations. */
function EvaluationPanel({ ev }: { ev: Data["evaluation"] }) {
  const agentId = useAgentId();
  if (!ev) return null;
  return (
    <div className="p-3.5">
      <PanelHead title={ev.title} cta={ev.cta} href={agentPath(agentId, "evaluations")} />
      <p className="mb-2 text-[0.62rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {ev.note}
      </p>
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {ev.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-[var(--tessera-text)]">{r.label}</span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {r.value ?? "—"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Debug tab — the live turn's full internals, real data only ─────────────

/** A titled, collapsible card grouping one debug surface. Collapsed by default
 *  so the eight surfaces stay a compact stack of headers — the operator expands
 *  only the one they need rather than scrolling a very long panel. */
function DebugSection({
  title,
  children,
  defaultOpen,
}: {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)]"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-2.5 py-1.5 text-[0.68rem] font-semibold text-[var(--tessera-text)] [&::-webkit-details-marker]:hidden">
        <span>{title}</span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)] transition-transform group-open:rotate-90" />
      </summary>
      <div className="border-t border-[var(--tessera-border)] px-2.5 py-2 text-[0.7rem]">
        {children}
      </div>
    </details>
  );
}

/** A compact label / value row. */
function DebugKV({ k, v, mono }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5">
      <span className="shrink-0 text-[0.64rem] text-[var(--tessera-text-muted)]">{k}</span>
      <span
        className={cn(
          "min-w-0 truncate text-right text-[var(--tessera-text)]",
          mono && "font-mono text-[0.66rem]",
        )}
      >
        {v}
      </span>
    </div>
  );
}

/** Render a 0..1 score as a percentage with a small bar; "—" when absent. */
function ScoreRow({ label, score }: { label: string; score: number | null }) {
  const pct = score === null ? null : Math.round(score * 100);
  const tone = pct === null ? "warn" : pct >= 80 ? "good" : pct >= 50 ? "warn" : "crit";
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="w-20 shrink-0 text-[0.64rem] text-[var(--tessera-text-muted)]">{label}</span>
      <div className="h-[4px] flex-1 overflow-hidden rounded-full bg-[var(--tessera-border)]">
        {pct !== null ? (
          <div
            className={cn("h-full rounded-full", SPAN_BAR_TONE[tone] ?? SPAN_BAR_TONE.ok)}
            style={{ width: `${pct}%` }}
          />
        ) : null}
      </div>
      <span className={cn("w-8 shrink-0 text-right tabular-nums text-[0.66rem]", SCORE_TONE[tone])}>
        {pct === null ? "—" : `${pct}%`}
      </span>
    </div>
  );
}

const ROLE_TONE: Record<string, string> = {
  system: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  user: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  assistant: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  tool: "border-amber-500/30 bg-amber-500/15 text-amber-300",
};

/** Small inline pill used for plans, guard categories, language codes. */
function Chip({ children, tone }: { children: ReactNode; tone?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-1.5 py-0.5 text-[0.6rem] font-medium",
        tone ??
          "border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--tessera-text)]",
      )}
    >
      {children}
    </span>
  );
}

/** The Debug panel: all eight live introspection surfaces. Honest awaiting
 *  state before a turn; each surface shows only real per-turn data. */
function DebugPanel({ debug, t }: { debug: ChatDebug | null; t: T }) {
  if (!debug) return <Awaiting text={t("debugAwaiting")} />;
  const { prompt, memory, routing, usage, reviewer, language, draft, config } = debug;
  return (
    <div className="flex flex-col gap-2.5 p-3.5">
      {/* #3 Routing & plan */}
      {routing ? (
        <DebugSection title={routing.title} defaultOpen>
          <DebugKV k="Agent" v={routing.agent_id} mono />
          <DebugKV
            k="Décision"
            v={
              <Chip tone={routing.handoff ? ROLE_TONE.tool : ROLE_TONE.assistant}>
                {routing.handoff ? `handoff ← ${routing.from_agent ?? "?"}` : "stay"}
              </Chip>
            }
          />
          <DebugKV k="Raison" v={routing.reason} />
          {routing.plan.length > 0 ? (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {routing.plan.map((w) => (
                <Chip key={w}>{w}</Chip>
              ))}
            </div>
          ) : (
            <p className="mt-1 text-[0.64rem] text-[var(--tessera-text-muted)]">Plan vide.</p>
          )}
          {routing.plan_rationale ? (
            <p className="mt-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
              {routing.plan_rationale}
            </p>
          ) : null}
        </DebugSection>
      ) : null}

      {/* #1 Exact LLM prompt */}
      {prompt ? (
        <DebugSection title={prompt.title}>
          <p className="mb-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
            {prompt.message_count} messages · {prompt.char_count.toLocaleString("fr-FR")} caractères
          </p>
          <div className="flex flex-col gap-1.5">
            {prompt.messages.map((m, i) => (
              <details
                key={`${m.role}-${i}`}
                className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
              >
                <summary className="flex cursor-pointer items-center gap-2 px-2 py-1 text-[0.64rem]">
                  <Chip tone={ROLE_TONE[m.role] ?? undefined}>{m.role}</Chip>
                  <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
                    {m.content.slice(0, 80)}
                  </span>
                </summary>
                <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words border-t border-[var(--tessera-border)] px-2 py-1.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text)]">
                  {m.content}
                </pre>
              </details>
            ))}
          </div>
        </DebugSection>
      ) : null}

      {/* #2 Injected memory context */}
      {memory ? (
        <DebugSection title={memory.title}>
          <DebugKV k="Backend" v={memory.backend} mono />
          <DebugKV k="Tours verbatim" v={memory.recent_verbatim} />
          <DebugKV k="Résumé" v={memory.summary ? memory.summary : "—"} />
          {memory.entities.length > 0 ? (
            <div className="mt-1.5">
              <p className="mb-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
                Entités préservées
              </p>
              <div className="flex flex-wrap gap-1">
                {memory.entities.map((e) => (
                  <Chip key={e}>{e}</Chip>
                ))}
              </div>
            </div>
          ) : null}
          {memory.long_term.length > 0 ? (
            <ul className="mt-1.5 flex flex-col gap-1">
              {memory.long_term.map((x) => (
                <li key={x} className="text-[0.64rem] text-[var(--tessera-text-muted)]">
                  • {x}
                </li>
              ))}
            </ul>
          ) : null}
        </DebugSection>
      ) : null}

      {/* #5 Reviewer sub-scores */}
      {reviewer ? (
        <DebugSection title={reviewer.title}>
          <ScoreRow label="Confiance" score={reviewer.confidence} />
          <ScoreRow label="Ancrage" score={reviewer.grounding} />
          <ScoreRow label="Couverture" score={reviewer.coverage} />
          <ScoreRow label="Garde-fous" score={reviewer.guard} />
          {typeof reviewer.threshold === "number" ? (
            // ADR 0033 — the escalation bar this turn was judged against.
            <DebugKV k="Seuil d'escalade" v={reviewer.threshold.toFixed(2)} mono />
          ) : null}
          <div className="mt-1.5">
            <DebugKV
              k="Escalade"
              v={
                <Chip tone={reviewer.needs_escalation ? ROLE_TONE.tool : ROLE_TONE.assistant}>
                  {reviewer.needs_escalation ? "requise" : "non"}
                </Chip>
              }
            />
            {reviewer.reason ? (
              <p className="mt-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
                {reviewer.reason}
              </p>
            ) : null}
          </div>
        </DebugSection>
      ) : null}

      {/* #4 Tokens / latency / cost */}
      {usage ? (
        <DebugSection title={usage.title}>
          <DebugKV k="Modèle" v={`${usage.model} · ${usage.provider}`} mono />
          <DebugKV
            k="Tokens"
            v={`${usage.input_tokens} entrée · ${usage.output_tokens} sortie · ${usage.total_tokens} total`}
          />
          <DebugKV k="Latence" v={fmtMs(usage.latency_ms)} />
          <DebugKV k="Coût estimé" v={`${usage.estimated_cost_eur.toFixed(6)} €`} />
          {usage.sampling && Object.keys(usage.sampling).length > 0 ? (
            // ADR 0031 — the sampling that actually served this turn (only the
            // SET parameters; an absent one means the backend default served).
            <DebugKV
              k="Sampling"
              v={Object.entries(usage.sampling)
                .map(([key, value]) => `${key}=${value}`)
                .join(" · ")}
              mono
            />
          ) : null}
          {usage.style && Object.keys(usage.style).length > 0 ? (
            // ADR 0032 — the behaviour style directives and hard cap that
            // served this turn (seam-resolved, injected into the prompt).
            <DebugKV
              k="Style"
              v={[
                ...Object.entries(usage.style).map(([key, value]) => `${key}=${value}`),
                ...(typeof usage.max_output_tokens === "number"
                  ? [`max_output_tokens=${usage.max_output_tokens}`]
                  : []),
              ].join(" · ")}
              mono
            />
          ) : null}
        </DebugSection>
      ) : null}

      {/* #6 Detected language */}
      {language ? (
        <DebugSection title={language.title}>
          <DebugKV
            k="Langue"
            v={
              <span className="inline-flex items-center gap-1.5">
                <Chip tone={ROLE_TONE.user}>{language.detected.toUpperCase()}</Chip>
                {language.pinned ? (
                  <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">(imposée)</span>
                ) : null}
              </span>
            }
          />
          <DebugKV
            k="Confiance"
            v={language.confidence === null ? "—" : `${Math.round(language.confidence * 100)}%`}
          />
        </DebugSection>
      ) : null}

      {/* #7 Draft vs final */}
      {draft ? (
        <DebugSection title={draft.title}>
          <DebugKV
            k="État"
            v={
              <Chip tone={draft.changed ? ROLE_TONE.tool : ROLE_TONE.assistant}>
                {draft.changed ? "reformulé" : "identique"}
              </Chip>
            }
          />
          <DebugKV k={draft.draft_label} v={`${draft.draft_chars} car.`} />
          <DebugKV k="Réponse finale" v={`${draft.final_chars} car.`} />
          {draft.draft ? (
            <details className="mt-1.5 rounded border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
              <summary className="cursor-pointer px-2 py-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
                Voir : {draft.draft_label}
              </summary>
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words border-t border-[var(--tessera-border)] px-2 py-1.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text)]">
                {draft.draft}
              </pre>
            </details>
          ) : null}
        </DebugSection>
      ) : null}

      {/* #8 Effective config */}
      {config ? (
        <DebugSection title={config.title}>
          <DebugKV k="Modèle" v={`${config.model} (${config.model_source})`} mono />
          <DebugKV
            k="Prompt override"
            v={
              <Chip tone={config.system_prompt_override ? ROLE_TONE.tool : undefined}>
                {config.system_prompt_override ? "actif" : "défaut"}
              </Chip>
            }
          />
          <div className="mt-1 flex items-center justify-between gap-2">
            <span className="text-[0.64rem] text-[var(--tessera-text-muted)]">
              Garde-fous désactivés
            </span>
            {config.guard_overrides.length > 0 ? (
              <div className="flex flex-wrap justify-end gap-1">
                {config.guard_overrides.map((g) => (
                  <Chip key={g} tone={ROLE_TONE.tool}>
                    {g}
                  </Chip>
                ))}
              </div>
            ) : (
              <span className="text-[0.66rem] text-[var(--tessera-text)]">aucun</span>
            )}
          </div>
        </DebugSection>
      ) : null}
    </div>
  );
}
