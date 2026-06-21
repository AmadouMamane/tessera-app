import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { GuardrailCatalogue } from "@/components/configurer/guardrail-catalogue";
import { AppShell } from "@/components/layout/app-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });
  return { title: t("item.platformGuardrails") };
}

export default async function PlatformGuardrailsPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const tn = await getTranslations({ locale, namespace: "nav" });
  const t = await getTranslations({ locale, namespace: "usedBy" });
  return (
    <AppShell title={tn("item.platformGuardrails")} description={t("guardrailsSubtitle")}>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("hint")}</span>
      </div>
      <GuardrailCatalogue />
    </AppShell>
  );
}
