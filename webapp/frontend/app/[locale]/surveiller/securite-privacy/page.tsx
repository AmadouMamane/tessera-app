import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { SecurityDashboard } from "@/components/security/security-dashboard";

interface SecurityPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: SecurityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "security" });
  return { title: t("title") };
}

export default async function SecurityPage({ params }: SecurityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "security" });
  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <SecurityDashboard />
    </AppShell>
  );
}
