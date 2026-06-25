"use client";

import { ChevronDown, FlaskConical, LogIn, LogOut, UserCog } from "lucide-react";
import { signOut, useSession } from "next-auth/react";
import { useTranslations } from "next-intl";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, useRouter } from "@/i18n/navigation";

/** Two-letter avatar initials from a display name (e.g. "Amadou D." → "AD"). */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "··";
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase() || "··";
}

/**
 * Anonymous behaviour of {@link AuthControl}, per the header normative
 * (`docs/design/header-normative.md` §4). The header REFLECTS; the RBAC GATES.
 *
 * - `optional` — product/espaces: optional auth that unlocks (anonymous →
 *   customer). Anonymous shows "Se connecter".
 * - `gated` — cockpit / collections console: the route is already RBAC-gated, an
 *   anonymous visitor never reaches it, so NEVER show "Se connecter".
 * - `demo` — launcher: a labelled demonstration session, not a real login.
 *
 * Signed-in behaviour is identical in every context: the user menu (who + sign
 * out). The context only changes the anonymous fallback.
 */
export type AuthContext = "demo" | "optional" | "gated";

/**
 * Header auth affordance (ADR 0009): a sign-in link for visitors, or a compact
 * user menu (avatar + name + role + chevron). Account switch and sign-out live
 * inside the dropdown — never as a bare button in the header.
 */
export function AuthControl({ context = "optional" }: { context?: AuthContext }) {
  const { data: session, status } = useSession();
  const t = useTranslations("auth");
  const router = useRouter();
  const role = session?.user?.role;

  // Reserve the resolved control's footprint while the session loads, so it
  // doesn't pop in and reflow the (flex-wrap) header row — which would make the
  // header "dance" at narrower widths. Mirrors the authenticated button below.
  if (status === "loading") {
    return (
      <div
        aria-hidden
        className="flex items-center gap-2 rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] py-1 pl-1 pr-2"
      >
        <span className="h-7 w-7 shrink-0 animate-pulse rounded-full bg-[var(--tessera-muted)]" />
        <span className="hidden min-w-0 flex-col gap-1 sm:flex">
          <span className="h-3 w-16 animate-pulse rounded bg-[var(--tessera-muted)]" />
          <span className="h-2.5 w-10 animate-pulse rounded bg-[var(--tessera-muted)]" />
        </span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
      </div>
    );
  }

  if (!role) {
    // Gated surfaces (cockpit / collections console) are reached only with a
    // role — an anonymous render here means the session is mid-resolve or the
    // RBAC layout is about to bounce. Never invite a sign-in: stay silent.
    if (context === "gated") return null;
    // Launcher: a labelled DEMO session, not a real login (ADR 0013). No
    // "Se connecter" CTA — the launcher is a demonstration, not a front door.
    if (context === "demo") {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border-subtle)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
          <FlaskConical className="h-3.5 w-3.5" />
          {t("demoSession")}
        </span>
      );
    }
    // Optional auth (product/espaces): sign-in unlocks the customer experience.
    return (
      <Link
        href="/login"
        className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-[var(--muted-foreground)] transition-colors hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
      >
        <LogIn className="h-3.5 w-3.5" />
        {t("signIn")}
      </Link>
    );
  }

  const name = session?.user?.name ?? "Amadou D.";
  const roleLabel = t(`roles.${role}`);

  async function onSignOut() {
    await signOut({ redirect: false });
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] py-1 pl-1 pr-2 text-left transition-colors hover:bg-[var(--tessera-muted)]"
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-green-soft)] text-[0.7rem] font-semibold text-[var(--tessera-green)]">
            {initials(name)}
          </span>
          <span className="hidden min-w-0 flex-col leading-tight sm:flex">
            <span className="truncate text-xs font-medium text-[var(--tessera-text)]">{name}</span>
            <span className="truncate text-[0.65rem] text-[var(--tessera-text-muted)]">
              {roleLabel}
            </span>
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[12rem]">
        <DropdownMenuLabel>{t("signedInAs", { name })}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/login" className="flex items-center gap-2">
            <UserCog className="h-4 w-4" />
            {t("auditorMode")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void onSignOut()} className="flex items-center gap-2">
          <LogOut className="h-4 w-4" />
          {t("signOut")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
