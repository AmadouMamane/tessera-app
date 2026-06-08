import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";

interface ObservabilityPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "observability" });
  return { title: t("title") };
}

export default async function ObservabilityPage({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "observability" });
  return (
    <AppShell title={t("title")} description={t("description")}>
      <ObservabilityDashboard />
    </AppShell>
  );
}
