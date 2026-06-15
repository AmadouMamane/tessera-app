import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { SignalCatalogue } from "@/components/signals/signal-catalogue";
import { SignalCatalogueSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface SignalsPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: SignalsPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "signalCatalogue" });
  return { title: t("title") };
}

async function prefetchSignals(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["signal-catalogue"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/signal-catalogue`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend signal-catalogue returned ${response.status}`);
      return SignalCatalogueSchema.parse(await response.json());
    },
  });
}

export default async function SignalsPage({ params }: SignalsPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "signalCatalogue" });
  const queryClient = new QueryClient();
  try {
    await prefetchSignals(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <SignalCatalogue />
      </HydrationBoundary>
    </AppShell>
  );
}
