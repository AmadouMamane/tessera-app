"use client";

import { useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { type AgentPage, agentPath } from "@/lib/agent-context";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";

import { AgentSwitcher } from "./agent-switcher";

/**
 * Shared command-bar tab strip + agent switcher for the AGENT section. Mounted
 * ONCE by `agents/[agentId]/layout.tsx` so it persists across every sub-page
 * (only the body swaps). The active tab derives from the URL; hrefs are
 * agent-scoped via `agentPath` — no literal `/agents/...` path, no hard-coded id.
 * Page-specific actions live in each page's body (until time/scope move to the
 * URL and they move to a parallel `@actions` slot).
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

export function AgentTabs() {
  const tn = useTranslations("nav");
  const pathname = usePathname();
  const agentId = useAgentId();
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-[var(--tessera-border)] pb-1.5">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <AgentSwitcher />
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
      </div>
    </div>
  );
}
