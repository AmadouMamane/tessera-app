import { getTranslations, setRequestLocale } from "next-intl/server";

import {
  ThreeMinuteBrief,
  type ThreeMinuteCopy,
} from "@/components/comprendre-codex/three-minute-brief";
import { AppShell } from "@/components/layout/app-shell";

interface UnderstandCodexPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: UnderstandCodexPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "comprendreCodex" });
  return { title: t("metaTitle"), description: t("metaDescription") };
}

export default async function UnderstandCodexPage({ params }: UnderstandCodexPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "comprendreCodex" });

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <ThreeMinuteBrief copy={t.raw("content") as ThreeMinuteCopy} />
    </AppShell>
  );
}
