import type { ReactNode } from "react";

import { AgentTabs } from "@/components/agent/agent-tabs";
import { redirect } from "@/i18n/navigation";
import { currentRole, hasCockpitAccess } from "@/lib/auth/session";

interface AgentLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string; agentId: string }>;
}

export const dynamic = "force-dynamic";

// Scope layout for the AGENT section. The selected agent is carried in the URL
// (`/agents/<agentId>/...`) and read per-page via `useAgentId()`. This layout
// gates cockpit access AND owns the per-agent command-bar (AgentTabs + switcher),
// so the bar persists across every sub-page (only the body swaps). Page actions
// stay in each page's body for now (until time/scope move to the URL, after which
// they move to a parallel `@actions` slot).
export default async function AgentLayout({ children, params }: AgentLayoutProps) {
  const { locale } = await params;
  const role = await currentRole();

  if (!hasCockpitAccess(role)) {
    redirect({ href: "/produit", locale });
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <AgentTabs />
      {children}
    </div>
  );
}
