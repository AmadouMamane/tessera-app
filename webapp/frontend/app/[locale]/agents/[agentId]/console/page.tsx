import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentConsole } from "@/components/agent/agent-console";
import { AgentConsoleSchema } from "@/lib/api/schemas";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "agentConsole" });
  return { title: t("title") };
}

// ADR 0019 §I2 — the console is agent-scoped: prefetch the binding-gated payload for
// THIS agent so SSR and the client query share a key and the honest-empty vs interactive
// shape is decided server-side (no chattable-by-default flash).
async function prefetch(queryClient: QueryClient, locale: string, agentId: string) {
  await queryClient.prefetchQuery({
    queryKey: ["agent-console", locale, agentId],
    queryFn: async () => {
      const params = new URLSearchParams({ lang: locale, agent: agentId });
      const response = await fetch(
        `${backendUrl()}/observability/agent-console?${params.toString()}`,
        {
          cache: "no-store",
          headers: backendHeaders({ Accept: "application/json" }),
        },
      );
      if (!response.ok) throw new Error(`Backend agent-console returned ${response.status}`);
      return AgentConsoleSchema.parse(await response.json());
    },
  });
}

export default async function AgentConsolePage({ params }: PageProps) {
  const { locale, agentId } = await params;
  setRequestLocale(locale);
  const queryClient = new QueryClient();
  try {
    await prefetch(queryClient, locale, agentId);
  } catch {
    // Keep the page resilient: the client query will surface backend failures.
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <AgentConsole />
    </HydrationBoundary>
  );
}
