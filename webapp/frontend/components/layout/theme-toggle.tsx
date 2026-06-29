"use client";

import { Monitor, Moon, MoonStar, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

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

  const Icon =
    !mounted || resolvedTheme === "light"
      ? Sun
      : resolvedTheme === "deep-night"
        ? MoonStar
        : resolvedTheme === "dark"
          ? Moon
          : Monitor;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={className}
          aria-label={t("label")}
          aria-haspopup="menu"
        >
          <Icon className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[8rem]">
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("light"))}>
          <Sun className="mr-2 h-4 w-4" />
          {t("light")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("dark"))}>
          <Moon className="mr-2 h-4 w-4" />
          {t("dark")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("deep-night"))}>
          <MoonStar className="mr-2 h-4 w-4" />
          {t("deepNight")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("system"))}>
          <Monitor className="mr-2 h-4 w-4" />
          {t("system")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
