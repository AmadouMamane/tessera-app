"use client";

import { Construction } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Placeholder view for routes whose content is not built yet.
 *
 * Each scaffolded leaf is already a real, deep-linkable route with its own
 * module; this renders a clean, honest empty state until the page is wired to
 * its data source. The loading / error states live in the data-bound pages that
 * replace it (see the catalogue pages for the pattern).
 */
export function ScaffoldView({ title }: { title: string }) {
  const t = useTranslations("scaffold");
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center py-16">
      <div className="flex max-w-md flex-col items-center gap-3 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-8 text-center">
        <span className="grid h-12 w-12 place-items-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
          <Construction className="h-5 w-5" />
        </span>
        <h2 className="text-sm font-semibold text-[var(--tessera-text)]">{title}</h2>
        <p className="text-[0.8rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {t("body")}
        </p>
      </div>
    </div>
  );
}
