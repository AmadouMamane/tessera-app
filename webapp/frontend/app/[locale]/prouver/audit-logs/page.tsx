import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ReactNode } from "react";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { AuditTable } from "@/components/audit/audit-table";
import { OperatorLocked } from "@/components/auth/operator-locked";
import { AppShell } from "@/components/layout/app-shell";
import { readAgentScope } from "@/lib/agent-scope";
import { AuditOverviewSchema, AuditPageSchema } from "@/lib/api/schemas";
import { currentRole, isOperator } from "@/lib/auth/session";
import { loadDeclaredLens } from "@/lib/server/agent-lens";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { loadFleet } from "@/lib/server/fleet";

// The operator gate reads the session (cookies) per request — never prerender.
export const dynamic = "force-dynamic";

interface AuditPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const INITIAL_PAGE_SIZE = 9;

function initialAuditWindow() {
  const until = new Date();
  const since = new Date(until.getTime() - 7 * 24 * 60 * 60 * 1000);
  return { preset: "7d" as const, since: since.toISOString(), until: until.toISOString() };
}

async function fetchBackendJson(path: string) {
  const response = await fetch(`${backendUrl()}${path}`, {
    cache: "no-store",
    headers: backendHeaders({ Accept: "application/json" }),
  });
  if (!response.ok) throw new Error(`Backend ${path} returned ${response.status}`);
  return response.json();
}

async function prefetchAuditWindow(
  queryClient: QueryClient,
  window: ReturnType<typeof initialAuditWindow>,
) {
  const filters = {
    outcome: undefined,
    eventType: undefined,
    actorRole: undefined,
    scope: undefined,
    query: undefined,
    since: window.since,
    until: window.until,
  };
  const overviewParams = new URLSearchParams({ since: window.since, until: window.until });
  const pageParams = new URLSearchParams({
    cursor: "0",
    limit: String(INITIAL_PAGE_SIZE),
    since: window.since,
    until: window.until,
  });

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: ["audit-overview", filters],
      queryFn: async () =>
        AuditOverviewSchema.parse(await fetchBackendJson(`/audit/overview?${overviewParams}`)),
    }),
    queryClient.prefetchQuery({
      queryKey: ["audit", 0, filters],
      queryFn: async () => AuditPageSchema.parse(await fetchBackendJson(`/audit?${pageParams}`)),
    }),
  ]);
}

export async function generateMetadata({ params }: AuditPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "audit" });
  return { title: t("title") };
}

export default async function AuditPage({ params, searchParams }: AuditPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "audit" });
  const role = await currentRole();
  const window = initialAuditWindow();
  const queryClient = new QueryClient();

  const operator = isOperator(role);
  let scope = "all";
  let proofSection: ReactNode = null;
  if (operator) {
    try {
      await prefetchAuditWindow(queryClient, window);
    } catch {
      // Keep the page resilient: the client-side queries will surface backend failures.
    }
    // The page's own per-agent question: each agent's proof — governed acts and ledger
    // entries (measured to deposit per agent). Chain INTEGRITY stays org-wide in the body.
    scope = readAgentScope(await searchParams);
    const fleet = await loadFleet(locale);
    const lens = await loadDeclaredLens("/prouver/audit-logs", fleet);
    proofSection = <AgentBreakdown fleet={fleet} scope={scope} locale={locale} lens={lens} />;
  }

  return (
    <AppShell title={t("title")} description={t("description")}>
      {operator ? (
        <HydrationBoundary state={dehydrate(queryClient)}>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <AgentScopeFilter />
            <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">
              {t("agentFilterHint")}
            </span>
          </div>
          <div className="mb-3">{proofSection}</div>
          <AuditTable initialWindow={window} />
        </HydrationBoundary>
      ) : (
        <OperatorLocked locale={locale} />
      )}
    </AppShell>
  );
}
