import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { CatalogueConsumers } from "@/components/configurer/catalogue-consumers";
import { ModelCatalogue } from "@/components/configurer/model-catalogue";
import { AppShell } from "@/components/layout/app-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });
  return { title: t("item.modeles") };
}

export default async function ModelesPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const tn = await getTranslations({ locale, namespace: "nav" });
  const t = await getTranslations({ locale, namespace: "usedBy" });
  return (
    <AppShell title={tn("item.modeles")} description={t("modelsSubtitle")}>
      <Suspense fallback={null}>
        <div className="flex flex-wrap items-center gap-3">
          <AgentScopeFilter />
          <span className="text-xs text-[var(--tessera-text-muted)]">{t("hint")}</span>
        </div>
        <ModelCatalogue />
        {/* The inverse of the AGENT instance binding: which agents consume each
            shared item, and which of them a change here would send back through the
            gate. Written, translated (`usedBy.*`), backed by a live route — and
            imported by nothing until 2026-08-01. This page already rendered
            `usedBy.hint` above, so the panel was designed for it and simply never
            mounted. */}
        <CatalogueConsumers kind="model" />
      </Suspense>
    </AppShell>
  );
}
