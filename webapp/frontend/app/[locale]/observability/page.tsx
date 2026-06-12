import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { QualityDashboard } from "@/components/quality/quality-dashboard";

interface ObservabilityPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "quality" });
  return { title: t("title") };
}

export default async function ObservabilityPage({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "quality" });
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="wide">
      <QualityDashboard />
    </AppShell>
  );
}
