import { EVAL_PATHNAME, evalQuery } from "@/components/eval/eval-route";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/**
 * The surfaces of the evaluations view, and why they are grouped (spec §P3, boundary migration).
 *
 * A DATASET is a versioned artefact. A RUN is an event. The screen used to fold them into one
 * tab, which makes the central question of any evaluation unanswerable: *did the score move
 * because the model changed, or because the test changed?*
 *
 * Four more surfaces arrived from the monitoring dashboard, where they never belonged: they read
 * the eval report archive and the judge's gold set, not a single live turn. Arriving here they
 * created a worse problem than the one they left, and it is a numeric one:
 *
 *     model          this sitting (12 Jul, re-judged 5 Aug)   the archive
 *     llama3.2:3b               160/174 = 92.0 %              51.7 % over 59 runs
 *     llama3.3:70b              157/174 = 90.2 %              58.3 % over 2 runs
 *     gemma3:27b                157/174 = 90.2 %              86.8 % over 1 run
 *
 * Forty points apart for the same model, and the ranking INVERTS. Both are true; they are
 * different populations judged by different rulers at different dates. Side by side in one flat
 * strip, with nothing between them, the page would contradict itself in silence — which is why
 * the tabs are grouped by the population they read, and each group says which one it is.
 *
 * The tabs are LINKS, not local state. Two consequences, both wanted: only the open tab is
 * rendered on the server, and a tab is a URL an operator can send to someone.
 */
export type EvalTab =
  // ── One sitting: the 63-case catalogue × 3 languages, three models, one ruler ──
  | "cases"
  | "runs"
  | "compare"
  // ── The archive: every report under `eval/reports`, months deep, models and eval sets mixed ──
  | "archive"
  | "failed"
  | "models"
  // ── The judge: agreement with the human gold set. Neither of the two above. ──
  | "judge";

/** The strip's groups, in render order. A group's label names the POPULATION its tabs read. */
export const EVAL_TAB_GROUPS = [
  { key: "sweep", tabs: ["cases", "runs", "compare"] },
  { key: "archive", tabs: ["archive", "failed", "models"] },
  { key: "judge", tabs: ["judge"] },
] as const satisfies readonly { key: string; tabs: readonly EvalTab[] }[];

export type EvalTabGroup = (typeof EVAL_TAB_GROUPS)[number]["key"];

export const EVAL_TABS: readonly EvalTab[] = EVAL_TAB_GROUPS.flatMap((g) => g.tabs);

/** The URL's `?tab=`, narrowed. An unknown value opens the runs — never a blank screen. */
export function parseTab(value: string | undefined): EvalTab {
  return EVAL_TABS.includes(value as EvalTab) ? (value as EvalTab) : "runs";
}

export function EvalTabs({
  active,
  labels,
  groupLabels,
}: {
  active: EvalTab;
  labels: Record<EvalTab, string>;
  groupLabels: Record<EvalTabGroup, string>;
}) {
  return (
    <nav
      aria-label="sections"
      // Wraps: seven tabs plus three group captions need ~980px, and below that the last group
      // used to run off the card with no way to reach it.
      className="flex flex-wrap items-stretch gap-1.5 self-start"
    >
      {EVAL_TAB_GROUPS.map((group) => (
        <div
          key={group.key}
          // The caption is what keeps 92 % and 51.7 % from reading as a contradiction, so it is
          // part of the control, not a legend somewhere else on the page.
          className="flex min-w-0 flex-col gap-0.5 rounded-lg border border-[var(--border)] bg-[var(--muted)]/40 px-1 pb-1 pt-0.5"
        >
          <span className="px-2 text-[0.6rem] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
            {groupLabels[group.key]}
          </span>
          <div className="flex">
            {group.tabs.map((tab) => (
              <Link
                key={tab}
                href={{ pathname: EVAL_PATHNAME, query: evalQuery({ tab }) }}
                aria-current={active === tab ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 font-medium text-sm transition-colors",
                  active === tab
                    ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
                )}
              >
                {labels[tab]}
              </Link>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}
