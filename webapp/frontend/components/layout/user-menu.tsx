"use client";

import { ChevronDown, Languages, LogOut, Palette, Repeat2 } from "lucide-react";
import { signOut } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useState, useTransition } from "react";

import { ThemeSwatch } from "@/components/layout/theme-swatch";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { LOCALE_LABELS, type Locale, routing } from "@/i18n/routing";
import { cn } from "@/lib/cn";

interface UserMenuProps {
  role: string;
  className?: string;
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "··";
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
  return (first + last).toUpperCase() || "··";
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

export function UserMenu({ role, className }: UserMenuProps) {
  const t = useTranslations("auth");
  const tc = useTranslations("common");
  const tt = useTranslations("common.theme");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const { setTheme } = useTheme();
  const [, startTransition] = useTransition();
  const [sessionStartedAt] = useState(() => new Date());
  const roleLabel = t(`roles.${role}`);
  const sessionTime = new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(sessionStartedAt);

  function selectLocale(next: string) {
    if (next === locale) return;
    startTransition(() => {
      router.replace(pathname, { locale: next as Locale });
    });
  }

  async function onSignOut() {
    await signOut({ redirect: false });
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("menuLabel", { role: roleLabel })}
          className={cn(
            "flex items-center gap-2 rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] py-1 pl-1 pr-2 text-left outline-none transition-colors hover:bg-[var(--tessera-muted)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            className,
          )}
        >
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-green-soft)] text-[0.7rem] font-semibold text-[var(--tessera-green)]">
            {initials(roleLabel)}
          </span>
          <span className="hidden min-w-0 flex-col sm:flex">
            <span className="truncate text-xs font-medium text-[var(--tessera-text)]">
              {roleLabel}
            </span>
            <span className="truncate text-[0.62rem] leading-tight text-[var(--tessera-text-muted)]">
              {t("sessionActive", { time: sessionTime })}
            </span>
          </span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[15rem]">
        <DropdownMenuLabel>{t("signedInAs", { role: roleLabel })}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/login" className="flex items-center gap-2">
            <Repeat2 className="h-4 w-4" />
            {t("changeAccount")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void onSignOut()} className="flex items-center gap-2">
          <LogOut className="h-4 w-4" />
          {t("signOut")}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="flex items-center gap-2 normal-case tracking-normal">
          <Languages className="h-3.5 w-3.5" />
          {tc("language")}
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup value={locale} onValueChange={selectLocale}>
          {routing.locales.map((option) => (
            <DropdownMenuRadioItem key={option} value={option}>
              <span className="flex w-full items-center justify-between gap-4">
                <span>{LOCALE_LABELS[option].native}</span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  {LOCALE_LABELS[option].short}
                </span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="flex items-center gap-2 normal-case tracking-normal">
          <Palette className="h-3.5 w-3.5" />
          {tt("label")}
        </DropdownMenuLabel>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("light"))}>
          <ThemeSwatch theme="light" className="mr-2" />
          {tt("light")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("dark"))}>
          <ThemeSwatch theme="dark" className="mr-2" />
          {tt("dark")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("deep-night"))}>
          <ThemeSwatch theme="deep-night" className="mr-2" />
          {tt("slate")}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => withTransition(() => setTheme("system"))}>
          <ThemeSwatch theme="system" className="mr-2" />
          {tt("system")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
