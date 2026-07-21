import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { EtatADate } from "@/components/proofs/etat-a-date";
import { EtatADateSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/** First value of a (possibly repeated) query param, or null. */
function one(value: string | string[] | undefined): string | null {
  return (Array.isArray(value) ? value[0] : value) || null;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "etatADate" });
  return { title: t("title") };
}

async function prefetch(
  queryClient: QueryClient,
  locale: string,
  asOf: string | null,
  sources: string | null,
  agentScope: string | null,
) {
  await queryClient.prefetchQuery({
    // Must mirror the CLIENT key exactly ([base, asOf, sources, agentScope, locale])
    // or the hydration hit silently misses and every visit pays a slow client fetch.
    // The deep-link params are honoured here so a shared `?asof=` URL hydrates
    // the reconstruction at T, not the live view.
    queryKey: ["etat-a-date", asOf, sources, agentScope, locale],
    queryFn: async () => {
      const params = new URLSearchParams({ lang: locale });
      if (asOf) params.set("as_of", asOf);
      if (sources) params.set("sources", sources);
      if (agentScope) params.set("agent", agentScope);
      const response = await fetch(`${backendUrl()}/observability/etat-a-date?${params}`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend etat-a-date returned ${response.status}`);
      return EtatADateSchema.parse(await response.json());
    },
  });
}

export default async function EtatADatePage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  const query = await searchParams;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "etatADate" });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient, locale, one(query.asof), one(query.sources), one(query.agent));
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <Suspense fallback={null}>
          <EtatADate />
        </Suspense>
      </HydrationBoundary>
    </AppShell>
  );
}
