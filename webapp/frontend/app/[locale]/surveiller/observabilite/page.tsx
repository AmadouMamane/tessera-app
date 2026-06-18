import { getTranslations, setRequestLocale } from "next-intl/server";

import { HealthDashboard } from "@/components/health/health-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { readAgentScope } from "@/lib/agent-scope";
import { loadFleet } from "@/lib/server/fleet";

interface HealthPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: HealthPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "health" });
  return { title: t("title") };
}

export default async function HealthPage({ params, searchParams }: HealthPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet();
  const t = await getTranslations({ locale, namespace: "health" });
  return (
    <AppShell title={t("title")} description={t("description")}>
      <div className="mb-3">
        <GovScopeSection fleet={fleet} scope={scope} locale={locale} signalHero />
      </div>
      <HealthDashboard />
    </AppShell>
  );
}
