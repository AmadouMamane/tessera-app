"use client";

import { ChevronDown, LogIn } from "lucide-react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";

import { UserMenu } from "@/components/layout/user-menu";
import { Link } from "@/i18n/navigation";

/**
 * Anonymous behaviour of {@link AuthControl}, per the header normative
 * (`docs/design/header-normative.md` §4). The header REFLECTS; the RBAC GATES.
 *
 * - `optional` — product/espaces: optional auth that unlocks (anonymous →
 *   customer). Anonymous shows "Se connecter".
 * - `gated` — cockpit / collections console: the route is already RBAC-gated, an
 *   anonymous visitor never reaches it, so NEVER show "Se connecter".
 * - `demo` — launcher: page-level demo badge already carries the context; no
 *   extra header auth affordance for anonymous visitors.
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
        <span className="hidden min-w-0 sm:flex">
          <span className="h-3 w-28 animate-pulse rounded bg-[var(--tessera-muted)]" />
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
    // Launcher: no "Se connecter" CTA — the launcher is a demonstration, not a
    // front door. The page-level DemoBadge is the single demo affordance.
    if (context === "demo") {
      return null;
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

  return <UserMenu role={role} />;
}
