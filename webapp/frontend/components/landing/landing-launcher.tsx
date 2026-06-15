"use client";

import {
  ArrowRight,
  Bell,
  BellRing,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  ListChecks,
  MessageSquare,
  Moon,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import type { CSSProperties, ReactNode } from "react";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type Accent = "gold" | "cyan";
type SpaceSelectorStyle = CSSProperties & Record<`--${string}`, string>;

interface SpaceItem {
  icon: React.ComponentType<{ className?: string }>;
  key: string;
}

const SPACE_SELECTOR_TOKENS: SpaceSelectorStyle = {
  "--bg-app": "#020817",
  "--bg-deep": "#030B18",
  "--bg-radial": "rgba(20, 43, 77, 0.26)",
  "--bg-panel": "rgba(6, 20, 38, 0.78)",
  "--bg-panel-soft": "rgba(10, 27, 47, 0.66)",
  "--panel": "rgba(6, 20, 38, 0.78)",
  "--panel-soft": "rgba(10, 27, 47, 0.66)",
  "--border-subtle": "rgba(148, 163, 184, 0.14)",
  "--border-gold": "rgba(214, 182, 106, 0.55)",
  "--border-cyan": "rgba(45, 212, 191, 0.48)",
  "--text-primary": "#F8FAFC",
  "--text-secondary": "#A6B3C8",
  "--champagne": "#D6B66A",
  "--champagne-strong": "#F4C76A",
  "--gold": "var(--champagne)",
  "--gold-strong": "var(--champagne-strong)",
  "--cyan": "#2DD4BF",
  "--cyan-soft": "#67E8F9",
  "--success": "#22C55E",
  "--radius-lg": "24px",
  "--radius-md": "16px",
  "--shadow-gold": "0 0 18px rgba(214, 182, 106, 0.08), inset 0 1px 0 rgba(255,255,255,0.04)",
  "--shadow-cyan": "0 0 18px rgba(45, 212, 191, 0.08), inset 0 1px 0 rgba(255,255,255,0.04)",
};

const CLIENT_ITEMS: SpaceItem[] = [
  { icon: MessageSquare, key: "chat" },
  { icon: ListChecks, key: "requests" },
  { icon: FileText, key: "documents" },
  { icon: BellRing, key: "alerts" },
  { icon: Settings, key: "settings" },
];

const OPERATOR_ITEMS: SpaceItem[] = [
  { icon: EyeIcon, key: "supervision" },
  { icon: ShieldCheck, key: "management" },
  { icon: SlidersHorizontal, key: "configuration" },
  { icon: UsersRound, key: "platform" },
];

const ACCENT: Record<
  Accent,
  {
    border: string;
    button: string;
    buttonStyle: CSSProperties;
    cardStyle: CSSProperties;
    icon: string;
    soft: string;
    tone: string;
  }
> = {
  gold: {
    border: "border-[var(--border-gold)]",
    button: "border-[var(--border-gold)] text-[var(--text-primary)]",
    buttonStyle: {
      background:
        "linear-gradient(180deg, rgba(214,182,106,0.30), rgba(88,62,24,0.78) 58%, rgba(42,31,18,0.92))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
    },
    cardStyle: {
      boxShadow: "var(--shadow-gold)",
    },
    icon: "text-[var(--gold-strong)]",
    soft: "text-[var(--gold)]",
    tone: "text-[var(--gold-strong)]",
  },
  cyan: {
    border: "border-[var(--border-cyan)]",
    button: "border-[var(--border-cyan)] text-[var(--text-primary)]",
    buttonStyle: {
      background:
        "linear-gradient(180deg, rgba(45,212,191,0.22), rgba(8,86,102,0.70) 55%, rgba(4,39,53,0.92))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
    },
    cardStyle: {
      boxShadow: "var(--shadow-cyan)",
    },
    icon: "text-[var(--cyan)]",
    soft: "text-[var(--cyan-soft)]",
    tone: "text-[var(--cyan)]",
  },
};

type T = ReturnType<typeof useTranslations<"landing">>;

export function LandingLauncher() {
  const t = useTranslations("landing");

  return (
    <div
      className="relative min-h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]"
      style={SPACE_SELECTOR_TOKENS}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at 50% 18%, var(--bg-radial) 0%, rgba(20,43,77,0.10) 32%, transparent 58%), linear-gradient(180deg, var(--bg-deep) 0%, var(--bg-app) 48%, #010511 100%)",
          boxShadow: "inset 0 0 150px rgba(0,0,0,0.70)",
        }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[150px] bg-cover bg-bottom bg-no-repeat"
        style={{
          backgroundImage: "url('/brand/select-space-waves.svg')",
        }}
      />

      <div className="relative z-10 flex min-h-screen flex-col">
        <Header t={t} />
        <main className="flex flex-1 flex-col items-center justify-center px-6 pt-4 pb-28">
          <section className="text-center">
            <h1 className="font-sans text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] text-[var(--text-primary)]">
              {t("welcome")}
            </h1>
            <p className="mt-[10px] text-[15px] font-normal leading-[1.4] tracking-[0.01em] text-[var(--text-secondary)]">
              {t("choose")}
            </p>
          </section>

          <section className="mt-16 grid w-full max-w-[1112px] grid-cols-1 gap-8 xl:grid-cols-[540px_540px]">
            <SpaceCard
              t={t}
              ns="client"
              accent="gold"
              badgeIcon={<UserRound className="h-[24px] w-[24px]" />}
              href="/produit"
              items={CLIENT_ITEMS}
              visual={<ChatVisual />}
            />
            <SpaceCard
              t={t}
              ns="operator"
              accent="cyan"
              badgeIcon={<ShieldCheck className="h-[23px] w-[23px]" />}
              href="/agent/synthese"
              items={OPERATOR_ITEMS}
              visual={<CockpitVisual />}
            />
          </section>
        </main>
      </div>
    </div>
  );
}

function Header({ t }: { t: T }) {
  return (
    <header className="relative flex h-[112px] shrink-0 items-start justify-between pl-[30px] pr-[48px] pt-[28px]">
      <Image
        src="/brand/tessera-interface-lockup.png"
        alt="Tessera AI Control Plane"
        width={280}
        height={72}
        priority
        unoptimized
        className="h-[72px] w-[280px] object-contain"
      />

      <SpaceToggle t={t} />

      <div className="flex items-center gap-[20px] pt-[6px] text-[var(--text-secondary)]">
        <Search className="h-[18px] w-[18px] stroke-[1.7]" aria-hidden="true" />
        <span className="relative inline-flex">
          <Bell className="h-[18px] w-[18px] stroke-[1.7]" aria-hidden="true" />
          <span className="absolute -right-[3px] -top-[4px] grid h-[14px] min-w-[14px] place-items-center rounded-full border border-[var(--border-gold)] bg-[color-mix(in_srgb,var(--gold)_52%,var(--bg-panel))] px-[2px] text-[7px] font-bold text-[var(--gold-strong)]">
            1
          </span>
        </span>
        <CircleHelp className="h-[18px] w-[18px] stroke-[1.7]" aria-hidden="true" />
        <Moon className="h-[18px] w-[18px] stroke-[1.7]" aria-hidden="true" />
        <div className="ml-1 flex items-center gap-[10px]">
          <span className="grid h-[36px] w-[36px] place-items-center rounded-full bg-[linear-gradient(135deg,var(--gold-strong),rgba(89,62,19,0.92))] text-[14px] font-semibold text-[var(--bg-app)] shadow-[0_0_26px_rgba(214,182,106,0.22)]">
            {t("user.initials")}
          </span>
          <span className="flex min-w-[110px] flex-col">
            <span className="text-[13px] font-semibold leading-[1.2] text-[var(--text-primary)]">
              {t("user.name")}
            </span>
            <span className="mt-[2px] text-[11px] font-normal leading-none text-[var(--text-secondary)]">
              {t("user.role")}
            </span>
          </span>
          <ChevronDown className="h-[16px] w-[16px] stroke-[1.7]" aria-hidden="true" />
        </div>
      </div>
    </header>
  );
}

function SpaceToggle({ t }: { t: T }) {
  return (
    <nav className="absolute left-[48.35%] top-[34px] flex h-[44px] w-[360px] -translate-x-1/2 items-center rounded-[12px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_76%,transparent)] p-0 shadow-[inset_0_1px_0_color-mix(in_srgb,var(--text-primary)_4%,transparent),0_0_32px_rgba(0,0,0,0.18)]">
      <Link
        href="/produit"
        className="flex h-[42px] w-[176px] items-center justify-center gap-[9px] rounded-[11px] border border-[rgba(214,182,106,0.50)] bg-[linear-gradient(180deg,rgba(214,182,106,0.22),rgba(55,38,14,0.86))] text-[13px] font-semibold uppercase tracking-[0.08em] text-[var(--gold)] shadow-[0_0_14px_rgba(214,182,106,0.10),inset_0_1px_0_rgba(255,255,255,0.07)]"
      >
        <UserRound className="h-[16px] w-[16px] fill-[color-mix(in_srgb,var(--gold-strong)_70%,transparent)] stroke-[var(--gold-strong)] stroke-[2]" />
        {t("toggle.product")}
      </Link>
      <Link
        href="/agent/synthese"
        className="flex h-[42px] flex-1 items-center justify-center gap-[9px] rounded-[11px] text-[13px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]"
      >
        <ShieldCheck className="h-[16px] w-[16px] stroke-[var(--cyan)] stroke-[2]" />
        {t("toggle.cockpit")}
      </Link>
    </nav>
  );
}

function SpaceCard({
  t,
  ns,
  accent,
  badgeIcon,
  href,
  items,
  visual,
}: {
  t: T;
  ns: "client" | "operator";
  accent: Accent;
  badgeIcon: ReactNode;
  href: "/produit" | "/agent/synthese";
  items: SpaceItem[];
  visual: ReactNode;
}) {
  const a = ACCENT[accent];

  return (
    <section
      className={cn(
        "relative h-[486px] overflow-hidden rounded-[var(--radius-lg)] border px-[30px] pb-[20px] pt-[24px] backdrop-blur-[2px]",
        a.border,
      )}
      style={{
        ...a.cardStyle,
        background:
          "linear-gradient(145deg, var(--panel) 0%, var(--panel-soft) 56%, rgba(2,8,23,0.94) 100%)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at 74% 10%, rgba(248,250,252,0.032), transparent 30%), linear-gradient(180deg, rgba(255,255,255,0.014), transparent 34%)",
        }}
      />

      <div className="relative">
        <div className="relative min-h-[146px]">
          <div className="min-w-0 max-w-[365px]">
            <div className="flex items-center gap-[14px]">
              <HexBadge className={cn(a.icon, a.soft)}>{badgeIcon}</HexBadge>
              <span className={cn("text-[12px] font-semibold uppercase tracking-[0.16em]", a.tone)}>
                {t(`${ns}.badge`)}
              </span>
            </div>
            <h2 className="mt-[14px] font-sans text-[22px] font-semibold leading-[1.1] tracking-[-0.01em] text-[var(--text-primary)]">
              {t(`${ns}.title`)}
            </h2>
            <p className="mt-[10px] max-w-[330px] text-[13px] font-normal leading-[1.5] text-[var(--text-secondary)]">
              {t(`${ns}.desc`)}
            </p>
          </div>
          <div
            className={cn(
              "absolute top-[2px] scale-[0.86] opacity-[0.24]",
              ns === "client" ? "-right-[5px]" : "right-0",
            )}
          >
            {visual}
          </div>
        </div>

        <div className="h-px w-full bg-[var(--border-subtle)]" />

        <ul className="mt-[16px] flex flex-col gap-[15px]">
          {items.map((item) => (
            <li key={item.key} className="grid grid-cols-[20px_1fr_14px] items-center">
              <item.icon className={cn("h-[18px] w-[18px] stroke-[1.6]", a.icon)} />
              <span className="min-w-0 pl-[14px]">
                <span className="block text-[13px] font-semibold leading-[1.2] text-[var(--text-primary)]">
                  {t(`${ns}.items.${item.key}.title`)}
                </span>
                <span className="mt-[1px] block text-[11.5px] font-normal leading-[1.25] text-[var(--text-secondary)]">
                  {t(`${ns}.items.${item.key}.desc`)}
                </span>
              </span>
              <ChevronRight
                className="h-[15px] w-[15px] stroke-[1.6] text-[var(--text-secondary)]"
                aria-hidden="true"
              />
            </li>
          ))}
        </ul>
      </div>

      <Link
        href={href}
        className={cn(
          "absolute bottom-[18px] left-[31px] right-[31px] flex h-[46px] items-center justify-center gap-[10px] rounded-[12px] border text-[14px] font-semibold leading-none tracking-[0.01em]",
          a.button,
        )}
        style={a.buttonStyle}
      >
        {t(`${ns}.cta`)}
        <ArrowRight className="h-[17px] w-[17px] stroke-[1.8]" />
      </Link>
    </section>
  );
}

function ChatVisual() {
  return (
    <div className="relative h-[136px] w-[238px]">
      <div className="absolute right-0 top-0 h-[55px] w-[148px] rounded-[7px] border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] shadow-[0_10px_28px_rgba(0,0,0,0.22)]">
        <div className="ml-[17px] mt-[18px] h-[6px] w-[86px] rounded-full bg-[var(--text-secondary)] opacity-55" />
        <div className="ml-[17px] mt-[14px] h-[6px] w-[112px] rounded-full bg-[var(--border-subtle)]" />
      </div>
      <div className="absolute right-0 top-[40px] h-[55px] w-[128px] rounded-[7px] border border-[var(--border-subtle)] bg-[var(--bg-panel)]">
        <div className="ml-[18px] mt-[15px] h-[6px] w-[58px] rounded-full bg-[var(--border-subtle)]" />
        <div className="ml-[18px] mt-[14px] h-[6px] w-[88px] rounded-full bg-[var(--border-subtle)]" />
        <div className="absolute -bottom-[11px] right-[24px] h-0 w-0 border-l-[15px] border-r-0 border-t-[12px] border-l-transparent border-t-[var(--bg-panel)]" />
      </div>
      <div className="absolute left-0 top-[27px] h-[59px] w-[74px] rounded-[10px] border border-[var(--border-gold)] bg-[linear-gradient(180deg,color-mix(in_srgb,var(--gold)_54%,var(--bg-panel-soft)),color-mix(in_srgb,var(--gold)_22%,var(--bg-panel)))] shadow-[var(--shadow-gold)]">
        <div className="ml-[17px] mt-[17px] h-[5px] w-[23px] rounded-full bg-[var(--gold-strong)]" />
        <div className="ml-[49px] mt-[-5px] h-[5px] w-[17px] rounded-full bg-[var(--gold-strong)]" />
        <div className="ml-[17px] mt-[12px] h-[5px] w-[39px] rounded-full bg-[var(--gold-strong)]" />
        <div className="absolute -bottom-[13px] left-[17px] h-0 w-0 border-l-[16px] border-r-0 border-t-[14px] border-l-transparent border-t-[var(--bg-panel)]" />
      </div>
      <div className="absolute bottom-[2px] left-[62px] h-[47px] w-[73px] rounded-[9px] border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)]">
        <div className="flex h-full items-center justify-center gap-[9px]">
          <span className="h-[6px] w-[6px] rounded-full bg-[var(--gold)]" />
          <span className="h-[6px] w-[6px] rounded-full bg-[var(--gold)]" />
          <span className="h-[6px] w-[6px] rounded-full bg-[var(--gold)]" />
        </div>
        <div className="absolute -bottom-[11px] right-[14px] h-0 w-0 border-l-[13px] border-r-0 border-t-[11px] border-l-transparent border-t-[var(--bg-panel-soft)]" />
      </div>
    </div>
  );
}

function CockpitVisual() {
  return (
    <div className="grid h-[144px] w-[272px] grid-cols-[140px_124px] gap-[10px]">
      <div className="row-span-2 rounded-[7px] border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] p-[14px]">
        <svg aria-hidden="true" viewBox="0 0 112 76" className="h-[76px] w-[112px]">
          <path
            d="M0 62H112M0 43H112M0 24H112M13 0V76M34 0V76M55 0V76M76 0V76M97 0V76"
            stroke="var(--border-subtle)"
            strokeWidth="1"
          />
          <path
            d="M3 58C18 49 22 31 35 33C48 35 51 50 64 41C74 34 77 18 88 20C98 22 100 37 111 29"
            fill="none"
            stroke="var(--cyan)"
            strokeWidth="2"
          />
        </svg>
        <div className="mt-[8px] h-[5px] w-[60px] rounded-full bg-[var(--border-subtle)]" />
        <div className="mt-[10px] h-[5px] w-[95px] rounded-full bg-[var(--border-subtle)]" />
        <div className="mt-[9px] h-[5px] w-[75px] rounded-full bg-[var(--border-subtle)]" />
      </div>
      <div className="rounded-[7px] border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] p-[12px]">
        <div className="flex items-center gap-[13px]">
          <div className="h-[49px] w-[49px] rounded-full border-[10px] border-[var(--border-subtle)] border-l-[var(--cyan)] border-t-[var(--cyan-soft)]" />
          <div className="flex flex-col gap-[9px]">
            <span className="h-[5px] w-[43px] rounded-full bg-[var(--border-subtle)]" />
            <span className="h-[5px] w-[32px] rounded-full bg-[var(--border-subtle)]" />
            <span className="h-[5px] w-[47px] rounded-full bg-[var(--border-subtle)]" />
          </div>
        </div>
      </div>
      <div className="rounded-[7px] border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] p-[12px]">
        <div className="grid grid-cols-3 gap-x-[12px] gap-y-[8px]">
          {Array.from({ length: 9 }, (_, index) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed decorative bars
              key={index}
              className="h-[5px] rounded-full bg-[var(--border-subtle)]"
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function HexBadge({ children, className }: { children: ReactNode; className: string }) {
  return (
    <span className={cn("relative grid h-[48px] w-[48px] place-items-center", className)}>
      <svg aria-hidden="true" className="absolute inset-0 h-full w-full" viewBox="0 0 48 48">
        <polygon
          points="24 2.5 42.6 13.2 42.6 34.8 24 45.5 5.4 34.8 5.4 13.2"
          fill="var(--bg-app)"
          fillOpacity="0.42"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
      <span className="relative">{children}</span>
    </span>
  );
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 28 28" fill="none">
      <path
        d="M2.5 14s4.2-6.5 11.5-6.5S25.5 14 25.5 14 21.3 20.5 14 20.5 2.5 14 2.5 14Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="14" cy="14" r="3.4" fill="currentColor" />
    </svg>
  );
}
