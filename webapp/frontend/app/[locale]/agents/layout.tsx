"use client";

import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { usePathname } from "@/i18n/navigation";
import { agentAreaHeaderNamespace } from "@/lib/agent-context";

/**
 * AGENT-area chrome, mounted ONCE. The cockpit shell (settled sidebar + global
 * topbar) lives here so it stays immobile across the fleet and every agent
 * sub-page — only the body swaps (true SPA navigation, no reload). The topbar
 * title/subtitle derive from the URL via the route→namespace registry, never
 * from page-local state (`ui-contract.md`: time/scope are URL-carried, not page).
 *
 * The per-agent command-bar (AgentTabs) is added by the nested
 * `agents/[agentId]/layout.tsx`; this layer owns only the shared chrome.
 */
export default function AgentsAreaLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const t = useTranslations();
  const ns = agentAreaHeaderNamespace(pathname);
  const title = t.has(`${ns}.title`) ? t(`${ns}.title`) : "";
  const subtitle = t.has(`${ns}.subtitle`) ? t(`${ns}.subtitle`) : undefined;

  return (
    <AppShell title={title} description={subtitle} contentWidth="full">
      {children}
    </AppShell>
  );
}
