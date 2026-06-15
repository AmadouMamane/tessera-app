import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentConsole } from "@/components/agent/agent-console";
import { AppShell } from "@/components/layout/app-shell";
import { AgentConsoleSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentConsole" });
  return { title: t("title") };
}

async function prefetch(queryClient: QueryClient) {
  await queryClient.prefetchQuery({
    queryKey: ["agent-console"],
    queryFn: async () => {
      const response = await fetch(`${backendUrl()}/observability/agent-console`, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!response.ok) throw new Error(`Backend agent-console returned ${response.status}`);
      return AgentConsoleSchema.parse(await response.json());
    },
  });
}

export default async function AgentConsolePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "agentConsole" });
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <HydrationBoundary state={dehydrate(queryClient)}>
        <AgentConsole />
      </HydrationBoundary>
    </AppShell>
  );
}
