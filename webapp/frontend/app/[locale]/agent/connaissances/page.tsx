import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentConnaissances } from "@/components/agent/agent-connaissances";
import { AppShell } from "@/components/layout/app-shell";
import { AgentConnaissancesSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentConnaissances" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["agent-connaissances", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/agent-connaissances?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend agent-connaissances returned ${response.status}`);
      return AgentConnaissancesSchema.parse(await response.json());
    },
  });
}

export default async function AgentConnaissancesPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "agentConnaissances" });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <AgentConnaissances />
      </HydrationBoundary>
    </AppShell>
  );
}
