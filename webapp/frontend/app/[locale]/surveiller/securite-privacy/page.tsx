import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { AppShell } from "@/components/layout/app-shell";
import { SecurityDashboard } from "@/components/security/security-dashboard";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { readAgentScope } from "@/lib/agent-scope";
import { loadDeclaredLens } from "@/lib/server/agent-lens";
import { loadFleet } from "@/lib/server/fleet";

interface SecurityPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: SecurityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "security" });
  return { title: t("title") };
}

export default async function SecurityPage({ params, searchParams }: SecurityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "security" });
  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet(locale);
  // The page's own per-agent question: PII leaks, toxicity, guard denials — the security
  // facts the spine deposits per agent. Org-wide probes (guard efficacy, injection bypass)
  // stay in the page body; they have no per-agent substrate and get no column.
  const lens = await loadDeclaredLens("/surveiller/securite-privacy", fleet);
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      {/* SLO breach alert LEADS; the dashboard's temporal rail sits directly beneath it;
          the agent-scope context renders below the rail via `agentScope`. */}
      <div className="mb-3">
        <SignalBreachHero />
      </div>
      <SecurityDashboard
        agentScope={<GovScopeSection fleet={fleet} scope={scope} locale={locale} lens={lens} />}
      />
    </AppShell>
  );
}
