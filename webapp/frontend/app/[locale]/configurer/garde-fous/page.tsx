import { getTranslations, setRequestLocale } from "next-intl/server";

import { ScaffoldView } from "@/components/common/scaffold-view";
import { AppShell } from "@/components/layout/app-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "nav" });
  return { title: t("item.platformGuardrails") };
}

export default async function ScaffoldPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "nav" });
  const title = t("item.platformGuardrails");
  return (
    <AppShell title={title} contentWidth="full">
      <ScaffoldView title={title} />
    </AppShell>
  );
}
