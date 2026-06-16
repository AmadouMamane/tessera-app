import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { EtatADate } from "@/components/proofs/etat-a-date";
import { EtatADateSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "etatADate" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["etat-a-date", null],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/etat-a-date`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend etat-a-date returned ${response.status}`);
      return EtatADateSchema.parse(await response.json());
    },
  });
}

export default async function EtatADatePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "etatADate" });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <EtatADate />
      </HydrationBoundary>
    </AppShell>
  );
}
