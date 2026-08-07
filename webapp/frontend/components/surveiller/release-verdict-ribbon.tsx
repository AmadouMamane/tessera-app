import { CheckCircle2, ShieldAlert } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { AlertRibbon } from "@/components/cockpit/alert-ribbon";
import { Link } from "@/i18n/navigation";
import type { ReleaseControlAgent } from "@/lib/api/schemas";
import { type AgentDecision, levelShortfalls, summarizeRelease } from "@/lib/release-verdict";
import { loadReleaseControl } from "@/lib/server/fleet";

/**
 * The verdict that decides a release, on the page named after it.
 *
 * `/surveiller/qualite-ia` carried every number about quality and not the one sentence an
 * operator opens it for. Worse, its two halves disagreed in silence: the per-agent table said
 * PRÊT three times while the evaluations view said BLOQUÉ three times, and both were true —
 * they describe different subjects (an agent's own eval set, versus a model on the shared
 * catalogue). Nothing said so, so the page read as self-contradictory.
 *
 * This ribbon sits ABOVE the view switch, so it holds on both views, and it states its subject
 * in its own first words. Three rules it must keep:
 *
 *  · it names the CAUSE, never just the colour — the four blocking conditions are four
 *    different pieces of work and a banner that conflates them sends the operator nowhere;
 *  · it distinguishes "not evaluated" from "blocked", because silence is not a failure;
 *  · it refuses to say "all clear" while a level could not be READ. A blind instrument is not
 *    a passing one (ADR 0026).
 */
export async function ReleaseVerdictRibbon({
  scope,
  locale,
}: {
  scope: string;
  locale: string;
}) {
  const [control, t] = await Promise.all([
    loadReleaseControl(scope, locale),
    getTranslations({ locale, namespace: "quality" }),
  ]);

  // The backend could not answer. That is a blind spot about the WHOLE verdict, and it is said
  // rather than skipped: a page that silently omits its verdict looks like a page with nothing
  // to report.
  if (!control?.available || !control.agents?.length) {
    return (
      <AlertRibbon
        variant="slim"
        severity="info"
        icon={ShieldAlert}
        title={t("verdict.unavailable")}
      />
    );
  }

  const agents = control.agents.map(toDecision);
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
    <AlertRibbon
      variant="slim"
      severity={undecidable > 0 && verdict.worst === null ? "info" : verdict.severity}
      icon={verdict.worst === null && undecidable === 0 ? CheckCircle2 : ShieldAlert}
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
          className="inline-flex h-7 items-center rounded-md border border-[var(--ribbon-border)] px-2.5 text-[11px] font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--ribbon-hover)]"
        >
          {t("verdict.open")}
        </Link>
      }
    />
  );
}

function toDecision(agent: ReleaseControlAgent): AgentDecision {
  const d = agent.decision;
  return {
    agentId: agent.agent_id,
    name: agent.name,
    // Without a decision the row is not "allowed" and not "run" — it is unjudgeable, and it is
    // counted as such by the caller rather than defaulted into either bucket.
    allowed: d?.allowed ?? false,
    hasRun: d?.has_run ?? false,
    blockedBy: d?.blocked_by ?? null,
    observabilityLevel: d?.observability_level ?? null,
    requiredLevel: d?.required_level ?? null,
    floorRegressions: d?.floor_regressions ?? [],
  };
}
