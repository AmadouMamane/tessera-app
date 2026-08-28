import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AccessOverview } from "@/components/access/access-overview";
import { RbacAgentMatrix } from "@/components/access/rbac-agent-matrix";
import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
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

async function prefetchAccess(queryClient: QueryClient, locale: string) {
  await queryClient.prefetchQuery({
    queryKey: ["access-overview", locale],
    queryFn: async () => {
      const response = await fetch(
        `${backendUrl()}/observability/access?lang=${encodeURIComponent(locale)}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
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
    await prefetchAccess(queryClient, locale);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <Suspense fallback={null}>
        <div className="flex flex-wrap items-center gap-3">
          <AgentScopeFilter />
          <span className="text-xs text-[var(--tessera-text-muted)]">{t("agentFilterHint")}</span>
        </div>
        <div>
          <RbacAgentMatrix />
        </div>
        <HydrationBoundary state={dehydrate(queryClient)}>
          <AccessOverview />
        </HydrationBoundary>
      </Suspense>
    </AppShell>
  );
}
