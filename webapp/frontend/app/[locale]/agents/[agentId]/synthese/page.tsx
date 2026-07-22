import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentSynthese } from "@/components/agent/agent-synthese";
import { AgentSyntheseSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentSynthese" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient, agentId: string) {
  await queryClient.prefetchQuery({
    // The trailing null is the client's `asOf ?? null` — the SSR seed must live
    // under the exact Live key or hydration misses it (Insight 175).
    queryKey: ["agent-synthese", agentId, "d7", null],
    queryFn: async () => {
      const params = new URLSearchParams({ period: "d7", agent_id: agentId });
      const response = await fetch(`${backendUrl()}/observability/agent-synthese?${params}`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend agent-synthese returned ${response.status}`);
      return AgentSyntheseSchema.parse(await response.json());
    },
  });
}

export default async function AgentSynthesePage({ params }: PageProps) {
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
      <AgentSynthese />
    </HydrationBoundary>
  );
}
