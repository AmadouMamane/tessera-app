"use client";

import { BookOpen, ChevronDown, FileText } from "lucide-react";
import { useTranslations } from "next-intl";

import type { ChatMessage } from "@/lib/stores/chat-store";
import { Markdown } from "./markdown";

/**
 * Shared, read-only "client view" of a message's body. This is the rendering a
 * customer actually sees and is reused, verbatim, by every surface that shows a
 * *real* client conversation: the interactive chat (`/produit`), the read-only
 * session detail (Historique · CT-01) and — where it shows a conversation — the
 * État à date proof. It carries NO interactivity (no edit/copy/composer) and NO
 * operator debug (traces, guardrail internals): those live only on their own
 * surfaces. Assistant turns render as Markdown (links/lists/headings), user
 * turns as justified plain text — exactly as the chat bubble does.
 */
export function MessageContent({
  speaker,
  content,
  className,
}: {
  speaker: "user" | "assistant";
  content: string;
  className?: string;
}) {
  if (speaker === "user") {
    return (
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-justify hyphens-auto">
        {content}
      </p>
    );
  }
  return <Markdown className={className}>{content}</Markdown>;
}

/**
 * Citation list as the client sees it — numbered, expandable `<details>` with
 * the source locator, language and excerpt. Shared so any client-faithful
 * surface renders citations identically.
 */
export function CitationList({
  citations,
  sourcesLabel,
}: {
  citations: NonNullable<ChatMessage["citations"]>;
  sourcesLabel: string;
}) {
  const t = useTranslations("chat");
  return (
    <div className="mt-1.5 flex flex-col gap-1 px-1">
      <span className="flex items-center gap-1 text-[0.6rem] font-medium uppercase tracking-wide text-slate-500">
        <BookOpen className="h-3 w-3" />
        {sourcesLabel}
      </span>
      <ol className="flex flex-col gap-1">
        {citations.map((c, idx) => {
          const hasTitle = Boolean(c.locator?.trim());
          const title = hasTitle ? c.locator : c.source;
          return (
            <li key={`${c.source}-${c.locator}-${idx}`}>
              <details className="group rounded-md border border-slate-100 bg-white transition-colors open:border-gold-500/50 open:bg-gold-500/5 hover:border-gold-500/50 hover:bg-gold-500/5">
                <summary className="grid min-h-10 cursor-pointer list-none grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-2 px-2 py-1.5 text-[0.68rem] [&::-webkit-details-marker]:hidden">
                  <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-50 text-[0.62rem] font-semibold text-slate-500 tabular-nums transition-colors group-hover:text-gold-700 dark:group-hover:text-gold-300">
                    {idx + 1}
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-1 font-medium text-slate-800">
                      <FileText className="h-3 w-3 shrink-0 text-gold-600 dark:text-gold-400" />
                      <span className="truncate">{title}</span>
                    </span>
                    {hasTitle && (
                      <span className="block truncate font-mono text-[0.62rem] text-slate-500">
                        {c.source}
                      </span>
                    )}
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5">
                    <span className="rounded border border-slate-200 px-1 py-px text-[0.55rem] font-medium text-slate-500 uppercase tracking-wide">
                      {c.language}
                    </span>
                    <ChevronDown className="h-3.5 w-3.5 text-slate-500 transition-transform group-open:rotate-180" />
                  </span>
                </summary>
                <p className="max-h-56 overflow-y-auto whitespace-pre-wrap break-words border-slate-200 border-t px-2.5 py-2 text-slate-800/90 text-xs leading-relaxed">
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
