"use client";

import { Maximize2, MessageCircle, Minimize2, ShieldCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { ChatRoom } from "@/components/chat/chat-room";
import type { ExternalChatPrompt } from "@/components/chat/chat-room";
import { cn } from "@/lib/cn";
import { fetchConversationMessages } from "@/lib/api/client";
import { type ChatMessage, useChatStore } from "@/lib/stores/chat-store";

export const PRODUCT_CHAT_EVENT = "tessera:open-product-chat";

// Per-browser key holding the customer's own conversation id, so the produit
// widget RESUMES it after a reload / return visit instead of dropping it (the
// chat store is in-memory). It is a capability the customer's browser already
// holds — resuming only ever loads the conversation whose id is stored here, so
// there is no cross-customer exposure (the transcript is not subject-scoped).
export const PRODUIT_CID_KEY = "tessera.produit.conversationId";

interface ProductChatEventDetail {
  prompt?: string;
}

interface ChatWidgetProps {
  hideLauncher?: boolean;
}

/**
 * Floating chat widget — the *new presentation* (v2 shell) of the customer
 * chat. It is a pure re-skin: a FAB + panel that mount the **existing**
 * `<ChatRoom>` verbatim. No streaming, message-rendering or store logic is
 * duplicated here — the widget only owns open/close state and the layout
 * frame. The panel gives `<ChatRoom>` a fixed-height flex column so its
 * internal `flex-1` scroll region resolves; ChatRoom's own card chrome is
 * neutralised via the `[&>div]` utilities so it blends into the panel.
 *
 * Desktop: ~400px × min(620px, 80vh) anchored bottom-right above the FAB.
 * Mobile: full-screen on open. Esc or the FAB/close button collapses it.
 */
export const CHAT_WIDGET_STATE_EVENT = "tessera-chat-widget-state";

export function ChatWidget({ hideLauncher = false }: ChatWidgetProps) {
  const t = useTranslations("product.apercu.widget");
  const [open, setOpen] = useState(!hideLauncher);
  const [isExpanded, setIsExpanded] = useState(false);
  const [externalPrompt, setExternalPrompt] = useState<ExternalChatPrompt | null>(null);
  const conversationId = useChatStore((s) => s.conversationId);
  const restoredRef = useRef(false);

  // Sync state with other components
  useEffect(() => {
    window.dispatchEvent(
      new CustomEvent(CHAT_WIDGET_STATE_EVENT, { detail: { open } })
    );
  }, [open]);

  // Resume the customer's last conversation on load — so turns made from
  // /produit "remontent" after a refresh / return visit instead of vanishing
  // (the store is ephemeral). Runs once; only when nothing is already active, so
  // it never clobbers an in-flight conversation. A stale/unknown id (e.g. a wiped
  // DB) loads empty → we clear it and start fresh rather than pin a dead id.
  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    const state = useChatStore.getState();
    if (state.conversationId || state.messages.length > 0) return;
    let cid: string | null = null;
    try {
      cid = localStorage.getItem(PRODUIT_CID_KEY);
    } catch {
      cid = null;
    }
    if (!cid) return;
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetchConversationMessages(cid);
        if (cancelled) return;
        if (res.messages.length === 0) {
          try {
            localStorage.removeItem(PRODUIT_CID_KEY);
          } catch {
            // ignore disabled storage
          }
          return;
        }
        const msgs: ChatMessage[] = res.messages.map((m: any) => ({
          id: m.id ?? globalThis.crypto?.randomUUID() ?? `${Date.now()}-${Math.random()}`,
          role: (m.role === "assistant" || m.role === "system") ? m.role : "user",
          content: m.content,
          createdAt: m.createdAt ?? m.created_at ?? Date.now(),
        }));
        useChatStore.getState().loadConversation(cid, msgs);
      } catch {
        // offline or stale id — leave the widget fresh, never block the UI
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Remember the active conversation id (while on /produit) so the effect above
  // can resume it next time. Cleared id (Nouveau chat / branch) is left as-is —
  // the next turn mints and persists a fresh id.
  useEffect(() => {
    try {
      if (conversationId) {
        localStorage.setItem(PRODUIT_CID_KEY, conversationId);
      } else {
        localStorage.removeItem(PRODUIT_CID_KEY);
      }
    } catch {
      // ignore disabled storage
    }
  }, [conversationId]);

  // Esc closes the panel (only while open so we don't swallow Esc elsewhere).
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    function onOpenChat(event: Event) {
      const detail = (event as CustomEvent<ProductChatEventDetail>).detail;
      setOpen(true);
      if (detail?.prompt) {
        setExternalPrompt({
          id: globalThis.crypto?.randomUUID() ?? `${Date.now()}`,
          prompt: detail.prompt,
        });
      }
    }
    window.addEventListener(PRODUCT_CHAT_EVENT, onOpenChat);
    return () => window.removeEventListener(PRODUCT_CHAT_EVENT, onOpenChat);
  }, []);

  // Fix ghost sessions: clear PRODUIT_CID_KEY when conversation is reset
  useEffect(() => {
    return useChatStore.subscribe((state) => {
      if (!state.conversationId) {
        try {
          localStorage.removeItem(PRODUIT_CID_KEY);
        } catch {}
      }
    });
  }, []);

  return (
    <>
      {/* Mobile backdrop — also a click target to close. Desktop keeps the host
          visible, so the backdrop is mobile-only. */}
      {open && (
        <button
          type="button"
          aria-hidden
          tabIndex={-1}
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-navy-950/30 backdrop-blur-[2px] sm:hidden"
        />
      )}

      {/* Panel */}
      {open && (
        // biome-ignore lint/a11y/useSemanticElements: floating chat overlay, not a native <dialog> (no modal backdrop semantics, must coexist with the host page)
        <div
          role="dialog"
          aria-label={t("title")}
          className={cn(
            "fixed inset-0 z-50 flex flex-col overflow-hidden border-[var(--border)] bg-[var(--card)] shadow-2xl animate-in fade-in-0 zoom-in-95 slide-in-from-bottom-8 duration-300 ease-out sm:inset-auto sm:bottom-24 sm:right-6 sm:rounded-2xl sm:border transition-[width,height]",
            isExpanded
              ? "sm:h-[85vh] sm:w-[550px]"
              : "sm:h-[min(620px,80vh)] sm:w-[400px]"
          )}
        >
          {/* Header strip */}
          <div className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-gradient-to-br from-navy-900 to-navy-950 px-4 py-3 text-white dark:from-navy-950 dark:to-black">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gold-500/15 text-gold-400 ring-1 ring-gold-500/25">
              <ShieldCheck className="h-4 w-4" />
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm font-semibold">{t("title")}</span>
              <span className="truncate text-[0.68rem] text-white/55">{t("subtitle")}</span>
            </div>
            
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              aria-label={isExpanded ? t("minimize") : t("maximize")}
              title={isExpanded ? t("minimize") : t("maximize")}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            >
              {isExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>

            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("close")}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* ChatRoom host — neutralise ChatRoom's own card chrome so it fills
              the panel flush. Conditionally mounted so the conversation state
              (global store) survives close/reopen without keeping ChatRoom's
              global "/" listener active while collapsed. */}
          <div className="relative flex min-h-0 flex-1 flex-col [&>div]:rounded-none [&>div]:border-0 [&>div]:bg-transparent [&>div]:shadow-none [&>div]:backdrop-blur-none">
            <ChatRoom
              externalPrompt={externalPrompt}
              onExternalPromptHandled={(id) => {
                setExternalPrompt((prompt) => (prompt?.id === id ? null : prompt));
              }}
            />
          </div>
        </div>
      )}

      {!hideLauncher && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? t("close") : t("open")}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-navy-900 text-gold-400 shadow-[0_8px_28px_-6px_oklch(0.2_0.04_255/0.5)] ring-1 ring-gold-500/25 transition-all duration-200 hover:scale-105 hover:bg-navy-800 active:scale-95 dark:bg-gold-500 dark:text-navy-950 dark:ring-gold-300/30 dark:hover:bg-gold-400"
        >
          {open ? <X className="h-5 w-5" /> : <MessageCircle className="h-6 w-6" />}
        </button>
      )}
    </>
  );
}
