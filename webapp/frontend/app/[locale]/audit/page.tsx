import { HydrationBoundary, QueryClient, dehydrate } from "@tanstack/react-query";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuditTable } from "@/components/audit/audit-table";
import { OperatorLocked } from "@/components/auth/operator-locked";
import { AppShell } from "@/components/layout/app-shell";
import { AuditOverviewSchema, AuditPageSchema } from "@/lib/api/schemas";
import { currentRole, isOperator } from "@/lib/auth/session";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

// The operator gate reads the session (cookies) per request — never prerender.
export const dynamic = "force-dynamic";

interface AuditPageProps {
  params: Promise<{ locale: string }>;
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

export default async function AuditPage({ params }: AuditPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "audit" });
  const role = await currentRole();
  const window = initialAuditWindow();
  const queryClient = new QueryClient();

  if (isOperator(role)) {
    try {
      await prefetchAuditWindow(queryClient, window);
    } catch {
      // Keep the page resilient: the client-side queries will surface backend failures.
    }
  }

  return (
    <AppShell title={t("title")} description={t("description")} contentWidth="full">
      {isOperator(role) ? (
        <HydrationBoundary state={dehydrate(queryClient)}>
          <AuditTable initialWindow={window} />
        </HydrationBoundary>
      ) : (
        <OperatorLocked locale={locale} />
      )}
    </AppShell>
  );
}
