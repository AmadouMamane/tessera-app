import type { ReactNode } from "react";

import { redirect } from "@/i18n/navigation";
import { currentRole, hasCockpitAccess } from "@/lib/auth/session";

interface AgentLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string; agentId: string }>;
}

export const dynamic = "force-dynamic";

// Scope layout for the AGENT section. The selected agent is carried in the URL
// (`/agents/<agentId>/...`) and read per-page via `useAgentId()`; this layout
// only gates cockpit access. Fleet/registry validation lands in Phase 1/3.
export default async function AgentLayout({ children, params }: AgentLayoutProps) {
  const { locale } = await params;
  const role = await currentRole();

  if (!hasCockpitAccess(role)) {
    redirect({ href: "/produit", locale });
  }

  return children;
}
