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
  Paperclip,
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
import { useLocale } from "next-intl";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchAgentConsole, fetchConsoleFeedback, saveConsoleFeedback } from "@/lib/api/client";
import type {
  ChatCitation,
  ChatDebug,
  ChatEndEvent,
  ChatTrace,
  AgentConsole as Data,
} from "@/lib/api/schemas";
import { streamChat } from "@/lib/api/sse";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";

import { AgentCrossLinks } from "./agent-cross-links";

type Rating = "up" | "down";

type T = ReturnType<typeof useTranslations<"agentConsole">>;

const FIELD_ICONS: LucideIcon[] = [Cpu, Tag, Database, Shield, Activity];

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
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["agent-console"],
    queryFn: ({ signal }) => fetchAgentConsole(signal),
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
          },
          {
            signal: controller.signal,
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
    [conversationId, isStreaming, locale, messages],
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

  const liveSession = conversationId
    ? `sess_${conversationId.slice(0, 8)}`
    : data.context?.session_id;
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="console" />

      {/* Top action row — the Console rail is XT-01 (registre : Console = XT-01 +
          Live); no temporal scrubber here. "Nouvelle session" sits top-right per
          normative 05. */}
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={resetSession}
          className="flex h-8 items-center gap-1.5 rounded-md border border-[#d98b1f]/55 bg-[linear-gradient(180deg,#3a2a14,#21180d)] px-3 text-[0.72rem] font-medium text-[#f4c76a] hover:border-[#f4c76a]/65"
        >
          <Plus className="h-3.5 w-3.5" /> {data.actions?.new_session ?? t("newSession")}
        </button>
      </div>

      <div className="grid gap-3 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-6">
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
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-3">
          <ResponseSummary data={data} debug={liveDebug} sessionId={liveSession} t={t} />
        </div>

        {/* XT-01 — the page's temporal rail, a persistent waterfall column. */}
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-3">
          <TraceColumn debug={liveDebug} sessionId={liveSession} t={t} />
        </div>
      </div>
    </div>
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
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="flex items-start gap-3 border-b border-[var(--tessera-border)] p-3.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#d98b1f]/45 bg-[#d98b1f]/12 text-[#f4c76a]">
          <MessageSquare className="h-4.5 w-4.5" />
        </span>
        <div className="min-w-0">
          <h2 className="text-[0.95rem] font-semibold text-[var(--tessera-text)]">{data.title}</h2>
          <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{data.subtitle}</p>
        </div>
      </div>

      <div className="flex min-h-[430px] flex-col gap-4 p-3.5">
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
    <section className="flex min-w-0 flex-1 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
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
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--tessera-bg)]">
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
  const tabs = data.tabs ?? ["Sources", "Outils", "Garde-fous", "Évaluation"];
  const [active, setActive] = useState(tabs[0] ?? "Sources");
  // Response-specific signals come from the live turn only (no static fallback);
  // config panels (tools/guardrails) fall back to the real loaded policy pre-turn.
  const quality = debug?.quality;
  const sources = debug?.sources;
  const tools = debug?.tools ?? data.tools;
  const guardrails = debug?.guardrails ?? data.guardrails;
  return (
    <section className="flex min-w-0 flex-1 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
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
              {tab}
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
