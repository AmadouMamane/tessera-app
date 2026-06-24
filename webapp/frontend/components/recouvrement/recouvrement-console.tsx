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
 * re-skin around the REAL shared `<ChatRoom>` core (no fork, no debug console),
 * keeping the proportions/structure of the legacy `/chat` page: a left column
 * (~218px) + a ~88px top bar + the chat in a centred, bounded `max-w-6xl` card
 * (never edge-to-edge). The left column carries the brand + HONEST-EMPTY business
 * context — never the cockpit navigation (this is the business plane, ADR 0013) —
 * and Tessera has no collections-case backend, so it fabricates no dossiers /
 * échéanciers / payment plans.
 */
export function RecouvrementConsole({ role }: { role: Role | null }) {
  const t = useTranslations("recouvrement");

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Left column — same proportion as the legacy /chat sidebar (≈218px). */}
      <aside className="hidden w-[218px] shrink-0 flex-col gap-4 overflow-y-auto border-[var(--border)] border-r bg-[var(--card)]/40 px-3 py-4 md:flex">
        <TesseraLogo className="h-8" />
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)]/55 p-3">
          <div className="flex items-center gap-2">
            <Info className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />
            <h2 className="font-semibold text-xs">{t("panelTitle")}</h2>
          </div>
          <p className="mt-1.5 text-[0.7rem] leading-relaxed text-[var(--muted-foreground)]">
            {t("panelEmpty")}
          </p>
        </section>
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)]/40 p-3">
          <h2 className="font-semibold text-xs">{t("contextTitle")}</h2>
          <p className="mt-1.5 text-[0.7rem] leading-relaxed text-[var(--muted-foreground)]">
            {t("context")}
          </p>
        </section>
      </aside>

      {/* Main — ≈88px top bar + the chat as a centred, bounded card. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex min-h-[5.5rem] shrink-0 items-center justify-between gap-4 border-[var(--border)] border-b px-6">
          <div className="flex min-w-0 items-center gap-2.5">
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
            <AuthControl />
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
