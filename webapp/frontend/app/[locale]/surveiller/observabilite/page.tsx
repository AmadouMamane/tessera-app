import { getTranslations, setRequestLocale } from "next-intl/server";

import { HealthDashboard } from "@/components/health/health-dashboard";
import { AppShell } from "@/components/layout/app-shell";

interface HealthPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: HealthPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "health" });
  return { title: t("title") };
}

export default async function HealthPage({ params }: HealthPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "health" });
  return (
    <AppShell title={t("title")} description={t("description")}>
      <HealthDashboard />
    </AppShell>
  );
}
