import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { HealthDashboard } from "@/components/health/health-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { readAgentScope } from "@/lib/agent-scope";
import { loadDeclaredLens } from "@/lib/server/agent-lens";
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
  const sp = await searchParams;
  const scope = readAgentScope(sp);
  const fleet = await loadFleet(locale, sp);
  const t = await getTranslations({ locale, namespace: "health" });
  // The page's own per-agent question: behavioural anomalies and tool-call schema
  // conformance — the telemetry facts measured to deposit per agent. Pipeline health
  // (collector, Langfuse traces) has no served per-agent substrate and stays in the body.
  const lens = await loadDeclaredLens("/surveiller/observabilite", fleet);
  return (
    <AppShell title={t("title")} description={t("description")}>
      <div>
        <GovScopeSection
          fleet={fleet}
          scope={scope}
          locale={locale}
          signalHero
          perAgent={false}
          lens={lens}
        />
      </div>
      <HealthDashboard />
    </AppShell>
  );
}
