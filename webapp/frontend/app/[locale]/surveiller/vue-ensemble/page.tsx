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
      contentWidth="wide"
      topbarContext={[
        {
          label: t("context.environment"),
          value: "prod",
          tone: "success",
          leading: "status",
          control: "select",
          options: [
            { value: "prod", label: "Prod" },
            { value: "staging", label: "Staging" },
            { value: "dev", label: "Dev" },
          ],
        },
        {
          label: t("context.lifecycle"),
          value: "d7",
          leading: "history",
          control: "select",
          options: [
            { value: "h24", label: t("context.lifecycle24h") },
            { value: "d7", label: t("context.lifecycleValue") },
            { value: "d30", label: t("context.lifecycle30d") },
          ],
        },
        { label: t("context.model"), value: "Llama 3.2 3B", control: "model" },
        { label: t("context.language"), value: "FR", leading: "globe", control: "locale" },
      ]}
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
      {/* GOUVERNER global agent filter — distinct from the AGENT switcher. */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{ts("hint")}</span>
      </div>
      <div className="mb-3">
        <AgentBreakdown fleet={fleet} scope={scope} locale={locale} />
      </div>
      <p className="mb-3 text-[0.62rem] text-[var(--tessera-text-muted)]">{ts("orgSignalsNote")}</p>
      <OverviewDashboard />
    </AppShell>
  );
}
