"use client";

import {
  Bell,
  CalendarDays,
  ChevronDown,
  CircleHelp,
  Download,
  Globe2,
  PackageCheck,
  RotateCcw,
  Search,
  SquareArrowOutUpRight,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useEffect, useState, useTransition } from "react";

import { type AuthContext, AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { DemoLauncherLink } from "@/components/layout/demo-launcher-link";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { ModelBadge } from "@/components/layout/model-badge";
import { useShellChrome } from "@/components/layout/shell-chrome";
import { StatusBadge } from "@/components/layout/status-badge";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { LOCALE_LABELS, type Locale, routing } from "@/i18n/routing";
import {
  fetchAIAct,
  fetchAuditIntegrity,
  fetchCost,
  fetchDisclosure,
  fetchPiiLeak,
  fetchSLO,
  fetchToxicity,
} from "@/lib/api/client";
import { cn } from "@/lib/cn";
import {
  CHAT_MODELS,
  CHAT_MODEL_EVENT,
  DEFAULT_CHAT_MODEL,
  findModel,
  getStoredModel,
  setStoredModel,
} from "@/lib/models";
import { getTemporalContext } from "@/lib/temporal-context";

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
  /** Makes the control interactive: a real locale/model switch, or a generic select. */
  control?: "locale" | "model" | "select";
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
  /** Cockpit row 2 — page-scoped context controls. */
  contextItems?: HeaderContextItem[];
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

function downloadJson(name: string, obj: unknown) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Snapshot the cockpit signals and download them as a report / evidence pack.
 *
 * Scoped to the cockpit's current temporal context `(period, asOf)` (ADR 0011
 * §3/§5): in history mode the pack reflects the state as of T, not just "now".
 * Audit integrity and the disclosure text are structural/static, so they stay
 * live and are labelled as such.
 */
async function runAction(kind: "export" | "evidence") {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const { asOf, period } = getTemporalContext();
  const at = asOf ?? undefined;
  const scope = { generated_at: new Date().toISOString(), as_of: asOf, period };
  const settle = async <T,>(p: Promise<T>) => p.catch(() => null);
  if (kind === "evidence") {
    const [audit, aiAct, disclosure, pii] = await Promise.all([
      settle(fetchAuditIntegrity()),
      settle(fetchAIAct(undefined, at)),
      settle(fetchDisclosure()),
      settle(fetchPiiLeak(undefined, at)),
    ]);
    downloadJson(`tessera-evidence-pack-${stamp}.json`, {
      ...scope,
      kind: "evidence_pack",
      audit_integrity: audit, // structural hash-chain check — always live
      ai_act: aiAct,
      disclosure,
      pii_leak: pii,
    });
    return;
  }
  const [slo, cost, toxicity] = await Promise.all([
    settle(fetchSLO(undefined, at)),
    settle(fetchCost(undefined, at)),
    settle(fetchToxicity(undefined, at)),
  ]);
  downloadJson(`tessera-report-${stamp}.json`, {
    ...scope,
    kind: "overview_report",
    slo,
    cost,
    toxicity,
  });
}

export function AppHeader({
  plan,
  auth,
  title,
  description,
  lead,
  brandHref = "/select-space",
  contextItems = [],
  actions = [],
  chromeClassName,
}: AppHeaderProps) {
  const authContext = auth ?? defaultAuth(plan);
  const cockpit = plan === "cockpit";
  const hasRow2 = cockpit && (contextItems.length > 0 || actions.length > 0);

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
          {/* Global cluster — fixed order everywhere: langue · thème · compte. */}
          <LanguageSwitcher />
          <ThemeToggle
            className={
              cockpit
                ? "h-9 w-9 rounded-full border border-[var(--tessera-border-strong)] bg-transparent text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]"
                : undefined
            }
          />
          <AuthControl context={authContext} />
        </div>
      </div>

      {/* Row 2 — cockpit page-scoped context + actions, below the global chrome
          so the global cluster never shifts from one page to the next. */}
      {hasRow2 ? (
        <div className="flex min-h-[3.25rem] flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-6 py-2">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            {contextItems.map((item) => (
              <ContextControl key={item.label} item={item} />
            ))}
          </div>
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
 * The cockpit-only contextual cluster (status · model · search · notifs · help ·
 * explore spaces · view product). Isolated so the `useShellChrome` hook (and the
 * cockpit-specific tokens) only run when the cockpit plan renders it.
 */
function CockpitTools() {
  const t = useTranslations("app");
  const { setPaletteOpen } = useShellChrome();
  return (
    <>
      <StatusBadge />
      <ModelBadge />
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
      {/* Discreet demo-launcher shortcut (ADR 0013) — a reviewer convenience to
          explore both spaces, never the front door. */}
      <DemoLauncherLink className="hidden xl:inline-flex" />
      {/* Operator switcher (ADR 0013) — the cockpit is operator-only by
          construction (the operator-rbac guard gates these routes), so this
          "view the customer product" affordance is inherently operator-only. */}
      <Link
        href="/produit"
        className="hidden h-9 items-center gap-2 rounded-full border border-[var(--tessera-border-strong)] bg-transparent px-3 text-xs font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)] lg:inline-flex"
      >
        <SquareArrowOutUpRight className="h-4 w-4" />
        {t("viewProduct")}
      </Link>
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
      await runAction(action.action);
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
  if (item.control === "select") return <SelectControl item={item} />;
  return <StaticControl item={item} />;
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
