import { getTranslations } from "next-intl/server";

import { StreamedAgentBreakdown } from "@/components/agent/agent-breakdown-stream";
import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { isScopedToAgent } from "@/lib/agent-scope";
import type { DeclaredLensRoute } from "@/lib/page-nature";

type SearchParams = Record<string, string | string[] | undefined>;

/**
 * Reusable GOUVERNER / PLATEFORME header section: the global agent-scope filter +
 * the per-agent breakdown + the honest "org signals not yet per-agent" banner.
 *
 * Drop it at the top of any global surface so the multi-agent dimension (filter,
 * deduplicated org total, per-agent breakdown) is consistent everywhere — distinct
 * from the AGENT switcher. Pass `signalsNote={false}` where the page below is
 * already fully per-agent and the banner would be misleading.
 *
 * The filter, the hero and the note render from the page's own props; the breakdown
 * table — the fleet read plus the per-agent lens fan-out, the page's slowest tunnel
 * work — is rendered INLINE by `<StreamedAgentBreakdown>` (blocking SSR, no `<Suspense>`
 * skeleton). It once streamed behind a fallback, but that flashed the card into a
 * skeleton on every CLIENT navigation; blocking folds the read into the page render (as
 * `vue-ensemble` does) so the card is present, populated, at first paint. The section
 * still takes the page's `route` and search params rather than a pre-loaded `fleet`/`lens`.
 *
 * `perAgent` declares whether the PAGE BODY responds to the agent filter:
 * - `true` (default): the dashboard below reads the selected agent's own signals
 *   (vue-ensemble / qualité IA / sécurité). The hero reads that agent's SLO and the
 *   note explains which shared-policy probes stay org-wide.
 * - `false`: an org-posture page (compliance / reliability / improvement) whose body
 *   is a fleet/regulatory aggregate. The per-agent breakdown above is still useful,
 *   but the hero is pinned to the fleet SLO and the note says the view stays org-wide
 *   — so we never imply per-agent numbers the page does not actually compute.
 *
 * It deliberately carries NO "useful links" row: cross-navigation belongs to each
 * page's own chrome, not stacked above the page's substance.
 */
export async function GovScopeSection({
  route,
  scope,
  locale,
  searchParams,
  signalId,
  signalsNote = true,
  signalHero = false,
  perAgent = true,
}: {
  /** The page's declared lens route — the breakdown's columns come from here. */
  route: DeclaredLensRoute;
  scope: string;
  locale: string;
  /** The page's URL params — opt the fleet read into the shared SURVEILLER window. */
  searchParams?: SearchParams;
  /** `?signal=` focus, honoured only by the quality lens. */
  signalId?: string;
  signalsNote?: boolean;
  signalHero?: boolean;
  perAgent?: boolean;
}) {
  const t = await getTranslations({ locale, namespace: "agentScope" });
  return (
    <div className="flex flex-col gap-2.5">
      {signalHero ? <SignalBreachHero orgWide={!perAgent} /> : null}
      <div className="flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-xs text-[var(--tessera-text-muted)]">{t("hint")}</span>
      </div>
      <StreamedAgentBreakdown
        route={route}
        scope={scope}
        locale={locale}
        fleetSearchParams={searchParams}
        signalId={signalId}
      />
      {/* Only when an agent is ACTUALLY selected: the note says "Filtre actif …",
          which is misleading on the default "Tous les agents" (no filter) view. The
          text matches the page: per-agent cards vs an org-posture aggregate. */}
      {signalsNote && isScopedToAgent(scope) ? (
        <p className="text-xs text-[var(--tessera-text-muted)]">
          {perAgent ? t("orgSignalsNote") : t("orgPostureNote")}
        </p>
      ) : null}
    </div>
  );
}
