import { getTranslations, setRequestLocale } from "next-intl/server";

import { ComplianceDashboard } from "@/components/compliance/compliance-dashboard";
import { AppShell } from "@/components/layout/app-shell";

interface CompliancePageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: CompliancePageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "compliance" });
  return { title: t("title") };
}

export default async function CompliancePage({ params }: CompliancePageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "compliance" });
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <ComplianceDashboard />
    </AppShell>
  );
}
