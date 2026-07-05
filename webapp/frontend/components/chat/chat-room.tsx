"use client";

import {
  AlertCircle,
  ArrowDown,
  Clock,
  CreditCard,
  Landmark,
  Lock,
  type LucideIcon,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserPlus,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { RecouvrementMark } from "@/components/recouvrement/recouvrement-logo";
import type { Locale } from "@/i18n/routing";
import { streamChat } from "@/lib/api/sse";
import { cn } from "@/lib/cn";
import { useChatStore } from "@/lib/stores/chat-store";
import { ChatComposer, type ChatComposerHandle } from "./chat-composer";
import { MessageBubble } from "./message-bubble";
import { TypingDots } from "./typing-dots";

/**
 * Stable per-browser long-term-memory identity (ADR 0007). Generated once and
 * persisted in localStorage so the agent can recall durable facts across
 * separate conversations. Replaced by a real customer id once auth exists.
 */
export const SUBJECT_ID_KEY = "tessera.subjectId";

function getSubjectId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  let id = window.localStorage.getItem(SUBJECT_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(SUBJECT_ID_KEY, id);
  }
  return id;
}

type Suggestion = { text: string; Icon: LucideIcon };

const SUGGESTED_PROMPTS: Record<string, Suggestion[]> = {
  fr: [
    { text: "Ma carte bancaire vient d'être volée — que faire en urgence ?", Icon: CreditCard },
    // Onboarding — "KYC" matches the supervisor's intent regex (language-agnostic),
    // so this routes the turn to the onboarding agent inside the single assistant.
    {
      text: "Je veux ouvrir un compte : quelles pièces justificatives pour le KYC ?",
      Icon: UserPlus,
    },
    { text: "Quels sont mes droits RGPD sur mes données bancaires ?", Icon: ShieldCheck },
    { text: "Expliquez-moi la garantie des dépôts en France.", Icon: Landmark },
    { text: "Quels délais pour un virement SEPA international ?", Icon: Clock },
    { text: "Comment contester un prélèvement non autorisé ?", Icon: AlertCircle },
    { text: "Quels sont mes droits en cas de fraude sur mon compte ?", Icon: ShieldAlert },
  ],
  de: [
    { text: "Meine Karte wurde gestohlen — was muss ich sofort tun?", Icon: CreditCard },
    { text: "Ich möchte ein Konto eröffnen — welche KYC-Unterlagen brauche ich?", Icon: UserPlus },
    { text: "Welche DSGVO-Rechte habe ich bezüglich meiner Bankdaten?", Icon: ShieldCheck },
    { text: "Wie funktioniert die Einlagensicherung in Deutschland?", Icon: Landmark },
    { text: "Wie lange dauert eine internationale SEPA-Überweisung?", Icon: Clock },
    { text: "Wie kann ich eine unberechtigte Abbuchung anfechten?", Icon: AlertCircle },
    { text: "Was sind meine Rechte bei Kontobetrug?", Icon: ShieldAlert },
  ],
  en: [
    { text: "My card was just stolen — what should I do urgently?", Icon: CreditCard },
    { text: "I'd like to open an account — what KYC documents are required?", Icon: UserPlus },
    { text: "What are my GDPR rights regarding my banking data?", Icon: ShieldCheck },
    { text: "Explain how deposit guarantees work in the EU.", Icon: Landmark },
    { text: "What are the timelines for an international SEPA transfer?", Icon: Clock },
    { text: "How do I dispute an unauthorized charge?", Icon: AlertCircle },
    { text: "What are my rights if I'm a victim of account fraud?", Icon: ShieldAlert },
  ],
};

export interface ExternalChatPrompt {
  id: string;
  prompt: string;
}

interface ChatRoomProps {
  externalPrompt?: ExternalChatPrompt | null;
  onExternalPromptHandled?: (id: string) => void;
  /**
   * Originating surface hint forwarded to the BFF (ADR 0010 Phase C). The
   * recouvrement business console passes `"recouvrement"` so a verified
   * collections/operator session is routed to recouvrement on the dedicated-ui
   * surface. Omitted (default) for the customer widget — that path is unchanged.
   */
  surface?: "recouvrement";
}

export function ChatRoom({ externalPrompt, onExternalPromptHandled, surface }: ChatRoomProps = {}) {
  const t = useTranslations("chat");
  const locale = useLocale() as Locale;
  const isRecouvrement = surface === "recouvrement";
  const assistantName = isRecouvrement ? t("recouvrementAssistantSaid") : t("assistantSaid");
  const emptyDescription = isRecouvrement ? t("recouvrementDescription") : t("description");
  const disclosure = isRecouvrement ? t("recouvrementDisclosure") : t("disclosure");
  const streamingPlaceholder = isRecouvrement
    ? t("recouvrementStreamingPlaceholder")
    : t("streamingPlaceholder");
  const composerRef = useRef<ChatComposerHandle>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const scrollAnchorRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const handledExternalPromptRef = useRef<string | null>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const {
    messages,
    isStreaming,
    appendUser,
    start,
    startAssistant,
    appendToken,
    finalizeAssistant,
    setError,
    setStreaming,
    truncateFromMessage,
    removeLastExchange,
    reset,
  } = useChatStore();

  // Scroll-to-bottom: watch the full messages reference so this fires on every
  // token append (appendToken creates a new array ref each time). During streaming
  // we use an instant scrollTop assignment — smooth scroll fights a moving target
  // and produces the visible "jitter" the user sees on each new line.
  // biome-ignore lint/correctness/useExhaustiveDependencies: must re-run on every messages change to follow streaming output
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (isNearBottom || isStreaming) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, isStreaming]);

  // Track scroll position for FAB.
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 120);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Cleanup on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  // Press "/" anywhere (outside inputs) to focus the composer.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (
        e.key === "/" &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.altKey &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault();
        composerRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const scrollToBottom = useCallback(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      // Snapshot history BEFORE appendUser modifies the store, and read
      // conversationId directly from the store so truncateFromMessage's
      // synchronous reset is always visible here.
      const snap = useChatStore.getState();
      const history = snap.messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));
      const currentConvId = snap.conversationId;

      appendUser(text);
      const controller = new AbortController();
      abortRef.current = controller;

      // Ensures an assistant bubble always exists before finalizeAssistant runs,
      // even on the non-streaming path (injection block, escalation, backend error).
      function ensureAssistantBubble(id: string) {
        startAssistant(id);
      }

      function showErrorInConversation(rawError: string) {
        const id = crypto.randomUUID();
        ensureAssistantBubble(id);
        finalizeAssistant({
          id,
          content: t("errorFallback"),
          citations: [],
          needsEscalation: false,
          confidence: null,
        });
        setError(rawError);
        toast.error(rawError);
      }

      let errorHandled = false;

      try {
        let assistantId: string | null = null;
        let bubbleCreated = false;
        // Batch tokens within a single animation frame so the DOM updates at most
        // once per frame (≤60/s) instead of once per raw SSE token. This eliminates
        // the micro-jitter caused by sub-frame height changes as each token lands.
        // startAssistant is also deferred to flushTokens so the bubble is created
        // and populated in the same render cycle — no empty-bubble flash between
        // the TypingDots disappearing and the first tokens appearing.
        let tokenBuffer = "";
        let rafId: number | null = null;
        function flushTokens() {
          if (assistantId !== null && tokenBuffer.length > 0) {
            if (!bubbleCreated) {
              ensureAssistantBubble(assistantId);
              bubbleCreated = true;
            }
            appendToken(tokenBuffer);
            tokenBuffer = "";
          }
          rafId = null;
        }

        await streamChat(
          {
            message: text,
            language: locale,
            conversation_id: currentConvId ?? undefined,
            subject_id: getSubjectId(),
            history: history.length > 0 ? history : undefined,
          },
          {
            signal: controller.signal,
            surface,
            onStart: ({ conversation_id, turn_id }) => start(conversation_id, turn_id),
            onToken: (token) => {
              if (assistantId === null) assistantId = crypto.randomUUID();
              tokenBuffer += token;
              if (rafId === null) {
                rafId = requestAnimationFrame(flushTokens);
              }
            },
            onEnd: (envelope) => {
              // Flush any tokens buffered in the pending frame before finalizing.
              if (rafId !== null) {
                cancelAnimationFrame(rafId);
                flushTokens();
              }
              // For non-streaming responses (injection block, escalation) no
              // tokens are emitted so no assistant bubble was created yet.
              if (assistantId === null) {
                ensureAssistantBubble(envelope.turn_id);
              }
              finalizeAssistant({
                id: envelope.turn_id,
                content: envelope.final_response,
                citations: envelope.citations,
                needsEscalation: envelope.needs_escalation,
                confidence: envelope.confidence,
              });
            },
            onError: (message) => {
              if (rafId !== null) {
                cancelAnimationFrame(rafId);
                rafId = null;
              }
              if (!errorHandled) {
                errorHandled = true;
                showErrorInConversation(message);
              }
            },
          },
        );
      } catch (err) {
        if (controller.signal.aborted) {
          // User hit stop: leave the partial reply in place but exit the
          // streaming state so the UI is interactive again.
          setStreaming(false);
          return;
        }
        if (!errorHandled) {
          errorHandled = true;
          showErrorInConversation(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        // @microsoft/fetch-event-source *resolves* (does not reject) when the
        // external signal aborts, so the catch above never runs on stop. Reset
        // the streaming flag here so the composer becomes interactive again and
        // the partial reply stays in place.
        if (controller.signal.aborted) setStreaming(false);
      }
    },
    [
      appendUser,
      appendToken,
      finalizeAssistant,
      locale,
      setError,
      setStreaming,
      start,
      startAssistant,
      surface,
      t,
    ],
  );

  const handleInlineEdit = useCallback(
    (messageId: string, newContent: string) => {
      if (isStreaming) return;
      truncateFromMessage(messageId);
      void sendMessage(newContent);
    },
    [isStreaming, truncateFromMessage, sendMessage],
  );

  const handleRegenerate = useCallback(() => {
    if (isStreaming) return;
    const lastAsstIdx = messages.findLastIndex((m) => m.role === "assistant");
    if (lastAsstIdx === -1) return;
    const lastUserMsg = messages
      .slice(0, lastAsstIdx)
      .reverse()
      .find((m) => m.role === "user");
    if (!lastUserMsg) return;
    removeLastExchange();
    void sendMessage(lastUserMsg.content);
  }, [isStreaming, messages, removeLastExchange, sendMessage]);

  useEffect(() => {
    if (!externalPrompt || isStreaming || abortRef.current !== null || handledExternalPromptRef.current === externalPrompt.id) {
      return;
    }
    handledExternalPromptRef.current = externalPrompt.id;
    onExternalPromptHandled?.(externalPrompt.id);
    void sendMessage(externalPrompt.prompt);
  }, [externalPrompt, isStreaming, onExternalPromptHandled, sendMessage]);

  const suggestions = SUGGESTED_PROMPTS[locale] ?? SUGGESTED_PROMPTS.en ?? [];

  return (
    <div className="relative flex min-h-0 flex-1 flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)]/55 backdrop-blur-xl shadow-sm">
      {/* Message list — fix 1: flex flex-col so empty wrapper can use flex-1 */}
      <div
        ref={scrollContainerRef}
        role="log"
        aria-live="polite"
        aria-label={t("title")}
        className="relative flex flex-1 flex-col overflow-y-auto [overflow-anchor:none] [mask-image:linear-gradient(180deg,transparent_0%,black_24px,black_calc(100%-24px),transparent_100%)] bg-[radial-gradient(ellipse_70%_45%_at_50%_15%,oklch(1_0.004_240/0.05),transparent)] px-4 py-6 sm:px-8 dark:bg-[radial-gradient(ellipse_70%_45%_at_50%_15%,oklch(1_0.004_240/0.08),transparent)]"
      >
        {/* fix 2: "Nouvelle conversation" as absolute overlay, only when there are messages */}
        {messages.length > 0 && (
          <button
            type="button"
            onClick={() => {
              abortRef.current?.abort();
              reset();
              composerRef.current?.focus();
            }}
            className="absolute right-4 top-3 z-10 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
          >
            <RotateCcw className="h-3 w-3" />
            {t("clear")}
          </button>
        )}

        {messages.length === 0 ? (
          /* fix 1: flex-1 + justify-center to vertically center the empty state */
          <div className="flex flex-1 items-center justify-center">
            <EmptyWithSuggestions
              description={emptyDescription}
              icon={
                isRecouvrement ? (
                  <RecouvrementMark className="h-[3.4rem] translate-x-[3.5px] brightness-80 contrast-125 saturate-90 drop-shadow-[0_5px_12px_rgba(0,0,0,0.32)]" />
                ) : undefined
              }
              iconClassName={
                isRecouvrement
                  ? "h-16 w-16 rounded-2xl bg-gold-500/65 shadow-[0_0_28px_-14px_oklch(0.8_0.066_85/0.4)] ring-1 ring-gold-400/15 dark:bg-gold-500/65 dark:shadow-[0_0_28px_-14px_oklch(0.8_0.066_85/0.4)] dark:ring-gold-400/15"
                  : undefined
              }
              suggestionsLabel={t("startWith")}
              suggestions={suggestions}
              onSelect={(text) => {
                // Send straight away — do NOT prefill the composer: sendMessage
                // already takes the text, and setValue would leave the prompt
                // stranded in the input box (only the composer's own submit clears it).
                void sendMessage(text);
              }}
            />
          </div>
        ) : (
          /* pt-8 so messages don't slide under the absolute button */
          <div className="mx-auto w-full flex max-w-3xl flex-col pt-8 pb-10 sm:pb-12">
            {messages.map((m, idx) => {
              const prev = messages[idx - 1];
              const isGrouped =
                !!prev && prev.role === m.role && m.createdAt - prev.createdAt < 120_000;
              const isLastUserMsg =
                m.role === "user" &&
                !messages.slice(idx + 1).some((later) => later.role === "user");
              return (
                <MessageBubble
                  key={m.id}
                  message={m}
                  isGrouped={isGrouped}
                  isFirst={idx === 0}
                  isStreaming={isStreaming}
                  isLastUserMessage={isLastUserMsg}
                  assistantName={assistantName}
                  assistantSurface={isRecouvrement ? "recouvrement" : undefined}
                  onEdit={m.role === "user" ? handleInlineEdit : undefined}
                />
              );
            })}
            {/* Typing indicator — borderless to match assistant messages */}
            {isStreaming && messages[messages.length - 1]?.role === "user" && (
              <div className="mt-5 flex items-start gap-3 animate-in fade-in-0 slide-in-from-bottom-2 duration-200">
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-navy-800 to-navy-950 text-gold-400 shadow-[inset_0_1px_1px_oklch(0.8_0.066_85/0.2)] ring-1 ring-gold-500/15 dark:from-gold-500 dark:to-gold-600 dark:text-navy-950 dark:ring-gold-300/25">
                  {isRecouvrement ? (
                    <RecouvrementMark className="h-5 animate-pulse" />
                  ) : (
                    <Sparkles className="h-4 w-4 animate-pulse" />
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[0.7rem] font-medium text-[var(--muted-foreground)]">
                    {assistantName}
                  </span>
                  <TypingDots />
                </div>
              </div>
            )}
            {/* Regenerate button — shown after a completed assistant response */}
            {!isStreaming &&
              messages[messages.length - 1]?.role === "assistant" &&
              messages.length >= 2 && (
                <div className="mt-3 pl-11">
                  <button
                    type="button"
                    onClick={handleRegenerate}
                    className="flex items-center gap-1.5 text-[0.65rem] text-[var(--muted-foreground)]/40 transition-colors hover:text-[var(--muted-foreground)]"
                  >
                    <RefreshCw className="h-3 w-3" />
                    {t("regenerate")}
                  </button>
                </div>
              )}
            <div ref={scrollAnchorRef} aria-hidden />
          </div>
        )}

        {/* Scroll-to-bottom FAB */}
        {showScrollBtn && (
          <button
            type="button"
            onClick={scrollToBottom}
            aria-label={t("scrollToBottom")}
            className="absolute bottom-4 right-4 flex h-8 w-8 items-center justify-center rounded-full border border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)] shadow-md transition-all hover:bg-[var(--muted)] animate-in fade-in-0 zoom-in-90 duration-150"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Composer */}
      <ChatComposer
        ref={composerRef}
        disabled={isStreaming}
        isStreaming={isStreaming}
        onSubmit={sendMessage}
        onAbort={() => abortRef.current?.abort()}
        streamingPlaceholder={streamingPlaceholder}
        disclosure={disclosure}
      />
    </div>
  );
}

interface EmptyWithSuggestionsProps {
  description: string;
  icon?: ReactNode;
  iconClassName?: string;
  suggestionsLabel: string;
  suggestions: Suggestion[];
  onSelect: (text: string) => void;
}

function EmptyWithSuggestions({
  description,
  icon,
  iconClassName,
  suggestionsLabel,
  suggestions,
  onSelect,
}: EmptyWithSuggestionsProps) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 text-center">
      {/* Icon — glow ring + mount animation */}
      <div
        className={cn(
          "animate-in zoom-in-90 flex h-16 w-16 items-center justify-center rounded-2xl bg-navy-900 text-gold-400 shadow-[0_0_28px_-4px_oklch(0.8_0.066_85/0.3)] ring-1 ring-gold-500/20 duration-500 dark:bg-gold-500 dark:text-navy-950 dark:shadow-[0_0_40px_-4px_oklch(0.8_0.066_85/0.55)] dark:ring-gold-400/30",
          iconClassName,
        )}
      >
        {icon ?? <Sparkles className="h-8 w-8" />}
      </div>

      {/* Description + regulatory trust badges — fade in after icon */}
      <div className="animate-in fade-in-0 slide-in-from-bottom-1 [animation-delay:180ms] [animation-fill-mode:both] flex flex-col items-center gap-3 duration-500">
        <p className="text-sm text-[var(--muted-foreground)]">{description}</p>
        <div className="flex flex-wrap justify-center gap-1.5">
          {(["RGPD", "DORA", "BaFin", "CNIL"] as const).map((label) => (
            <span
              key={label}
              className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--muted)]/30 px-2.5 py-0.5 text-[0.65rem] font-medium tracking-wider text-[var(--muted-foreground)]"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-green-500/80" />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Suggested prompts — decorative divider + stagger animation */}
      <div className="w-full space-y-3">
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-[var(--border)]" />
          <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            {suggestionsLabel}
          </p>
          <div className="h-px flex-1 bg-[var(--border)]" />
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {suggestions.map(({ text, Icon }, idx) => (
            <button
              key={text}
              type="button"
              onClick={() => onSelect(text)}
              style={{ animationDelay: `${idx * 60}ms` }}
              className="animate-in fade-in-0 slide-in-from-bottom-2 [animation-fill-mode:both] group relative flex items-start gap-2.5 overflow-hidden rounded-xl border border-white/10 bg-white/5 backdrop-blur-md px-4 py-3 text-left text-sm text-[var(--foreground)] shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-gold-500/40 hover:bg-white/10 hover:shadow-[0_8px_20px_-6px_rgba(185,146,69,0.2)] dark:border-navy-700/50 dark:bg-navy-800/40 dark:hover:border-gold-400/40 dark:hover:bg-navy-700/60"
            >
              {/* spotlight inner glow */}
              <span className="absolute inset-0 z-0 bg-gradient-to-br from-white/10 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100 dark:from-gold-400/5" />
              {/* sliding gold left border */}
              <span className="absolute left-0 top-0 z-10 h-full w-0.5 origin-top scale-y-0 bg-gradient-to-b from-gold-400 to-gold-600 transition-transform duration-300 group-hover:scale-y-100" />
              
              {/* icon container */}
              <div className="relative z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--muted)]/50 backdrop-blur-sm transition-colors duration-300 group-hover:bg-gold-500/20 dark:bg-navy-900/50 dark:group-hover:bg-gold-500/30">
                <Icon className="h-3.5 w-3.5 text-[var(--muted-foreground)] transition-colors duration-300 group-hover:text-gold-600 dark:group-hover:text-gold-300" />
              </div>
              <span className="relative z-10 leading-snug drop-shadow-sm">{text}</span>
            </button>
          ))}
        </div>

        {/* Security assurance row — distinct from badges above and tagline */}
        <div className="mt-4 flex flex-wrap justify-center gap-x-5 gap-y-1.5">
          {[
            { icon: ShieldCheck, label: "Pare-feu multi-référentiel" },
            { icon: ShieldAlert, label: "Escalade conseiller si besoin" },
            { icon: Lock, label: "Journal d'audit horodaté" },
          ].map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="flex items-center gap-1.5 text-[0.62rem] text-[var(--muted-foreground)]/50"
            >
              <Icon className="h-3 w-3" />
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
