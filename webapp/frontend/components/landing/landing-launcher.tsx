"use client";

import {
  Activity,
  ArrowRight,
  Bell,
  Boxes,
  ChevronDown,
  CircleHelp,
  FileText,
  ListChecks,
  type LucideIcon,
  MessageSquare,
  Settings,
  SlidersHorizontal,
  Workflow,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type Accent = "gold" | "teal";

interface SpaceItem {
  icon: LucideIcon;
  key: string;
}

const CLIENT_ITEMS: SpaceItem[] = [
  { icon: MessageSquare, key: "chat" },
  { icon: ListChecks, key: "requests" },
  { icon: FileText, key: "documents" },
  { icon: Bell, key: "alerts" },
  { icon: Settings, key: "settings" },
];

const OPERATOR_ITEMS: SpaceItem[] = [
  { icon: Activity, key: "supervision" },
  { icon: Workflow, key: "management" },
  { icon: SlidersHorizontal, key: "configuration" },
  { icon: Boxes, key: "platform" },
];

export function LandingLauncher() {
  const t = useTranslations("landing");
  return (
    <div className="bg-canvas-glow relative flex min-h-screen flex-col bg-[var(--tessera-bg)] text-[var(--tessera-text)]">
      <Header t={t} />
      <main className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-5xl">
          <div className="text-center">
            <h1 className="font-serif text-3xl font-semibold text-white md:text-4xl">
              {t("welcome")}
            </h1>
            <p className="mt-2 text-sm text-[var(--tessera-text-muted)] md:text-base">
              {t("choose")}
            </p>
          </div>

          <div className="mt-9 grid gap-5 md:grid-cols-2">
            <SpaceCard
              t={t}
              ns="client"
              accent="gold"
              href="/produit"
              items={CLIENT_ITEMS}
              mock={<ChatMock />}
            />
            <SpaceCard
              t={t}
              ns="operator"
              accent="teal"
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
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-[var(--tessera-border)] px-5 md:px-8">
      <div className="flex items-center gap-3">
        <TesseraMark />
        <div className="flex flex-col leading-tight">
          <span className="font-sans text-lg font-semibold tracking-[0.18em] text-white">
            TESSERA
          </span>
          <span className="text-[0.6rem] uppercase tracking-[0.22em] text-[var(--tessera-text-muted)]">
            {t("brandTagline")}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <CircleHelp className="h-5 w-5 text-[var(--tessera-text-muted)]" />
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-[var(--tessera-muted)] text-xs font-semibold text-[var(--tessera-text)]">
            TO
          </span>
          <div className="hidden flex-col leading-tight sm:flex">
            <span className="text-sm font-semibold text-white">{t("user.name")}</span>
            <span className="text-[0.7rem] text-[var(--tessera-text-muted)]">{t("user.role")}</span>
          </div>
          <ChevronDown className="h-4 w-4 text-[var(--tessera-text-muted)]" />
        </div>
      </div>
    </header>
  );
}

const ACCENT: Record<
  Accent,
  { badge: string; icon: string; ring: string; cta: string; glow: string }
> = {
  gold: {
    badge: "border-gold-700/60 bg-gold-900/40 text-gold-200",
    icon: "border-gold-700/40 bg-gold-900/30 text-gold-200",
    ring: "hover:border-gold-700/60",
    cta: "bg-gradient-to-r from-[#caa45a] to-[#b8893f] text-[#1a1406] hover:brightness-110",
    glow: "before:bg-[radial-gradient(120%_60%_at_50%_0%,rgba(202,164,90,0.10),transparent)]",
  },
  teal: {
    badge: "border-emerald-700/60 bg-emerald-900/40 text-emerald-200",
    icon: "border-emerald-700/40 bg-emerald-900/30 text-emerald-200",
    ring: "hover:border-emerald-700/60",
    cta: "bg-gradient-to-r from-[#3ec99a] to-[#2bb6c4] text-[#04201a] hover:brightness-110",
    glow: "before:bg-[radial-gradient(120%_60%_at_50%_0%,rgba(62,201,154,0.10),transparent)]",
  },
};

function SpaceCard({
  t,
  ns,
  accent,
  href,
  items,
  mock,
}: {
  t: T;
  ns: "client" | "operator";
  accent: Accent;
  href: "/produit" | "/agent/synthese";
  items: SpaceItem[];
  mock: React.ReactNode;
}) {
  const a = ACCENT[accent];
  return (
    <section
      className={cn(
        "relative flex flex-col overflow-hidden rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6 transition-colors",
        "before:pointer-events-none before:absolute before:inset-0 before:content-['']",
        a.glow,
        a.ring,
      )}
    >
      <div className="relative flex items-start justify-between gap-4">
        <div className="min-w-0">
          <span
            className={cn(
              "inline-flex rounded-full border px-2.5 py-0.5 text-[0.62rem] font-semibold uppercase tracking-[0.14em]",
              a.badge,
            )}
          >
            {t(`${ns}.badge`)}
          </span>
          <h2 className="mt-3 text-2xl font-semibold text-white">{t(`${ns}.title`)}</h2>
          <p className="mt-1.5 max-w-xs text-[0.82rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {t(`${ns}.desc`)}
          </p>
        </div>
        <div className="hidden shrink-0 sm:block">{mock}</div>
      </div>

      <ul className="relative mt-5 flex flex-col gap-3">
        {items.map((item) => (
          <li key={item.key} className="flex items-start gap-3">
            <span
              className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg border", a.icon)}
            >
              <item.icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-[0.84rem] font-medium text-[var(--tessera-text)]">
                {t(`${ns}.items.${item.key}.title`)}
              </p>
              <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
                {t(`${ns}.items.${item.key}.desc`)}
              </p>
            </div>
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
