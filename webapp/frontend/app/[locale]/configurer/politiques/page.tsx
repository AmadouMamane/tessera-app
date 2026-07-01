import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { PoliciesOverview } from "@/components/policies/policies-overview";
import { PoliciesOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PoliciesPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PoliciesPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "policies" });
  return { title: t("title") };
}

async function prefetchPolicies(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["policies-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/policies?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend policies returned ${response.status}`);
      return PoliciesOverviewSchema.parse(await response.json());
    },
  });
}

export default async function PoliciesPage({ params }: PoliciesPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "policies" });
  const queryClient = new QueryClient();
  try {
    await prefetchPolicies(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <PoliciesOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
