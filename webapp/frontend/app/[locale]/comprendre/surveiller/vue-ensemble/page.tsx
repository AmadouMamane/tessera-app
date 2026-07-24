import { getTranslations, setRequestLocale } from "next-intl/server";

import { OverviewPageGuide } from "@/components/comprendre/overview-page-guide";
import { AppShell } from "@/components/layout/app-shell";
import { safeOverviewHelpReturnTo } from "@/lib/contextual-help";

interface PageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "pageHelp.overview" });
  return { title: t("pageTitle") };
}

export default async function OverviewHelpPage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "pageHelp.overview" });
  const backHref = safeOverviewHelpReturnTo((await searchParams).from);

  return (
    <AppShell title={t("pageTitle")} description={t("pageLead")}>
      <OverviewPageGuide backHref={backHref} />
    </AppShell>
  );
}
