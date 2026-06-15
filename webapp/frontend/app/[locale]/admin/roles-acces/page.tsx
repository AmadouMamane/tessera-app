import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AccessOverview } from "@/components/access/access-overview";
import { AppShell } from "@/components/layout/app-shell";
import { AccessOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface AccessPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: AccessPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "roles" });
  return { title: t("title") };
}

async function prefetchAccess(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["access-overview"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/access`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend access returned ${response.status}`);
      return AccessOverviewSchema.parse(await response.json());
    },
  });
}

export default async function AccessPage({ params }: AccessPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "roles" });
  const queryClient = new QueryClient();
  try {
    await prefetchAccess(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <AccessOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
