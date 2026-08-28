import { getTranslations } from "next-intl/server";

import { ReleaseVerdictBand } from "@/components/surveiller/release-verdict-band";
import { Link } from "@/i18n/navigation";
import type { ReleaseControl } from "@/lib/api/schemas";
import { levelShortfalls, summarizeRelease, toAgentDecision } from "@/lib/release-verdict";

/**
 * The verdict that decides a release, on the view whose question it answers.
 *
 * `/surveiller/qualite-ia` carried every number about quality and not the one sentence an
 * operator opens it for. Worse, its two halves disagreed in silence: the per-agent table said
 * PRÊT three times while the evaluations view said BLOQUÉ three times, and both were true —
 * they describe different subjects (an agent's own eval set, versus a model on the shared
 * catalogue). Nothing said so, so the page read as self-contradictory.
 *
 * This ribbon used to sit above the view switch on BOTH views; the operator read that as the
 * monitoring view leading with the other view's headline, and they were right — "can this go
 * live" is the evaluations view's question. The full ribbon now leads that view only, and the
 * switch's evaluations DOOR carries its one-line summary, so the fact stays visible everywhere
 * without a foreign banner. Three rules it must keep:
 *
 *  · it names the CAUSE, never just the colour — the four blocking conditions are four
 *    different pieces of work and a banner that conflates them sends the operator nowhere;
 *  · it distinguishes "not evaluated" from "blocked", because silence is not a failure;
 *  · it refuses to say "all clear" while a level could not be READ. A blind instrument is not
 *    a passing one (ADR 0026).
 */
export async function ReleaseVerdictRibbon({
  control,
  locale,
}: {
  /** The release-control payload the page loaded — `null` when the backend could not answer. */
  control: ReleaseControl | null;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "quality" });

  // The backend could not answer. That is a blind spot about the WHOLE verdict, and it is said
  // rather than skipped: a page that silently omits its verdict looks like a page with nothing
  // to report.
  if (!control?.available || !control.agents?.length) {
    return (
      <ReleaseVerdictBand
        severity="info"
        title={t("verdict.unavailable")}
        meta={null}
        action={null}
      />
    );
  }

  const agents = control.agents.map(toAgentDecision);
  // A row whose `decision` never arrived cannot be judged. Older payloads (and any producer
  // that predates the field) would otherwise be read as "not evaluated", which is a claim.
  const undecidable = control.agents.filter((a) => a.decision === undefined).length;
  const verdict = summarizeRelease(agents);
  const shortfalls = levelShortfalls(agents);

  const worstAgents = verdict.blocked[0]?.agents ?? [];
  const title =
    verdict.worst === null
      ? verdict.notEvaluated.length > 0
        ? t("verdict.clearWithPending", {
            releasable: verdict.releasable,
            total: verdict.total,
            pending: verdict.notEvaluated.length,
          })
        : t("verdict.clear", { total: verdict.total })
      : t(`verdict.cause.${verdict.worst}`, {
          count: worstAgents.length,
          agents: worstAgents.map((a) => a.name).join(", "),
        });

  return (
    <ReleaseVerdictBand
      severity={undecidable > 0 && verdict.worst === null ? "info" : verdict.severity}
      title={title}
      meta={
        <span className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
          <span>{t("verdict.subject")}</span>
          {shortfalls.length > 0 ? (
            <>
              <span aria-hidden>·</span>
              <span>
                {t("verdict.levelShortfall", {
                  count: shortfalls.length,
                  reached: shortfalls[0]?.reached ?? "—",
                  required: shortfalls[0]?.required ?? "—",
                })}
              </span>
            </>
          ) : null}
          {undecidable > 0 ? (
            <>
              <span aria-hidden>·</span>
              <span>{t("verdict.undecidable", { count: undecidable })}</span>
            </>
          ) : null}
        </span>
      }
      action={
        <Link
          href={{ pathname: "/agir/release-control" }}
          className="inline-flex h-7 items-center rounded-md border border-[var(--ribbon-border)] px-2.5 text-xs font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--ribbon-hover)]"
        >
          {t("verdict.open")}
        </Link>
      }
    />
  );
}
