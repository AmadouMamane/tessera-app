import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import type { DeclaredLensRoute } from "@/lib/page-nature";
import { loadDeclaredLens } from "@/lib/server/agent-lens";

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
 * The blocking part of the per-agent breakdown.
 *
 * It performs the tunnel read that dominates a GOUVERNER page's TTFB — the fleet aggregate plus
 * the per-agent lens fan-out — and renders the SAME `<AgentBreakdown>` with the SAME props the
 * pages built inline before. On a domain page those were TWO serial reads although neither
 * depended on the other; `loadDeclaredLens` now owns both and asks for them together, so the page
 * pays ONE round-trip instead of two (the quality lens keeps its two: its org plan decides what
 * the second read asks for). The reads are `cache()`-deduped by URL, so this never doubles a read
 * the surrounding render already did.
 *
 * `fleetSearchParams` is passed straight through — `undefined` keeps the all-history fleet
 * contract, exactly the distinction the pages made before this component existed.
 */
async function BreakdownContent({
  route,
  scope,
  locale,
  fleetSearchParams,
  signalId,
}: StreamedAgentBreakdownProps) {
  const { fleet, lens } = await loadDeclaredLens(route, locale, { fleetSearchParams, signalId });
  return <AgentBreakdown fleet={fleet} scope={scope} locale={locale} lens={lens} />;
}

/**
 * The per-agent breakdown, rendered INLINE (blocking SSR) — deliberately NOT streamed.
 *
 * It used to stream behind `<Suspense>` with a skeleton fallback, so the shell painted
 * first and the card swapped in a beat later. That cost a visible flash on CLIENT
 * navigation: every soft nav to (or between) these pages mounted a FRESH Suspense
 * boundary, so the card VANISHED into its skeleton for the ~0.3s of the fleet + lens
 * fan-out, then reappeared. Blocking instead folds the fleet + lens read into the page's
 * own render — exactly what `vue-ensemble` does with its `await loadFleet` — so the router
 * holds the previous page until the new one is ready and the card is present, populated,
 * at first paint. No skeleton, no flash. The read is fast enough post-snapshot (ADR 0046)
 * to block on, and correctness is unchanged: the rendered DOM is identical to the streamed
 * version, and nothing caches across requests, so a mutation is still reflected on the
 * very next render.
 *
 * The name is retained on purpose: `page-nature` scans page source for the literal
 * `<StreamedAgentBreakdown` token as the marker that a page declares a lens route.
 */
export function StreamedAgentBreakdown(props: StreamedAgentBreakdownProps) {
  return <BreakdownContent {...props} />;
}
