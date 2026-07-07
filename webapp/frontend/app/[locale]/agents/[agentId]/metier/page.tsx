import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentMetier } from "@/components/agent/agent-metier";
import { BusinessCapabilitiesResponseSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentMetier" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient, agentId: string) {
  await queryClient.prefetchQuery({
    queryKey: ["business-capabilities", agentId],
    queryFn: async () => {
      const params = new URLSearchParams({ agent: agentId });
      const response = await fetch(
        `${backendUrl()}/observability/business/capabilities?${params}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) {
        throw new Error(`Backend business-capabilities returned ${response.status}`);
      }
      return BusinessCapabilitiesResponseSchema.parse(await response.json());
    },
  });
}

export default async function AgentMetierPage({ params }: PageProps) {
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
      <AgentMetier />
    </HydrationBoundary>
  );
}
