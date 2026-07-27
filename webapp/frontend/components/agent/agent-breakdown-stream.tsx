import { Suspense } from "react";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { Skeleton } from "@/components/ui/skeleton";
import type { DeclaredLensRoute } from "@/lib/page-nature";
import { loadDeclaredLens } from "@/lib/server/agent-lens";
import { loadFleet } from "@/lib/server/fleet";

type SearchParams = Record<string, string | string[] | undefined>;

interface StreamedAgentBreakdownProps {
  /** The page's declared lens route — decides the columns (page-nature registry). */
  route: DeclaredLensRoute;
  /** The selected agent scope (breakdown row highlight); the page reads it from the URL. */
  scope: string;
  locale: string;
  /**
   * The URL search params that opt the fleet read into the shared SURVEILLER window.
   * OMITTED (audit-logs proof breakdown) keeps the all-history fleet contract — the exact
   * distinction the pages made before this component existed.
   */
  fleetSearchParams?: SearchParams;
  /** `?signal=` focus, honoured only by the quality lens (ignored by the domain lenses). */
  signalId?: string;
}

/**
 * A fallback that reserves the breakdown card's footprint so the streamed content
 * causes no layout jump when it swaps in.
 */
function BreakdownFallback() {
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
 * The blocking part of the per-agent breakdown, isolated so it can stream.
 *
 * It performs the two tunnel reads that dominate a GOUVERNER page's TTFB — the fleet
 * aggregate then the per-agent lens fan-out — and renders the SAME `<AgentBreakdown>`
 * with the SAME props the pages built inline before. `loadFleet`/`fetchSnapshot` are
 * `cache()`-deduped, so this never doubles a read the surrounding render already did.
 */
async function BreakdownContent({
  route,
  scope,
  locale,
  fleetSearchParams,
  signalId,
}: StreamedAgentBreakdownProps) {
  // Preserve the all-history vs windowed fleet distinction exactly: only pass the
  // search params through when the caller provided them.
  const fleet = fleetSearchParams
    ? await loadFleet(locale, fleetSearchParams)
    : await loadFleet(locale);
  const lens = await loadDeclaredLens(route, fleet, { signalId });
  return <AgentBreakdown fleet={fleet} scope={scope} locale={locale} lens={lens} />;
}

/**
 * The per-agent breakdown, streamed behind `<Suspense>`.
 *
 * The page shell, the agent-scope filter and the client dashboards paint at the first
 * round-trip; the fleet + 6× snapshot fan-out arrives as a second chunk in place of the
 * skeleton. The rendered DOM — and therefore every asserted value — is identical to the
 * pre-streaming version; only the paint order changes. Nothing here caches across
 * requests, so a mutation is still reflected on the very next render.
 */
export function StreamedAgentBreakdown(props: StreamedAgentBreakdownProps) {
  return (
    <Suspense fallback={<BreakdownFallback />}>
      <BreakdownContent {...props} />
    </Suspense>
  );
}
