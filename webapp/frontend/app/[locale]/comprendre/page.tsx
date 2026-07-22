import { getTranslations, setRequestLocale } from "next-intl/server";

import { ComprendreShell } from "@/components/comprendre/comprendre-shell";
import { ComprendreV2Overview } from "@/components/comprendre/comprendre-v2-overview";
import { loadComprendreFacts } from "@/lib/server/comprendre";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "comprendreV2" });
  return { title: t("pageTitle") };
}

/** Public, concise explanation backed by the cockpit's live observability seams. */
export default async function ComprendrePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const [t, facts] = await Promise.all([
    getTranslations({ locale, namespace: "comprendreV2" }),
    loadComprendreFacts(),
  ]);

  return (
    <ComprendreShell title={t("pageTitle")} description={t("pageLead")}>
      <ComprendreV2Overview initialFacts={facts} />
    </ComprendreShell>
  );
}
