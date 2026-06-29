"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { ThemeSwatch } from "@/components/layout/theme-swatch";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/cn";

interface ThemeToggleProps {
  className?: string;
}

function withTransition(callback: () => void) {
  document.documentElement.classList.add("theme-transitioning");
  callback();
  const timer = setTimeout(
    () => document.documentElement.classList.remove("theme-transitioning"),
    200,
  );
  return () => clearTimeout(timer);
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { setTheme, resolvedTheme } = useTheme();
  const t = useTranslations("common.theme");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Trigger glyph: a light/dark/auto affordance (the menu carries the per-theme
  // colour swatches). Both dark themes share the moon — the swatch tells them apart.
  const Icon =
    !mounted || resolvedTheme === "light" ? Sun : resolvedTheme === "system" ? Monitor : Moon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          // Neutral focus ring instead of the green --ring, so picking an appearance
          // never leaves a green halo around this round control.
          className={cn("[--ring:var(--tessera-border-strong)]", className)}
          aria-label={t("label")}
          aria-haspopup="menu"
        >
          <Icon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[9rem]">
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("light"))}>
          <ThemeSwatch theme="light" className="mr-2" />
          {t("light")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("dark"))}>
          <ThemeSwatch theme="dark" className="mr-2" />
          {t("dark")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("deep-night"))}>
          <ThemeSwatch theme="deep-night" className="mr-2" />
          {t("slate")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("system"))}>
          <ThemeSwatch theme="system" className="mr-2" />
          {t("system")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
