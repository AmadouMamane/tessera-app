import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { SystemProfile } from "@/components/system/system-profile";
import { SystemProfileSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface SystemPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: SystemPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "systemProfile" });
  return { title: t("title") };
}

async function prefetchSystem(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["system-profile", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/system-profile?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend system-profile returned ${response.status}`);
      return SystemProfileSchema.parse(await response.json());
    },
  });
}

export default async function SystemPage({ params }: SystemPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "systemProfile" });
  const queryClient = new QueryClient();
  try {
    await prefetchSystem(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <HydrationBoundary state={dehydrate(queryClient)}>
        <SystemProfile />
      </HydrationBoundary>
    </AppShell>
  );
}
