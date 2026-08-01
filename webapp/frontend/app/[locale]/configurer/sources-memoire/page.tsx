import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { CatalogueConsumers } from "@/components/configurer/catalogue-consumers";
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

async function prefetchSources(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["sources-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/sources?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
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
    await prefetchSources(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <Suspense fallback={null}>
          <SourcesOverview />
          {/* The inverse of the AGENT instance binding: which agents consume each
            shared item, and which of them a change here would send back through the
            gate. Written, translated (`usedBy.*`), backed by a live route — and
            imported by nothing until 2026-08-01. This page already rendered
            `usedBy.hint` above, so the panel was designed for it and simply never
            mounted. */}
          <CatalogueConsumers kind="knowledge" />
        </Suspense>
      </HydrationBoundary>
    </AppShell>
  );
}
