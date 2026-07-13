import { AlertTriangle, CalendarClock, FileSearch, Layers } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { OperatorLocked } from "@/components/auth/operator-locked";
import { CaseMatrix } from "@/components/eval/case-matrix";
import { CaseRunDetail } from "@/components/eval/case-run-detail";
import { CatalogueTab } from "@/components/eval/catalogue-tab";
import { type EvalTab, EvalTabs } from "@/components/eval/eval-tabs";
import { FailureSynthesis } from "@/components/eval/failure-synthesis";
import { RunPicker } from "@/components/eval/run-picker";
import { ScoreCard } from "@/components/eval/score-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { currentRole, isAdmin, isOperator, isSuperadmin } from "@/lib/auth/session";
import {
  MIN_CONTRIBUTION_UNCALIBRATED,
  ageInDays,
  caseKey,
  cellState,
  decomposeRun,
  isStale,
} from "@/lib/eval-score";
import { type Sweep, loadSweep, loadSweepRun } from "@/lib/eval-sweep";
import { getSynthesisAdminFlag } from "@/lib/server/settings";

interface ScorecardViewProps {
  locale: string;
  /** Which surface is open. A dataset is an artefact, a run is an event — they are not one tab. */
  tab: EvalTab;
  /** Which run's per-case detail to open. A run id from the sweep, never a path. */
  run?: string;
  /** Which cell of the matrix is open — a (case, language) pair. */
  caseId?: string;
  lang?: string;
}

/**
 * The eval surface, rebuilt on the SWEEP.
 *
 * What it used to do, and why none of it survived:
 *
 *  - It read `latest.json`, which resolved to a THREE-CASE, ZERO-TOKEN run from 20 June, and
 *    rendered "3/3 — 100%". A run no model ever answered, published as a perfect score.
 *  - Its `SummaryRow` printed a raw pass rate. A raw rate adds the guard's deterministic floor
 *    to the model's contribution and reads as if the model earned the sum (§A1.2).
 *  - Its `BestRunHighlight` pinned "the best run" by that rate. The sweep proves the rate ranks
 *    nothing: two models tie at 157/174 and one of them degrades the agent.
 *
 * What replaces them: the sweep's runs, each through the one {@link ScoreCard} that cannot
 * render a bare number, and the référentiel + freshness stated in the header — never implied.
 */
export async function ScorecardView({ locale, tab, run, caseId, lang }: ScorecardViewProps) {
  const [sweep, t] = await Promise.all([
    loadSweep(),
    getTranslations({ locale, namespace: "eval" }),
  ]);

  const tabs = (
    <EvalTabs
      active={tab}
      labels={{ cases: t("tabs.cases"), runs: t("tabs.runs"), compare: t("tabs.compare") }}
    />
  );

  if (tab === "cases") {
    return (
      <div className="flex flex-col gap-6 pb-10">
        {tabs}
        <CatalogueTab
          catalogue={sweep?.catalogue ?? []}
          version={sweep?.currentCatalogueVersion ?? null}
          locale={locale}
        />
      </div>
    );
  }

  // Default to the NEWEST run, never the best-scoring one. "Newest" is a fact about a run;
  // "best" would be a ranking, and on this catalogue the absolute rate ranks nothing.
  const selected = sweep?.runs.find((r) => r.id === run) ?? sweep?.runs[0];

  if (!sweep || !selected) {
    return (
      <div className="flex flex-col gap-6 pb-10">
        {tabs}
        <Card>
          <CardContent className="p-6">
            <EmptyState
              icon={<FileSearch />}
              title={t("sweep.empty.title")}
              description={t("sweep.empty.body")}
            />
            <div className="mt-6 rounded-md bg-[var(--muted)]/40 p-4 font-mono text-xs leading-relaxed text-[var(--muted-foreground)]">
              $ uv run python scripts/run_eval.py --report eval/reports/sweep/&lt;model&gt;.json
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Aggregate scores stay public (showcase); the per-case detail — case status and failure
  // reasons, i.e. a map of the live deployment's weaknesses — is an operator surface (ADR 0009).
  const role = await currentRole();
  const operator = isOperator(role);
  const superadmin = isSuperadmin(role);
  const admin = isAdmin(role);
  const synthesisForAdmin = superadmin || admin ? await getSynthesisAdminFlag() : false;
  const showSynthesis = superadmin || (admin && synthesisForAdmin);

  const detail = await loadSweepRun(selected.id, sweep);

  return (
    <div className="flex flex-col gap-6 pb-10">
      {tabs}
      <SweepHeader sweep={sweep} locale={locale} />

      {/* Every run of the sweep, decomposed. Three cards, one référentiel, no ranking. */}
      <div className="grid gap-4 lg:grid-cols-3">
        {sweep.runs.map((r) => (
          <ScoreCard
            key={r.id}
            card={decomposeRun(r, sweep.floor, MIN_CONTRIBUTION_UNCALIBRATED)}
            locale={locale}
            runAt={r.runAt}
          />
        ))}
      </div>

      <div id="run-detail" className="flex scroll-mt-4 flex-col gap-6">
        <RunPicker
          runs={sweep.runs.map((r) => ({ id: r.id, model: r.model, runAt: r.runAt }))}
          selected={selected.id}
          label={t("sweep.pickRun")}
        />

        {showSynthesis && detail ? (
          <FailureSynthesis synthesis={detail.synthesis} results={detail.results} locale={locale} />
        ) : null}

        {operator && detail ? (
          <>
            {/* The case set moved under a run → its definitions are no longer the ones it was
                scored against, and recomputing a criterion from them would show a rule that never
                applied. The verdicts still display; only the reconstruction stands down. */}
            {(() => {
              const recomputable = !isStale(
                selected.catalogueVersion,
                sweep.currentCatalogueVersion,
              );
              const openCase = caseId
                ? (sweep.catalogue.find((c) => c.id === caseId) ?? null)
                : null;
              const openResult =
                caseId && lang
                  ? (detail.results.find((r) => r.case_id === caseId && r.language === lang) ??
                    null)
                  : null;
              return (
                <>
                  {openResult ? (
                    <CaseRunDetail
                      evalCase={openCase}
                      result={openResult}
                      state={
                        sweep.floor
                          ? cellState(
                              caseKey(openResult.case_id, openResult.language),
                              selected.verdicts,
                              sweep.floor.verdicts,
                            )
                          : "unknown"
                      }
                      locale={locale}
                      recomputable={recomputable}
                    />
                  ) : null}
                  <CaseMatrix
                    catalogue={sweep.catalogue}
                    runVerdicts={selected.verdicts}
                    floorVerdicts={sweep.floor?.verdicts ?? null}
                    runId={selected.id}
                    selected={caseId && lang ? { caseId, lang } : null}
                    locale={locale}
                  />
                </>
              );
            })()}
          </>
        ) : (
          <OperatorLocked locale={locale} />
        )}
      </div>
    </div>
  );
}

/**
 * The référentiel and the freshness, stated before any number is shown.
 *
 * Criterion 4 asks for the freshness and criterion 2 for the référentiel, and both are here for
 * the same reason: a verdict without the case set it was scored against, and without the date it
 * was scored on, is a number an operator cannot act on.
 */
async function SweepHeader({ sweep, locale }: { sweep: Sweep; locale: string }) {
  const t = await getTranslations({ locale, namespace: "eval" });
  const days = ageInDays(sweep.newestRunAt, new Date());
  const stale = isStale(sweep.catalogueVersion, sweep.currentCatalogueVersion);

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-gold-600 dark:text-gold-400" />
            <h2 className="font-semibold text-base">
              {t("sweep.title", { count: sweep.runs.length })}
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="navy" className="font-mono">
              {t("sweep.referential", { version: sweep.catalogueVersion ?? "—" })}
            </Badge>
            <Badge tone={days !== null && days > 0 ? "neutral" : "success"} className="gap-1.5">
              <CalendarClock className="h-3 w-3" />
              {days === null ? t("sweep.freshnessUnknown") : t("sweep.freshness", { days })}
            </Badge>
          </div>
        </div>

        <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
          {t("sweep.subtitle")}
        </p>

        {sweep.floorTotals ? (
          <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
            {t("sweep.floorRead", {
              passed: sweep.floorTotals.passed,
              total: sweep.floorTotals.total,
            })}
          </p>
        ) : null}

        {stale ? (
          <Note tone="warning">
            {t("sweep.staleCatalogue", {
              run: sweep.catalogueVersion ?? "—",
              current: sweep.currentCatalogueVersion ?? "—",
            })}
          </Note>
        ) : null}

        {sweep.offReferential.length > 0 ? (
          <Note tone="warning">
            {t("sweep.offReferential", { count: sweep.offReferential.length })}
          </Note>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Note({ children, tone }: { children: React.ReactNode; tone: "warning" }) {
  return (
    <div
      className={`flex items-start gap-2 rounded-md border p-2.5 text-xs leading-relaxed ${
        tone === "warning"
          ? "border-warning-500/30 bg-warning-50 text-warning-800 dark:bg-warning-700/15 dark:text-warning-100"
          : ""
      }`}
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
