import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

/**
 * The way in to `/eval` — which had none.
 *
 * `/eval` holds the case set, the runs, the model comparison, the floor measured with no
 * model at all, and what a model adds over it. Nothing in the app linked to it: no sidebar
 * entry, no command-palette action, no cross-page link. It was reachable only by typing the
 * URL, which means in practice it was reachable by nobody.
 *
 * Meanwhile THIS page's subtitle promised "Évaluations, régressions…" and served a
 * continuous-monitoring dashboard. The promise and the page it was written on pointed at
 * two different things, and the thing it promised had no door. This is the door; the
 * subtitle now describes what this page actually serves.
 *
 * It lives in the page CONTENT on purpose. The shared chrome (sidebar, header) is another
 * lane's file, and two agents editing it is how a worktree gets corrupted.
 */
export function EvalDoor() {
  const t = useTranslations("quality.evalDoor");
  return (
    <Link
      href="/eval"
      className="group mb-5 flex items-center justify-between gap-4 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 transition-colors hover:border-[var(--foreground)]/25"
    >
      <div className="min-w-0">
        <p className="font-medium text-[var(--foreground)] text-sm">{t("lead")}</p>
        <p className="mt-0.5 text-[var(--muted-foreground)] text-xs">{t("body")}</p>
      </div>
      <span className="inline-flex shrink-0 items-center gap-1.5 font-medium text-[var(--foreground)] text-xs">
        {t("cta")}
        <ArrowRight
          aria-hidden
          className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
        />
      </span>
    </Link>
  );
}
