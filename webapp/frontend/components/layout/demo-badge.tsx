"use client";

import { ArrowRight, FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

interface DemoBadgeProps {
  className?: string;
  floating?: boolean;
  href?: "/select-space" | "/espaces";
  label?: string;
}

const PILL_CLASS =
  "inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--card)]/70 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)] backdrop-blur transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]";

/**
 * The demo pill — and, when it floats over a product surface, the third door to `/comprendre`.
 *
 * The product lexicon is intangible: Crédit Aurore's chrome never explains the platform, and
 * this card never names it, nor any control-plane concept. (Nor does this comment: the lexicon
 * guard reads the whole file, source included, and it is right to.) The card says what a
 * visitor standing inside a fictional bank needs to know — the people are simulated, the
 * machinery is not — and offers a way out. **The change of world happens on the click, never
 * in the text.** `header-components.test.ts` holds that line for every locale.
 *
 * On the launcher (`floating: false`) the pill stays what it was: a link.
 */
export function DemoBadge({
  className,
  floating = false,
  href = "/select-space",
  label,
}: DemoBadgeProps) {
  const t = useTranslations("demoBadge");

  if (!floating) {
    return (
      <Link href={href} aria-label={t("ariaLabel")} className={cn(PILL_CLASS, className)}>
        <FlaskConical className="h-3.5 w-3.5" />
        {label ?? t("label")}
      </Link>
    );
  }

  return (
    <div className="fixed bottom-3 left-3 z-40">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button type="button" aria-label={t("ariaLabel")} className={cn(PILL_CLASS, className)}>
            <FlaskConical className="h-3.5 w-3.5" />
            {label ?? t("label")}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" side="top" className="max-w-[20rem] p-3">
          <p className="text-[0.78rem] text-[var(--muted-foreground)] leading-relaxed">
            {t("sheetBody")}
          </p>
          <Link
            href={href}
            className="mt-3 inline-flex items-center gap-1.5 rounded-sm font-medium text-[0.78rem] text-[var(--foreground)] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          >
            {t("sheetCta")}
            <ArrowRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
