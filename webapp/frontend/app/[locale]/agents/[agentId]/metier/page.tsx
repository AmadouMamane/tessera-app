import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentMetier } from "@/components/agent/agent-metier";
import { BusinessCapabilitiesResponseSchema } from "@/lib/api/schemas";
import { resolveMetierAsOf } from "@/lib/metier-temporal";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstParam(value: string | string[] | undefined): string | null {
  return Array.isArray(value) ? (value[0] ?? null) : (value ?? null);
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentMetier" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient, agentId: string, asOf: string | null) {
  await queryClient.prefetchQuery({
    // Key mirrors the client (BR-01 §5): the deep-linked as-of is part of the read identity.
    queryKey: ["business-capabilities", agentId, asOf],
    queryFn: async () => {
      const params = new URLSearchParams({ agent: agentId });
      if (asOf) params.set("at", asOf);
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

export default async function AgentMetierPage({ params, searchParams }: PageProps) {
  const { locale, agentId } = await params;
  const sp = await searchParams;
  setRequestLocale(locale);
  const asOf = resolveMetierAsOf({ asof: firstParam(sp.asof), at: firstParam(sp.at) });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient, agentId, asOf);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <AgentMetier />
    </HydrationBoundary>
  );
}
