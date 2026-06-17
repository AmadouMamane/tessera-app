import { redirect } from "@/i18n/navigation";

import { DEFAULT_AGENT_ID, agentPath } from "@/lib/agent-context";

interface PageProps {
  params: Promise<{ locale: string }>;
}

// Compat: the AGENT section moved to `/agents/<agentId>/*` (multi-agent
// foundation). `/agent` lands on the default agent's Synthese.
export default async function RedirectPage({ params }: PageProps) {
  const { locale } = await params;
  redirect({ href: agentPath(DEFAULT_AGENT_ID, "synthese"), locale });
}
