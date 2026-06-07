import { getTranslations, setRequestLocale } from "next-intl/server";

import { OperatorLocked } from "@/components/auth/operator-locked";
import { AppShell } from "@/components/layout/app-shell";
import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";
import { currentRole, isOperator } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

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
  const role = await currentRole();

  return (
    <AppShell title={t("title")} description={t("description")}>
      {isOperator(role) ? <ObservabilityDashboard /> : <OperatorLocked locale={locale} />}
    </AppShell>
  );
}
