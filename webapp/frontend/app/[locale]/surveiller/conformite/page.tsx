import { getTranslations, setRequestLocale } from "next-intl/server";

import { ComplianceDashboard } from "@/components/compliance/compliance-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { readAgentScope } from "@/lib/agent-scope";
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
  const fleet = await loadFleet();
  const t = await getTranslations({ locale, namespace: "compliance" });
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <div className="mb-3">
        <GovScopeSection fleet={fleet} scope={scope} locale={locale} />
      </div>
      <ComplianceDashboard />
    </AppShell>
  );
}
