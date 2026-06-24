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
 * surface. A LEFT column carries the brand + HONEST-EMPTY business context
 * (Tessera has no collections-case backend, so it fabricates no dossiers /
 * échéanciers / payment plans), and the chat sits in a contained, centred card —
 * never edge-to-edge. No cockpit navigation (this is the business plane, ADR 0013).
 */
export function RecouvrementConsole({ role }: { role: Role | null }) {
  const t = useTranslations("recouvrement");

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Left column — brand + honest-empty business context (never the cockpit nav). */}
      <aside className="hidden w-[300px] shrink-0 flex-col gap-4 overflow-y-auto border-[var(--border)] border-r bg-[var(--card)]/40 p-4 lg:flex">
        <div className="flex items-center gap-3">
          <TesseraLogo className="h-8" />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500" />
              <h1 className="truncate font-semibold text-sm">{t("title")}</h1>
            </div>
            <span className="text-[0.62rem] uppercase tracking-wider text-amber-600 dark:text-amber-400">
              {t("badge")}
            </span>
          </div>
        </div>

        <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/55 p-4">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-[var(--muted-foreground)]" />
            <h2 className="font-semibold text-sm">{t("panelTitle")}</h2>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
            {t("panelEmpty")}
          </p>
        </section>

        <section className="rounded-2xl border border-[var(--border)] bg-[var(--card)]/40 p-4">
          <h2 className="font-semibold text-sm">{t("contextTitle")}</h2>
          <p className="mt-2 text-xs leading-relaxed text-[var(--muted-foreground)]">
            {t("context")}
          </p>
        </section>
      </aside>

      {/* Main — slim header + the chat as a contained, centred card. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex shrink-0 items-center justify-between gap-3 border-[var(--border)] border-b px-4 py-2.5">
          <div className="flex min-w-0 items-center gap-2">
            <ShieldAlert className="h-4 w-4 shrink-0 text-amber-500 lg:hidden" />
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

        <div className="flex min-h-0 flex-1 justify-center overflow-hidden p-4 sm:p-6">
          {/* Contained chat card — bounded width, not the full screen. */}
          <div className="flex h-full min-h-0 w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]/30">
            <ChatRoom surface="recouvrement" />
          </div>
        </div>
      </div>
    </div>
  );
}
