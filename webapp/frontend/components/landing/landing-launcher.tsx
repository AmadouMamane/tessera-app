"use client";

import {
  Activity,
  ArrowRight,
  Bell,
  Boxes,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  ListChecks,
  type LucideIcon,
  MessageSquare,
  Moon,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  Workflow,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type Accent = "gold" | "teal";

interface SpaceItem {
  icon: LucideIcon;
  key: string;
  href: string;
}

const CLIENT_ITEMS: SpaceItem[] = [
  { icon: MessageSquare, key: "chat", href: "/produit" },
  { icon: ListChecks, key: "requests", href: "/produit/mes-demandes" },
  { icon: FileText, key: "documents", href: "/produit/documents" },
  { icon: Bell, key: "alerts", href: "/produit/alertes" },
  { icon: Settings, key: "settings", href: "/produit/parametres" },
];

const OPERATOR_ITEMS: SpaceItem[] = [
  { icon: Activity, key: "supervision", href: "/surveiller/vue-ensemble" },
  { icon: Workflow, key: "management", href: "/agir/incidents-playbooks" },
  { icon: SlidersHorizontal, key: "configuration", href: "/configurer/signal-catalog" },
  { icon: Boxes, key: "platform", href: "/admin/utilisateurs" },
];

export function LandingLauncher() {
  const t = useTranslations("landing");
  return (
    <div className="bg-canvas-glow relative flex min-h-screen flex-col bg-[var(--tessera-bg)] text-[var(--tessera-text)]">
      <Header t={t} />
      <main className="flex flex-1 items-center justify-center px-4 py-8">
        <div className="w-full max-w-5xl">
          <div className="text-center">
            <h1 className="font-serif text-3xl font-semibold text-white md:text-4xl">
              {t("welcome")}
            </h1>
            <p className="mt-2 text-sm text-[var(--tessera-text-muted)] md:text-base">
              {t("choose")}
            </p>
          </div>

          <div className="mt-8 grid gap-5 md:grid-cols-2">
            <SpaceCard
              t={t}
              ns="client"
              accent="gold"
              badgeIcon={UserRound}
              href="/produit"
              items={CLIENT_ITEMS}
              mock={<ChatMock />}
            />
            <SpaceCard
              t={t}
              ns="operator"
              accent="teal"
              badgeIcon={ShieldCheck}
              href="/agent/synthese"
              items={OPERATOR_ITEMS}
              mock={<DashboardMock />}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

type T = ReturnType<typeof useTranslations<"landing">>;

function Header({ t }: { t: T }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-[var(--tessera-border)] px-4 md:px-6">
      <div className="flex shrink-0 items-center gap-3">
        <TesseraMark />
        <div className="hidden flex-col leading-tight sm:flex">
          <span className="font-sans text-base font-semibold tracking-[0.18em] text-white">
            TESSERA
          </span>
          <span className="text-[0.55rem] uppercase tracking-[0.22em] text-[var(--tessera-text-muted)]">
            {t("brandTagline")}
          </span>
        </div>
      </div>

      <SpaceToggle t={t} />

      <div className="flex shrink-0 items-center gap-3">
        <Search className="hidden h-4 w-4 text-[var(--tessera-text-muted)] sm:block" />
        <span className="relative hidden sm:block">
          <Bell className="h-4 w-4 text-[var(--tessera-text-muted)]" />
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-red-500" />
        </span>
        <CircleHelp className="hidden h-4 w-4 text-[var(--tessera-text-muted)] sm:block" />
        <Moon className="hidden h-4 w-4 text-[var(--tessera-text-muted)] sm:block" />
        <div className="flex items-center gap-2 border-l border-[var(--tessera-border)] pl-3">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-[#caa45a] to-[#b8893f] text-xs font-semibold text-[#1a1406]">
            CD
          </span>
          <div className="hidden flex-col leading-tight md:flex">
            <span className="text-[0.8rem] font-semibold text-white">{t("user.name")}</span>
            <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("user.role")}
            </span>
          </div>
          <ChevronDown className="hidden h-4 w-4 text-[var(--tessera-text-muted)] md:block" />
        </div>
      </div>
    </header>
  );
}

function SpaceToggle({ t }: { t: T }) {
  return (
    <div className="flex items-center gap-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-1">
      <Link
        href="/produit"
        className="flex items-center gap-2 rounded-md bg-gradient-to-r from-[#caa45a] to-[#b8893f] px-4 py-1.5 text-[0.78rem] font-semibold text-[#1a1406] shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]"
      >
        <UserRound className="h-3.5 w-3.5" />
        {t("toggle.product")}
      </Link>
      <Link
        href="/agent/synthese"
        className="flex items-center gap-2 rounded-md px-4 py-1.5 text-[0.78rem] font-medium text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)]"
      >
        <ShieldCheck className="h-3.5 w-3.5" />
        {t("toggle.cockpit")}
      </Link>
    </div>
  );
}

const ACCENT: Record<
  Accent,
  { badge: string; badgeIcon: string; row: string; chevron: string; cta: string; glow: string }
> = {
  gold: {
    badge: "text-gold-300",
    badgeIcon: "border-gold-700/40 bg-gold-900/30 text-gold-200",
    row: "text-gold-300",
    chevron: "group-hover/row:text-gold-300",
    cta: "bg-gradient-to-r from-[#caa45a] to-[#b8893f] text-[#1a1406] hover:brightness-110",
    glow: "before:bg-[radial-gradient(120%_55%_at_50%_0%,rgba(202,164,90,0.10),transparent)]",
  },
  teal: {
    badge: "text-emerald-300",
    badgeIcon: "border-emerald-700/40 bg-emerald-900/30 text-emerald-200",
    row: "text-emerald-300",
    chevron: "group-hover/row:text-emerald-300",
    cta: "bg-gradient-to-r from-[#3ec99a] to-[#2bb6c4] text-[#04201a] hover:brightness-110",
    glow: "before:bg-[radial-gradient(120%_55%_at_50%_0%,rgba(62,201,154,0.10),transparent)]",
  },
};

function SpaceCard({
  t,
  ns,
  accent,
  badgeIcon: BadgeIcon,
  href,
  items,
  mock,
}: {
  t: T;
  ns: "client" | "operator";
  accent: Accent;
  badgeIcon: LucideIcon;
  href: "/produit" | "/agent/synthese";
  items: SpaceItem[];
  mock: React.ReactNode;
}) {
  const a = ACCENT[accent];
  return (
    <section
      className={cn(
        "relative flex flex-col overflow-hidden rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6",
        "before:pointer-events-none before:absolute before:inset-0 before:content-['']",
        a.glow,
      )}
    >
      <div className="relative flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span className="inline-flex items-center gap-2">
            <span className={cn("grid h-7 w-7 place-items-center rounded-lg border", a.badgeIcon)}>
              <BadgeIcon className="h-4 w-4" />
            </span>
            <span
              className={cn("text-[0.62rem] font-semibold uppercase tracking-[0.18em]", a.badge)}
            >
              {t(`${ns}.badge`)}
            </span>
          </span>
          <h2 className="mt-3 text-2xl font-semibold text-white">{t(`${ns}.title`)}</h2>
          <p className="mt-1.5 max-w-xs text-[0.82rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {t(`${ns}.desc`)}
          </p>
        </div>
        <div className="hidden shrink-0 sm:block">{mock}</div>
      </div>

      <ul className="relative mt-5 flex flex-col">
        {items.map((item) => (
          <li key={item.key}>
            <Link
              href={item.href}
              className="group/row flex items-center gap-3 border-t border-[var(--tessera-border)]/60 py-2.5 transition-colors first:border-t-0 hover:bg-[var(--tessera-muted)]/30"
            >
              <item.icon className={cn("h-4 w-4 shrink-0", a.row)} />
              <div className="min-w-0 flex-1">
                <p className="text-[0.84rem] font-medium text-[var(--tessera-text)]">
                  {t(`${ns}.items.${item.key}.title`)}
                </p>
                <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
                  {t(`${ns}.items.${item.key}.desc`)}
                </p>
              </div>
              <ChevronRight
                className={cn(
                  "h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] transition-colors",
                  a.chevron,
                )}
              />
            </Link>
          </li>
        ))}
      </ul>

      <Link
        href={href}
        className={cn(
          "relative mt-6 flex h-11 items-center justify-center gap-2 rounded-lg text-sm font-semibold shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] transition-all",
          a.cta,
        )}
      >
        {t(`${ns}.cta`)}
        <ArrowRight className="h-4 w-4" />
      </Link>
    </section>
  );
}

function ChatMock() {
  return (
    <div className="flex w-28 flex-col gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2">
      <div className="h-1.5 w-3/4 self-end rounded-full bg-gold-700/50" />
      <div className="h-1.5 w-full rounded-full bg-[var(--tessera-muted)]" />
      <div className="h-1.5 w-5/6 rounded-full bg-[var(--tessera-muted)]" />
      <div className="mt-1 h-4 w-12 rounded-md bg-gold-800/40" />
    </div>
  );
}

function DashboardMock() {
  return (
    <div className="flex w-28 gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2">
      <div className="flex flex-1 flex-col justify-end gap-1">
        <div className="flex items-end gap-1">
          <div className="h-5 w-2 rounded-sm bg-emerald-700/50" />
          <div className="h-7 w-2 rounded-sm bg-emerald-600/60" />
          <div className="h-4 w-2 rounded-sm bg-emerald-700/40" />
          <div className="h-8 w-2 rounded-sm bg-emerald-500/60" />
        </div>
        <div className="h-1.5 w-full rounded-full bg-[var(--tessera-muted)]" />
      </div>
      <div className="h-10 w-10 shrink-0 rounded-full border-[3px] border-emerald-600/50 border-r-emerald-400/80" />
    </div>
  );
}

function TesseraMark() {
  return (
    <svg
      aria-hidden="true"
      className="h-9 w-9 shrink-0 text-[var(--tessera-green)]"
      viewBox="0 0 36 36"
      fill="none"
    >
      <path
        d="M18 3.5 31 10.75v14.5L18 32.5 5 25.25v-14.5L18 3.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <path
        d="M18 3.5v14.7m0 14.3V18.2m0 0L5 10.75m13 7.45 13-7.45M5 25.25l13-7.05 13 7.05"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  );
}
