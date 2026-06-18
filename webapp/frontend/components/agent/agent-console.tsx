"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  Download,
  History,
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

import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchAgentConsole, fetchConsoleFeedback, saveConsoleFeedback } from "@/lib/api/client";
import type {
  ChatCitation,
  ChatDebug,
  ChatEndEvent,
  AgentConsole as Data,
} from "@/lib/api/schemas";
import { streamChat } from "@/lib/api/sse";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";

import { AgentCrossLinks } from "./agent-cross-links";

type Rating = "up" | "down";

type T = ReturnType<typeof useTranslations<"agentConsole">>;

const FIELD_ICONS: LucideIcon[] = [Cpu, Tag, Database, Shield, Activity];

const CHIP_TONE: Record<string, string> = {
  info: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  ghost: "border-[var(--tessera-border)] bg-transparent text-[var(--tessera-text-muted)]",
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
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
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

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="console" />
      <StatusBar
        data={data}
        sessionId={conversationId}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        onReplay={() => temporal.changeMode("replay")}
        onNewSession={resetSession}
      />

      <div className="grid gap-3 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-6">
          <TemporalRail
            mode={temporal.mode}
            liveStatus={t("realtime")}
            timeline={railTimeline.data}
            selectedAt={temporal.selectedAt}
            onSelectedAtChange={temporal.setSelectedAt}
            periodKey={temporal.periodKey}
            onPeriodChange={temporal.setPeriodKey}
            onModeChange={temporal.changeMode}
          />
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

        <div className="flex min-w-0 flex-col gap-3 xl:col-span-3">
          <KpiRow data={data} />
          <Inspector data={data} debug={liveDebug} sessionId={conversationId} t={t} />
        </div>

        {/* XT-01 — execution-trace rail, a persistent 3rd column (rails registry,
            normative 05), no longer a tab inside the inspector. */}
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-3">
          <TraceColumn data={data} debug={liveDebug} />
        </div>
      </div>
    </div>
  );
}

// ── status sub-bar ───────────────────────────────────────────────────────────

const PERIOD_LABEL: Record<string, string> = { h24: "24h", d7: "7j", d30: "30j" };

function StatusBar({
  data,
  sessionId,
  periodKey,
  onPeriodChange,
  onReplay,
  onNewSession,
}: {
  data: Data;
  sessionId: string | null;
  periodKey: string;
  onPeriodChange: (key: string) => void;
  onReplay: () => void;
  onNewSession: () => void;
}) {
  const s = data.status;
  const a = data.actions;
  if (!s || !a) return null;
  const visibleSession = sessionId ? `sess_${sessionId.slice(0, 8)}` : s.session_id;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-1.5 text-[0.72rem]">
        <span className="inline-flex items-center gap-1.5 font-medium text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Session active
        </span>
        <span className="text-[var(--tessera-text-muted)]">
          ID: <span className="tabular-nums text-[var(--tessera-text)]">{visibleSession}</span>
        </span>
        {s.fields.map((f, i) => {
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
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          onClick={onReplay}
          className="flex h-8 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.72rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <History className="h-3.5 w-3.5" /> {a.replay}
        </button>
        <div className="relative flex h-8 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[0.72rem] text-[var(--tessera-text-muted)]">
          <select
            aria-label="Fenetre temporelle"
            value={periodKey}
            onChange={(event) => onPeriodChange(event.target.value)}
            className="h-full cursor-pointer appearance-none bg-transparent pr-7 pl-2.5 text-[var(--tessera-text)] outline-none"
          >
            {Object.entries(PERIOD_LABEL).map(([key, label]) => (
              <option key={key} value={key} className="bg-[var(--tessera-surface)]">
                {label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2 h-3.5 w-3.5" />
        </div>
        <button
          type="button"
          onClick={onNewSession}
          className="flex h-8 items-center gap-1.5 rounded-md border border-[#d98b1f]/55 bg-[linear-gradient(180deg,#3a2a14,#21180d)] px-3 text-[0.72rem] font-medium text-[#f4c76a] hover:border-[#f4c76a]/65"
        >
          <Plus className="h-3.5 w-3.5" /> {a.new_session}
        </button>
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
        {hasLiveMessages
          ? messages.map((message) => {
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
          : (data.transcript ?? []).map((m) =>
              m.role === "user" ? (
                <UserMsg key={`u-${m.time}`} time={m.time} text={m.text ?? ""} />
              ) : (
                <AssistantMsg key={`a-${m.time}`} m={m} />
              ),
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

function AssistantMsg({ m }: { m: NonNullable<Data["transcript"]>[number] }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="inline-flex items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
          <ShieldCheck className="h-3 w-3" />
        </span>
        <span className="font-medium text-[var(--tessera-text)]">Assistant</span> {m.time}
        {m.latency ? <span>- {m.latency}</span> : null}
      </span>
      <div className="rounded-xl rounded-tl-sm border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3.5 py-3 text-[0.78rem] leading-relaxed text-[var(--tessera-text)]">
        {m.intro ? <p>{m.intro}</p> : null}
        {m.points ? (
          <ol className="mt-2 flex list-decimal flex-col gap-1.5 pl-4 marker:text-[var(--tessera-text-muted)]">
            {m.points.map((p) => (
              <li key={p.ref}>
                <span className="font-medium text-[#e0a23a]">
                  {p.title} ({p.ref})
                </span>{" "}
                : {p.body}
              </li>
            ))}
          </ol>
        ) : null}
        {m.closing ? <p className="mt-2">{m.closing}</p> : null}

        {m.chips ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {m.chips.map((c) => (
              <span
                key={c.label}
                className={cn(
                  "rounded-md border px-2 py-1 text-[0.64rem]",
                  CHIP_TONE[c.kind] ?? CHIP_TONE.info,
                )}
              >
                {c.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>
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

// ── XT-01 — persistent execution-trace column (normative 05) ────────────────

/** The XT-01 execution trace as a persistent 3rd column (was an inspector tab).
 *  Reuses the same real per-turn debug trace streamed on the SSE envelope; renders
 *  an honest empty state before the operator runs a turn. */
function TraceColumn({ data, debug }: { data: Data; debug: ChatDebug | null }) {
  const trace = debug?.trace ?? data.trace;
  return (
    <section className="flex min-w-0 flex-1 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="flex items-center gap-2 border-b border-[var(--tessera-border)] px-3.5 py-2.5">
        <Activity className="h-4 w-4 text-[#e0a23a]" />
        <span className="text-[0.72rem] font-medium text-[#e0a23a]">XT-01 · Trace d&apos;exécution</span>
      </div>
      {trace ? (
        <TracePanel tr={trace} />
      ) : (
        <p className="px-3.5 py-6 text-center text-[0.72rem] text-[var(--tessera-text-muted)]">
          La trace d&apos;exécution apparaîtra ici après un tour.
        </p>
      )}
    </section>
  );
}

// ── right: KPIs + inspector ────────────────────────────────────────────────

function KpiRow({ data }: { data: Data }) {
  const a = data.actions;
  return (
    <div className="flex items-stretch gap-2.5">
      {(data.kpis ?? []).map((k) => (
        <div
          key={k.key}
          className="flex flex-1 flex-col justify-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2"
        >
          <p className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">{k.label}</p>
          <p className="mt-0.5 text-[1.1rem] font-semibold tabular-nums text-emerald-300">
            {k.value}
          </p>
        </div>
      ))}
      <Link
        href="/prouver/audit-logs"
        className="flex shrink-0 items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 text-[0.7rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        {a?.timeline_incidents}
      </Link>
    </div>
  );
}

function Inspector({
  data,
  debug,
  sessionId,
  t,
}: {
  data: Data;
  debug: ChatDebug | null;
  sessionId: string | null;
  t: T;
}) {
  // "Trace" now lives in its own persistent XT-01 column, not as a tab here.
  const tabs = (data.tabs ?? []).filter((tb) => tb !== "Trace");
  const [active, setActive] = useState(tabs[0] ?? "Contexte");
  const visibleSession = sessionId ? `sess_${sessionId.slice(0, 8)}` : data.footer?.session_id;
  const quality = debug?.quality ?? data.quality;
  const sources = debug?.sources ?? data.sources;
  const tools = debug?.tools ?? data.tools;
  const guardrails = debug?.guardrails ?? data.guardrails;
  return (
    <section className="flex min-w-0 flex-1 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
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

      <div className="flex flex-col divide-y divide-[var(--tessera-border)]">
        {(active === "Contexte" || active === "Trace") && quality && active === "Contexte" ? (
          <Quality q={quality} />
        ) : null}
        {(active === "Contexte" || active === "Sources") && sources ? (
          <SourcesPanel s={sources} />
        ) : null}
        {(active === "Contexte" || active === "Outils") && tools ? <ToolsPanel tl={tools} /> : null}
        {(active === "Contexte" || active === "Garde-fous") && guardrails ? (
          <GuardrailsPanel g={guardrails} />
        ) : null}
      </div>
      <div className="mt-auto border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {t("idSession")}: <span className="tabular-nums">{visibleSession}</span>
      </div>
    </section>
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

function Quality({ q }: { q: NonNullable<Data["quality"]> }) {
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

function SourcesPanel({ s }: { s: NonNullable<Data["sources"]> }) {
  const agentId = useAgentId();
  return (
    <div className="p-3.5">
      <PanelHead title={s.title} cta={s.cta} href={agentPath(agentId, "connaissances")} />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {s.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
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

function TracePanel({ tr }: { tr: NonNullable<Data["trace"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={tr.title} cta={tr.cta} href="/prouver/audit-logs" />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {tr.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span className="inline-flex min-w-0 items-center gap-2 text-[var(--tessera-text)]">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
              <span className="truncate">{r.label}</span>
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {r.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
