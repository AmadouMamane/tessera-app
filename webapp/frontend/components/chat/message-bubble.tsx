"use client";

import {
  AlertTriangle,
  BookOpen,
  Check,
  ChevronDown,
  Copy,
  FileText,
  Pencil,
  Sparkles,
  User2,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import type { ChatMessage } from "@/lib/stores/chat-store";
import { Markdown } from "./markdown";

interface MessageBubbleProps {
  message: ChatMessage;
  isGrouped?: boolean;
  isFirst?: boolean;
  isStreaming?: boolean;
  isLastUserMessage?: boolean;
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
  onEdit,
}: MessageBubbleProps) {
  const t = useTranslations("chat");
  const isUser = message.role === "user";
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
      aria-label={isUser ? t("youSaid") : t("assistantSaid")}
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
              ? "bg-[var(--secondary)] text-[var(--muted-foreground)] ring-1 ring-[var(--border)]"
              : "bg-gradient-to-br from-navy-800 to-navy-950 text-gold-400 shadow-[inset_0_1px_1px_oklch(0.8_0.066_85/0.2)] ring-1 ring-gold-500/15 dark:from-gold-500 dark:to-gold-600 dark:text-navy-950 dark:ring-gold-300/25",
          )}
        >
          {isUser ? <User2 className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
        </div>
      )}

      {/* Content column — no items-start/end: default stretch makes children always fill the column */}
      <div className="flex w-[80%] flex-col gap-1.5">
        {/* Name + timestamp + badges — hidden for grouped messages */}
        {!isGrouped && (
          <div className={cn("flex items-baseline gap-2", isUser ? "justify-end px-1" : "")}>
            <span className="text-[0.7rem] font-medium text-[var(--muted-foreground)]">
              {isUser ? t("youSaid") : t("assistantSaid")}
            </span>
            <span className="text-[0.62rem] tabular-nums text-[var(--muted-foreground)]/40">
              {formatTime(message.createdAt)}
            </span>
            {message.needsEscalation && (
              <Badge tone="warning" className="gap-1">
                <AlertTriangle className="h-3 w-3" />
                {t("escalated")}
              </Badge>
            )}
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
              ? "px-4 py-2.5 rounded-2xl rounded-br-sm bg-gradient-to-br from-navy-800 to-navy-950 text-navy-50 dark:from-gold-400 dark:to-gold-500 dark:text-navy-950 text-sm leading-relaxed shadow-[var(--shadow-card)]"
              : "text-[var(--foreground)]",
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
                className="w-full resize-none bg-transparent text-sm leading-relaxed text-navy-50 dark:text-navy-950 focus:outline-none"
              />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-justify hyphens-auto">
                {message.content}
              </p>
            )
          ) : (
            <Markdown>{message.content}</Markdown>
          )}
        </div>

        {/* User actions: copy + edit */}
        {isUser &&
          message.content &&
          (isEditing ? (
            <div className="self-end flex flex-col items-end gap-1">
              {/* Truncation warning — only when this is not the last user message */}
              {!isLastUserMessage && (
                <p className="text-[0.6rem] text-amber-400 dark:text-amber-500 select-none">
                  ⚠ {t("editWillTruncate")}
                </p>
              )}
              <div className="flex items-center gap-2">
                <p className="text-[0.6rem] text-navy-300/60 dark:text-navy-700/60 select-none">
                  {t("editHint")}
                </p>
                <button
                  type="button"
                  onClick={cancelEdit}
                  className="flex items-center gap-1 text-[0.62rem] text-[var(--muted-foreground)]/60 hover:text-[var(--muted-foreground)] transition-colors duration-150"
                >
                  {t("cancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmEdit}
                  disabled={!draft.trim() || draft.trim() === message.content}
                  className="flex items-center gap-1 text-[0.62rem] font-medium text-gold-600 dark:text-gold-500 hover:text-gold-700 dark:hover:text-gold-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors duration-150"
                >
                  {t("confirm")}
                </button>
              </div>
            </div>
          ) : (
            /* On desktop: fade-in on hover. On touch (hover:none): always visible. */
            <div className="self-end flex items-center gap-2 opacity-20 group-hover:opacity-100 [@media(hover:none)]:!opacity-100 transition-opacity duration-150">
              <button
                type="button"
                onClick={handleUserCopy}
                aria-label={userCopied ? t("copied") : t("copy")}
                className={cn(
                  "flex items-center gap-1 text-[0.62rem] transition-colors duration-150",
                  "text-[var(--muted-foreground)]/60 hover:text-[var(--muted-foreground)]",
                  userCopied && "!opacity-100 text-green-600 dark:text-green-400",
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
                  className="flex items-center gap-1 text-[0.62rem] text-[var(--muted-foreground)]/60 hover:text-[var(--muted-foreground)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
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
              "text-[var(--muted-foreground)]/40 hover:text-[var(--muted-foreground)]",
              "opacity-20 group-hover:opacity-100",
              copied && "!opacity-100 text-green-600 dark:text-green-400",
            )}
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? t("copied") : t("copy")}
          </button>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <CitationList citations={message.citations} sourcesLabel={t("sources")} />
        )}
      </div>
    </article>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value >= 0.7
      ? "text-green-700 bg-green-50 dark:text-green-400 dark:bg-green-950/40 border-green-200 dark:border-green-800"
      : value >= 0.4
        ? "text-amber-700 bg-amber-50 dark:text-amber-400 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800"
        : "text-red-700 bg-red-50 dark:text-red-400 dark:bg-red-950/40 border-red-200 dark:border-red-800";
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

function CitationList({
  citations,
  sourcesLabel,
}: {
  citations: NonNullable<ChatMessage["citations"]>;
  sourcesLabel: string;
}) {
  const t = useTranslations("chat");
  return (
    <div className="mt-1.5 flex flex-col gap-1 px-1">
      <span className="flex items-center gap-1 text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
        <BookOpen className="h-3 w-3" />
        {sourcesLabel}
      </span>
      <ol className="flex flex-col gap-1">
        {citations.map((c, idx) => {
          const hasTitle = Boolean(c.locator?.trim());
          const title = hasTitle ? c.locator : c.source;
          return (
            <li key={`${c.source}-${c.locator}-${idx}`}>
              <details className="group rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 transition-colors open:border-gold-500/40 open:bg-gold-500/5 hover:border-gold-500/30">
                <summary className="flex cursor-pointer list-none items-center gap-2 px-2.5 py-1.5 [&::-webkit-details-marker]:hidden">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-[var(--muted)] text-[0.65rem] font-semibold text-[var(--muted-foreground)] tabular-nums">
                    {idx + 1}
                  </span>
                  <FileText className="h-3.5 w-3.5 shrink-0 text-gold-600 dark:text-gold-400" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-[var(--foreground)] text-xs">
                      {title}
                    </span>
                    {hasTitle && (
                      <span className="block truncate text-[0.65rem] text-[var(--muted-foreground)]">
                        {c.source}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 rounded border border-[var(--border)] px-1 py-px text-[0.55rem] font-medium text-[var(--muted-foreground)] uppercase tracking-wide">
                    {c.language}
                  </span>
                  <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)] transition-transform group-open:rotate-180" />
                </summary>
                <p className="max-h-56 overflow-y-auto whitespace-pre-wrap break-words border-[var(--border)] border-t px-2.5 py-2 text-[var(--foreground)]/90 text-xs leading-relaxed">
                  {c.excerpt?.trim() ? c.excerpt : t("noExcerpt")}
                </p>
              </details>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
