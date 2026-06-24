"use client";

import { MessageSquareText, Plus, ShieldAlert, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { ChatRoom } from "@/components/chat/chat-room";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import type { Role } from "@/lib/auth/accounts";
import { cn } from "@/lib/cn";
import {
  type StoredConversation,
  listConversations,
  removeConversation,
  saveConversation,
} from "@/lib/recouvrement-history";
import { useChatStore } from "@/lib/stores/chat-store";

/**
 * Recouvrement's dedicated business console (ADR 0010 Phase C) — a ChatGPT/Claude
 * style shell around the REAL shared `<ChatRoom>` core (no fork, no debug console):
 * a left sidebar (new chat + conversation history) and a clean centered chat. The
 * history is HONEST: the user's OWN conversations persisted in their browser
 * (localStorage) — the chat store has no persistence and there is no per-user
 * conversations API, so nothing is fabricated (no dossiers / échéanciers / plans).
 */
export function RecouvrementConsole({ role }: { role: Role | null }) {
  const t = useTranslations("recouvrement");
  const messages = useChatStore((s) => s.messages);
  const conversationId = useChatStore((s) => s.conversationId);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const reset = useChatStore((s) => s.reset);
  const hydrate = useChatStore((s) => s.hydrate);

  const [convs, setConvs] = useState<StoredConversation[]>([]);
  useEffect(() => {
    setConvs(listConversations());
  }, []);

  // Persist the active conversation once a turn settles (never mid-stream).
  useEffect(() => {
    if (!isStreaming && conversationId && messages.length > 0) {
      saveConversation(conversationId, messages);
      setConvs(listConversations());
    }
  }, [isStreaming, conversationId, messages]);

  const newChat = () => reset();
  const openConversation = (c: StoredConversation) => {
    if (c.id === conversationId) return;
    hydrate(c.id, c.messages);
  };
  const deleteConversation = (id: string) => {
    setConvs(removeConversation(id));
    if (id === conversationId) reset();
  };

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Sidebar — new chat + real (browser-local) history. */}
      <aside className="hidden w-[268px] shrink-0 flex-col border-[var(--border)] border-r bg-[var(--card)]/40 md:flex">
        <div className="flex items-center gap-2 px-4 py-4">
          <TesseraLogo className="h-7" />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-500" />
              <span className="truncate font-semibold text-sm">{t("title")}</span>
            </div>
            <span className="text-[0.62rem] uppercase tracking-wider text-[var(--muted-foreground)]">
              {t("badge")}
            </span>
          </div>
        </div>

        <div className="px-3">
          <button
            type="button"
            onClick={newChat}
            className="flex w-full items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background)]/60 px-3 py-2.5 text-sm font-medium transition-colors hover:border-amber-500/50 hover:bg-[var(--card)]"
          >
            <Plus className="h-4 w-4 text-amber-500" />
            {t("newChat")}
          </button>
        </div>

        <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-2">
          <p className="px-2 pb-1.5 text-[0.62rem] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            {t("historyTitle")}
          </p>
          {convs.length === 0 ? (
            <p className="px-2 py-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
              {t("historyEmpty")}
            </p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              {convs.map((c) => (
                <li key={c.id} className="group/conv relative">
                  <button
                    type="button"
                    onClick={() => openConversation(c)}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[0.8rem] transition-colors",
                      c.id === conversationId
                        ? "bg-[var(--card)] text-[var(--foreground)]"
                        : "text-[var(--muted-foreground)] hover:bg-[var(--card)]/60 hover:text-[var(--foreground)]",
                    )}
                  >
                    <MessageSquareText className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate pr-5">{c.title}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteConversation(c.id)}
                    aria-label={t("deleteChat")}
                    className="-translate-y-1/2 absolute top-1/2 right-1.5 grid h-6 w-6 place-items-center rounded-md text-[var(--muted-foreground)] opacity-0 transition-opacity hover:text-red-400 group-hover/conv:opacity-100"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Honest-empty business note — no fabricated collections data. */}
        <div className="border-[var(--border)] border-t px-4 py-3">
          <p className="text-[0.62rem] leading-relaxed text-[var(--muted-foreground)]">
            {t("panelEmpty")}
          </p>
        </div>
      </aside>

      {/* Main — clean centered chat. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between gap-3 border-[var(--border)] border-b px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2">
            <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500 md:hidden" />
            <p className="truncate text-xs text-[var(--muted-foreground)]">
              {t("subtitle")}
              {role ? ` · ${t("roleLabel")}: ${role}` : null}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <LanguageSwitcher />
            <AuthControl />
          </div>
        </header>
        <main className="min-h-0 flex-1">
          <ChatRoom surface="recouvrement" />
        </main>
      </div>
    </div>
  );
}
