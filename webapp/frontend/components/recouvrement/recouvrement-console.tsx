"use client";

import { Info, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { ChatRoom } from "@/components/chat/chat-room";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import type { Role } from "@/lib/auth/accounts";

/**
 * Recouvrement's dedicated business console (ADR 0010 Phase C). A standalone
 * re-skin around the REAL shared `<ChatRoom>` core (no fork, no debug console):
 * the chat is the live internal recouvrement agent, reached because the BFF
 * forwarded a signed operator assertion on the `recouvrement` → dedicated-ui
 * surface. The side panel is HONEST-EMPTY: Tessera has no collections-case
 * backend, so it fabricates no dossiers / échéanciers / payment plans.
 */
export function RecouvrementConsole({ role }: { role: Role | null }) {
  const t = useTranslations("recouvrement");

  return (
    <div className="flex h-screen flex-col bg-[var(--background)] text-[var(--foreground)]">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-[var(--border)] px-6 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <TesseraLogo className="h-8" />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500" />
              <h1 className="truncate text-sm font-semibold">{t("title")}</h1>
              <span className="hidden shrink-0 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[0.65rem] font-medium uppercase tracking-wider text-amber-600 sm:inline dark:text-amber-400">
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
          <AuthControl />
        </div>
      </header>

      <main className="grid min-h-0 flex-1 gap-4 p-4 xl:grid-cols-[1fr_340px]">
        {/* The REAL chat core — the premium shared ChatRoom, surface=recouvrement. */}
        <div className="flex min-h-0 min-w-0 flex-col">
          <ChatRoom surface="recouvrement" />
        </div>

        {/* Honest-empty business panel: no fabricated collections data. */}
        <aside className="hidden min-h-0 flex-col gap-3 overflow-y-auto xl:flex">
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/55 p-4">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-[var(--muted-foreground)]" />
              <h2 className="text-sm font-semibold">{t("panelTitle")}</h2>
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
              {t("panelEmpty")}
            </p>
          </section>
          <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/40 p-4">
            <h2 className="text-sm font-semibold">{t("contextTitle")}</h2>
            <p className="mt-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
              {t("context")}
            </p>
          </section>
        </aside>
      </main>
    </div>
  );
}
