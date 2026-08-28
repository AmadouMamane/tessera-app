"use client";

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect } from "react";

import { useOptionalShellChrome } from "@/components/layout/shell-chrome";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";

export type CommandSearchPlan = "cockpit" | "business";

interface CommandSearchProps {
  plan?: CommandSearchPlan;
  compact?: boolean;
  className?: string;
  onOpen?: () => void;
}

export function CommandSearch({
  plan = "cockpit",
  compact = false,
  className,
  onOpen,
}: CommandSearchProps) {
  const t = useTranslations("commandSearch");
  const shell = useOptionalShellChrome();
  const open = useCallback(() => {
    if (onOpen) {
      onOpen();
      return;
    }
    shell?.setPaletteOpen(true);
  }, [onOpen, shell]);

  useEffect(() => {
    if (!onOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      const meta = event.metaKey || event.ctrlKey;
      if (meta && event.key.toLowerCase() === "k") {
        event.preventDefault();
        open();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onOpen, open]);

  const trigger = (
    <button
      type="button"
      aria-label={t(`scope.${plan}`)}
      title={compact ? undefined : t(`scope.${plan}`)}
      onClick={open}
      className={cn(
        compact
          ? "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-transparent bg-transparent text-[var(--tessera-text-muted)] outline-none transition-colors hover:text-[var(--tessera-text)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          : "inline-flex h-9 min-w-[13rem] items-center gap-2 rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] px-3 text-left text-xs text-[var(--tessera-text-muted)] outline-none transition-colors hover:bg-[var(--tessera-muted)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
        className,
      )}
    >
      <Search
        className={cn("shrink-0", compact ? "h-[18px] w-[18px]" : "h-4 w-4")}
        strokeWidth={1.75}
        aria-hidden
      />
      <span className={compact ? "sr-only" : "min-w-0 flex-1 truncate"}>{t("placeholder")}</span>
      {compact ? null : (
        <kbd className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-xs text-[var(--tessera-text-muted)]">
          {t("shortcut")}
        </kbd>
      )}
    </button>
  );

  if (!compact) return trigger;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{trigger}</TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={10}>
        {t("tooltip", { shortcut: t("shortcut") })}
      </TooltipContent>
    </Tooltip>
  );
}
