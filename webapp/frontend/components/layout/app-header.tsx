"use client";

import {
  Bell,
  CalendarDays,
  ChevronDown,
  CircleHelp,
  Download,
  Globe2,
  Grid2X2,
  PackageCheck,
  RotateCcw,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useEffect, useState, useTransition } from "react";

import { type AuthContext, AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { CommandSearch } from "@/components/layout/command-search";
import { SystemStatusPill } from "@/components/layout/system-status-pill";
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
    (cockpit ? "bg-[var(--tessera-bg)]" : "border-b border-[var(--border-subtle)]");

  // No border on the header itself: with a row 2 carrying only page actions, a full-width
  // line under the whole header glues those actions to the page content below — the
  // anti-pattern the comment above forbids. The single rule belongs on row 1, continuous
  // with the under-logo divider, with the actions BELOW it. Restored 2026-07-10; 2735f9ad
  // had moved it onto <header> and deleted the comment that said why it must not live there.
  if (cockpit) {
    return (
      <header className={cn("relative", chrome)}>
        {/* 5.5rem = 88px, the same rule height as the launcher's `h-[88px]` row and as the
            sidebar's brand block, so the under-logo divider and the header rule are one
            continuous line. `2735f9ad` cut all three to 56px and the alignment went with them. */}
        <div className="grid min-h-[5.5rem] grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-[var(--tessera-border)] px-4 md:grid-cols-[minmax(10rem,1fr)_minmax(15rem,28rem)_minmax(10rem,1fr)] md:gap-4 md:px-5">
          <div className="min-w-0">{left}</div>
          <div className="hidden min-w-0 justify-center md:flex">
            <CommandSearch plan="cockpit" className="w-full max-w-md" />
          </div>
          <div className="flex min-w-0 items-center justify-end gap-2">
            <CockpitTools />
          </div>
        </div>
        {hasRow2 ? (
          <div
            className={cn(
              "flex flex-wrap items-center justify-between gap-3 px-5",
              hasFilterRow ? "min-h-[3.25rem] py-2.5" : "justify-end pt-2 pb-1",
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

  return (
    <header className={cn("relative", chrome)}>
      {/* Row 1 — the single global header. The global cluster (langue · thème ·
          compte) sits at the far right in the SAME order on every plan; the
          contextual cluster (cockpit only) sits just before it. */}
      {/* `cockpit` returned above, so this row is always the launcher/business one: 88px,
          the height the cockpit's row 1 now matches. */}
      <div className="flex h-[88px] items-center justify-between gap-4 px-6">
        <div className="min-w-0">{left}</div>
        <div className="flex shrink-0 flex-nowrap items-center justify-end gap-2">
          {/* Non-cockpit surfaces keep identity/preferences in the shared user
              menu; language and theme are no longer loose header icons. */}
          <AuthControl context={authContext} />
        </div>
      </div>

      {/* Row 2 — cockpit page-scoped context + actions, below the global chrome
          so the global cluster never shifts from one page to the next. */}
      {hasRow2 ? (
        <div
          className={cn(
            "flex flex-wrap items-center justify-between gap-3 px-6",
            // Sits BELOW row 1's rule — no border of its own (no double line, no
            // cheap separator under the actions). A filter row gets normal breathing
            // room; an actions-ONLY row hugs the rule (a slim shelf, pt-2 pb-1) so
            // the page actions read as part of the header instead of floating in the
            // empty band above the temporal bar.
            hasFilterRow ? "min-h-[3.25rem] py-2.5" : "justify-end pt-2 pb-1",
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

// 1.45rem / text-sm are the sizes this block has always used. `2735f9ad` cut them to
// text-base / text-xs when it cut the header's height, and the page title stopped reading as a
// page title. Restored with the row's 88px.
function TitleBlock({ title, description }: { title?: string; description?: string }) {
  const t = useTranslations("app");
  return (
    <div className="min-w-0">
      <h1 className="truncate font-sans text-[1.45rem] font-semibold leading-tight tracking-normal text-[var(--tessera-text)]">
        {title ?? t("tagline")}
      </h1>
      {description ? (
        <p className="mt-1 truncate text-sm text-[var(--tessera-text-muted)]">{description}</p>
      ) : null}
    </div>
  );
}

function BrandLead({ title, href }: { title?: string; href: string }) {
  return (
    <div className="flex min-w-0 items-center gap-4">
      <Link href={href} className="flex shrink-0 items-center gap-2">
        <TesseraLogo className="h-11" />
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
 * Cockpit right zone: one composite system posture, then the two visible icon
 * tools allowed by the header spec. Account/preferences live in the sidebar.
 */
function CockpitTools() {
  return (
    <>
      <OperatorProductMenu />
      <SystemStatusPill className="hidden lg:inline-flex" />
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

function OperatorProductMenu() {
  const t = useTranslations("app");
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label={t("businessMenu")}
          title={t("businessMenu")}
          className="hidden h-9 w-9 items-center justify-center rounded-full border border-[var(--tessera-border-strong)] bg-transparent text-[var(--tessera-text)] outline-none transition-colors hover:bg-[var(--tessera-muted)] focus-visible:ring-2 focus-visible:ring-[var(--ring)] lg:inline-flex"
        >
          <Grid2X2 className="h-4 w-4" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[13rem]">
        <DropdownMenuItem asChild>
          <Link href="/espaces">{t("business")}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/produit">{t("clientSpace")}</Link>
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
        "relative h-9 w-9 items-center justify-center rounded-full border border-[var(--tessera-border-strong)] bg-transparent text-[var(--tessera-text)] outline-none transition-colors hover:bg-[var(--tessera-muted)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
        className ?? "inline-flex",
      )}
    >
      <Icon className="h-4 w-4" aria-hidden />
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
