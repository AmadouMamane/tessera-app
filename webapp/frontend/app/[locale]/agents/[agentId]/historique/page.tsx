import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentHistorique } from "@/components/agent/agent-historique";
import { AgentHistoriqueSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentHistorique" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient, agentId: string) {
  await queryClient.prefetchQuery({
    queryKey: ["agent-historique", agentId],
    queryFn: async () => {
      const q = `?agent_id=${encodeURIComponent(agentId)}`;
      const response = await fetch(`${backendUrl()}/observability/agent-historique${q}`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend agent-historique returned ${response.status}`);
      return AgentHistoriqueSchema.parse(await response.json());
    },
  });
}

export default async function AgentHistoriquePage({ params }: PageProps) {
  const { locale, agentId } = await params;
  setRequestLocale(locale);
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient, agentId);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <AgentHistorique />
    </HydrationBoundary>
  );
}
