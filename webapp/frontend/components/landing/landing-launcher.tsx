"use client";

import {
  ArrowRight,
  Bell,
  Boxes,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  HandCoins,
  Lock,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { Link } from "@/i18n/navigation";
import { DEFAULT_AGENT_ID, agentPath } from "@/lib/agent-context";
import { cn } from "@/lib/cn";

type Accent = "gold" | "cyan" | "amber";
type SpaceSelectorStyle = CSSProperties & Record<`--${string}`, string>;

interface SpaceItem {
  icon: React.ComponentType<{ className?: string }>;
  key: string;
  href: string;
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
  "--border-gold": "rgba(214, 182, 106, 0.28)",
  "--border-cyan": "rgba(45, 212, 191, 0.26)",
  "--border-amber": "rgba(245, 158, 11, 0.28)",
  "--text-primary": "#F8FAFC",
  "--text-secondary": "#A6B3C8",
  "--champagne": "#D6B66A",
  "--champagne-strong": "#F4C76A",
  "--gold": "var(--champagne)",
  "--gold-strong": "var(--champagne-strong)",
  "--cyan": "#2DD4BF",
  "--cyan-soft": "#67E8F9",
  "--amber": "#F59E0B",
  "--amber-soft": "#FBBF24",
  "--success": "#22C55E",
  "--radius-lg": "24px",
  "--radius-md": "16px",
  "--shadow-gold": "0 10px 30px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04)",
  "--shadow-cyan": "0 10px 30px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04)",
  "--shadow-amber": "0 10px 30px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04)",
};

// Cockpit (control plane) sub-areas — listed inside the governance card.
const OPERATOR_ITEMS: SpaceItem[] = [
  { icon: EyeIcon, key: "supervision", href: "/surveiller/vue-ensemble" },
  { icon: ShieldCheck, key: "management", href: "/agir/incidents-playbooks" },
  { icon: SlidersHorizontal, key: "configuration", href: "/configurer/signal-catalog" },
  { icon: UsersRound, key: "platform", href: "/admin/utilisateurs" },
];

const CARD_BG =
  "linear-gradient(145deg, var(--panel) 0%, var(--panel-soft) 56%, rgba(2,8,23,0.94) 100%)";

type AccentStyle = {
  border: string;
  button: string;
  buttonStyle: CSSProperties;
  cardStyle: CSSProperties;
  icon: string;
  soft: string;
  tone: string;
};

const ACCENT: Record<Accent, AccentStyle> = {
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
  amber: {
    border: "border-[var(--border-amber)]",
    button: "border-[var(--border-amber)] text-[var(--text-primary)]",
    buttonStyle: {
      background:
        "linear-gradient(180deg, rgba(245,158,11,0.24), rgba(120,72,12,0.72) 55%, rgba(60,38,8,0.92))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
    },
    cardStyle: {
      boxShadow: "var(--shadow-amber)",
    },
    icon: "text-[var(--amber)]",
    soft: "text-[var(--amber-soft)]",
    tone: "text-[var(--amber-soft)]",
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
      {/* Flat night-blue base fills the whole viewport at any width. */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(circle at 50% 12%, rgba(13, 38, 71, 0.55), transparent 46%), linear-gradient(180deg, #001025 0%, #00101f 60%, #000b18 100%)",
        }}
      />
      {/* One continuous full-width wave band, stretched horizontally but at a
          fixed height so it never grows taller as the window widens. */}
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 z-0 h-[300px]"
        style={{
          backgroundImage: "url('/assets/tessera-waves-band.png')",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "center bottom",
          backgroundSize: "100% 100%",
          maskImage: "linear-gradient(to top, #000 60%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to top, #000 60%, transparent 100%)",
        }}
      />

      <div className="relative z-10 flex min-h-screen flex-col">
        <Header t={t} />
        <main className="flex flex-1 flex-col items-center justify-center px-6 pt-2 pb-36">
          <section className="flex flex-col items-center text-center">
            {/* ADR 0013 — this is a labelled demo launcher, NOT the product's
                front door. Make the "démonstration" framing explicit and visible. */}
            <span className="mb-[14px] inline-flex items-center gap-[7px] rounded-full border border-[var(--border-gold)] bg-[color-mix(in_srgb,var(--gold)_12%,transparent)] px-[12px] py-[5px] text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--gold-strong)]">
              <span className="h-[6px] w-[6px] rounded-full bg-[var(--gold-strong)]" />
              {t("demoBadge")}
            </span>
            <h1 className="font-sans text-[38px] font-semibold leading-[1.05] tracking-[-0.02em] text-[var(--text-primary)]">
              {t("demoTitle")}
            </h1>
            <p className="mt-[10px] max-w-[560px] text-[15px] font-normal leading-[1.4] tracking-[0.01em] text-[var(--text-secondary)]">
              {t("demoSubtitle")}
            </p>
          </section>

          {/* Two PLANES (ADR 0013), not three flat surfaces: the BUSINESS plane
              (do the work — external customer + internal collections) and the
              CONTROL plane (govern — the cockpit). The business card reveals its
              two sub-surfaces in place. */}
          <section className="mt-14 grid w-full max-w-[1080px] grid-cols-1 items-start gap-7 lg:grid-cols-2">
            <BusinessPlaneCard t={t} />
            <ControlPlaneCard t={t} />
          </section>

          {/* Fleet note — showcase, NOT navigation (ADR 0008/0010). Names the
              governed fleet so a visitor sees onboarding exists without a
              dedicated entry: it is a supervisor-routed agent of the customer
              assistant, not a surface of its own. */}
          <p className="mt-9 max-w-[680px] text-center text-[12px] leading-[1.5] text-[var(--text-secondary)]">
            {t("fleetNote")}
          </p>
        </main>
      </div>
    </div>
  );
}

function Header({ t }: { t: T }) {
  return (
    <header className="relative flex h-[88px] shrink-0 items-center justify-between border-b border-[var(--border-subtle)] px-6">
      <TesseraLogo className="h-[40px]" />

      <SpaceToggle t={t} />

      <div className="flex items-center gap-3 text-[var(--text-secondary)]">
        <Search className="hidden h-[17px] w-[17px] stroke-[1.7] sm:block" aria-hidden="true" />
        <span className="relative hidden sm:inline-flex">
          <Bell className="h-[17px] w-[17px] stroke-[1.7]" aria-hidden="true" />
          <span className="absolute -right-[3px] -top-[4px] h-[7px] w-[7px] rounded-full bg-[var(--gold-strong)]" />
        </span>
        <CircleHelp className="hidden h-[17px] w-[17px] stroke-[1.7] sm:block" aria-hidden="true" />
        <LanguageSwitcher />
        <AuthControl />
      </div>
    </header>
  );
}

function SpaceToggle({ t }: { t: T }) {
  return (
    <nav className="absolute left-1/2 top-1/2 flex h-[38px] w-[332px] -translate-x-1/2 -translate-y-1/2 items-center rounded-[11px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_76%,transparent)] p-0 shadow-[inset_0_1px_0_color-mix(in_srgb,var(--text-primary)_4%,transparent),0_0_32px_rgba(0,0,0,0.18)]">
      <Link
        href="/produit"
        className="flex h-[36px] w-[164px] items-center justify-center gap-[8px] rounded-[10px] border border-[rgba(214,182,106,0.50)] bg-[linear-gradient(180deg,rgba(214,182,106,0.22),rgba(55,38,14,0.86))] text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--gold)] shadow-[0_0_14px_rgba(214,182,106,0.10),inset_0_1px_0_rgba(255,255,255,0.07)]"
      >
        <UserRound className="h-[15px] w-[15px] fill-[color-mix(in_srgb,var(--gold-strong)_70%,transparent)] stroke-[var(--gold-strong)] stroke-[2]" />
        {t("toggle.product")}
      </Link>
      <Link
        href={agentPath(DEFAULT_AGENT_ID, "synthese")}
        className="flex h-[36px] flex-1 items-center justify-center gap-[8px] rounded-[10px] text-[12px] font-semibold uppercase tracking-[0.08em] text-[var(--text-secondary)]"
      >
        <ShieldCheck className="h-[15px] w-[15px] stroke-[var(--cyan)] stroke-[2]" />
        {t("toggle.cockpit")}
      </Link>
    </nav>
  );
}

function CardGlow() {
  return (
    <div
      className="pointer-events-none absolute inset-0"
      style={{
        background:
          "radial-gradient(circle at 74% 10%, rgba(248,250,252,0.032), transparent 30%), linear-gradient(180deg, rgba(255,255,255,0.014), transparent 34%)",
      }}
    />
  );
}

function PlaneHeader({
  a,
  icon,
  badge,
  title,
  desc,
  authNote,
}: {
  a: AccentStyle;
  icon: ReactNode;
  badge: string;
  title: string;
  desc: string;
  authNote?: string;
}) {
  return (
    <div className="max-w-[440px]">
      <div className="flex items-center gap-[14px]">
        <HexBadge className={cn(a.icon, a.soft)}>{icon}</HexBadge>
        <span className={cn("text-[12px] font-semibold uppercase tracking-[0.16em]", a.tone)}>
          {badge}
        </span>
      </div>
      <h2 className="mt-[14px] font-sans text-[22px] font-semibold leading-[1.1] tracking-[-0.01em] text-[var(--text-primary)]">
        {title}
      </h2>
      <p className="mt-[10px] text-[13px] font-normal leading-[1.5] text-[var(--text-secondary)]">
        {desc}
      </p>
      {authNote ? (
        <span
          className={cn(
            "mt-[12px] inline-flex items-center gap-[6px] rounded-full border px-[10px] py-[4px] text-[11px] font-medium",
            a.border,
            a.soft,
          )}
        >
          <Lock className="h-[12px] w-[12px]" />
          {authNote}
        </span>
      ) : null}
    </div>
  );
}

// Business plane (ADR 0013): external customer + internal collections. Two
// sub-surfaces revealed in place on click — distinct from the cockpit.
function BusinessPlaneCard({ t }: { t: T }) {
  const [open, setOpen] = useState(false);
  const a = ACCENT.gold;
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-lg)] border px-[28px] pb-[24px] pt-[26px] backdrop-blur-[2px]",
        a.border,
      )}
      style={{ ...a.cardStyle, background: CARD_BG }}
    >
      <CardGlow />
      <div className="relative">
        <PlaneHeader
          a={a}
          icon={<Boxes className="h-[23px] w-[23px]" />}
          badge={t("business.badge")}
          title={t("business.title")}
          desc={t("business.desc")}
        />
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className={cn(
            "mt-[18px] flex w-full items-center justify-between rounded-[12px] border px-[16px] py-[12px] text-[13px] font-semibold transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)]",
            a.border,
            a.soft,
          )}
        >
          <span>{t(open ? "business.collapse" : "business.reveal")}</span>
          <ChevronDown
            className={cn("h-[16px] w-[16px] transition-transform", open && "rotate-180")}
          />
        </button>
        {open ? (
          <div className="mt-[14px] flex flex-col gap-[12px]">
            <SubSurface t={t} ns="client" accent="gold" href="/produit" icon={UserRound} />
            <SubSurface
              t={t}
              ns="recouvrement"
              accent="amber"
              href="/recouvrement"
              icon={HandCoins}
              authRequired
            />
          </div>
        ) : null}
      </div>
    </section>
  );
}

// One revealed business sub-surface (external client / internal collections).
function SubSurface({
  t,
  ns,
  accent,
  href,
  icon: Icon,
  authRequired = false,
}: {
  t: T;
  ns: "client" | "recouvrement";
  accent: Accent;
  href: "/produit" | "/recouvrement";
  icon: React.ComponentType<{ className?: string }>;
  // Guarded sub-surface (recouvrement → collections role) shows a "sign-in
  // required" note so a reviewer understands the gate. routing ≠ authorization:
  // the layout guard decides; this only informs and links (ADR 0013).
  authRequired?: boolean;
}) {
  const a = ACCENT[accent];
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-start gap-[14px] rounded-[14px] border bg-[color-mix(in_srgb,var(--bg-panel)_60%,transparent)] px-[16px] py-[14px] transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)]",
        a.border,
      )}
    >
      <span
        className={cn(
          "mt-[2px] grid h-[34px] w-[34px] shrink-0 place-items-center rounded-[10px] border",
          a.border,
          a.icon,
        )}
      >
        <Icon className="h-[17px] w-[17px]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-center gap-[8px]">
          <span className="text-[14px] font-semibold text-[var(--text-primary)]">
            {t(`${ns}.title`)}
          </span>
          <span
            className={cn(
              "rounded-full border px-[8px] py-[2px] text-[10px] font-semibold uppercase tracking-[0.1em]",
              a.border,
              a.tone,
            )}
          >
            {t(`${ns}.kind`)}
          </span>
        </span>
        <span className="mt-[5px] block text-[12px] leading-[1.45] text-[var(--text-secondary)]">
          {t(`${ns}.desc`)}
        </span>
        {authRequired ? (
          <span
            className={cn(
              "mt-[8px] inline-flex items-center gap-[5px] text-[11px] font-medium",
              a.soft,
            )}
          >
            <Lock className="h-[11px] w-[11px]" />
            {t(`${ns}.authNote`)}
          </span>
        ) : null}
      </span>
      <ArrowRight className="mt-[3px] h-[16px] w-[16px] shrink-0 text-[var(--text-secondary)] transition-transform group-hover:translate-x-[2px] group-hover:text-[var(--text-primary)]" />
    </Link>
  );
}

// Control plane (ADR 0013): the cockpit — govern the platform. Guarded to the
// platform roles; the card surfaces the "sign-in required" note and links.
function ControlPlaneCard({ t }: { t: T }) {
  const a = ACCENT.cyan;
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-lg)] border px-[28px] pb-[24px] pt-[26px] backdrop-blur-[2px]",
        a.border,
      )}
      style={{ ...a.cardStyle, background: CARD_BG }}
    >
      <CardGlow />
      <div className="pointer-events-none absolute right-0 top-[20px] scale-[0.82] opacity-[0.2]">
        <CockpitVisual />
      </div>
      <div className="relative">
        <PlaneHeader
          a={a}
          icon={<ShieldCheck className="h-[23px] w-[23px]" />}
          badge={t("control.badge")}
          title={t("control.title")}
          desc={t("control.desc")}
          authNote={t("control.authNote")}
        />
        <ul className="mt-[18px] flex flex-col gap-[16px]">
          {OPERATOR_ITEMS.map((item) => (
            <li key={item.key}>
              <Link
                href={item.href}
                className="group/row -mx-[8px] grid grid-cols-[20px_1fr_14px] items-center rounded-[8px] px-[8px] py-[3px] transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)]"
              >
                <item.icon className={cn("h-[18px] w-[18px] stroke-[1.6]", a.icon)} />
                <span className="min-w-0 pl-[14px]">
                  <span className="block text-[13px] font-semibold leading-[1.2] text-[var(--text-primary)]">
                    {t(`operator.items.${item.key}.title`)}
                  </span>
                  <span className="mt-[4px] block text-[11.5px] font-normal leading-[1.25] text-[var(--text-secondary)]">
                    {t(`operator.items.${item.key}.desc`)}
                  </span>
                </span>
                <ChevronRight
                  className="h-[15px] w-[15px] stroke-[1.6] text-[var(--text-secondary)] transition-transform group-hover/row:translate-x-[2px] group-hover/row:text-[var(--text-primary)]"
                  aria-hidden="true"
                />
              </Link>
            </li>
          ))}
        </ul>
        <Link
          href={agentPath(DEFAULT_AGENT_ID, "synthese")}
          className={cn(
            "mt-[22px] flex h-[46px] items-center justify-center gap-[10px] rounded-[12px] border text-[14px] font-semibold leading-none tracking-[0.01em]",
            a.button,
          )}
          style={a.buttonStyle}
        >
          {t("control.cta")}
          <ArrowRight className="h-[17px] w-[17px] stroke-[1.8]" />
        </Link>
      </div>
    </section>
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
