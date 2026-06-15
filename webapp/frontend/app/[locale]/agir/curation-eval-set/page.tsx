import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { CurationOverview } from "@/components/curation/curation-overview";
import { AppShell } from "@/components/layout/app-shell";
import { CurationOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface CurationPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: CurationPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "curation" });
  return { title: t("title") };
}

async function prefetchCuration(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["curation-overview"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/curation`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend curation returned ${response.status}`);
      return CurationOverviewSchema.parse(await response.json());
    },
  });
}

export default async function CurationPage({ params }: CurationPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "curation" });
  const queryClient = new QueryClient();
  try {
    await prefetchCuration(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <CurationOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
