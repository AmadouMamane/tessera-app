"use client";

import {
  Activity,
  Bell,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Download,
  FlaskConical,
  Globe2,
  Grid2X2,
  Landmark,
  PackageCheck,
  RotateCcw,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { Suspense, useEffect, useRef, useState, useTransition } from "react";

import { type AuthContext, AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { CommandSearch } from "@/components/layout/command-search";
import {
  SystemStatusPanel,
  SystemStatusTrigger,
  useSystemStatusState,
} from "@/components/layout/system-status-pill";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { LOCALE_LABELS, type Locale, routing } from "@/i18n/routing";
import { type ChromeNotification, useChromeNotifications } from "@/lib/chrome";
import { cn } from "@/lib/cn";
import {
  contextualHelpCoachmarkKey,
  contextualHelpHref,
  hasContextualHelp,
} from "@/lib/contextual-help";
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
        <div className="grid min-h-[5.5rem] grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-b border-[var(--tessera-border)] px-4 md:px-5">
          <div className="min-w-0">{left}</div>
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

const HEADER_TOOL_ICON_CLASS = "h-[18px] w-[18px]";
const HEADER_ICON_BUTTON_CLASS =
  "relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-transparent bg-transparent text-[var(--tessera-text-muted)] outline-none transition-colors after:pointer-events-none after:absolute after:left-1/2 after:-bottom-[1.625rem] after:h-px after:w-5 after:-translate-x-1/2 after:bg-transparent after:transition-colors hover:text-[var(--tessera-text)] focus-visible:ring-2 focus-visible:ring-[var(--ring)] data-[state=open]:text-[var(--tessera-green)] data-[state=open]:after:bg-[var(--tessera-green)]";
const COCKPIT_TRAY_ID = "cockpit-control-tray";
const COCKPIT_TRAY_TITLE_ID = "cockpit-control-tray-title";
type CockpitPanel = "spaces" | "status" | "notifications";

/**
 * Cockpit right zone: one compact dock for global controls. The account and
 * preferences remain exclusively in the sidebar, where the operator identity lives.
 */
function CockpitTools() {
  const [activePanel, setActivePanel] = useState<CockpitPanel | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const notifications = useChromeNotifications();
  const systemStatus = useSystemStatusState();

  useEffect(() => {
    function closeFromOutside(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setActivePanel(null);
      }
    }
    function closeFromKeyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActivePanel(null);
      }
    }
    document.addEventListener("pointerdown", closeFromOutside);
    document.addEventListener("keydown", closeFromKeyboard);
    return () => {
      document.removeEventListener("pointerdown", closeFromOutside);
      document.removeEventListener("keydown", closeFromKeyboard);
    };
  }, []);

  const togglePanel = (panel: CockpitPanel) => {
    setActivePanel((current) => (current === panel ? null : panel));
  };
  const closePanel = () => setActivePanel(null);

  return (
    <div ref={rootRef} className="relative hidden lg:block" data-testid="cockpit-control-root">
      <div data-testid="cockpit-control-dock" className="flex h-11 items-center gap-1">
        <div onClick={closePanel}>
          <CommandSearch plan="cockpit" compact />
        </div>
        <OperatorProductTrigger
          active={activePanel === "spaces"}
          onToggle={() => togglePanel("spaces")}
        />
        <SystemStatusTrigger
          state={systemStatus}
          active={activePanel === "status"}
          controls={COCKPIT_TRAY_ID}
          onToggle={() => togglePanel("status")}
        />
        <NotificationsTrigger
          items={notifications}
          active={activePanel === "notifications"}
          onToggle={() => togglePanel("notifications")}
        />
        <HelpLink onNavigate={closePanel} suppressCoachmark={activePanel !== null} />
      </div>
      {activePanel ? (
        <section
          id={COCKPIT_TRAY_ID}
          aria-labelledby={COCKPIT_TRAY_TITLE_ID}
          data-testid="cockpit-control-tray"
          className="absolute right-0 top-[calc(100%+1.375rem)] z-50 w-[24rem] animate-in overflow-hidden border-[var(--tessera-border)] border-l bg-[var(--tessera-bg)] p-2 text-left text-[var(--tessera-text)] fade-in-0 slide-in-from-top-1 duration-150"
        >
          {activePanel === "spaces" ? (
            <OperatorProductPanel titleId={COCKPIT_TRAY_TITLE_ID} onNavigate={closePanel} />
          ) : null}
          {activePanel === "status" ? (
            <SystemStatusPanel state={systemStatus} titleId={COCKPIT_TRAY_TITLE_ID} />
          ) : null}
          {activePanel === "notifications" ? (
            <NotificationsPanel
              items={notifications}
              titleId={COCKPIT_TRAY_TITLE_ID}
              onNavigate={closePanel}
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

/**
 * The bell counts facts, and each one is a place to go.
 *
 * It used to read a hardcoded `7`. There is no notification store and this adds none: the
 * facts already exist — operator items awaiting validation, a canary that came back red, an
 * audit ledger whose integrity does not verify, a degraded opposability seal — and the
 * backend composes them (`tessera.observability.chrome`). Every row deep-links to the page
 * where the act is actually performed; a bell that announces something you cannot navigate
 * to is a decoration with a number on it.
 *
 * Zero notifications means no dot. Not a grey zero: nothing.
 */
function NotificationsTrigger({
  items,
  active,
  onToggle,
}: {
  items: ChromeNotification[];
  active: boolean;
  onToggle: () => void;
}) {
  const t = useTranslations("app");
  const label = items.length
    ? t("notificationsWithCount", { count: items.length })
    : t("notificationsEmpty");

  return (
    <button
      type="button"
      aria-label={label}
      aria-expanded={active}
      aria-controls={COCKPIT_TRAY_ID}
      title={label}
      data-state={active ? "open" : "closed"}
      onClick={onToggle}
      className={HEADER_ICON_BUTTON_CLASS}
    >
      <Bell className={HEADER_TOOL_ICON_CLASS} strokeWidth={1.75} aria-hidden />
      {items.length ? (
        <span
          aria-hidden
          className="absolute right-1 top-1 h-2 w-2 rounded-full bg-red-500 ring-2 ring-[var(--tessera-surface)]"
        />
      ) : null}
    </button>
  );
}

function NotificationsPanel({
  items,
  titleId,
  onNavigate,
}: {
  items: ChromeNotification[];
  titleId: string;
  onNavigate: () => void;
}) {
  const t = useTranslations("app");
  const groups = groupNotifications(items);

  return (
    <>
      <div className="px-2.5 pb-2 pt-1.5">
        <p id={titleId} className="text-sm font-semibold">
          {t("actionCenter.title")}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
          {t("actionCenter.description")}
        </p>
      </div>
      {items.length ? (
        <div className="divide-y divide-[var(--tessera-border)] border-[var(--tessera-border)] border-t">
          {groups.map((group) => {
            const meta = notificationGroupMeta(group.href);
            const Icon = meta.icon;
            const deadlineSummary =
              group.count === undefined
                ? null
                : group.overdueCount === group.count
                  ? t("actionCenter.deadline.all")
                  : group.overdueCount
                    ? t("actionCenter.deadline.some", {
                        count: group.overdueCount,
                        total: group.count,
                      })
                    : t("actionCenter.deadline.none");
            return (
              <Link
                key={group.href}
                href={group.href}
                onClick={onNavigate}
                className="group flex items-start gap-3 rounded-lg px-2.5 py-3 outline-none hover:bg-[var(--tessera-muted)] focus-visible:bg-[var(--tessera-muted)]"
              >
                <Icon
                  className={cn(
                    HEADER_TOOL_ICON_CLASS,
                    "mt-0.5 shrink-0",
                    group.tone === "danger" ? "text-red-400" : "text-[var(--tessera-text-muted)]",
                  )}
                  strokeWidth={1.75}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-[0.8rem] font-medium">
                      {t(meta.key)}
                      {group.count === undefined ? null : (
                        <span className="font-normal tabular-nums text-[var(--tessera-text-muted)]">
                          {" — "}
                          {group.count}
                        </span>
                      )}
                    </span>
                    <ChevronRight
                      className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] transition-transform group-hover:translate-x-0.5"
                      strokeWidth={1.75}
                      aria-hidden
                    />
                  </span>
                  {deadlineSummary ? (
                    <span className="mt-1.5 flex items-start gap-2 text-[0.72rem] leading-snug text-[var(--tessera-text-muted)]">
                      <span
                        aria-hidden
                        className={cn(
                          "mt-[0.38rem] h-1.5 w-1.5 shrink-0 rounded-full",
                          group.overdueCount ? "bg-red-400" : "bg-amber-400",
                        )}
                      />
                      <span>{deadlineSummary}</span>
                    </span>
                  ) : (
                    <span className="mt-1.5 block space-y-1">
                      {group.items.map((item) => (
                        <span
                          key={item.id}
                          className="flex items-start gap-2 text-[0.72rem] leading-snug text-[var(--tessera-text-muted)]"
                        >
                          <span
                            aria-hidden
                            className={cn(
                              "mt-[0.38rem] h-1.5 w-1.5 shrink-0 rounded-full",
                              item.tone === "danger" ? "bg-red-400" : "bg-amber-400",
                            )}
                          />
                          <span>{item.label}</span>
                        </span>
                      ))}
                    </span>
                  )}
                </span>
              </Link>
            );
          })}
        </div>
      ) : (
        <p className="border-[var(--tessera-border)] border-t px-3 py-4 text-center text-xs text-[var(--tessera-text-muted)]">
          {t("notificationsEmpty")}
        </p>
      )}
    </>
  );
}

interface NotificationGroup {
  href: string;
  items: ChromeNotification[];
  tone: ChromeNotification["tone"];
  count: number | undefined;
  overdueCount: number;
}

function groupNotifications(items: ChromeNotification[]): NotificationGroup[] {
  const groups = new Map<string, ChromeNotification[]>();
  for (const item of items) {
    const current = groups.get(item.href) ?? [];
    current.push(item);
    groups.set(item.href, current);
  }
  return [...groups.entries()].map(([href, groupedItems]) => {
    const pending = groupedItems.find((item) => item.id.startsWith("queue:pending:"));
    const overdue = groupedItems.find((item) => item.id.startsWith("queue:overdue:"));
    return {
      href,
      items: groupedItems,
      tone: groupedItems.some((item) => item.tone === "danger") ? "danger" : "warning",
      count: pending?.count ?? undefined,
      overdueCount: overdue?.count ?? 0,
    };
  });
}

type NotificationGroupKey =
  | "actionCenter.groups.validations"
  | "actionCenter.groups.evaluations"
  | "actionCenter.groups.agents"
  | "actionCenter.groups.proofs"
  | "actionCenter.groups.other";

function notificationGroupMeta(href: string): {
  key: NotificationGroupKey;
  icon: LucideIcon;
} {
  if (href === "/a-traiter") {
    return { key: "actionCenter.groups.validations", icon: ClipboardCheck };
  }
  if (href === "/a-faire") {
    return { key: "actionCenter.groups.evaluations", icon: FlaskConical };
  }
  if (href === "/surveiller/observabilite") {
    return { key: "actionCenter.groups.agents", icon: Activity };
  }
  if (href === "/prouver/etat-a-date") {
    return { key: "actionCenter.groups.proofs", icon: ShieldCheck };
  }
  return { key: "actionCenter.groups.other", icon: Bell };
}

function HelpLink(props: { onNavigate: () => void; suppressCoachmark: boolean }) {
  // HelpLink reads the URL via useSearchParams (contextual help keys off the current
  // path + query), which triggers a CSR bailout during static prerendering. It lives
  // in the shared header, so every statically-rendered public page (comprendre/*)
  // trips `next build` without this boundary — same pattern as AgentScopeFilter. The
  // fallback reserves the exact 9×9 icon box so the header never shifts.
  return (
    <Suspense fallback={<div className="h-9 w-9 shrink-0" />}>
      <HelpLinkInner {...props} />
    </Suspense>
  );
}

function HelpLinkInner({
  onNavigate,
  suppressCoachmark,
}: {
  onNavigate: () => void;
  suppressCoachmark: boolean;
}) {
  const t = useTranslations("comprendre");
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const contextual = hasContextualHelp(pathname);
  const href = contextualHelpHref(pathname, searchParams.toString());
  const label = contextual ? t("helpThisPage") : t("helpUnderstand");
  const storageKey = contextualHelpCoachmarkKey(pathname);
  const [coachmarkVisible, setCoachmarkVisible] = useState(false);

  useEffect(() => {
    if (!contextual) {
      setCoachmarkVisible(false);
      return;
    }
    try {
      setCoachmarkVisible(window.localStorage.getItem(storageKey) !== "seen");
    } catch {
      setCoachmarkVisible(true);
    }
  }, [contextual, storageKey]);

  const dismissCoachmark = () => {
    try {
      window.localStorage.setItem(storageKey, "seen");
    } catch {
      // Storage may be unavailable in a hardened browser; the current cue can
      // still be dismissed for this render without blocking access to the guide.
    }
    setCoachmarkVisible(false);
  };

  const openGuide = () => {
    dismissCoachmark();
    onNavigate();
  };

  return (
    <div className="relative h-9 w-9 shrink-0">
      <Tooltip open={coachmarkVisible && !suppressCoachmark ? false : undefined}>
        <TooltipTrigger asChild>
          <Link
            href={href}
            aria-label={label}
            onClick={openGuide}
            className={HEADER_ICON_BUTTON_CLASS}
          >
            <CircleHelp className={HEADER_TOOL_ICON_CLASS} strokeWidth={1.75} aria-hidden />
          </Link>
        </TooltipTrigger>
        <TooltipContent side="bottom" sideOffset={10}>
          {label}
        </TooltipContent>
      </Tooltip>
      {contextual && coachmarkVisible && !suppressCoachmark ? (
        <aside
          aria-label={t("coachmark.title")}
          data-testid="contextual-help-coachmark"
          className="absolute right-0 top-[calc(100%+1.625rem)] z-[60] w-[20rem] border-cyan-300/45 border-l bg-[var(--tessera-bg)] py-3 pl-4 pr-3 text-left text-[var(--tessera-text)]"
        >
          <button
            type="button"
            aria-label={t("coachmark.dismiss")}
            onClick={dismissCoachmark}
            className="absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-300/60"
          >
            <X className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
          </button>
          <p className="pr-8 text-[0.78rem] font-semibold">{t("coachmark.title")}</p>
          <p className="mt-1.5 pr-5 text-[0.72rem] leading-5 text-[var(--tessera-text-muted)]">
            {t("coachmark.body")}
          </p>
          <Link
            href={href}
            onClick={openGuide}
            className="mt-3 inline-flex items-center gap-1.5 text-[0.72rem] font-medium text-cyan-200 transition-colors hover:text-[var(--tessera-text-strong)]"
          >
            {t("coachmark.open")}
            <ChevronRight className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden />
          </Link>
        </aside>
      ) : null}
    </div>
  );
}

function OperatorProductTrigger({
  active,
  onToggle,
}: {
  active: boolean;
  onToggle: () => void;
}) {
  const t = useTranslations("app");
  return (
    <button
      type="button"
      aria-label={t("businessMenu")}
      aria-expanded={active}
      aria-controls={COCKPIT_TRAY_ID}
      title={t("businessMenu")}
      data-state={active ? "open" : "closed"}
      onClick={onToggle}
      className={HEADER_ICON_BUTTON_CLASS}
    >
      <Grid2X2 className={HEADER_TOOL_ICON_CLASS} strokeWidth={1.75} aria-hidden />
    </button>
  );
}

function OperatorProductPanel({
  titleId,
  onNavigate,
}: {
  titleId: string;
  onNavigate: () => void;
}) {
  const t = useTranslations("app");
  return (
    <>
      <div className="px-2.5 pb-2 pt-1.5">
        <p id={titleId} className="text-sm font-semibold">
          {t("spacesMenu.title")}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
          {t("spacesMenu.description")}
        </p>
      </div>
      <div className="divide-y divide-[var(--tessera-border)] border-[var(--tessera-border)] border-t">
        <Link
          href="/espaces"
          onClick={onNavigate}
          className="group flex items-center gap-3 rounded-lg px-2.5 py-3 outline-none hover:bg-[var(--tessera-muted)] focus-visible:bg-[var(--tessera-muted)]"
        >
          <Landmark
            className={cn(
              HEADER_TOOL_ICON_CLASS,
              "shrink-0 text-[var(--tessera-text-muted)] transition-colors group-hover:text-[var(--tessera-text)]",
            )}
            strokeWidth={1.75}
            aria-hidden
          />
          <span className="min-w-0 flex-1">
            <span className="block text-[0.8rem] font-medium">{t("business")}</span>
            <span className="mt-0.5 block text-[0.72rem] leading-snug text-[var(--tessera-text-muted)]">
              {t("spacesMenu.businessDescription")}
            </span>
          </span>
          <ChevronRight
            className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] transition-transform group-hover:translate-x-0.5"
            strokeWidth={1.75}
            aria-hidden
          />
        </Link>
        <Link
          href="/produit"
          onClick={onNavigate}
          className="group flex items-center gap-3 rounded-lg px-2.5 py-3 outline-none hover:bg-[var(--tessera-muted)] focus-visible:bg-[var(--tessera-muted)]"
        >
          <UserRound
            className={cn(
              HEADER_TOOL_ICON_CLASS,
              "shrink-0 text-[var(--tessera-text-muted)] transition-colors group-hover:text-[var(--tessera-text)]",
            )}
            strokeWidth={1.75}
            aria-hidden
          />
          <span className="min-w-0 flex-1">
            <span className="block text-[0.8rem] font-medium">{t("clientSpace")}</span>
            <span className="mt-0.5 block text-[0.72rem] leading-snug text-[var(--tessera-text-muted)]">
              {t("spacesMenu.clientDescription")}
            </span>
          </span>
          <ChevronRight
            className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] transition-transform group-hover:translate-x-0.5"
            strokeWidth={1.75}
            aria-hidden
          />
        </Link>
      </div>
    </>
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

function getLeadingIcon(kind?: HeaderContextItem["leading"]): LucideIcon | null {
  if (kind === "history") return RotateCcw;
  if (kind === "globe") return Globe2;
  return null;
}
