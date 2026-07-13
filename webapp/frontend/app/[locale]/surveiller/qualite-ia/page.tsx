import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { AppShell } from "@/components/layout/app-shell";
import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";
import { EvalDoor } from "@/components/surveiller/eval-door";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
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
  const fleet = await loadFleet(locale);
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      {/* SLO breach alert LEADS; the dashboard's temporal rail sits directly beneath it;
          the agent-scope context (Vue par agent) renders below the rail via `agentScope`.
          The gap must exceed the sticky chrome's upward `shadow-[0_-16px_…]` (16px) so the
          rail's bg-coloured shadow never paints over the banner's bottom edge — `mb-5` (20px)
          keeps a 4px clearance. */}
      <div className="mb-5">
        <SignalBreachHero variant="gauge" />
      </div>
      {/* `/eval` had no inbound link anywhere in the app — no sidebar entry, no palette
          action — while this page's subtitle promised the very thing that lives there.
          The subtitle now describes what this page serves; this is the way to the rest. */}
      <EvalDoor />
      <ObservabilityDashboard
        agentScope={<GovScopeSection fleet={fleet} scope={scope} locale={locale} />}
      />
    </AppShell>
  );
}
