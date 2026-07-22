import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { ParametersOverview } from "@/components/parameters/parameters-overview";
import { ParametersOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface ParametresPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ParametresPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "parameters" });
  return { title: t("title") };
}

async function prefetchParameters(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    // MUST match the client's key EXACTLY (Insight 175): the client key carries
    // the as-of instant (null = live), so the SSR seed hydrates the live view.
    queryKey: ["parameters-overview", locale, null],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/parameters?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend parameters returned ${response.status}`);
      return ParametersOverviewSchema.parse(await response.json());
    },
  });
}

export default async function ParametresPage({ params }: ParametresPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "parameters" });
  const queryClient = new QueryClient();
  try {
    await prefetchParameters(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <ParametersOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
