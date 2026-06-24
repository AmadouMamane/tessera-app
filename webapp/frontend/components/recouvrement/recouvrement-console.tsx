"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PanelLeftClose, PanelLeftOpen, Search, ShieldAlert, SquarePen } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { ChatRoom } from "@/components/chat/chat-room";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { fetchConversationMessages, fetchConversations } from "@/lib/api/client";
import type { Role } from "@/lib/auth/accounts";
import { cn } from "@/lib/cn";
import { type ChatMessage, useChatStore } from "@/lib/stores/chat-store";

const COLLAPSE_KEY = "tessera.recouvrement.sidebarCollapsed";
const AGENT_ID = "recouvrement";
const RECENTS_KEY = ["recouvrement-conversations"] as const;

function uid(): string {
  return globalThis.crypto?.randomUUID() ?? Math.random().toString(36).slice(2);
}

/**
 * Recouvrement's dedicated business console (ADR 0010 Phase C). A standalone
 * re-skin around the REAL shared `<ChatRoom>` core (no fork, no debug console),
 * keeping the legacy `/chat` proportions: a left column + a ~88px top bar + the
 * chat in a centred, bounded `max-w-6xl` card.
 *
 * The left column follows the product's conversation-sidebar normative
 * (ChatGPT-style, business-plane skin): a "Nouveau chat" action, a search box
 * and a REAL "Récents" list of the agent's past conversations read from the
 * durable transcript. Selecting one resumes it (same `conversation_id`); a new
 * turn appears in "Récents" (and in the cockpit Historique) as soon as it lands.
 * Only real, backed affordances are shown — no ChatGPT-specific dead nav.
 */
export function RecouvrementConsole({ role }: { role: Role | null }) {
  const t = useTranslations("recouvrement");
  const qc = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [query, setQuery] = useState("");

  const conversationId = useChatStore((s) => s.conversationId);
  const reset = useChatStore((s) => s.reset);
  const loadConversation = useChatStore((s) => s.loadConversation);

  // Real, durable conversation list of the recouvrement agent (the transcript).
  const recents = useQuery({
    queryKey: RECENTS_KEY,
    queryFn: ({ signal }) => fetchConversations(AGENT_ID, 30, signal),
    refetchInterval: 15_000,
  });
  const conversations = recents.data?.conversations ?? [];

  // A fresh turn mints a conversation id → refresh "Récents" so it shows up.
  useEffect(() => {
    if (conversationId) qc.invalidateQueries({ queryKey: RECENTS_KEY });
  }, [conversationId, qc]);

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  const toggleSidebar = () =>
    setCollapsed((v) => {
      const next = !v;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // ignore disabled storage
      }
      return next;
    });

  const q = query.trim().toLowerCase();
  const shown = useMemo(
    () => (q ? conversations.filter((c) => c.title.toLowerCase().includes(q)) : conversations),
    [conversations, q],
  );

  const openConversation = async (id: string) => {
    if (id === conversationId) return;
    const res = await fetchConversationMessages(id);
    const msgs: ChatMessage[] = res.messages.map((m) => ({
      id: uid(),
      role: m.role === "assistant" ? "assistant" : "user",
      content: m.content,
      createdAt: Date.now(),
    }));
    loadConversation(id, msgs);
  };

  const newChat = () => {
    reset();
    setQuery("");
  };

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Left column — conversation sidebar (cockpit skin), retractable. */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col overflow-hidden transition-[width] duration-200 ease-out md:flex",
          collapsed ? "w-0" : "w-[264px] border-[var(--tessera-border)] border-r",
        )}
        style={{ background: "var(--tessera-bg-soft)", color: "var(--tessera-text)" }}
      >
        {/* Fixed inner width so content doesn't reflow as the panel animates. */}
        <div className="flex w-[264px] min-w-[264px] flex-1 flex-col overflow-hidden p-2">
          <div className="flex items-center justify-between px-1 py-1">
            <TesseraLogo className="h-7" />
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={t("collapsePanel")}
              className="grid h-8 w-8 place-items-center rounded-md text-[var(--tessera-text-muted)] transition-colors hover:bg-[var(--tessera-surface)] hover:text-[var(--tessera-text)]"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={newChat}
            className="mt-1 flex items-center gap-2 rounded-lg px-2 py-2 text-left font-medium text-[0.82rem] text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-surface)]"
          >
            <SquarePen className="h-4 w-4 text-[var(--tessera-text-muted)]" />
            {t("newChat")}
          </button>

          <div className="relative mt-1">
            <Search className="-translate-y-1/2 absolute top-1/2 left-2.5 h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("search")}
              aria-label={t("search")}
              className="h-9 w-full rounded-lg border border-transparent bg-[var(--tessera-surface)] pr-2 pl-8 text-[0.78rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)] focus:border-[var(--tessera-border)]"
            />
          </div>

          <div className="mt-3 px-2 text-[0.66rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
            {t("recents")}
          </div>
          <nav className="mt-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
            {shown.length === 0 ? (
              <p className="py-1.5 pr-2 pl-3 text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {q ? t("searchEmpty") : t("recentsEmpty")}
              </p>
            ) : (
              shown.map((c) => (
                <button
                  key={c.conversation_id}
                  type="button"
                  onClick={() => openConversation(c.conversation_id)}
                  title={c.title || t("untitled")}
                  className={cn(
                    "truncate rounded-md py-1.5 pr-2 pl-3 text-left text-[0.78rem] transition-colors",
                    c.conversation_id === conversationId
                      ? "bg-[var(--tessera-surface)] text-[var(--tessera-text)]"
                      : "text-[var(--tessera-text)]/85 hover:bg-[var(--tessera-surface)]",
                  )}
                >
                  {c.title || t("untitled")}
                </button>
              ))
            )}
          </nav>

          <div className="mt-2 border-[var(--tessera-border)] border-t pt-2">
            <AuthControl />
          </div>
        </div>
      </aside>

      {/* Main — ≈88px top bar + the chat as a centred, bounded card. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-[5.5rem] shrink-0 items-center justify-between gap-4 border-[var(--border)] border-b px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            {/* OpenAI-style open handle — visible when the panel is retracted. */}
            {collapsed ? (
              <button
                type="button"
                onClick={toggleSidebar}
                aria-label={t("expandPanel")}
                className="hidden h-9 w-9 shrink-0 place-items-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--card)] hover:text-[var(--foreground)] md:grid"
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            ) : null}
            <ShieldAlert className="h-5 w-5 shrink-0 text-amber-500" />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate font-semibold text-sm">{t("title")}</h1>
                <span className="hidden shrink-0 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[0.62rem] font-medium uppercase tracking-wider text-amber-600 sm:inline dark:text-amber-400">
                  {t("badge")}
                </span>
              </div>
              <p className="truncate text-xs text-[var(--muted-foreground)]">
                {t("subtitle")}
                {role ? ` · ${t("roleLabel")}: ${role}` : null}
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <LanguageSwitcher />
            {/* AuthControl lives in the sidebar footer; surface it here too when
                the sidebar is retracted so sign-out stays reachable. */}
            {collapsed ? <AuthControl /> : null}
          </div>
        </header>

        <main className="min-h-0 min-w-0 flex-1 overflow-hidden px-4 py-5 sm:px-6">
          {/* Centred, bounded chat card (max-w-6xl) — like /chat, not full screen. */}
          <div className="mx-auto flex h-full min-h-0 w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]/30">
            <ChatRoom surface="recouvrement" />
          </div>
        </main>
      </div>
    </div>
  );
}
