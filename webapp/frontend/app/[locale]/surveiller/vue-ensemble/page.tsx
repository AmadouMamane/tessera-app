import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { AppShell } from "@/components/layout/app-shell";
import { OverviewDashboard } from "@/components/overview/overview-dashboard";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { readAgentScope } from "@/lib/agent-scope";
import { loadFleet } from "@/lib/server/fleet";

interface OverviewPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: OverviewPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "overview" });
  return { title: t("title") };
}

export default async function OverviewPage({ params, searchParams }: OverviewPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "overview" });
  const ts = await getTranslations({ locale, namespace: "agentScope" });

  const scope = readAgentScope(await searchParams);
  const fleet = await loadFleet();

  return (
    <AppShell
      title={t("title")}
      description={t("subtitle")}
      // View filters only. Période is the SINGLE temporal-window owner (shared
      // store) — the rail reads it, it has no period selector of its own.
      // Environnement + Modèle are deployment CONTEXT (header badges) and Langue
      // is global — none are page filters, so they no longer live here.
      topbarContext={[
        {
          label: t("context.lifecycle"),
          value: "d7",
          leading: "history",
          control: "window",
          options: [
            { value: "h24", label: t("context.lifecycle24h") },
            { value: "d7", label: t("context.lifecycleValue") },
            { value: "d30", label: t("context.lifecycle30d") },
          ],
        },
      ]}
      // The agent filter sits in the SAME bar as Période (the view filters).
      topbarFilters={<AgentScopeFilter />}
      topbarActions={[
        {
          label: t("actions.exportReport"),
          icon: "download",
          variant: "outline",
          action: "export",
        },
        {
          label: t("actions.generateEvidencePack"),
          icon: "evidence",
          variant: "accent",
          action: "evidence",
        },
      ]}
    >
      {/* P2 — lead with the named breached signal (real SLO) + remediation. */}
      <div className="mb-3">
        <SignalBreachHero />
      </div>
      <div className="mb-3">
        <AgentBreakdown fleet={fleet} scope={scope} locale={locale} />
      </div>
      <p className="mb-3 text-[0.62rem] text-[var(--tessera-text-muted)]">{ts("orgSignalsNote")}</p>
      <OverviewDashboard />
    </AppShell>
  );
}
