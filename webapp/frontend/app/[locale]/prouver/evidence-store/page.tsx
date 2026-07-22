import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { ProofsOverview } from "@/components/proofs/proofs-overview";
import { ProofsOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface ProofsPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ProofsPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "proofs" });
  return { title: t("title") };
}

async function prefetchProofs(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    // MUST match the client's key EXACTLY (Insight 175): the client key carries
    // the as-of instant (null = live), so the SSR seed hydrates the live view.
    queryKey: ["proofs-overview", locale, null],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/proofs?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend proofs returned ${response.status}`);
      return ProofsOverviewSchema.parse(await response.json());
    },
  });
}

export default async function ProofsPage({ params }: ProofsPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "proofs" });
  const queryClient = new QueryClient();
  try {
    await prefetchProofs(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <ProofsOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
