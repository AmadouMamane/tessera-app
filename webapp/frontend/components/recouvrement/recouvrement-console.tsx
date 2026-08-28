"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PanelLeftClose, Search, ShieldAlert, SquarePen } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { ChatRoom } from "@/components/chat/chat-room";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { AppHeader } from "@/components/layout/app-header";
import { RecouvrementLogo, RecouvrementMark } from "@/components/recouvrement/recouvrement-logo";
import { fetchConversationMessages, fetchConversations } from "@/lib/api/client";
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
export function RecouvrementConsole() {
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
      {/* Left column — full height; its right border is the continuous vertical
          rule that separates the logo (above the panel) from the page header. */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col overflow-hidden border-[var(--tessera-border)] border-r transition-[width] duration-200 ease-out md:flex",
          collapsed ? "w-[60px]" : "w-[264px]",
        )}
        style={{ background: "var(--tessera-bg-soft)", color: "var(--tessera-text)" }}
      >
        {/* Logo band — same height as the page header so the top forms one band
            and the vertical rule runs straight to the top. */}
        <div
          className={cn(
            "flex min-h-[5.5rem] shrink-0 items-center border-[var(--tessera-border)] border-b",
            collapsed ? "justify-center px-2" : "justify-between px-3",
          )}
        >
          {collapsed ? (
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={t("expandPanel")}
              title={t("expandPanel")}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-md transition-colors hover:bg-[var(--tessera-surface)]"
            >
              <RecouvrementMark className="h-8" />
            </button>
          ) : (
            <>
              <RecouvrementLogo label={t("title")} tagline={t("badge")} />
              <button
                type="button"
                onClick={toggleSidebar}
                aria-label={t("collapsePanel")}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-md text-[var(--tessera-text-muted)] transition-colors hover:bg-[var(--tessera-surface)] hover:text-[var(--tessera-text)]"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </>
          )}
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-1 p-2">
          {/* New chat — icon-only when folded. */}
          <button
            type="button"
            onClick={newChat}
            aria-label={t("newChat")}
            title={t("newChat")}
            className={cn(
              "flex h-9 items-center gap-2 rounded-lg font-medium text-[0.82rem] text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-surface)]",
              collapsed ? "justify-center" : "px-2",
            )}
          >
            <SquarePen className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
            {collapsed ? null : t("newChat")}
          </button>

          {/* Search — a search icon (expands the panel) when folded. */}
          {collapsed ? (
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={t("search")}
              title={t("search")}
              className="flex h-9 items-center justify-center rounded-lg text-[var(--tessera-text-muted)] transition-colors hover:bg-[var(--tessera-surface)] hover:text-[var(--tessera-text)]"
            >
              <Search className="h-4 w-4 shrink-0" />
            </button>
          ) : (
            <div className="relative">
              <Search className="-translate-y-1/2 absolute top-1/2 left-2.5 h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("search")}
                aria-label={t("search")}
                className="h-9 w-full rounded-lg border border-transparent bg-[var(--tessera-surface)] pr-2 pl-8 text-[0.78rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)] focus:border-[var(--tessera-border)]"
              />
            </div>
          )}

          {/* Récents — full list only when the panel is expanded. */}
          {collapsed ? null : (
            <>
              <div className="mt-3 px-2 text-xs font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
                {t("recents")}
              </div>
              <nav className="mt-1 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
                {recents.isError && recents.data === undefined ? (
                  <QueryErrorState
                    compact
                    onRetry={() => recents.refetch()}
                    retrying={recents.isFetching}
                    className="border-0 bg-transparent shadow-none"
                  />
                ) : shown.length === 0 ? (
                  <p className="py-1.5 pr-2 pl-3 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
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
            </>
          )}
        </div>
      </aside>

      {/* Right column — page header (right of the vertical rule) + the chat. */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Unified header (docs/design/header-normative.md) — business variant,
            GATED: the brand lives in this console's own left rail, so the header
            shows the console subtitle as its `lead` (no second brand). Auth is
            `gated` (collections RBAC), so the account control shows WHO + sign
            out and NEVER "Se connecter". */}
        <AppHeader
          plan="business"
          auth="gated"
          chromeClassName="border-[var(--border)] border-b"
          lead={
            <>
              <ShieldAlert className="h-5 w-5 shrink-0 text-[var(--tessera-fg-warning)]" />
              <p className="truncate text-sm text-[var(--tessera-text)]">{t("subtitle")}</p>
            </>
          }
        />

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
