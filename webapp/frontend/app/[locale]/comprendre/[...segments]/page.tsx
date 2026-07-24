import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";

import { CockpitPageGuide } from "@/components/comprendre/cockpit-page-guide";
import { AppShell } from "@/components/layout/app-shell";
import {
  AGENT_CONTEXTUAL_HELP_GUIDES,
  STATIC_CONTEXTUAL_HELP_GUIDES,
  contextualHelpGuideForHref,
  safeContextualHelpReturnTo,
} from "@/lib/contextual-help";

interface PageProps {
  params: Promise<{ locale: string; segments: string[] }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function guideHref(segments: string[]): string {
  return `/comprendre/${segments.join("/")}`;
}

export function generateStaticParams() {
  const guideHrefs = [
    ...STATIC_CONTEXTUAL_HELP_GUIDES.filter((guide) => guide.key !== "overview").map(
      (guide) => guide.guideHref,
    ),
    ...AGENT_CONTEXTUAL_HELP_GUIDES.map((guide) => `/comprendre/agents/${guide.page}`),
  ];
  return guideHrefs.map((href) => ({ segments: href.replace("/comprendre/", "").split("/") }));
}

export async function generateMetadata({ params }: PageProps) {
  const { locale, segments } = await params;
  const guide = contextualHelpGuideForHref(guideHref(segments));
  if (!guide) return {};
  const t = await getTranslations({ locale, namespace: "pageHelp" });
  return { title: t("sharedGuide.pageTitle", { page: t(`guides.${guide.key}.title`) }) };
}

export default async function ContextualHelpPage({ params, searchParams }: PageProps) {
  const { locale, segments } = await params;
  setRequestLocale(locale);
  const guide = contextualHelpGuideForHref(guideHref(segments));
  if (!guide || guide.key === "overview") notFound();

  const t = await getTranslations({ locale, namespace: "pageHelp" });
  const pageTitle = t(`guides.${guide.key}.title`);
  const backHref = safeContextualHelpReturnTo((await searchParams).from, guide.key);

  return (
    <AppShell
      title={t("sharedGuide.pageTitle", { page: pageTitle })}
      description={t(`guides.${guide.key}.lead`)}
    >
      <CockpitPageGuide backHref={backHref} guideKey={guide.key} section={guide.section} />
    </AppShell>
  );
}
