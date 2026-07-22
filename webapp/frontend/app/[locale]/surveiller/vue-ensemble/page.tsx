import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { AppShell } from "@/components/layout/app-shell";
import { OverviewDashboard } from "@/components/overview/overview-dashboard";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { isScopedToAgent, readAgentScope } from "@/lib/agent-scope";
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
      // Période et le filtre Agent vivent dans le SignalCommandBar (SR-01) en tête de
      // page (un seul foyer temporel, registre §8). Les actions de SORTIE (Exporter
      // rapport / Générer le dossier de preuves) ne sont plus dans le header : elles
      // sont rendues dans la page, juste au-dessus du rail (PageEvidenceActions).
    >
      {/* The SLO breach alert LEADS (passed as `lead`); the temporal command bar
          (SR-01) sits directly beneath it; the per-agent breakdown follows below the
          bar (children). */}
      <OverviewDashboard
        lead={
          // Keep the alert and its temporal controls visually connected. The sticky
          // chrome uses only a shallow background fill, so 12px is sufficient.
          <div className="mb-3">
            <SignalBreachHero />
          </div>
        }
      >
        <div className="mb-3">
          <AgentBreakdown fleet={fleet} scope={scope} locale={locale} />
        </div>
        {isScopedToAgent(scope) ? (
          <p className="mb-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
            {ts("orgSignalsNote")}
          </p>
        ) : null}
      </OverviewDashboard>
    </AppShell>
  );
}
