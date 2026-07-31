"use client";

import { Check, Copy, Pencil, Sparkles, ThumbsDown, ThumbsUp, User2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { RecouvrementMark } from "@/components/recouvrement/recouvrement-logo";
import { submitCustomerFeedback } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { type ChatMessage, useChatStore } from "@/lib/stores/chat-store";
import { CitationList, MessageContent } from "./message-content";

interface MessageBubbleProps {
  message: ChatMessage;
  isGrouped?: boolean;
  isFirst?: boolean;
  isStreaming?: boolean;
  isLastUserMessage?: boolean;
  assistantName?: string;
  assistantSurface?: "recouvrement";
  onEdit?: (id: string, newContent: string) => void;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({
  message,
  isGrouped = false,
  isFirst = false,
  isStreaming = false,
  isLastUserMessage = true,
  assistantName,
  assistantSurface,
  onEdit,
}: MessageBubbleProps) {
  const t = useTranslations("chat");
  const isUser = message.role === "user";
  const assistantLabel = assistantName ?? t("assistantSaid");
  const [copied, setCopied] = useState(false);
  const [userCopied, setUserCopied] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      const el = textareaRef.current;
      el.focus();
      el.selectionStart = el.selectionEnd = el.value.length;
    }
  }, [isEditing]);

  // Auto-resize textarea as draft grows.
  // biome-ignore lint/correctness/useExhaustiveDependencies: must re-run on draft change to recompute height
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  function handleCopy() {
    void navigator.clipboard.writeText(message.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  function handleUserCopy() {
    void navigator.clipboard.writeText(message.content).then(() => {
      setUserCopied(true);
      setTimeout(() => setUserCopied(false), 1500);
    });
  }

  function startEdit() {
    setDraft(message.content);
    setIsEditing(true);
  }

  function confirmEdit() {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== message.content && onEdit) {
      onEdit(message.id, trimmed);
    }
    setIsEditing(false);
  }

  function cancelEdit() {
    setIsEditing(false);
  }

  function handleEditKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      confirmEdit();
    } else if (e.key === "Escape") {
      cancelEdit();
    }
  }

  return (
    <article
      className={cn(
        "group flex w-full gap-3 animate-in fade-in-0 slide-in-from-bottom-2 duration-200",
        !isFirst && (isGrouped ? "mt-1" : "mt-5"),
        isUser ? "flex-row-reverse" : "flex-row",
      )}
      aria-label={isUser ? t("youSaid") : assistantLabel}
    >
      {/* Avatar — invisible spacer when grouped to preserve alignment */}
      {isGrouped ? (
        <div aria-hidden className="mt-0.5 w-8 shrink-0" />
      ) : (
        <div
          aria-hidden
          className={cn(
            "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl",
            isUser
              ? "bg-slate-100 text-slate-500 ring-1 ring-slate-200"
              : "bg-gradient-to-br from-navy-800 to-navy-950 text-gold-400 shadow-[inset_0_1px_1px_oklch(0.8_0.066_85/0.2)] ring-1 ring-gold-500/15 ",
          )}
        >
          {isUser ? (
            <User2 className="h-4 w-4" />
          ) : assistantSurface === "recouvrement" ? (
            <RecouvrementMark className="h-5" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
        </div>
      )}

      {/* Content column — no items-start/end: default stretch makes children always fill the column */}
      <div className="flex w-[80%] flex-col gap-1.5">
        {/* Name + timestamp + badges — hidden for grouped messages */}
        {!isGrouped && (
          <div className={cn("flex items-baseline gap-2", isUser ? "justify-end px-1" : "")}>
            <span className="text-[0.7rem] font-medium text-slate-700">
              {isUser ? t("youSaid") : assistantLabel}
            </span>
            <span className="text-[0.62rem] tabular-nums text-slate-500">
              {formatTime(message.createdAt)}
            </span>
            {!isUser && typeof message.confidence === "number" && (
              <ConfidenceBadge value={message.confidence} />
            )}
          </div>
        )}

        {/* Bubble — w-full keeps width stable during streaming */}
        <div
          className={cn(
            "relative w-full",
            isUser
              ? "px-4 py-2.5 rounded-2xl rounded-br-sm bg-slate-100 text-slate-800 text-sm leading-relaxed"
              : "text-slate-900",
          )}
        >
          {isUser ? (
            isEditing ? (
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={handleEditKey}
                rows={1}
                className="w-full resize-none bg-transparent text-sm leading-relaxed text-slate-800 focus:outline-none"
              />
            ) : (
              <MessageContent speaker="user" content={message.content} />
            )
          ) : (
            <MessageContent speaker="assistant" content={message.content} />
          )}
        </div>

        {/* User actions: copy + edit */}
        {isUser &&
          message.content &&
          (isEditing ? (
            <div className="self-end flex flex-col items-end gap-1">
              {/* Truncation warning — only when this is not the last user message */}
              {!isLastUserMessage && (
                <p className="text-[0.6rem] text-[var(--tessera-fg-warning)] font-medium select-none">
                  ⚠ {t("editWillTruncate")}
                </p>
              )}
              <div className="flex items-center gap-2">
                <p className="text-[0.6rem] text-navy-300/80 select-none">{t("editHint")}</p>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className="flex items-center gap-1 text-[0.62rem] text-slate-600 hover:text-slate-800 transition-colors duration-150"
                >
                  {t("cancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmEdit}
                  disabled={!draft.trim() || draft.trim() === message.content}
                  className="flex items-center gap-1 text-[0.62rem] font-medium text-gold-600 hover:text-gold-700 :text-gold-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150"
                >
                  {t("confirm")}
                </button>
              </div>
            </div>
          ) : (
            /* On desktop: fade-in on hover. On touch (hover:none): always visible. */
            <div className="self-end flex items-center gap-2 opacity-60 group-hover:opacity-100 [@media(hover:none)]:!opacity-100 transition-opacity duration-150">
              <button
                type="button"
                onClick={handleUserCopy}
                aria-label={userCopied ? t("copied") : t("copy")}
                className={cn(
                  "flex items-center gap-1 text-[0.62rem] transition-colors duration-150",
                  "text-slate-600 hover:text-slate-800",
                  userCopied && "!opacity-100 text-[var(--tessera-fg-success)] ",
                )}
              >
                {userCopied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {userCopied ? t("copied") : t("copy")}
              </button>
              {onEdit && (
                <button
                  type="button"
                  onClick={startEdit}
                  disabled={isStreaming}
                  aria-label={t("edit")}
                  className="flex items-center gap-1 text-[0.62rem] text-slate-600 hover:text-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150"
                >
                  <Pencil className="h-3 w-3" />
                  {t("edit")}
                </button>
              )}
            </div>
          ))}

        {/* Assistant copy — self-start prevents stretching to full column width */}
        {!isUser && message.content && (
          <button
            type="button"
            onClick={handleCopy}
            aria-label={copied ? t("copied") : t("copy")}
            className={cn(
              "self-start flex items-center gap-1 px-1 text-[0.62rem] transition-all duration-150",
              "text-slate-600 hover:text-slate-800",
              "opacity-60 group-hover:opacity-100",
              copied && "!opacity-100 text-[var(--tessera-fg-success)] ",
            )}
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? t("copied") : t("copy")}
          </button>
        )}

        {/* Customer CSAT (ADR 0041) — a real 👍/👎 on a COMPLETED reply, customer plane only
            (never the recouvrement operator surface). message.id is the turn_id after finalize. */}
        {!isUser && message.content && !isStreaming && assistantSurface === undefined && (
          <AssistantFeedback turnId={message.id} />
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} sourcesLabel={t("sources")} />
        )}
      </div>
    </article>
  );
}

/**
 * The customer's 👍/👎 on one assistant reply (ADR 0041). Renders only once the store holds
 * the conversation id AND the signed resume capability — the vote cannot be bound without
 * them, so the widget stays hidden rather than posting something the agent would reject. The
 * vote is best-effort telemetry: a failure is swallowed, never surfaced to the customer.
 */
function AssistantFeedback({ turnId }: { turnId: string }) {
  const t = useTranslations("chat");
  const conversationId = useChatStore((s) => s.conversationId);
  const resumeToken = useChatStore((s) => s.resumeToken);
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [pending, setPending] = useState(false);

  if (!conversationId || !resumeToken) return null;

  const vote = (next: "up" | "down") => {
    if (pending || rating === next) return;
    setPending(true);
    submitCustomerFeedback({ conversationId, turnId, rating: next, resumeToken })
      .then(() => setRating(next))
      .catch(() => {
        /* best-effort telemetry — never break the chat over a feedback POST */
      })
      .finally(() => setPending(false));
  };

  return (
    <div className="self-start flex items-center gap-2 px-1 opacity-60 group-hover:opacity-100 transition-opacity duration-150">
      <span className="text-[0.62rem] text-slate-500 select-none">
        {rating ? t("feedbackThanks") : t("feedbackPrompt")}
      </span>
      <button
        type="button"
        onClick={() => vote("up")}
        disabled={pending}
        aria-label={t("feedbackUp")}
        aria-pressed={rating === "up"}
        className={cn(
          "flex items-center transition-colors duration-150 disabled:cursor-not-allowed",
          rating === "up"
            ? "text-[var(--tessera-fg-success)]"
            : "text-slate-500 hover:text-slate-800",
        )}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        onClick={() => vote("down")}
        disabled={pending}
        aria-label={t("feedbackDown")}
        aria-pressed={rating === "down"}
        className={cn(
          "flex items-center transition-colors duration-150 disabled:cursor-not-allowed",
          rating === "down" ? "text-red-600" : "text-slate-500 hover:text-slate-800",
        )}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.7
      ? "text-green-700 bg-green-50 border-green-200 "
      : value >= 0.4
        ? "text-amber-700 bg-amber-50 border-amber-200 "
        : "text-red-700 bg-red-50 border-red-200 ";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-1.5 py-px text-[0.65rem] font-medium tabular-nums",
        tone,
      )}
    >
      {pct}%
    </span>
  );
}
