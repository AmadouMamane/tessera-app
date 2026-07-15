import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { ReplayOverview } from "@/components/replay/replay-overview";
import { ReplayShadowOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface ReplayPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ReplayPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "replay" });
  return { title: t("title") };
}

async function prefetchReplay(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["replay-shadow-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/replay-shadow?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend replay-shadow returned ${response.status}`);
      return ReplayShadowOverviewSchema.parse(await response.json());
    },
  });
}

export default async function ReplayPage({ params }: ReplayPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "replay" });
  const queryClient = new QueryClient();
  try {
    await prefetchReplay(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <ReplayOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
