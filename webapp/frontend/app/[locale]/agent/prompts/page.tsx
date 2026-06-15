import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentPrompts } from "@/components/agent/agent-prompts";
import { AppShell } from "@/components/layout/app-shell";
import { AgentPromptsSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentPrompts" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["agent-prompts"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/agent-prompts`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend agent-prompts returned ${response.status}`);
      return AgentPromptsSchema.parse(await response.json());
    },
  });
}

export default async function AgentPromptsPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "agentPrompts" });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <AgentPrompts />
      </HydrationBoundary>
    </AppShell>
  );
}
