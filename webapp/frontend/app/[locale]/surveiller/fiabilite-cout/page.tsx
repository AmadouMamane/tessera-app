import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { AppShell } from "@/components/layout/app-shell";
import { ReliabilityDashboard } from "@/components/reliability/reliability-dashboard";
import { readAgentScope } from "@/lib/agent-scope";
import { loadFleet } from "@/lib/server/fleet";

interface ReliabilityPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: ReliabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "reliability" });
  return { title: t("title") };
}

export default async function ReliabilityPage({ params, searchParams }: ReliabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet(locale);
  const t = await getTranslations({ locale, namespace: "reliability" });
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <div className="mb-3">
        <GovScopeSection fleet={fleet} scope={scope} locale={locale} signalHero perAgent={false} />
      </div>
      <ReliabilityDashboard />
    </AppShell>
  );
}
