"use client";

import { Send, StopCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import {
  type KeyboardEvent,
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/cn";

export interface ChatComposerHandle {
  focus: () => void;
  setValue: (text: string) => void;
}

interface ChatComposerProps {
  disabled?: boolean;
  isStreaming?: boolean;
  onSubmit: (message: string) => void | Promise<void>;
  onAbort?: () => void;
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(
  ({ disabled, isStreaming, onSubmit, onAbort }, ref) => {
    const t = useTranslations("chat");
    const textareaRef = useRef<HTMLTextAreaElement | null>(null);
    const [value, setValue] = useState("");

    useImperativeHandle(ref, () => ({
      focus: () => textareaRef.current?.focus(),
      setValue: (text: string) => {
        setValue(text);
        textareaRef.current?.focus();
      },
    }));

    // Auto-resize: grow with content, cap at 160px.
    // biome-ignore lint/correctness/useExhaustiveDependencies: must re-run on value change to recompute height
    useEffect(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }, [value]);

    function submit() {
      const trimmed = value.trim();
      if (!trimmed || disabled) return;
      setValue("");
      void onSubmit(trimmed);
    }

    function handleKey(event: KeyboardEvent<HTMLTextAreaElement>) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        submit();
      }
    }

    return (
      <div className="rounded-b-2xl border-t border-[var(--border)] bg-[var(--card)] px-4 pb-3 pt-3">
        <form
          className="mx-auto max-w-3xl"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {/* Integrated pill — focus glow on the wrapper, not on the textarea */}
          <div className="flex items-end gap-2 rounded-2xl border border-[var(--border)] bg-[var(--muted)]/40 px-4 py-2 transition-[border-color,box-shadow] duration-200 focus-within:border-blue-500/50 focus-within:shadow-[0_0_0_3px_oklch(0.55_0.2_263/0.15)] dark:focus-within:border-blue-400/40 dark:focus-within:shadow-[0_0_0_3px_oklch(0.55_0.2_263/0.18)]">
            <Textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={handleKey}
              placeholder={isStreaming ? t("streamingPlaceholder") : t("placeholder")}
              rows={1}
              className="min-h-[36px] flex-1 resize-none overflow-hidden border-0 bg-transparent px-0 py-1 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
              aria-label={t("placeholder")}
            />
            {isStreaming && onAbort ? (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onAbort}
                aria-label={t("stop")}
                className="mb-0.5 shrink-0 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                type="submit"
                variant="primary"
                size="icon"
                disabled={disabled || value.trim().length === 0}
                aria-label={t("send")}
                className="mb-0.5 shrink-0"
              >
                <Send className="h-4 w-4" />
              </Button>
            )}
          </div>
          {/* Always rendered so its line-height is reserved — toggling only the
              opacity avoids the layout shift (and jitter) when typing begins. */}
          <p
            aria-hidden={value.trim().length > 0 || isStreaming}
            className={cn(
              "mt-1.5 px-1 text-[0.65rem] text-[var(--muted-foreground)] transition-opacity duration-150",
              value.trim().length === 0 && !isStreaming ? "opacity-100" : "opacity-0",
            )}
          >
            {t("composerHint")}
          </p>
        </form>
        {/* AI Act Art. 50 disclosure — must always be visible to the user, so it
            is persistent (never toggled) and rendered from bundled i18n rather
            than a network call. Mirrors tessera.observability.disclosure. */}
        <p className="mx-auto mt-1 max-w-3xl px-1 text-center text-[0.6rem] text-[var(--muted-foreground)]/70">
          {t("disclosure")}
        </p>
      </div>
    );
  },
);
ChatComposer.displayName = "ChatComposer";
