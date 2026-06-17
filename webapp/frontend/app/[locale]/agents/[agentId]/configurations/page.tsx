import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentConfigurations } from "@/components/agent/agent-configurations";
import { AppShell } from "@/components/layout/app-shell";
import { AgentConfigurationsSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentConfigurations" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["agent-configurations"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/agent-configurations`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend agent-configurations returned ${response.status}`);
      return AgentConfigurationsSchema.parse(await response.json());
    },
  });
}

export default async function AgentConfigurationsPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "agentConfigurations" });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell
      title={t("title")}
      contentWidth="full"
      breadcrumb={{ section: t("topbarTitle"), label: t("title") }}
    >
      <HydrationBoundary state={dehydrate(queryClient)}>
        <AgentConfigurations />
      </HydrationBoundary>
    </AppShell>
  );
}
