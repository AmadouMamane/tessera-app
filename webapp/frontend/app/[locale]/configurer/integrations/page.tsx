import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { IntegrationsOverview } from "@/components/integrations/integrations-overview";
import { AppShell } from "@/components/layout/app-shell";
import { IntegrationsOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface IntegrationsPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: IntegrationsPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "integrations" });
  return { title: t("title") };
}

async function prefetchIntegrations(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["integrations-overview"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/integrations`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend integrations returned ${response.status}`);
      return IntegrationsOverviewSchema.parse(await response.json());
    },
  });
}

export default async function IntegrationsPage({ params }: IntegrationsPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "integrations" });
  const queryClient = new QueryClient();
  try {
    await prefetchIntegrations(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <IntegrationsOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
