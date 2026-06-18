import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { readAgentScope } from "@/lib/agent-scope";
import { loadFleet } from "@/lib/server/fleet";
import { ReplayOverview } from "@/components/replay/replay-overview";
import { ReplayShadowOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface ReplayPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: ReplayPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "replay" });
  return { title: t("title") };
}

async function prefetchReplay(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["replay-shadow-overview"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/replay-shadow`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend replay-shadow returned ${response.status}`);
      return ReplayShadowOverviewSchema.parse(await response.json());
    },
  });
}

export default async function ReplayPage({ params, searchParams }: ReplayPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet();
  const t = await getTranslations({ locale, namespace: "replay" });
  const queryClient = new QueryClient();
  try {
    await prefetchReplay(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <div className="mb-3">
        <GovScopeSection fleet={fleet} scope={scope} locale={locale} />
      </div>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <ReplayOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
