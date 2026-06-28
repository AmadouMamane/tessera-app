import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
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
      // Période, le filtre Agent et les exports vivent désormais dans le
      // SignalCommandBar (SR-01) en tête de page — un seul foyer temporel, pas de
      // doublon dans le header (registre §8). Le header ne garde que le contexte
      // de déploiement (read-only) + chrome global.
    >
      {/* The temporal command bar (SR-01) is the FIRST line of the page; the lead
          content — breached signal + per-agent breakdown — follows it (rendered as
          children, right under the bar). */}
      <OverviewDashboard>
        <div className="mt-3 mb-3">
          <SignalBreachHero />
        </div>
        <div className="mb-3">
          <AgentBreakdown fleet={fleet} scope={scope} locale={locale} />
        </div>
        <p className="mb-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
          {ts("orgSignalsNote")}
        </p>
      </OverviewDashboard>
    </AppShell>
  );
}
