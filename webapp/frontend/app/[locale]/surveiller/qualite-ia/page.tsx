import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { AppShell } from "@/components/layout/app-shell";
import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";
import { readAgentScope } from "@/lib/agent-scope";
import { loadFleet } from "@/lib/server/fleet";

interface ObservabilityPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "quality" });
  return { title: t("title") };
}

export default async function ObservabilityPage({ params, searchParams }: ObservabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "quality" });
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet();
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <div className="mb-3">
        <GovScopeSection fleet={fleet} scope={scope} locale={locale} />
      </div>
      <ObservabilityDashboard />
    </AppShell>
  );
}
