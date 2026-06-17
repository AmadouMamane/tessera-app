import { redirect } from "@/i18n/navigation";

import { agentPath } from "@/lib/agent-context";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
}

// `/agents/<agentId>` lands on that agent's Synthese (the section's primary).
export default async function AgentRootPage({ params }: PageProps) {
  const { locale, agentId } = await params;
  redirect({ href: agentPath(agentId, "synthese"), locale });
}
