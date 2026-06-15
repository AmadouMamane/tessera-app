import { getTranslations, setRequestLocale } from "next-intl/server";

import { ScaffoldView } from "@/components/common/scaffold-view";
import { AppShell } from "@/components/layout/app-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "assistant" });
  return { title: t("synthese.title") };
}

export default async function AgentSynthesePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "assistant" });
  return (
    <AppShell title={t("synthese.title")} description={t("synthese.subtitle")} contentWidth="full">
      <ScaffoldView title={t("synthese.title")} />
    </AppShell>
  );
}
