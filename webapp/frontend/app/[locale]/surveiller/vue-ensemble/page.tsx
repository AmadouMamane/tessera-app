import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { AppShell } from "@/components/layout/app-shell";
import { OverviewDashboard } from "@/components/overview/overview-dashboard";
import { OverviewWindowBar } from "@/components/overview/overview-window-bar";
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
      // The view filters (window + agent) live in a single bar at the top of the
      // content (`OverviewWindowBar`), not in the header chrome: the window needs
      // the rich WindowControl (presets + "Aller à une date" calendar), and it is
      // the single owner the rail reads.
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
      {/* Single window owner (duration + "Aller à une date") + agent filter. */}
      <OverviewWindowBar />
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
