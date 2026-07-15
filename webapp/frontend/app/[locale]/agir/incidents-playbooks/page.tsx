import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { IncidentsOverview } from "@/components/incidents/incidents-overview";
import { AppShell } from "@/components/layout/app-shell";
import { IncidentsOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface IncidentsPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: IncidentsPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "incidents" });
  return { title: t("title") };
}

async function prefetchIncidents(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["incidents-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/incidents?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend incidents returned ${response.status}`);
      return IncidentsOverviewSchema.parse(await response.json());
    },
  });
}

export default async function IncidentsPage({ params }: IncidentsPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "incidents" });
  const queryClient = new QueryClient();
  try {
    await prefetchIncidents(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <IncidentsOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
