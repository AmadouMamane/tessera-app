import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { CatalogueConsumers } from "@/components/configurer/catalogue-consumers";
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

async function prefetchIntegrations(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["integrations-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/integrations?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
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
    await prefetchIntegrations(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <IntegrationsOverview />
      </HydrationBoundary>
      {/* Which agents consume each shared tool, and which of them a change here would send
          back through the gate. Written, translated, backed by a live route — and imported by
          nothing until 2026-08-01. */}
      <CatalogueConsumers kind="tools" />
    </AppShell>
  );
}
