import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { IncidentsOverview } from "@/components/incidents/incidents-overview";
import { AppShell } from "@/components/layout/app-shell";
import { readAgentScope } from "@/lib/agent-scope";
import { IncidentsOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { loadFleet } from "@/lib/server/fleet";

interface IncidentsPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
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

export default async function IncidentsPage({ params, searchParams }: IncidentsPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet(locale);
  const t = await getTranslations({ locale, namespace: "incidents" });
  const queryClient = new QueryClient();
  try {
    await prefetchIncidents(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <div className="mb-3">
        <GovScopeSection fleet={fleet} scope={scope} locale={locale} perAgent={false} />
      </div>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <IncidentsOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
