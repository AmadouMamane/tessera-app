import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AssistantOverview } from "@/components/assistant/assistant-overview";
import { AppShell } from "@/components/layout/app-shell";
import { AssistantOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface AssistantPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: AssistantPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "assistant" });
  return { title: t("title") };
}

async function prefetchAssistant(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["assistant-overview"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/assistant`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend assistant returned ${response.status}`);
      return AssistantOverviewSchema.parse(await response.json());
    },
  });
}

export default async function AssistantPage({ params }: AssistantPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "assistant" });
  const queryClient = new QueryClient();
  try {
    await prefetchAssistant(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <AssistantOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
