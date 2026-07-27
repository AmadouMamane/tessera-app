import { getTranslations, setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { ReleaseControlView } from "@/components/agir/release-control-view";
import { AppShell } from "@/components/layout/app-shell";
import { Skeleton } from "@/components/ui/skeleton";
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

/**
 * A fallback that reserves the release-control card's footprint so the streamed
 * content causes no layout jump when it swaps in.
 */
function ReleaseControlFallback() {
  return (
    <section
      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4"
      aria-busy="true"
    >
      <Skeleton className="h-3.5 w-44" />
      <Skeleton className="mt-3 h-28 w-full" />
    </section>
  );
}

/**
 * The blocking part of the page, isolated so it can stream.
 *
 * It performs the one tunnel read that dominated this page's TTFB — the release-control
 * fold, scoped by the global agent filter — and renders the SAME `<ReleaseControlView>`
 * with the SAME props the page passed inline before. `loadReleaseControl` is
 * `cache()`-deduped; nothing here caches across requests, so a governed release act is
 * still reflected on the very next render.
 */
async function ReleaseControlSection({ scope, locale }: { scope: string; locale: string }) {
  const data = await loadReleaseControl(scope, locale);
  return <ReleaseControlView data={data} locale={locale} />;
}

export default async function ReleaseControlPage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "releaseControl" });
  const ts = await getTranslations({ locale, namespace: "agentScope" });

  const scope = readAgentScope(await searchParams);

  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <div className="flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{ts("hint")}</span>
      </div>
      {/* The shell + agent-scope filter paint at the first round-trip; the release-control
          fold (its one tunnel read) streams in behind the skeleton — same DOM, only the
          paint order changes. */}
      <Suspense fallback={<ReleaseControlFallback />}>
        <ReleaseControlSection scope={scope} locale={locale} />
      </Suspense>
    </AppShell>
  );
}
