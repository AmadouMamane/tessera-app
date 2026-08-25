import { getTranslations, setRequestLocale } from "next-intl/server";

import { GovScopeSection } from "@/components/agent/gov-scope-section";
import { EVAL_VIEW_PARAM, EVAL_VIEW_VALUE } from "@/components/eval/eval-route";
import { parseTab } from "@/components/eval/eval-tabs";
import { ScorecardView } from "@/components/eval/scorecard-view";
import { AppShell } from "@/components/layout/app-shell";
import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";
import { QualityViewSwitch } from "@/components/surveiller/quality-view-switch";
import { ReleaseVerdictRibbon } from "@/components/surveiller/release-verdict-ribbon";
import { SignalBreachHero } from "@/components/surveiller/signal-breach-hero";
import { readAgentScope } from "@/lib/agent-scope";
import { loadReleaseControl } from "@/lib/server/fleet";
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
  const scope = readAgentScope(sp);
  // Loaded ONCE for the page (the loader is request-memoised): the switch prints its one-line
  // summary on the evaluations door of both views, and the full ribbon reads the same payload.
  const control = await loadReleaseControl(scope, locale);

  if (isEvalView) {
    const tEval = await getTranslations({ locale, namespace: "eval" });
    return (
      <AppShell title={tEval("title")} description={tEval("description")}>
        <QualityViewSwitch active="evaluations" locale={locale} control={control} />
        {/* The verdict that decides a release LEADS the view whose question it answers. It used
            to sit above the switch on both views — the monitoring view then opened on the other
            view's headline (operator feedback, 2026-08-12). */}
        <ReleaseVerdictRibbon control={control} locale={locale} />
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
  // The breakdown lens answers the page's question: the breached signal when the SLO hero is in
  // alarm (per-agent culprits, sorted by contribution), the quality lens otherwise — never
  // volume/latency columns under a quality banner. `?signal=` focuses one signal from the
  // registry; an org-wide one masks the table and says why (its capability, not a guess).
  return (
    <AppShell title={t("title")} description={t("subtitle")}>
      {/* No full verdict ribbon here: "can this go live" is the evaluations view's question,
          and its one-line summary rides on that view's door just above the content. The
          per-agent PRÊT column below still gets its explainer — at door size, not banner size. */}
      <QualityViewSwitch active="signals" locale={locale} control={control} />
      {/* The alert leads and the temporal controls follow as one compact reading sequence.
          A shallow background fill on the sticky chrome keeps both rounded edges clean. */}
      <div>
        <SignalBreachHero variant="gauge" />
        {/* The hero's verdict covers ONE population (judged responses). One quiet line keeps
            "0 judged" from reading as "nothing else is measured"; the full method cards live
            in the « Méthodes de notation » zone of the dashboard below (ADR 0017 §A4 —
            moved into the house mould, operator feedback 2026-08-25). */}
        <p className="mt-1 text-[0.66rem] text-[var(--tessera-text-muted)]">{t("methodsNote")}</p>
      </div>
      <ObservabilityDashboard
        agentScope={
          <GovScopeSection
            route="/surveiller/qualite-ia"
            scope={scope}
            locale={locale}
            searchParams={sp}
            signalId={readSignalFocus(sp)}
          />
        }
      />
    </AppShell>
  );
}
