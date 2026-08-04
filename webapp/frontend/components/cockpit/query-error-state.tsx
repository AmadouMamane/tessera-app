"use client";

import { RefreshCw, ServerOff } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/** Honest, reusable replacement for a spinner that would otherwise never resolve. */
export function QueryErrorState({
  onRetry,
  retrying = false,
  compact = false,
  className,
}: {
  onRetry: () => void;
  retrying?: boolean;
  /** Fit the state inside a drawer, table cell or narrow side rail. */
  compact?: boolean;
  className?: string;
}) {
  const t = useTranslations("queryError");
  return (
    <section
      role="alert"
      className={cn(
        "grid place-items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[var(--shadow-card)]",
        compact ? "min-h-0 px-3 py-5" : "min-h-[280px] px-5 py-10",
        className,
      )}
    >
      <div className="flex max-w-md flex-col items-center text-center">
        <span
          className={cn(
            "grid place-items-center rounded-xl border border-red-500/20 bg-red-500/[0.08] text-[var(--tessera-fg-danger)]",
            compact ? "mb-3 h-8 w-8" : "mb-4 h-10 w-10",
          )}
        >
          <ServerOff className="h-4.5 w-4.5" aria-hidden="true" />
        </span>
        <h2 className="text-sm font-semibold text-[var(--tessera-text)]">{t("title")}</h2>
        <p className="mt-1.5 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
          {t("detail")}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onRetry}
          disabled={retrying}
          className={compact ? "mt-3" : "mt-5"}
        >
          <RefreshCw className={retrying ? "animate-spin motion-reduce:animate-none" : undefined} />
          {retrying ? t("retrying") : t("retry")}
        </Button>
      </div>
    </section>
  );
}
