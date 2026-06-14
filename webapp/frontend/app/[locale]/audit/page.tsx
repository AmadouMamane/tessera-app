import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuditTable } from "@/components/audit/audit-table";
import { OperatorLocked } from "@/components/auth/operator-locked";
import { AppShell } from "@/components/layout/app-shell";
import { currentRole, isOperator } from "@/lib/auth/session";

// The operator gate reads the session (cookies) per request — never prerender.
export const dynamic = "force-dynamic";

interface AuditPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: AuditPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "audit" });
  return { title: t("title") };
}

export default async function AuditPage({ params }: AuditPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "audit" });
  const role = await currentRole();

  return (
    <AppShell title={t("title")} description={t("description")} contentWidth="full">
      {isOperator(role) ? <AuditTable /> : <OperatorLocked locale={locale} />}
    </AppShell>
  );
}
