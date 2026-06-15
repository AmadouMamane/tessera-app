"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/**
 * Shared command-bar tab strip for the AGENT section (same tabs as the
 * Synthese overview). Each page renders it with its own action buttons on the
 * right via the `actions` slot.
 */
const TABS = [
  { href: "/agent/synthese", labelKey: "item.synthese" },
  { href: "/agent/configurations", labelKey: "item.configurations" },
  { href: "/agent/connaissances", labelKey: "item.connaissances" },
  { href: "/agent/garde-fous", labelKey: "item.agentGuardrails" },
  { href: "/agent/prompts", labelKey: "item.prompts" },
  { href: "/agent/evaluations", labelKey: "item.evaluations" },
  { href: "/agent/console", labelKey: "item.console" },
  { href: "/agent/historique", labelKey: "item.historique" },
] as const;

export function AgentTabs({ actions }: { actions?: ReactNode }) {
  const tn = useTranslations("nav");
  const pathname = usePathname();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--tessera-border)] pb-1.5">
      <nav className="flex min-w-0 flex-wrap items-center gap-1">
        {TABS.map((tab) => {
          const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "-mb-px shrink-0 border-b-2 px-3 py-2 text-[0.8rem] transition-colors",
                active
                  ? "border-[#6d4aed] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tn(tab.labelKey)}
            </Link>
          );
        })}
      </nav>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
