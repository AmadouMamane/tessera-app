import { getTranslations, setRequestLocale } from "next-intl/server";

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

  const sp = await searchParams;
  const scope = readAgentScope(sp);
  const fleet = await loadFleet(locale, sp);
  const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
  const initialFleetPeriod = first(sp.period) ?? "d7";
  const initialFleetAt = first(sp.asof) ?? first(sp.at) ?? first(sp.to) ?? null;

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
        initialFleet={fleet}
        fleetScope={scope}
        fleetLocale={locale}
        initialFleetPeriod={initialFleetPeriod}
        initialFleetAt={initialFleetAt}
        lead={<SignalBreachHero />}
      >
        {isScopedToAgent(scope) ? (
          <p className="mb-1 text-xs text-[var(--tessera-text-muted)]">{ts("orgSignalsNote")}</p>
        ) : null}
      </OverviewDashboard>
    </AppShell>
  );
}
