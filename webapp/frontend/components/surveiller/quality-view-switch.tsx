import { getTranslations } from "next-intl/server";

import { EVAL_PATHNAME, EVAL_VIEW_PARAM, EVAL_VIEW_VALUE } from "@/components/eval/eval-route";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

export type QualityView = "signals" | "evaluations";

/**
 * The two views of Qualité IA, as two labelled doors — never a bare toggle.
 *
 * This replaces the EvalDoor banner: `/eval` was an orphan (zero inbound links) and the
 * banner was the way in; the eval screen now lives ON this page, so the way in is a view
 * switch. The doctrine the banner's tests carried still holds here: each door SAYS what is
 * behind it (its sublabel names the content), because a door that only says "other view"
 * teaches the visitor nothing and hides the screen it guards.
 */
export async function QualityViewSwitch({
  active,
  locale,
}: {
  active: QualityView;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "quality" });
  const views = [
    {
      key: "signals" as const,
      href: { pathname: EVAL_PATHNAME },
      label: t("views.signals"),
      sub: t("views.signalsSub"),
    },
    {
      key: "evaluations" as const,
      href: { pathname: EVAL_PATHNAME, query: { [EVAL_VIEW_PARAM]: EVAL_VIEW_VALUE } },
      label: t("views.evaluations"),
      sub: t("views.evaluationsSub"),
    },
  ];
  return (
    <nav aria-label={t("views.ariaLabel")} className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
      {views.map((view) => (
        <Link
          key={view.key}
          href={view.href}
          aria-current={active === view.key ? "page" : undefined}
          className={cn(
            "rounded-lg border px-4 py-2.5 transition-colors",
            active === view.key
              ? "border-[#7c5cf5]/50 bg-[#7c5cf5]/10"
              : "border-[var(--tessera-border)] bg-[var(--tessera-surface)] hover:border-[#7c5cf5]/30",
          )}
        >
          <span className="block text-[0.8rem] font-semibold">{view.label}</span>
          <span className="mt-0.5 block text-[0.66rem] text-[var(--tessera-text-muted)]">
            {view.sub}
          </span>
        </Link>
      ))}
    </nav>
  );
}
