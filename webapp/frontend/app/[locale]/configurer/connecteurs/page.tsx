import { getTranslations, setRequestLocale } from "next-intl/server";

import { ConnectorsOverview } from "@/components/connectors/connectors-overview";
import { AppShell } from "@/components/layout/app-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });
  return { title: t("item.connecteurs") };
}

export default async function ConnecteursPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "nav" });
  return (
    <AppShell title={t("item.connecteurs")}>
      <ConnectorsOverview />
    </AppShell>
  );
}
