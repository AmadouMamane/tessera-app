import { getTranslations, setRequestLocale } from "next-intl/server";

import { parseTab } from "@/components/eval/eval-tabs";
import { ScorecardView } from "@/components/eval/scorecard-view";
import { AppShell } from "@/components/layout/app-shell";

// ScorecardView gates the per-case detail on the session (cookies) per request.
export const dynamic = "force-dynamic";

interface EvalPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{
    tab?: string;
    run?: string;
    case?: string;
    lang?: string;
    a?: string;
    b?: string;
  }>;
}

export async function generateMetadata({ params }: EvalPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "eval" });
  return { title: t("title") };
}

export default async function EvalPage({ params, searchParams }: EvalPageProps) {
  const { locale } = await params;
  const { tab, run, case: caseId, lang, a, b } = await searchParams;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "eval" });
  return (
    <AppShell title={t("title")} description={t("description")}>
      <ScorecardView
        locale={locale}
        tab={parseTab(tab)}
        run={run}
        caseId={caseId}
        lang={lang}
        a={a}
        b={b}
      />
    </AppShell>
  );
}
