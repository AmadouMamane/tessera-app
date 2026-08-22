"use client";

import { EyeOff, Gavel, Ruler } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";
import { useDeclaredQualityRegime } from "@/lib/use-quality-regime";

/**
 * The agent command-bar's rating-method chip (ADR 0017 §Amendment 4): every agent page
 * names, in two words, HOW this agent's answers are rated — the same declaration the
 * quality band renders, read through the same query. It links to the quality page, where
 * the three methods are explained side by side.
 *
 * States: pending or an undeclared id render nothing (a chip is an affordance, not a
 * report — but a FAILED read is still named, never silently absent); the three regimes
 * render their short label with the band's icon grammar, the full label as the tooltip.
 */
const CHIP: Record<string, { icon: typeof Gavel; short: string; full: string; accent: string }> = {
  llm_judged: {
    icon: Gavel,
    short: "chip.llm_judged",
    full: "llm_judged.label",
    accent: "border-[#7c5cf5]/40 text-[var(--tessera-text)]",
  },
  business_scored: {
    icon: Ruler,
    short: "chip.business_scored",
    full: "business_scored.label",
    accent: "border-emerald-500/40 text-[var(--tessera-text)]",
  },
  unscored: {
    icon: EyeOff,
    short: "chip.unscored",
    full: "unscored.label",
    accent: "border-[var(--tessera-border)] text-[var(--tessera-text-muted)]",
  },
};

const CHIP_BASE =
  "inline-flex shrink-0 items-center gap-1.5 rounded-full border bg-[var(--tessera-surface)] px-2.5 py-1 text-[0.64rem] font-medium";

export function RatingMethodChip({ agentId }: { agentId: string }) {
  const t = useTranslations("qualityRegimes");
  const { entry, isError } = useDeclaredQualityRegime(agentId);
  if (isError) {
    // The failed read is named: an absent chip would read as "no declared method".
    return (
      <span
        className={cn(CHIP_BASE, "border-[var(--tessera-border)] text-[var(--tessera-text-muted)]")}
      >
        {t("chip.unreadable")}
      </span>
    );
  }
  if (!entry) return null;
  const style = CHIP[entry.regime];
  if (!style) return null;
  const Icon = style.icon;
  return (
    <Link
      href="/surveiller/qualite-ia"
      title={t(style.full)}
      className={cn(
        CHIP_BASE,
        style.accent,
        "transition-colors hover:text-[var(--tessera-text-strong)]",
      )}
    >
      <Icon className="h-3 w-3" aria-hidden />
      {t(style.short)}
    </Link>
  );
}
