"use client";

import { FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/**
 * Discreet, labelled shortcut to the demo launcher (/select-space).
 *
 * ADR 0013 keeps identity as the real front door (the root role-routes); the demo
 * launcher is only a reviewer convenience and was otherwise unreachable. This is a
 * small, clearly-labelled affordance — never the door — surfaced on the customer
 * product and in the cockpit so an evaluator can jump between spaces.
 *
 * `floating` pins it to a screen corner (for the full-bleed product host);
 * otherwise it renders inline (e.g. in the cockpit topbar).
 */
export function DemoLauncherLink({
  className,
  floating = false,
}: {
  className?: string;
  floating?: boolean;
}) {
  const t = useTranslations("app");
  const link = (
    <Link
      href="/select-space"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--card)]/70 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)] backdrop-blur transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]",
        className,
      )}
    >
      <FlaskConical className="h-3.5 w-3.5" />
      {t("demoExplore")}
    </Link>
  );
  if (floating) {
    return <div className="fixed bottom-3 left-3 z-40">{link}</div>;
  }
  return link;
}
