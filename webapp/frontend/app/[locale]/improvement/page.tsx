import { getTranslations, setRequestLocale } from "next-intl/server";

import { ImprovementDashboard } from "@/components/improvement/improvement-dashboard";
import { AppShell } from "@/components/layout/app-shell";

interface ImprovementPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ImprovementPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "improvement" });
  return { title: t("title") };
}

export default async function ImprovementPage({ params }: ImprovementPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "improvement" });
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <ImprovementDashboard />
    </AppShell>
  );
}
