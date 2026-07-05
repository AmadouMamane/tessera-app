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
 placeholder?: string;
 streamingPlaceholder?: string;
 disclosure?: string;
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(
 (
 { disabled, isStreaming, onSubmit, onAbort, placeholder, streamingPlaceholder, disclosure },
 ref,
 ) => {
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
 <div className="rounded-b-2xl border-t border-[var(--border)] bg-transparent px-4 pb-3 pt-3">
 <form
 className="mx-auto max-w-3xl"
 onSubmit={(e) => {
 e.preventDefault();
 submit();
 }}
 >
 {/* Integrated pill — focus glow on the wrapper, not on the textarea */}
 <div className="flex items-end gap-2 rounded-2xl border border-navy-900 bg-white px-4 py-2 text-slate-900">
 <Textarea
 ref={textareaRef}
 value={value}
 onChange={(e) => setValue(e.target.value)}
 onKeyDown={handleKey}
 placeholder={
 isStreaming
 ? (streamingPlaceholder ?? t("streamingPlaceholder"))
 : (placeholder ?? t("placeholder"))
 }
 rows={1}
 className="min-h-[36px] flex-1 resize-none overflow-hidden border-0 bg-transparent px-0 py-1 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
 aria-label={placeholder ?? t("placeholder")}
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
 size="icon"
 disabled={disabled || value.trim().length === 0}
 aria-label={t("send")}
 className="mb-0.5 shrink-0 bg-gradient-to-br from-navy-900 to-navy-950 text-white hover:from-navy-950 hover:to-black disabled:bg-none disabled:bg-navy-800 disabled:text-white/50 border-0"
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
 {disclosure ?? t("disclosure")}
 </p>
 </div>
 );
 },
);
ChatComposer.displayName = "ChatComposer";
