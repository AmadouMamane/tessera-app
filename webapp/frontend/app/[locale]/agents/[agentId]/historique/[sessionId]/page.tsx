import { getTranslations, setRequestLocale } from "next-intl/server";

import { ScaffoldView } from "@/components/common/scaffold-view";
import { AppShell } from "@/components/layout/app-shell";

interface PageProps {
  params: Promise<{ locale: string; sessionId: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale, sessionId } = await params;
  const t = await getTranslations({ locale, namespace: "assistant" });
  return { title: `${t("sessionDetail.title")} ${sessionId}` };
}

export default async function SessionDetailPage({ params }: PageProps) {
  const { locale, sessionId } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "assistant" });
  const title = `${t("sessionDetail.title")} ${sessionId}`;
  return (
    <AppShell title={title} description={t("sessionDetail.subtitle")} contentWidth="full">
      <ScaffoldView title={title} />
    </AppShell>
  );
}
