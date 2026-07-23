import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { EVAL_VIEW_PARAM, EVAL_VIEW_VALUE } from "@/components/eval/eval-route";
import { parseTab } from "@/components/eval/eval-tabs";
import { ScorecardView } from "@/components/eval/scorecard-view";
import { AppShell } from "@/components/layout/app-shell";
import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";
import { QualityViewSwitch } from "@/components/surveiller/quality-view-switch";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { readAgentScope } from "@/lib/agent-scope";
import { loadDeclaredLens } from "@/lib/server/agent-lens";
import { loadFleet } from "@/lib/server/fleet";
import { readSignalFocus } from "@/lib/signal-focus";

// The evaluations view gates the per-case detail on the session (cookies) per request.
export const dynamic = "force-dynamic";

interface ObservabilityPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "quality" });
  return { title: t("title") };
}

const first = (v: string | string[] | undefined): string | undefined =>
  Array.isArray(v) ? v[0] : v;

/**
 * Qualité IA — one page, two views, switched by `?vue=`.
 *
 * The default view is the continuous-monitoring dashboard (signals, SLOs, judge). The
 * `?vue=evaluations` view is the non-regression screen (case set, floor, model contribution,
 * comparisons) that used to live at `/eval` — an orphan reachable only by typed URL while THIS
 * page's sidebar entry promised its content. `/eval` now redirects here with its params intact.
 */
export default async function ObservabilityPage({ params, searchParams }: ObservabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const sp = await searchParams;
  const isEvalView = first(sp[EVAL_VIEW_PARAM]) === EVAL_VIEW_VALUE;

  if (isEvalView) {
    const tEval = await getTranslations({ locale, namespace: "eval" });
    return (
      <AppShell title={tEval("title")} description={tEval("description")}>
        <QualityViewSwitch active="evaluations" locale={locale} />
        {/* Plain-language way in for a visitor: what the catalogue is, what the floor means,
            why an absolute score is not the grade. The expert detail below stays intact. */}
        <details className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-3">
          <summary className="cursor-pointer text-[0.8rem] font-semibold">
            {tEval("explainer.title")}
          </summary>
          <div className="mt-2 space-y-2 text-[0.74rem] leading-relaxed text-[var(--tessera-text-muted)]">
            <p>{tEval("explainer.p1")}</p>
            <p>{tEval("explainer.p2")}</p>
            <p>{tEval("explainer.p3")}</p>
          </div>
        </details>
        <ScorecardView
          locale={locale}
          tab={parseTab(first(sp.tab))}
          run={first(sp.run)}
          caseId={first(sp.case)}
          lang={first(sp.lang)}
          a={first(sp.a)}
          b={first(sp.b)}
        />
      </AppShell>
    );
  }

  const t = await getTranslations({ locale, namespace: "quality" });
  const scope = readAgentScope(sp);
  const fleet = await loadFleet(locale, sp);
  // The breakdown lens answers the page's question: the breached signal when the SLO hero is in
  // alarm (per-agent culprits, sorted by contribution), the quality lens otherwise — never
  // volume/latency columns under a quality banner. `?signal=` focuses one signal from the
  // registry; an org-wide one masks the table and says why (its capability, not a guess).
  const lens = await loadDeclaredLens("/surveiller/qualite-ia", fleet, {
    signalId: readSignalFocus(sp),
  });
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      <QualityViewSwitch active="signals" locale={locale} />
      {/* The alert leads and the temporal controls follow as one compact reading sequence.
          A shallow background fill on the sticky chrome keeps both rounded edges clean. */}
      <div>
        <SignalBreachHero variant="gauge" />
      </div>
      <ObservabilityDashboard
        agentScope={<GovScopeSection fleet={fleet} scope={scope} locale={locale} lens={lens} />}
      />
    </AppShell>
  );
}
