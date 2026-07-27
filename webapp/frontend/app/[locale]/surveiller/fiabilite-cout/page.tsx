import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { AppShell } from "@/components/layout/app-shell";
import { ReliabilityDashboard } from "@/components/reliability/reliability-dashboard";
import { readAgentScope } from "@/lib/agent-scope";

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
  const sp = await searchParams;
  const scope = readAgentScope(sp);
  const t = await getTranslations({ locale, namespace: "reliability" });
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <div>
        <GovScopeSection
          route="/surveiller/fiabilite-cout"
          scope={scope}
          locale={locale}
          searchParams={sp}
          signalHero
          perAgent={false}
        />
      </div>
      <ReliabilityDashboard />
    </AppShell>
  );
}
