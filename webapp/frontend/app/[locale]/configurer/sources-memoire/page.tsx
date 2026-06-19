import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { SourcesOverview } from "@/components/sources/sources-overview";
import { SourcesOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface SourcesPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: SourcesPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "sources" });
  return { title: t("title") };
}

async function prefetchSources(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["sources-overview"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/sources`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend sources returned ${response.status}`);
      return SourcesOverviewSchema.parse(await response.json());
    },
  });
}

export default async function SourcesPage({ params }: SourcesPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "sources" });
  const queryClient = new QueryClient();
  try {
    await prefetchSources(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <SourcesOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
