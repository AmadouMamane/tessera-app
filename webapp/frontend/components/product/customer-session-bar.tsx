"use client";

import { LogIn, LogOut, ShieldCheck, User } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { fetchSessionState, loginDemo, logoutSession, type SessionState } from "@/lib/api/session";
import { useChatStore } from "@/lib/stores/chat-store";
import { SUBJECT_ID_KEY } from "@/components/chat/chat-room";
import { PRODUIT_CID_KEY } from "./chat-widget";

/**
 * Customer-session strip for the chat widget (ADR 0008/0009).
 *
 * Reflects the *real* server-derived session (anonymous vs. an authenticated
 * demo customer) and exposes the demo login/logout. Authenticating flips the
 * agent's auth_state — read server-side from the signed cookie — so the account
 * tools become reachable in the very next turn. (It does not unlock recouvrement:
 * that agent is operator-only, off the customer widget — ADR 0010 Phase A.) The
 * "demo" labelling is explicit: this is a seeded identity, not a real login.
 */
export function CustomerSessionBar() {
  const t = useTranslations("product.apercu.widget.session");
  const [session, setSession] = useState<SessionState | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let active = true;
    fetchSessionState().then((s) => {
      if (active) setSession(s);
    });
    return () => {
      active = false;
    };
  }, []);

  const run = useCallback(async (action: () => Promise<SessionState>) => {
    setPending(true);
    try {
      const newState = await action();
      setSession(newState);
      try {
        localStorage.removeItem(PRODUIT_CID_KEY);
        // Wipe long-term agent memory identity when auth changes (ADR 0007).
        localStorage.removeItem(SUBJECT_ID_KEY);
      } catch {}
      useChatStore.getState().reset();
    } finally {
      setPending(false);
    }
  }, []);

  const authenticated = session?.authenticated ?? false;

  return (
    <div
      className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--muted)]/40 px-4 py-2 text-[0.7rem]"
      title={authenticated ? t("demoHint") : t("anonymousHint")}
    >
      <span className="flex min-w-0 items-center gap-1.5 text-[var(--muted-foreground)]">
        {authenticated ? (
          <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
        ) : (
          <User className="h-3.5 w-3.5 shrink-0" />
        )}
        <span className="truncate font-medium">
          {authenticated ? t("demoActive") : t("anonymous")}
        </span>
      </span>
      {authenticated ? (
        <button
          type="button"
          onClick={() => run(logoutSession)}
          disabled={pending}
          className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1 font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--muted)] disabled:opacity-50"
        >
          <LogOut className="h-3 w-3" />
          {t("logout")}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => run(loginDemo)}
          disabled={pending}
          className="inline-flex shrink-0 items-center gap-1 rounded-md bg-navy-900 px-2 py-1 font-medium text-gold-400 ring-1 ring-gold-500/25 transition-colors hover:bg-navy-800 disabled:opacity-50 dark:bg-gold-500 dark:text-navy-950 dark:ring-gold-300/30 dark:hover:bg-gold-400"
        >
          <LogIn className="h-3 w-3" />
          {t("login")}
        </button>
      )}
    </div>
  );
}
