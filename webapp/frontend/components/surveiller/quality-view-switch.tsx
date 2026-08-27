import { Activity, ChevronRight, FlaskConical } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { EVAL_PATHNAME, EVAL_VIEW_PARAM, EVAL_VIEW_VALUE } from "@/components/eval/eval-route";
import { Link } from "@/i18n/navigation";
import type { ReleaseControl } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { summarizeRelease, toAgentDecision } from "@/lib/release-verdict";

export type QualityView = "signals" | "evaluations";

/** The door status dot, from the verdict's own severity — never a colour chosen here. */
const DOT: Record<string, string> = {
  critical: "bg-red-500",
  warning: "bg-amber-500",
  info: "bg-sky-500",
  ok: "bg-emerald-500",
};

/**
 * The two views of Qualité IA, as two labelled doors — never a bare toggle.
 *
 * This replaces the EvalDoor banner: `/eval` was an orphan (zero inbound links) and the
 * banner was the way in; the eval screen now lives ON this page, so the way in is a view
 * switch. The doctrine the banner's tests carried still holds here: each door SAYS what is
 * behind it (its sublabel names the content), because a door that only says "other view"
 * teaches the visitor nothing and hides the screen it guards.
 *
 * Two lessons this component had to relearn from the operator:
 *
 *  · **A door must look like a door.** The first version was two bordered cards — no icon, no
 *    arrow, no verb — and read as static summaries. Each door now carries an explicit "open"
 *    affordance and the active one says it is the open view, so a visitor knows both that they
 *    can enter and where they already are.
 *  · **The go-live verdict lives where its question lives.** The full ribbon used to sit above
 *    this switch on BOTH views, so the monitoring view led with the other view's headline. The
 *    ribbon now leads the evaluations view only; here, its one-line summary rides ON the door to
 *    that view — the fact stays visible on both views, at the size of a door caption, and the
 *    per-agent PRÊT column below keeps its explainer without the foreign banner.
 */
export async function QualityViewSwitch({
  active,
  locale,
  control,
}: {
  active: QualityView;
  locale: string;
  /** The release-control payload the page already loaded — `null` when it could not be read. */
  control: ReleaseControl | null;
}) {
  const t = await getTranslations({ locale, namespace: "quality" });
  const views = [
    {
      key: "signals" as const,
      href: { pathname: EVAL_PATHNAME },
      icon: Activity,
      label: t("views.signals"),
      sub: t("views.signalsSub"),
      status: null,
    },
    {
      key: "evaluations" as const,
      href: { pathname: EVAL_PATHNAME, query: { [EVAL_VIEW_PARAM]: EVAL_VIEW_VALUE } },
      icon: FlaskConical,
      label: t("views.evaluations"),
      sub: t("views.evaluationsSub"),
      status: doorVerdict(control, t),
    },
  ];
  return (
    <nav aria-label={t("views.ariaLabel")} className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {views.map((view) => {
        const isActive = active === view.key;
        return (
          <Link
            key={view.key}
            href={view.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "group flex items-center gap-3 rounded-lg border px-4 py-2.5 transition-colors",
              isActive
                ? "border-[#7c5cf5]/50 bg-[#7c5cf5]/10"
                : "border-[var(--tessera-border)] bg-[var(--tessera-surface)] hover:border-[#7c5cf5]/40 hover:bg-[#7c5cf5]/5",
            )}
          >
            <span
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border",
                isActive
                  ? "border-[#7c5cf5]/40 bg-[#7c5cf5]/15 text-[var(--tessera-text)]"
                  : "border-[var(--tessera-border)] bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]",
              )}
            >
              <view.icon className="h-4 w-4" aria-hidden />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[0.8rem] font-semibold">{view.label}</span>
              <span className="mt-0.5 block text-[0.66rem] text-[var(--tessera-text-muted)]">
                {view.sub}
              </span>
              {view.status ? (
                <span className="mt-1 flex items-center gap-1.5 text-[0.66rem]">
                  <span
                    className={cn("h-1.5 w-1.5 shrink-0 rounded-full", view.status.dot)}
                    aria-hidden
                  />
                  <span className="min-w-0 truncate text-[var(--tessera-text)]">
                    {view.status.text}
                  </span>
                </span>
              ) : null}
            </span>
            {isActive ? (
              <span className="shrink-0 text-[0.66rem] font-medium uppercase tracking-wide text-[var(--tessera-fg-accent)]">
                {t("views.current")}
              </span>
            ) : (
              <span className="flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)] transition-colors group-hover:text-[var(--tessera-text)]">
                {t("views.enter")}
                <ChevronRight
                  className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * The verdict at door size: ready count, blocked count, never-evaluated count.
 *
 * An unreadable payload is said as such — a door that shows a green dot because it could not
 * ask is a witness reporting "ok" from a blind spot (ADR 0026).
 */
function doorVerdict(
  control: ReleaseControl | null,
  t: Awaited<ReturnType<typeof getTranslations>>,
): { dot: string; text: string } {
  if (!control?.available || !control.agents?.length) {
    return {
      dot: "bg-[var(--tessera-text-muted)]",
      text: t("views.verdict.unavailable"),
    };
  }
  const verdict = summarizeRelease(control.agents.map(toAgentDecision));
  const blockedCount = verdict.blocked.reduce((n, b) => n + b.agents.length, 0);
  const parts = [
    t("views.verdict.ready", { releasable: verdict.releasable, total: verdict.total }),
  ];
  if (blockedCount > 0) parts.push(t("views.verdict.blocked", { count: blockedCount }));
  if (verdict.notEvaluated.length > 0) {
    parts.push(t("views.verdict.notEvaluated", { count: verdict.notEvaluated.length }));
  }
  return {
    dot: DOT[verdict.severity] ?? "bg-[var(--tessera-text-muted)]",
    text: parts.join(" · "),
  };
}
