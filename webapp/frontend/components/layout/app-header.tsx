"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  Boxes,
  CalendarDays,
  ChevronDown,
  CircleHelp,
  Download,
  Globe2,
  PackageCheck,
  RotateCcw,
  Search,
  ServerCog,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useEffect, useState, useTransition } from "react";

import { type AuthContext, AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { ModelBadge } from "@/components/layout/model-badge";
import { useShellChrome } from "@/components/layout/shell-chrome";
import { StatusBadge } from "@/components/layout/status-badge";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { LOCALE_LABELS, type Locale, routing } from "@/i18n/routing";
import { fetchHealth } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { exportSnapshot } from "@/lib/evidence-export";
import {
  CHAT_MODELS,
  CHAT_MODEL_EVENT,
  DEFAULT_CHAT_MODEL,
  findModel,
  getStoredModel,
  setStoredModel,
} from "@/lib/models";
import { useWindowStore } from "@/lib/stores/window-store";

/**
 * The single application header (see `docs/design/header-normative.md`).
 *
 * ONE parameterized shell, THREE plan variants — never a per-page header and
 * never one identical header everywhere. Three zones:
 *   LEFT   — brand (one mark) OR title when the brand lives in a side rail.
 *   CENTER — title + subtitle (absent on the launcher).
 *   RIGHT  — `[ contextual ] ‖ [ global ]`, where the global cluster
 *            (langue · thème · compte) is rendered in the SAME ORDER on every
 *            surface. That fixed right-hand order is the load-bearing invariant.
 */
export type HeaderPlan = "launcher" | "cockpit" | "business";

export interface HeaderContextItem {
  label: string;
  value: string;
  tone?: "default" | "success";
  leading?: "status" | "history" | "globe";
  trailing?: "chevron" | "calendar";
  /**
   * Makes the control interactive: a real locale/model switch, a generic select,
   * or `window` — the shared temporal window (single owner, read by the rail).
   */
  control?: "locale" | "model" | "select" | "window";
  /** Options for `control: "select"`. */
  options?: { value: string; label: string }[];
}

export interface HeaderAction {
  label: string;
  icon: "download" | "evidence";
  variant: "outline" | "accent";
  /** Behaviour triggered on click. */
  action?: "export" | "evidence";
}

interface AppHeaderProps {
  plan: HeaderPlan;
  /**
   * Anonymous behaviour of the account control. Defaults per plan: launcher →
   * `demo`, cockpit → `gated`, business → `optional`. Override `business` to
   * `gated` for an already-gated business surface (e.g. the collections console)
   * so it never shows a "sign in" prompt.
   */
  auth?: AuthContext;
  /** CENTER title (cockpit + business). */
  title?: string;
  /** CENTER subtitle (cockpit). */
  description?: string;
  /**
   * LEFT override for business surfaces that carry their own side rail (so the
   * brand is not repeated): renders this instead of the Tessera mark.
   */
  lead?: ReactNode;
  /** Where the brand links (default `/select-space`). */
  brandHref?: string;
  /** Cockpit row 2 — page-scoped context controls (view filters: e.g. Période). */
  contextItems?: HeaderContextItem[];
  /** Cockpit row 2 — extra view filters rendered as-is (e.g. the agent filter). */
  filters?: ReactNode;
  /** Cockpit row 2 — page-scoped actions. */
  actions?: HeaderAction[];
  /** Chrome (border/bg) override for surfaces on a non-cockpit token set. */
  chromeClassName?: string;
}

function defaultAuth(plan: HeaderPlan): AuthContext {
  if (plan === "launcher") return "demo";
  if (plan === "cockpit") return "gated";
  return "optional";
}

export function AppHeader({
  plan,
  auth,
  title,
  description,
  lead,
  brandHref = "/select-space",
  contextItems = [],
  filters,
  actions = [],
  chromeClassName,
}: AppHeaderProps) {
  const authContext = auth ?? defaultAuth(plan);
  const cockpit = plan === "cockpit";
  // A "filter row" (view filters / context controls) earns the divider; a row that
  // carries ONLY page actions (e.g. export / evidence) must NOT — a full-width line
  // there reads as a cheap separator gluing the actions to the page content below.
  const hasFilterRow = contextItems.length > 0 || Boolean(filters);
  const hasRow2 = cockpit && (hasFilterRow || actions.length > 0);

  // The cockpit carries its title at left (brand lives in the sidebar rail). The
  // launcher and business surfaces show the brand at left — unless a business
  // surface passes its own `lead` (it already has a side rail with the brand).
  const left = cockpit ? (
    <TitleBlock title={title} description={description} />
  ) : lead ? (
    <div className="flex min-w-0 items-center gap-3">{lead}</div>
  ) : (
    <BrandLead title={title} href={brandHref} />
  );

  const chrome =
    chromeClassName ??
    (cockpit
      ? "border-b border-[var(--tessera-border)] bg-[var(--tessera-bg)]"
      : "border-b border-[var(--border-subtle)]");

  return (
    <header className={cn("relative", chrome)}>
      {/* Row 1 — the single global header. The global cluster (langue · thème ·
          compte) sits at the far right in the SAME order on every plan; the
          contextual cluster (cockpit only) sits just before it. */}
      <div
        className={cn(
          "flex items-center justify-between gap-4 px-6",
          cockpit ? "min-h-[5.5rem] py-3" : "h-[88px]",
        )}
      >
        <div className="min-w-0">{left}</div>
        <div className="flex shrink-0 flex-nowrap items-center justify-end gap-2">
          {cockpit ? <CockpitTools /> : null}
          {/* Global utilities — langue · thème. On the cockpit the account/identity
              lives ONCE, in the sidebar (Linear/Notion pattern), so it is NOT
              repeated here; the launcher/business surfaces keep it in the header. */}
          <LanguageSwitcher />
          <ThemeToggle
            className={
              cockpit
                ? "h-9 w-9 rounded-full border border-[var(--tessera-border-strong)] bg-transparent text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]"
                : undefined
            }
          />
          {cockpit ? null : <AuthControl context={authContext} />}
        </div>
      </div>

      {/* Row 2 — cockpit page-scoped context + actions, below the global chrome
          so the global cluster never shifts from one page to the next. */}
      {hasRow2 ? (
        <div
          className={cn(
            "flex flex-wrap items-center justify-between gap-3 px-6",
            // Filter row → divider + comfortable height. Actions-only → no divider,
            // tighter, so the buttons float cleanly at the right of the page header.
            hasFilterRow
              ? "min-h-[3.25rem] border-t border-[var(--tessera-border)] py-2"
              : "justify-end pb-2.5 pt-0",
          )}
        >
          {hasFilterRow ? (
            <div className="flex min-w-0 flex-wrap items-center gap-3">
              {contextItems.map((item) => (
                <ContextControl key={item.label} item={item} />
              ))}
              {filters}
            </div>
          ) : null}
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            {actions.map((action) => (
              <ActionButton key={action.label} action={action} />
            ))}
          </div>
        </div>
      ) : null}
    </header>
  );
}

function TitleBlock({ title, description }: { title?: string; description?: string }) {
  const t = useTranslations("app");
  return (
    <>
      <h1 className="truncate font-sans text-[1.45rem] font-semibold leading-tight tracking-normal text-[var(--tessera-text)]">
        {title}
      </h1>
      <p className="mt-1 truncate text-sm text-[var(--tessera-text-muted)]">
        {description ?? t("tagline")}
      </p>
    </>
  );
}

function BrandLead({ title, href }: { title?: string; href: string }) {
  return (
    <div className="flex min-w-0 items-center gap-4">
      <Link href={href} className="flex shrink-0 items-center gap-2">
        <TesseraLogo className="h-[40px]" />
      </Link>
      {title ? (
        <span className="truncate font-sans text-base font-semibold text-[var(--text-primary)]">
          {title}
        </span>
      ) : null}
    </div>
  );
}

/**
 * The cockpit-only contextual cluster, grouped BY NATURE:
 *   1. Deployment context — read-only badges (env · model · status · locality).
 *      Mono-env by construction, so the env is a badge, never a dropdown.
 *   2. Cross-plane — ONE point (operator → business), not two buttons.
 *   3. Global utilities — search · notifs · help (langue · thème follow in the
 *      header's global cluster).
 * Isolated so the `useShellChrome` hook only runs when the cockpit renders it.
 */
function CockpitTools() {
  const { setPaletteOpen } = useShellChrome();
  return (
    <>
      {/* 1 — deployment context (read-only, one cluster): env · model · locality
          · status. Mono-env → env is a badge, never a re-scoping dropdown. */}
      <div className="hidden items-center gap-2 lg:flex">
        <EnvBadge />
        <ModelBadge />
        <LocalityBadge />
        <StatusBadge />
      </div>
      {/* 2 — cross-plane: one point to the business surfaces. */}
      <BusinessMenu />
      {/* 3 — global utilities. */}
      <HeaderIconButton
        icon={Search}
        label="Rechercher (⌘K)"
        className="hidden lg:inline-flex"
        onClick={() => setPaletteOpen(true)}
      />
      <HeaderIconButton
        icon={Bell}
        label="Notifications"
        badge="7"
        className="hidden lg:inline-flex"
      />
      <HeaderIconButton icon={CircleHelp} label="Aide" className="hidden lg:inline-flex" />
    </>
  );
}

const CONTEXT_PILL =
  "inline-flex items-center gap-1.5 rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] px-2.5 py-1 text-[0.65rem] font-medium text-[var(--tessera-text)]";

const ENV_LABEL: Record<string, string> = {
  production: "Prod",
  staging: "Staging",
  ci: "CI",
  local: "Local",
};

/**
 * Deployment environment — read-only (mono-env, fixed by the process; never a
 * re-scoping dropdown — that would be an isolation breach). Reads the REAL env
 * the backend reports; with no env data it renders nothing (honest-empty).
 */
function EnvBadge() {
  const t = useTranslations("app");
  const { data } = useQuery({
    queryKey: ["health-badge"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
  const env = data?.environment;
  if (!env) return null;
  const label = ENV_LABEL[env] ?? env.charAt(0).toUpperCase() + env.slice(1);
  return (
    <span className={CONTEXT_PILL} title={`${t("environment")} · ${label}`}>
      <ServerCog className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" aria-hidden />
      {label}
    </span>
  );
}

/** Deployment locality — read-only (on-prem, EU residency). */
function LocalityBadge() {
  const t = useTranslations("app");
  return (
    <span className={CONTEXT_PILL}>
      <ShieldCheck className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" aria-hidden />
      {t("locality")}
    </span>
  );
}

/**
 * Cross-plane access — ONE point (operator → business). "Voir le produit" and
 * "Explorer les espaces" are the same intent, so they live behind a single menu
 * (ADR 0013: the cockpit is operator-only, so this is inherently operator-only).
 */
function BusinessMenu() {
  const t = useTranslations("app");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("business")}
          title={t("business")}
          className="inline-flex h-9 items-center gap-1.5 rounded-full border border-[var(--tessera-border-strong)] bg-transparent px-3 text-xs font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)]"
        >
          <Boxes className="h-4 w-4" />
          <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[12rem]">
        <DropdownMenuItem asChild>
          <Link href="/produit">{t("viewProduct")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/espaces">{t("exploreSpaces")}</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ActionButton({ action }: { action: HeaderAction }) {
  const [pending, setPending] = useState(false);
  const Icon = action.icon === "download" ? Download : PackageCheck;
  async function onClick() {
    if (!action.action) return;
    setPending(true);
    try {
      await exportSnapshot(action.action);
    } finally {
      setPending(false);
    }
  }
  return (
    <Button
      type="button"
      variant={action.variant}
      size="sm"
      disabled={pending}
      onClick={onClick}
      className={cn(
        "h-9 rounded-md px-3 text-xs shadow-none",
        action.variant === "outline" &&
          "border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]",
        action.variant === "accent" &&
          "border border-[#007a55] bg-[#005c42] text-[#d6f0e3] hover:bg-[#006d4e]",
      )}
    >
      <Icon className="h-4 w-4" />
      {action.label}
    </Button>
  );
}

/** The pill shown for each context item; doubles as a dropdown trigger. */
function ControlBox({
  label,
  value,
  leading,
  tone,
  interactive,
}: {
  label: string;
  value: string;
  leading?: HeaderContextItem["leading"];
  tone?: HeaderContextItem["tone"];
  interactive?: boolean;
}) {
  const LeadingIcon = getLeadingIcon(leading);
  return (
    <div
      className={cn(
        "flex h-[46px] min-w-[132px] flex-col items-center justify-center rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] px-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]",
        interactive && "cursor-pointer transition-colors hover:bg-[var(--tessera-muted)]",
      )}
    >
      <p className="text-[0.65rem] leading-none text-[var(--tessera-text-muted)]">{label}</p>
      <div className="relative mt-1.5 flex w-full items-center justify-center text-xs font-semibold text-[var(--tessera-text)]">
        <span className="flex min-w-0 items-center justify-center gap-2">
          {leading === "status" || tone === "success" ? (
            <span className="h-2 w-2 rounded-full bg-[var(--tessera-green)] shadow-[0_0_8px_rgba(0,200,120,0.75)]" />
          ) : null}
          {LeadingIcon ? (
            <LeadingIcon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          ) : null}
          <span className="truncate">{value}</span>
        </span>
        <ChevronDown className="absolute right-0 h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
      </div>
    </div>
  );
}

function ContextControl({ item }: { item: HeaderContextItem }) {
  if (item.control === "locale") return <LocaleControl item={item} />;
  if (item.control === "model") return <ModelControl item={item} />;
  if (item.control === "window") return <WindowControl item={item} />;
  if (item.control === "select") return <SelectControl item={item} />;
  return <StaticControl item={item} />;
}

/**
 * The shared temporal window — the SINGLE owner of the period. Writes the window
 * store; the rail and the KPIs read it. This is the only window control on the
 * page (the rail no longer carries its own period selector).
 */
function WindowControl({ item }: { item: HeaderContextItem }) {
  const period = useWindowStore((s) => s.period);
  const setPeriod = useWindowStore((s) => s.setPeriod);
  const options = item.options ?? [];
  const current = options.find((o) => o.value === period)?.label ?? item.value;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button">
          <ControlBox label={item.label} value={current} leading={item.leading} interactive />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center" className="min-w-[11rem]">
        <DropdownMenuRadioGroup value={period} onValueChange={setPeriod}>
          {options.map((o) => (
            <DropdownMenuRadioItem key={o.value} value={o.value}>
              {o.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function StaticControl({ item }: { item: HeaderContextItem }) {
  const TrailingIcon = item.trailing === "calendar" ? CalendarDays : ChevronDown;
  const LeadingIcon = getLeadingIcon(item.leading);
  return (
    <div className="flex h-[46px] min-w-[132px] flex-col items-center justify-center rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] px-3 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="text-[0.65rem] leading-none text-[var(--tessera-text-muted)]">{item.label}</p>
      <div className="relative mt-1.5 flex w-full items-center justify-center text-xs font-semibold text-[var(--tessera-text)]">
        <span className="flex min-w-0 items-center justify-center gap-2">
          {item.leading === "status" || item.tone === "success" ? (
            <span className="h-2 w-2 rounded-full bg-[var(--tessera-green)] shadow-[0_0_8px_rgba(0,200,120,0.75)]" />
          ) : null}
          {LeadingIcon ? (
            <LeadingIcon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          ) : null}
          <span className="truncate">{item.value}</span>
        </span>
        <TrailingIcon className="absolute right-0 h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
      </div>
    </div>
  );
}

function LocaleControl({ item }: { item: HeaderContextItem }) {
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const [, startTransition] = useTransition();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button">
          <ControlBox
            label={item.label}
            value={LOCALE_LABELS[locale].short}
            leading="globe"
            interactive
          />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center" className="min-w-[10rem]">
        <DropdownMenuRadioGroup
          value={locale}
          onValueChange={(next) =>
            startTransition(() => router.replace(pathname, { locale: next as Locale }))
          }
        >
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
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ModelControl({ item }: { item: HeaderContextItem }) {
  const [modelId, setModelId] = useState(DEFAULT_CHAT_MODEL);
  useEffect(() => {
    setModelId(getStoredModel());
    const sync = () => setModelId(getStoredModel());
    window.addEventListener(CHAT_MODEL_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CHAT_MODEL_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button">
          <ControlBox label={item.label} value={findModel(modelId).label} interactive />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center" className="min-w-[12rem]">
        <DropdownMenuRadioGroup value={modelId} onValueChange={(next) => setStoredModel(next)}>
          {CHAT_MODELS.map((m) => (
            <DropdownMenuRadioItem key={m.id} value={m.id}>
              <span className="flex w-full items-center justify-between gap-4">
                <span>{m.label}</span>
                <span className="text-xs text-[var(--muted-foreground)]">{m.params}</span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SelectControl({ item }: { item: HeaderContextItem }) {
  const options = item.options ?? [];
  const [value, setValue] = useState(item.value);
  const current = options.find((o) => o.value === value)?.label ?? value;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button">
          <ControlBox
            label={item.label}
            value={current}
            leading={item.leading}
            tone={item.tone}
            interactive
          />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center" className="min-w-[11rem]">
        <DropdownMenuRadioGroup value={value} onValueChange={setValue}>
          {options.map((o) => (
            <DropdownMenuRadioItem key={o.value} value={o.value}>
              {o.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function HeaderIconButton({
  icon: Icon,
  label,
  badge,
  className,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  badge?: string;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className={cn(
        "relative h-9 w-9 items-center justify-center rounded-full border border-[var(--tessera-border-strong)] bg-transparent text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)]",
        className ?? "inline-flex",
      )}
    >
      <Icon className="h-4 w-4" />
      {badge ? (
        <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[0.6rem] font-semibold leading-none text-white">
          {badge}
        </span>
      ) : null}
    </button>
  );
}

function getLeadingIcon(kind?: HeaderContextItem["leading"]): LucideIcon | null {
  if (kind === "history") return RotateCcw;
  if (kind === "globe") return Globe2;
  return null;
}
