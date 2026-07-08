"use client";

import { Search } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect } from "react";

import { useOptionalShellChrome } from "@/components/layout/shell-chrome";
import { cn } from "@/lib/cn";

export type CommandSearchPlan = "cockpit" | "business";

interface CommandSearchProps {
  plan?: CommandSearchPlan;
  className?: string;
  onOpen?: () => void;
}

export function CommandSearch({ plan = "cockpit", className, onOpen }: CommandSearchProps) {
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

  return (
    <button
      type="button"
      aria-label={t(`scope.${plan}`)}
      onClick={open}
      className={cn(
        "inline-flex h-9 min-w-[13rem] items-center gap-2 rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] px-3 text-left text-xs text-[var(--tessera-text-muted)] outline-none transition-colors hover:bg-[var(--tessera-muted)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
        className,
      )}
    >
      <Search className="h-4 w-4 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1 truncate">{t("placeholder")}</span>
      <kbd className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
        {t("shortcut")}
      </kbd>
    </button>
  );
}
