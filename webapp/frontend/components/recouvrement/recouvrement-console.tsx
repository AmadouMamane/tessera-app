"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldAlert,
  TicketCheck,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { ChatRoom } from "@/components/chat/chat-room";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { fetchAudit } from "@/lib/api/client";
import type { AuditEntry } from "@/lib/api/schemas";
import type { Role } from "@/lib/auth/accounts";
import { cn } from "@/lib/cn";

const COLLAPSE_KEY = "tessera.recouvrement.sidebarCollapsed";

/** A recouvrement turn whose tool call opened a human-handoff ticket. */
function isEscalation(e: AuditEntry): boolean {
  return e.event_type === "tool" && /escalat|ticket/i.test(e.target);
}

/**
 * Recouvrement's dedicated business console (ADR 0010 Phase C). A standalone
 * re-skin around the REAL shared `<ChatRoom>` core (no fork, no debug console),
 * keeping the legacy `/chat` proportions: a left column + a ~88px top bar + the
 * chat in a centred, bounded `max-w-6xl` card. The left column wears the Tessera
 * COCKPIT skin (`--tessera-*`) and is RETRACTABLE (OpenAI-style toggle, persisted)
 * — but it carries the brand + HONEST-EMPTY business context, never the cockpit
 * navigation (business plane, ADR 0013). No fabricated dossiers / échéanciers.
 */
export function RecouvrementConsole({ role }: { role: Role | null }) {
  const t = useTranslations("recouvrement");
  const locale = useLocale();
  const [collapsed, setCollapsed] = useState(false);

  // Real, durable activity of the recouvrement agent — its turns + human
  // escalations from the hash-chained audit journal. No fabricated dossiers.
  const activity = useQuery({
    queryKey: ["recouvrement-activity"],
    queryFn: ({ signal }) => fetchAudit({ agent: "recouvrement", limit: 8, signal }),
    refetchInterval: 30_000,
  });
  const entries = activity.data?.entries ?? [];

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

  return (
    <div className="flex h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Left column — Tessera cockpit skin, retractable (OpenAI-style). */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col overflow-hidden transition-[width] duration-200 ease-out md:flex",
          collapsed ? "w-0" : "w-[264px] border-[var(--tessera-border)] border-r",
        )}
        style={{ background: "var(--tessera-bg-soft)", color: "var(--tessera-text)" }}
      >
        {/* Fixed inner width so content doesn't reflow as the panel animates. */}
        <div className="flex w-[264px] min-w-[264px] flex-1 flex-col gap-3 overflow-y-auto p-3">
          <div className="flex items-center justify-between">
            <TesseraLogo className="h-8" />
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label={t("collapsePanel")}
              className="grid h-8 w-8 place-items-center rounded-md text-[var(--tessera-text-muted)] transition-colors hover:bg-[var(--tessera-surface)] hover:text-[var(--tessera-text)]"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>

          <section className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
            <div className="flex items-center gap-2">
              <Activity className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
              <h2 className="font-semibold text-xs">{t("panelTitle")}</h2>
            </div>
            {entries.length === 0 ? (
              <p className="mt-1.5 text-[0.7rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {t("activityEmpty")}
              </p>
            ) : (
              <ul className="mt-2 flex flex-col gap-1.5">
                {entries.map((e) => {
                  const esc = isEscalation(e);
                  const Icon = esc ? TicketCheck : MessageSquare;
                  return (
                    <li
                      key={`${e.occurred_at}:${e.target}:${e.hash ?? ""}`}
                      className="flex items-start gap-2 text-[0.7rem]"
                    >
                      <Icon
                        className={cn(
                          "mt-0.5 h-3.5 w-3.5 shrink-0",
                          esc ? "text-amber-500" : "text-[var(--tessera-text-muted)]",
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[var(--tessera-text)]">
                          {esc ? t("activityEscalation") : t("activityExchange")}
                        </div>
                        <time className="text-[0.62rem] text-[var(--tessera-text-muted)]">
                          {new Date(e.occurred_at).toLocaleString(locale, {
                            day: "2-digit",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </time>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
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
