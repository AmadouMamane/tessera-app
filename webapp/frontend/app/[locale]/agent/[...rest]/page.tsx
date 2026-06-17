import { redirect } from "@/i18n/navigation";

import { DEFAULT_AGENT_ID, agentPath } from "@/lib/agent-context";

interface PageProps {
  params: Promise<{ locale: string; rest: string[] }>;
}

// Compat for deep links into the former single-agent section. AGENT leaf pages
// move under the default agent (`/agent/synthese` -> `/agents/support-client/synthese`);
// the Inbox (a-traiter / a-faire) is now GLOBAL, so it redirects to the top level.
const GLOBAL_INBOX = new Set(["a-traiter", "a-faire"]);

export default async function AgentCompatRedirect({ params }: PageProps) {
  const { locale, rest } = await params;
  const path = rest.join("/");
  const href = GLOBAL_INBOX.has(rest[0] ?? "") ? `/${path}` : agentPath(DEFAULT_AGENT_ID, path);
  redirect({ href, locale });
}
