"use client";

import { AlertTriangle, ArrowRight, Boxes, Lock, LockOpen, ShieldCheck, Users } from "lucide-react";
import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Link, useRouter } from "@/i18n/navigation";
import { cn } from "@/lib/cn";
import type { LauncherSignal } from "@/lib/server/launcher-signal";

export interface DemoCred {
  username: string;
  password: string;
}
export interface DemoLogin {
  operator?: DemoCred;
  collections?: DemoCred;
}

type Accent = "gold" | "cyan" | "amber";
export type SpaceSelectorStyle = CSSProperties & Record<`--${string}`, string>;

export const SPACE_SELECTOR_TOKENS: SpaceSelectorStyle = {
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

const CARD_BG =
  "linear-gradient(145deg, var(--panel) 0%, var(--panel-soft) 56%, rgba(2,8,23,0.94) 100%)";

// Always-visible keyboard focus ring (a bright near-white ring reads on every
// accent over the night-blue base) — WCAG 2.4.7 on this dark launcher.
const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--text-primary)_72%,transparent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-app)]";

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

export function LandingLauncher({
  signal,
  demoLogin,
}: {
  signal: LauncherSignal | null;
  demoLogin: DemoLogin | null;
}) {
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
        <Header />
        <main className="flex flex-1 flex-col items-center justify-start px-6 pt-[110px] pb-36">
          <section className="flex w-full flex-col items-center text-center">
            {/* ADR 0013 — this is a labelled demo launcher, NOT the product's
                front door. Make the "démonstration" framing explicit and visible. */}
            <span className="mb-[28px] inline-flex items-center gap-[7px] rounded-full border border-[var(--border-gold)] bg-[color-mix(in_srgb,var(--gold)_12%,transparent)] px-[12px] py-[5px] text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--gold-strong)]">
              <span className="h-[6px] w-[6px] rounded-full bg-[var(--gold-strong)]" />
              {t("demoBadge")}
            </span>
            <h1 className="font-sans text-[30px] font-semibold leading-[1.1] tracking-[-0.02em] text-[var(--text-primary)]">
              {t("demoTitle")}
            </h1>
            <SignalBand t={t} signal={signal} />
          </section>

          {/* Two PLANES (ADR 0013): the launcher is a CHOOSER OF PLANES, not a
              flat surface list. The business card links to the /espaces directory
              (symmetric to the Flotte list→détail); the control card enters the
              cockpit. Individual business surfaces live in /espaces, never inline. */}
          <section className="mt-14 grid w-full max-w-[1040px] grid-cols-1 gap-7 lg:grid-cols-2">
            <BusinessPlaneCard t={t} />
            <ControlPlaneCard t={t} demoOperator={demoLogin?.operator} />
          </section>

          {/* No per-agent breakdown here (ADR 0008/0010/0013): a front DOOR carries
              only the fleet DIGEST (the rollup, in the hero band above). The
              per-agent verdict + eval-gate detail lives one altitude down, on the
              Flotte (/agents) governance facet — not duplicated on the launcher. */}
        </main>
      </div>
    </div>
  );
}

// 1-click seeded-account login (demo mode only). It opens a REAL next-auth session
// on the seeded Credentials account (ADR 0009) then navigates to the surface — it
// satisfies the guard by logging in, never a bypass. Rendered only when the server
// passed demo credentials (off in production).
function DemoEnterButton({
  label,
  cred,
  target,
  accent,
}: {
  label: string;
  cred: DemoCred;
  target: "/recouvrement" | "/surveiller/vue-ensemble";
  accent: Accent;
}) {
  const a = ACCENT[accent];
  const router = useRouter();
  const [pending, setPending] = useState(false);
  async function enter() {
    setPending(true);
    const res = await signIn("credentials", {
      username: cred.username,
      password: cred.password,
      redirect: false,
    });
    if (res && !res.error) {
      router.push(target);
      router.refresh();
    } else {
      setPending(false);
    }
  }
  return (
    <button
      type="button"
      onClick={enter}
      disabled={pending}
      className={cn(
        "flex h-[46px] w-full items-center justify-center gap-[10px] rounded-[12px] border text-[14px] font-semibold leading-none tracking-[0.01em] disabled:opacity-70",
        a.button,
        FOCUS,
      )}
      style={a.buttonStyle}
    >
      <Lock className="h-[15px] w-[15px]" />
      {label}
    </button>
  );
}

// Real public-safe signal band (ADR 0009). Renders a "live" pulse ONLY when real
// data is present; honest "indisponible" otherwise.
//
// HONESTY OF SCOPE: a release verdict and a pass rate belong to ONE agent, never
// to the fleet. The only legitimate fleet-level number is the verdict rollup —
// how many agents are releasable. So the headline is "Contrôle actif ·
// {passed}/{total} agents libérables" (the gate is doing its job — positive —
// AND the count it currently clears). The per-agent verdict + strict pass rate
// live in the footer below; WHICH case failed (the failure category) is never
// shown publicly — it lives behind the operator gate.
function SignalBand({ t, signal }: { t: T; signal: LauncherSignal | null }) {
  const neutral =
    "inline-flex items-center gap-[7px] rounded-full border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_70%,transparent)] px-[12px] py-[6px] text-[12px] leading-none text-[var(--text-secondary)]";
  if (!signal) {
    return (
      <div className={cn("mt-7", neutral)}>
        <span
          className="h-[7px] w-[7px] rounded-full bg-[var(--text-secondary)] opacity-50"
          aria-hidden="true"
        />
        {t("signal.unavailable")}
      </div>
    );
  }
  // The verdict rollup is the only fleet number. Its tone is the honest verdict:
  // green when every agent clears the gate, red while none do, amber in between.
  const allReleasable =
    signal.agentsWithRelease > 0 && signal.passedAgents === signal.agentsWithRelease;
  const noneReleasable = signal.agentsWithRelease > 0 && signal.passedAgents === 0;
  const rollupColor = allReleasable
    ? "var(--success)"
    : noneReleasable
      ? "#F87171"
      : "var(--amber)";
  return (
    <div className="mt-7 flex w-full max-w-[840px] flex-col items-center gap-[12px]">
      {/* One bounded status band — three segments, one fact each: control is
          active (the green dot is the live indicator), how many agents it holds
          under review, and the only fleet-level verdict number (how many are
          cleared for production). */}
      <div className="flex w-full flex-col divide-y divide-[var(--border-subtle)] overflow-hidden rounded-[16px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-panel)_55%,transparent)] backdrop-blur-[2px] sm:flex-row sm:divide-x sm:divide-y-0">
        <span
          className="flex flex-1 items-center justify-center gap-[8px] px-[16px] py-[14px] text-center text-[13px] font-semibold leading-[1.3]"
          style={{ color: "var(--success)" }}
        >
          <span
            className="h-[7px] w-[7px] shrink-0 rounded-full bg-[var(--success)]"
            aria-hidden="true"
          />
          {t("signal.controlActive")}
        </span>
        <span className="flex flex-1 items-center justify-center gap-[8px] px-[16px] py-[14px] text-center text-[13px] leading-[1.3] text-[var(--text-secondary)]">
          <Users className="h-[15px] w-[15px] shrink-0 stroke-[1.7]" aria-hidden="true" />
          {t("signal.agentsUnderReview", { count: signal.agentsCount })}
        </span>
        {signal.agentsWithRelease > 0 ? (
          <span
            className="flex flex-1 items-center justify-center gap-[8px] px-[16px] py-[14px] text-center text-[13px] font-semibold leading-[1.3]"
            style={{ color: rollupColor }}
          >
            {allReleasable ? (
              <ShieldCheck className="h-[15px] w-[15px] shrink-0 stroke-[1.8]" aria-hidden="true" />
            ) : (
              <AlertTriangle
                className="h-[15px] w-[15px] shrink-0 stroke-[1.8]"
                aria-hidden="true"
              />
            )}
            {t("signal.releasableRollup", {
              passed: signal.passedAgents,
              total: signal.agentsWithRelease,
            })}
          </span>
        ) : null}
      </div>
      {/* The socle line, under the band: why a "0" is not a failure of control. */}
      {!allReleasable && signal.agentsWithRelease > 0 ? (
        <p className="flex items-center gap-[7px] text-center text-[12px] leading-[1.5] text-[var(--text-secondary)]">
          <Lock className="h-[13px] w-[13px] shrink-0" aria-hidden="true" />
          {t("signal.gateContext")}
        </p>
      ) : null}
    </div>
  );
}

function Header() {
  return (
    <header className="relative flex h-[88px] shrink-0 items-center justify-between border-b border-[var(--border-subtle)] px-6">
      {/* The launcher IS the plane chooser — no PRODUIT/COCKPIT toggle here (it
          would be redundant). The toggle stays in the cockpit for operators. */}
      <TesseraLogo className="h-[40px]" />

      {/* Launcher header variant: the global group ONLY (theme · language ·
          account). No search / notifications / help — there is nothing to search
          or be notified about on the plane chooser. */}
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <LanguageSwitcher />
        <AuthControl />
      </div>
    </header>
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
  gated = true,
}: {
  a: AccentStyle;
  icon: ReactNode;
  badge: string;
  title: string;
  desc: string;
  authNote?: string;
  /** Whether the plane is access-gated — drives the chip's padlock (closed vs
   * open). The chip is the SAME component both sides; only icon + text change. */
  gated?: boolean;
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
          {gated ? (
            <Lock className="h-[12px] w-[12px]" />
          ) : (
            <LockOpen className="h-[12px] w-[12px]" />
          )}
          {authNote}
        </span>
      ) : null}
    </div>
  );
}

// "What you'll find" line — a non-clickable, accent-neutral contents strip,
// IDENTICAL on both plane cards (twin doors). The two cards differ only by their
// header + single primary CTA; the nav into each plane lives on the other side
// of that door (the /espaces directory, the cockpit's own sidebar). Listing
// deep-links here created asymmetry and role-dependent dead ends (ADR 0013).
// Each contained surface as its own STATIC label chip (no "·" string that reads
// as one entity). Labels, not buttons — no hover, no click; the card's CTA stays
// the only action. When an item carries a `gated` flag, a static padlock
// (open / closed) discloses its access PER chip — for a mixed-access plane where
// a single pill would be false. Identical chip style on both plane cards.
function ContainsLine({ items }: { items: { label: string; gated?: boolean }[] }) {
  return (
    <div className="mt-[18px] mb-[84px] flex flex-wrap gap-[8px] border-t border-[var(--border-subtle)] pt-[14px]">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-[6px] rounded-[8px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)] px-[10px] py-[5px] text-[12px] font-medium leading-none text-[var(--text-secondary)]"
        >
          {item.gated ? (
            <Lock className="h-[12px] w-[12px] shrink-0 opacity-80" aria-hidden="true" />
          ) : null}
          {item.label}
        </span>
      ))}
    </div>
  );
}

// Business plane (ADR 0013): a PURE plan card — a door to the /espaces directory,
// not an inline surface list. The surfaces, their guards and 1-click demo logins
// live in /espaces.
function BusinessPlaneCard({ t }: { t: T }) {
  const a = ACCENT.gold;
  return (
    <section
      className={cn(
        "relative flex h-full flex-col overflow-hidden rounded-[var(--radius-lg)] border px-[28px] pb-[28px] pt-[28px] backdrop-blur-[2px]",
        a.border,
      )}
      style={{ ...a.cardStyle, background: CARD_BG }}
    >
      <CardGlow />
      <div className="relative flex flex-1 flex-col">
        <PlaneHeader
          a={a}
          icon={<Boxes className="h-[23px] w-[23px]" />}
          badge={t("business.badge")}
          title={t("business.title")}
          desc={t("business.desc")}
        />
        {/* Mixed-access plane → no single pill; the padlock is PER chip
            (Espace client open, Console recouvrement gated/collections). */}
        <ContainsLine
          items={[
            { label: t("client.title"), gated: false },
            { label: t("recouvrement.title"), gated: true },
          ]}
        />
        <Link
          href="/espaces"
          className={cn(
            "mt-auto flex h-[46px] items-center justify-center gap-[10px] rounded-[12px] border text-[14px] font-semibold leading-none tracking-[0.01em]",
            a.button,
            FOCUS,
          )}
          style={a.buttonStyle}
        >
          {t("business.reveal")}
          <ArrowRight className="h-[17px] w-[17px] stroke-[1.8]" />
        </Link>
      </div>
    </section>
  );
}

// Control plane (ADR 0013): the cockpit — govern the platform. Guarded to the
// platform roles; the card surfaces the "sign-in required" note and links.
function ControlPlaneCard({ t, demoOperator }: { t: T; demoOperator?: DemoCred }) {
  const a = ACCENT.cyan;
  return (
    <section
      className={cn(
        "relative flex h-full flex-col overflow-hidden rounded-[var(--radius-lg)] border px-[28px] pb-[28px] pt-[28px] backdrop-blur-[2px]",
        a.border,
      )}
      style={{ ...a.cardStyle, background: CARD_BG }}
    >
      <CardGlow />
      <div className="pointer-events-none absolute right-0 top-[20px] scale-[0.82] opacity-[0.2]">
        <CockpitVisual />
      </div>
      <div className="relative flex flex-1 flex-col">
        <PlaneHeader
          a={a}
          icon={<ShieldCheck className="h-[23px] w-[23px]" />}
          badge={t("control.badge")}
          title={t("control.title")}
          desc={t("control.desc")}
        />
        {/* Below the horizontal rule: the light section legend. The access
            signal is the padlock on the CTA (whole plane gated), not a pill —
            the DÉMONSTRATION badge already carries the demo reality. */}
        <div className="mt-[18px] mb-[22px] border-t border-[var(--border-subtle)] pt-[14px]">
          <p className="text-[12.5px] leading-[1.5] text-[color-mix(in_srgb,var(--text-secondary)_70%,transparent)]">
            {[
              t("operator.items.supervision.title"),
              t("operator.items.management.title"),
              t("operator.items.configuration.title"),
              t("operator.items.platform.title"),
            ].join("  ·  ")}
          </p>
        </div>
        {demoOperator ? (
          <div className="mt-auto">
            <DemoEnterButton
              label={t("control.cta")}
              cred={demoOperator}
              target="/surveiller/vue-ensemble"
              accent="cyan"
            />
          </div>
        ) : (
          <Link
            href="/surveiller/vue-ensemble"
            className={cn(
              "mt-auto flex h-[46px] items-center justify-center gap-[10px] rounded-[12px] border text-[14px] font-semibold leading-none tracking-[0.01em]",
              a.button,
              FOCUS,
            )}
            style={a.buttonStyle}
          >
            <Lock className="h-[15px] w-[15px]" />
            {t("control.cta")}
            <ArrowRight className="h-[17px] w-[17px] stroke-[1.8]" />
          </Link>
        )}
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
