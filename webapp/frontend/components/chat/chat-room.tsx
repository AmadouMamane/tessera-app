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
    if (
      !externalPrompt ||
      isStreaming ||
      abortRef.current !== null ||
      handledExternalPromptRef.current === externalPrompt.id
    ) {
      return;
    }
    handledExternalPromptRef.current = externalPrompt.id;
    onExternalPromptHandled?.(externalPrompt.id);
    void sendMessage(externalPrompt.prompt);
  }, [externalPrompt, isStreaming, onExternalPromptHandled, sendMessage]);

  const suggestions = SUGGESTED_PROMPTS[locale] ?? SUGGESTED_PROMPTS.en ?? [];

  return (
    <div className="relative flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Message list — fix 1: flex flex-col so empty wrapper can use flex-1 */}
      <div
        ref={scrollContainerRef}
        role="log"
        aria-live="polite"
        aria-label={t("title")}
        className="relative flex flex-1 flex-col overflow-y-auto [overflow-anchor:none] bg-[radial-gradient(ellipse_70%_45%_at_50%_15%,rgba(244,63,94,0.03),transparent)] px-4 py-6 sm:px-8 text-slate-800"
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
            className="absolute right-4 top-3 z-10 flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-800"
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
                  ? "h-16 w-16 rounded-2xl bg-gold-500/65 shadow-[0_0_28px_-14px_oklch(0.8_0.066_85/0.4)] ring-1 ring-gold-400/15 )] "
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
                <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-navy-800 to-navy-950 text-gold-400 shadow-[inset_0_1px_1px_oklch(0.8_0.066_85/0.2)] ring-1 ring-gold-500/15 ">
                  {isRecouvrement ? (
                    <RecouvrementMark className="h-5 animate-pulse" />
                  ) : (
                    <Sparkles className="h-4 w-4 animate-pulse" />
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[0.7rem] font-medium text-slate-500">{assistantName}</span>
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
                    className="flex items-center gap-1.5 text-[0.65rem] text-slate-500/60 transition-colors hover:text-slate-500"
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
            className="absolute bottom-4 right-4 flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 shadow-md transition-all hover:bg-slate-50 animate-in fade-in-0 zoom-in-90 duration-150"
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
          "animate-in zoom-in-90 relative flex h-16 w-16 items-center justify-center rounded-[1.35rem] border border-[#D6B36A]/35 bg-slate-900 shadow-[0_18px_45px_rgba(15,23,42,0.22),0_0_0_8px_rgba(214,179,106,0.06)] duration-500",
          iconClassName,
        )}
      >
        <div className="absolute inset-px rounded-[1.25rem] bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.12),transparent_38%)]" />
        {icon ?? <Sparkles className="relative h-7 w-7 text-[#F1D899]" />}
      </div>

      {/* Description + regulatory trust badges — premium trust layer */}
      <div className="animate-in fade-in-0 slide-in-from-bottom-1 [animation-delay:180ms] [animation-fill-mode:both] relative flex flex-col items-center gap-3 duration-500">
        {/* subtle champagne halo */}
        <div className="pointer-events-none absolute -top-14 h-44 w-44 rounded-full bg-[radial-gradient(circle,rgba(214,179,106,0.18)_0%,rgba(214,179,106,0.08)_36%,transparent_70%)] blur-2xl" />

        <p className="relative text-[0.92rem] font-medium tracking-[-0.01em] text-slate-600">
          {description}
        </p>

        <div className="relative flex flex-wrap justify-center gap-1.5">
          {(["RGPD", "DORA", "BaFin", "CNIL"] as const).map((label) => (
            <span
              key={label}
              className="inline-flex h-6 items-center gap-1.5 rounded-full border border-[#D6B36A]/35 bg-white/70 px-2.5 text-[0.62rem] font-semibold tracking-[0.12em] text-slate-600 shadow-[0_1px_0_rgba(255,255,255,0.8),0_8px_24px_rgba(15,23,42,0.04)] backdrop-blur-sm"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#D6B36A] shadow-[0_0_8px_rgba(214,179,106,0.55)]" />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Suggested prompts — decorative divider + stagger animation */}
      <div className="w-full space-y-3">
        <div className="flex items-center gap-3">
          <div className="h-px flex-1 bg-slate-200" />
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
            {suggestionsLabel}
          </p>
          <div className="h-px flex-1 bg-slate-200" />
        </div>
        <div className="mx-auto grid w-full max-w-[540px] gap-2 sm:grid-cols-2">
          {suggestions.map(({ text, Icon }, idx) => (
            <button
              key={text}
              type="button"
              onClick={() => onSelect(text)}
              style={{ animationDelay: `${idx * 60}ms` }}
              className="animate-in fade-in-0 slide-in-from-bottom-2 [animation-fill-mode:both] group relative overflow-hidden flex min-h-[102px] items-start gap-3 rounded-2xl border border-slate-200/80 bg-white/75 p-4 text-left shadow-[0_1px_0_rgba(255,255,255,0.9),0_12px_32px_rgba(15,23,42,0.045)] backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-[#D6B36A]/45 hover:bg-white hover:shadow-[0_18px_42px_rgba(15,23,42,0.075)]"
            >
              {/* sliding left border */}
              <span className="absolute left-0 top-0 z-10 h-full w-[2px] origin-top scale-y-0 bg-[#EAB308] shadow-[0_0_14px_rgba(234,179,8,0.9)] transition-transform duration-300 group-hover:scale-y-100" />

              {/* icon container */}
              <div className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-200/70 bg-slate-50 text-slate-500 transition-colors group-hover:border-[#D6B36A]/40 group-hover:bg-[#FBF7EA] group-hover:text-slate-800">
                <Icon className="h-4 w-4" />
              </div>
              <span className="relative z-10 leading-relaxed text-[0.82rem] text-slate-700">{text}</span>
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
              className="flex items-center gap-1.5 text-[0.62rem] font-medium text-slate-600"
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
