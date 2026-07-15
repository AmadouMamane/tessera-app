import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { ComplianceDashboard } from "@/components/compliance/compliance-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { readAgentScope } from "@/lib/agent-scope";
import { loadDeclaredLens } from "@/lib/server/agent-lens";
import { loadFleet } from "@/lib/server/fleet";

interface CompliancePageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: CompliancePageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "compliance" });
  return { title: t("title") };
}

export default async function CompliancePage({ params, searchParams }: CompliancePageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet(locale);
  const t = await getTranslations({ locale, namespace: "compliance" });
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      {/* SLO breach alert LEADS; the dashboard's temporal rail sits directly beneath it;
          the agent-scope context (Vue par agent) renders below the rail via `agentScope`. */}
      <div className="mb-3">
        {/* Regulatory posture is a fleet/framework aggregate (org-wide), so the hero
            reads the FLEET SLO even under an agent filter — never one agent's SLO. */}
        <SignalBreachHero orgWide />
      </div>
      <ComplianceDashboard
        agentScope={
          <GovScopeSection
            fleet={fleet}
            scope={scope}
            locale={locale}
            perAgent={false}
            lens={await loadDeclaredLens("/surveiller/conformite", fleet)}
          />
        }
      />
    </AppShell>
  );
}
