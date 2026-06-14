import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { ReliabilityDashboard } from "@/components/reliability/reliability-dashboard";

interface ReliabilityPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ReliabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "reliability" });
  return { title: t("title") };
}

export default async function ReliabilityPage({ params }: ReliabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "reliability" });
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <ReliabilityDashboard />
    </AppShell>
  );
}
