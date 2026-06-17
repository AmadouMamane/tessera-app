"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Link, usePathname } from "@/i18n/navigation";
import { type AgentPage, agentPath } from "@/lib/agent-context";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";

/**
 * Shared command-bar tab strip for the AGENT section (same tabs as the
 * Synthese overview). Each page renders it with its own action buttons on the
 * right via the `actions` slot. Hrefs are agent-scoped via `agentPath` — no
 * literal `/agents/...` path and no hard-coded agent id.
 */
const TABS: ReadonlyArray<{ page: AgentPage; labelKey: string }> = [
  { page: "synthese", labelKey: "item.synthese" },
  { page: "configurations", labelKey: "item.configurations" },
  { page: "connaissances", labelKey: "item.connaissances" },
  { page: "garde-fous", labelKey: "item.agentGuardrails" },
  { page: "prompts", labelKey: "item.prompts" },
  { page: "evaluations", labelKey: "item.evaluations" },
  { page: "console", labelKey: "item.console" },
  { page: "historique", labelKey: "item.historique" },
];

export function AgentTabs({ actions }: { actions?: ReactNode }) {
  const tn = useTranslations("nav");
  const pathname = usePathname();
  const agentId = useAgentId();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--tessera-border)] pb-1.5">
      <nav className="flex min-w-0 flex-wrap items-center gap-1">
        {TABS.map((tab) => {
          const href = agentPath(agentId, tab.page);
          const active = pathname === href || pathname.startsWith(`${href}/`);
          return (
            <Link
              key={tab.page}
              href={href}
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
