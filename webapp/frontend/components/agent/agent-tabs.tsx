"use client";

import {
  BookOpen,
  ClipboardCheck,
  History,
  LayoutDashboard,
  type LucideIcon,
  MessageSquareText,
  ShieldCheck,
  SlidersHorizontal,
  TerminalSquare,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { TabStrip } from "@/components/cockpit/tab-strip";
import { usePathname } from "@/i18n/navigation";
import { type AgentPage, agentPath } from "@/lib/agent-context";
import { useAgentId } from "@/lib/use-agent-id";

import { AgentSwitcher } from "./agent-switcher";

/**
 * Shared command-bar tab strip + agent switcher for the AGENT section. Mounted
 * ONCE by `agents/[agentId]/layout.tsx` so it persists across every sub-page
 * (only the body swaps). The active tab derives from the URL; hrefs are
 * agent-scoped via `agentPath` — no literal `/agents/...` path, no hard-coded id.
 * Renders the shared premium `TabStrip` with the AGENT plane's violet accent.
 * Page-specific actions live in each page's body (until time/scope move to the
 * URL and they move to a parallel `@actions` slot).
 */
const TABS: ReadonlyArray<{ page: AgentPage; labelKey: string; icon: LucideIcon }> = [
  { page: "synthese", labelKey: "item.synthese", icon: LayoutDashboard },
  { page: "configurations", labelKey: "item.configurations", icon: SlidersHorizontal },
  { page: "connaissances", labelKey: "item.connaissances", icon: BookOpen },
  { page: "garde-fous", labelKey: "item.agentGuardrails", icon: ShieldCheck },
  { page: "prompts", labelKey: "item.prompts", icon: MessageSquareText },
  { page: "evaluations", labelKey: "item.evaluations", icon: ClipboardCheck },
  { page: "console", labelKey: "item.console", icon: TerminalSquare },
  { page: "historique", labelKey: "item.historique", icon: History },
];

export function AgentTabs() {
  const tn = useTranslations("nav");
  const pathname = usePathname();
  const agentId = useAgentId();
  const active =
    TABS.find((tab) => {
      const href = agentPath(agentId, tab.page);
      return pathname === href || pathname.startsWith(`${href}/`);
    })?.page ?? "synthese";
  return (
    <div className="flex flex-wrap items-center gap-3">
      <AgentSwitcher />
      <TabStrip
        accent="violet"
        active={active}
        className="min-w-0 flex-1"
        items={TABS.map((tab) => ({
          key: tab.page,
          label: tn(tab.labelKey),
          icon: tab.icon,
          href: agentPath(agentId, tab.page),
        }))}
      />
    </div>
  );
}
