"use client";

import {
  Check,
  CircleHelp,
  CircleUserRound,
  FileText,
  Gauge,
  Languages,
  LogOut,
  Palette,
  Plus,
  Repeat2,
  Settings,
  SlidersHorizontal,
  Store,
} from "lucide-react";
import { signOut } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { useState, useTransition } from "react";

import { ThemeSwatch } from "@/components/layout/theme-swatch";
import {
  DropdownMenu,
  DropdownMenuChevron,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { LOCALE_LABELS, type Locale, routing } from "@/i18n/routing";
import { cn } from "@/lib/cn";

interface UserMenuProps {
  role: string;
  compact?: boolean;
  className?: string;
}

type OpenSubmenu = "account" | "customize" | "help" | null;

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

export function UserMenu({ role, compact = false, className }: UserMenuProps) {
  const t = useTranslations("auth");
  const tc = useTranslations("common");
  const tt = useTranslations("common.theme");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const { setTheme } = useTheme();
  const [, startTransition] = useTransition();
  const [openSubmenu, setOpenSubmenu] = useState<OpenSubmenu>(null);
  const roleLabel = t(`roles.${role}`);

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

  function controlSubmenu(key: Exclude<OpenSubmenu, null>) {
    return (open: boolean) => {
      setOpenSubmenu((current) => (open ? key : current === key ? null : current));
    };
  }

  return (
    <DropdownMenu onOpenChange={(open) => !open && setOpenSubmenu(null)}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("menuLabel", { role: roleLabel })}
          className={cn(
            "flex items-center border border-transparent text-left outline-none transition-colors",
            compact ? "h-10 w-10 justify-center rounded-full p-1" : "w-full gap-2 rounded-lg p-2",
            "hover:border-[var(--tessera-border)] hover:bg-[var(--tessera-muted)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            "data-[state=open]:border-[var(--tessera-border-strong)] data-[state=open]:bg-[var(--tessera-muted)]",
            className,
          )}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-green)] text-[0.68rem] font-semibold text-[#031810]">
            {initials(roleLabel)}
          </span>
          {compact ? null : (
            <>
              <span className="hidden min-w-0 flex-1 flex-col md:flex">
                <span className="truncate text-[0.78rem] font-medium text-[var(--tessera-text)]">
                  {roleLabel}
                </span>
                <span className="truncate text-[0.62rem] leading-tight text-[var(--tessera-text-muted)]">
                  {t("operatorAccount")}
                </span>
              </span>
              <Store className="hidden h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] md:block" />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        side={compact ? "bottom" : "top"}
        align={compact ? "end" : "start"}
        sideOffset={6}
        className={cn(
          "rounded-xl p-1.5",
          compact
            ? "w-[14rem] min-w-[14rem]"
            : "w-[var(--radix-dropdown-menu-trigger-width)] min-w-[14rem] md:min-w-[var(--radix-dropdown-menu-trigger-width)]",
        )}
      >
        <DropdownMenuSub open={openSubmenu === "account"} onOpenChange={controlSubmenu("account")}>
          <DropdownMenuSubTrigger className="gap-2 rounded-lg">
            <CircleUserRound className="h-4 w-4" />
            {t("accounts")}
            <DropdownMenuChevron className="ml-auto h-4 w-4 text-[var(--tessera-text-muted)]" />
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="min-w-[16.5rem]">
            <DropdownMenuItem
              onSelect={(event) => event.preventDefault()}
              className="gap-2 rounded-lg px-2 py-2"
            >
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-green)] text-[0.56rem] font-semibold text-[#031810]">
                {initials(roleLabel)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs font-medium">{roleLabel}</span>
                <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {t("currentAccount")}
                </span>
              </span>
              <Check className="h-4 w-4 shrink-0" />
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild className="rounded-lg">
              <Link href="/login" className="flex items-center gap-2">
                <Plus className="h-4 w-4" />
                {t("addAccount")}
              </Link>
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild className="rounded-lg">
          <Link href="/login" className="flex items-center gap-2">
            <Repeat2 className="h-4 w-4" />
            {t("changeAccount")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSub
          open={openSubmenu === "customize"}
          onOpenChange={controlSubmenu("customize")}
        >
          <DropdownMenuSubTrigger className="gap-2 rounded-lg">
            <SlidersHorizontal className="h-4 w-4" />
            {t("customize")}
            <DropdownMenuChevron className="ml-auto h-4 w-4 text-[var(--tessera-text-muted)]" />
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="min-w-[16.5rem]">
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
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuItem asChild className="rounded-lg">
          <Link href="/admin/profil-systeme" className="flex items-center gap-2">
            <CircleUserRound className="h-4 w-4" />
            {t("profile")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="rounded-lg">
          <Link href="/configurer/parametres" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            {t("settings")}
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuSub open={openSubmenu === "help"} onOpenChange={controlSubmenu("help")}>
          <DropdownMenuSubTrigger className="gap-2 rounded-lg">
            <CircleHelp className="h-4 w-4" />
            {t("help")}
            <DropdownMenuChevron className="ml-auto h-4 w-4 text-[var(--tessera-text-muted)]" />
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent className="min-w-[16.5rem]">
            <DropdownMenuItem asChild className="rounded-lg">
              <Link href="/comprendre" className="flex items-center gap-2">
                <Gauge className="h-4 w-4" />
                {t("understand")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild className="rounded-lg">
              <Link href="/comprendre/en-detail" className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                {t("detailedGuide")}
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild className="rounded-lg">
              <Link href="/settings" className="flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4" />
                {t("preferences")}
              </Link>
            </DropdownMenuItem>
          </DropdownMenuSubContent>
        </DropdownMenuSub>
        <DropdownMenuItem
          onSelect={() => void onSignOut()}
          className="flex items-center gap-2 rounded-lg"
        >
          <LogOut className="h-4 w-4" />
          {t("signOut")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
