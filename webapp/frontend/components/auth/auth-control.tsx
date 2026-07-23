"use client";

import { ChevronDown, LogIn } from "lucide-react";
import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";

import { UserMenu } from "@/components/layout/user-menu";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

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
 * Signed-in behaviour keeps the same actions in every context. Optional
 * selection surfaces use an avatar-only trigger; gated cockpit surfaces retain
 * the full role card because the active operator role matters there.
 */
export type AuthContext = "demo" | "optional" | "gated";

/**
 * Header auth affordance (ADR 0009): a sign-in link for visitors, an avatar on
 * selection surfaces, or the full role card in the cockpit. Account switch and
 * sign-out live inside the dropdown — never as bare header buttons.
 */
export function AuthControl({ context = "optional" }: { context?: AuthContext }) {
  const { data: session, status } = useSession();
  const t = useTranslations("auth");
  const role = session?.user?.role;
  const compact = context === "optional";

  // Reserve the resolved control's footprint while the session loads, so it
  // doesn't pop in and reflow the (flex-wrap) header row — which would make the
  // header "dance" at narrower widths. Mirrors the authenticated button below.
  if (status === "loading") {
    return (
      <div
        aria-hidden
        className={cn(
          "flex items-center border border-transparent",
          compact ? "h-10 w-10 justify-center rounded-full p-1" : "w-full gap-2 rounded-lg p-2",
        )}
      >
        <span className="h-8 w-8 shrink-0 animate-pulse rounded-full bg-[var(--tessera-muted)]" />
        {compact ? null : (
          <>
            <span className="hidden min-w-0 flex-1 flex-col gap-1 md:flex">
              <span className="h-3 w-24 animate-pulse rounded bg-[var(--tessera-muted)]" />
              <span className="h-2.5 w-20 animate-pulse rounded bg-[var(--tessera-muted)]" />
            </span>
            <ChevronDown className="hidden h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)] md:block" />
          </>
        )}
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

  return <UserMenu role={role} compact={compact} />;
}
