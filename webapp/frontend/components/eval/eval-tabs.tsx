import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/**
 * The three surfaces of this screen, and why they are three (spec §P3).
 *
 * A DATASET is a versioned artefact. A RUN is an event. The screen used to fold them into one
 * tab, which makes the central question of any evaluation unanswerable: *did the score move
 * because the model changed, or because the test changed?*
 *
 * The tabs are LINKS, not local state. Two consequences, both wanted: only the open tab is
 * rendered on the server (the catalogue is 63 cases, a run is 174 results — rendering all three
 * to switch between them is waste), and a tab is a URL an operator can send to someone.
 */
export type EvalTab = "cases" | "runs" | "compare";

export const EVAL_TABS: readonly EvalTab[] = ["cases", "runs"] as const;

/** The URL's `?tab=`, narrowed. An unknown value opens the runs — never a blank screen. */
export function parseTab(value: string | undefined): EvalTab {
  return EVAL_TABS.includes(value as EvalTab) ? (value as EvalTab) : "runs";
}

export function EvalTabs({
  active,
  labels,
}: {
  active: EvalTab;
  labels: Record<EvalTab, string>;
}) {
  return (
    <nav
      aria-label="sections"
      className="inline-flex self-start rounded-lg border border-[var(--border)] bg-[var(--muted)]/40 p-1"
    >
      {EVAL_TABS.map((tab) => (
        <Link
          key={tab}
          href={{ pathname: "/eval", query: { tab } }}
          aria-current={active === tab ? "page" : undefined}
          className={cn(
            "rounded-md px-3.5 py-1.5 font-medium text-sm transition-colors",
            active === tab
              ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
          )}
        >
          {labels[tab]}
        </Link>
      ))}
    </nav>
  );
}
