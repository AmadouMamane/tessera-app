import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { InboxOverview } from "@/components/inbox/inbox-overview";
import { AppShell } from "@/components/layout/app-shell";
import { InboxOverviewSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface InboxPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: InboxPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "inbox" });
  return { title: t("title") };
}

async function prefetchInbox(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["inbox-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/inbox?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend inbox returned ${response.status}`);
      return InboxOverviewSchema.parse(await response.json());
    },
  });
}

export default async function InboxPage({ params }: InboxPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "inbox" });
  const queryClient = new QueryClient();
  try {
    await prefetchInbox(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <InboxOverview />
      </HydrationBoundary>
    </AppShell>
  );
}
