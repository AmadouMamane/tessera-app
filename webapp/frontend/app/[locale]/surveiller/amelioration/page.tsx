import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { ImprovementDashboard } from "@/components/improvement/improvement-dashboard";
import { AppShell } from "@/components/layout/app-shell";
import { readAgentScope } from "@/lib/agent-scope";
import { loadDomainLens } from "@/lib/server/agent-lens";
import { loadFleet } from "@/lib/server/fleet";

interface ImprovementPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: ImprovementPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "improvement" });
  return { title: t("title") };
}

export default async function ImprovementPage({ params, searchParams }: ImprovementPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet(locale);
  const t = await getTranslations({ locale, namespace: "improvement" });
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <div className="mb-3">
        {/* Product decision (2026-07-15): no per-agent improvement signal exists, so the page
            reuses the QUALITY lens — the per-agent regression facts (blocking T1, gate,
            eval freshness) are the improvement facts that actually exist. */}
        <GovScopeSection
          fleet={fleet}
          scope={scope}
          locale={locale}
          signalHero
          perAgent={false}
          lens={await loadDomainLens(fleet, "improvement")}
        />
      </div>
      <ImprovementDashboard />
    </AppShell>
  );
}
