import { getTranslations, setRequestLocale } from "next-intl/server";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { ReleaseControlView } from "@/components/agir/release-control-view";
import { AppShell } from "@/components/layout/app-shell";
import { readAgentScope } from "@/lib/agent-scope";
import { loadReleaseControl } from "@/lib/server/fleet";

interface PageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "releaseControl" });
  return { title: t("title") };
}

export default async function ReleaseControlPage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "releaseControl" });
  const ts = await getTranslations({ locale, namespace: "agentScope" });

  const scope = readAgentScope(await searchParams);
  const data = await loadReleaseControl(scope, locale);

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{ts("hint")}</span>
      </div>
      <ReleaseControlView data={data} locale={locale} />
    </AppShell>
  );
}
