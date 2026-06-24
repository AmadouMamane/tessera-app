"use client";

import {
  ArrowRight,
  Bell,
  Boxes,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  FileCheck,
  HandCoins,
  Lock,
  LogIn,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  UsersRound,
} from "lucide-react";
import { signIn } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { useState } from "react";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import { Link, useRouter } from "@/i18n/navigation";
import type { Role } from "@/lib/auth/accounts";
import { hasCockpitAccess, hasCollectionsAccess, hasProductAccess } from "@/lib/auth/roles";
import { cn } from "@/lib/cn";
import type { LauncherAgentSignal, LauncherSignal } from "@/lib/server/launcher-signal";

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

// A preview row inside a plane card (same gabarit on both sides — icon + label +
// short desc + chevron). `access` decides GRACEFUL entry, never an RBAC rebound:
// when the current role may enter, the row deep-links to its real target; when it
// may not (e.g. an anonymous visitor and an internal/operator surface), it routes
// to the locale login — a page that HANDLES the sign-in and then role-routes —
// instead of bouncing silently to some other landing (ADR 0013). Routing here is
// UX, not authorization: the plane's own layout guard stays the authority.
interface PlaneRow {
  icon: React.ComponentType<{ className?: string }>;
  key: string;
  target: string;
  access: (role: Role | null) => boolean;
}

// Business plane — the two audience surfaces (count: 2). Honest asymmetry with the
// 5-section cockpit below: we match the row TREATMENT, not the count.
const BUSINESS_ROWS: PlaneRow[] = [
  { icon: UserRound, key: "client", target: "/produit", access: hasProductAccess },
  { icon: HandCoins, key: "recouvrement", target: "/recouvrement", access: hasCollectionsAccess },
];

// Control plane — the cockpit's five top-level sections (the breadth is the point).
const COCKPIT_ROWS: PlaneRow[] = [
  {
    icon: EyeIcon,
    key: "supervision",
    target: "/surveiller/vue-ensemble",
    access: hasCockpitAccess,
  },
  {
    icon: ShieldCheck,
    key: "management",
    target: "/agir/incidents-playbooks",
    access: hasCockpitAccess,
  },
  { icon: FileCheck, key: "proof", target: "/prouver/evidence-store", access: hasCockpitAccess },
  {
    icon: SlidersHorizontal,
    key: "configuration",
    target: "/configurer/signal-catalog",
    access: hasCockpitAccess,
  },
  { icon: UsersRound, key: "platform", target: "/admin/utilisateurs", access: hasCockpitAccess },
];

// Where a guarded row sends a role that may not (yet) enter: a real auth page.
const rowHref = (row: PlaneRow, role: Role | null): string =>
  row.access(role) ? row.target : "/login";

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
  role,
}: {
  signal: LauncherSignal | null;
  demoLogin: DemoLogin | null;
  role: Role | null;
}) {
  const t = useTranslations("landing");
  const locale = useLocale();

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
            {/* Honesty as one line of precision (ADR 0013) — not a defensive
                disclaimer. The DEMO badge above already frames the visit. */}
            <p className="mt-[8px] max-w-[520px] text-[12px] leading-[1.5] text-[color-mix(in_srgb,var(--text-secondary)_82%,transparent)]">
              {t("demoHonesty")}
            </p>
            <SignalBand t={t} signal={signal} />
          </section>

          {/* Two PLANES (ADR 0013): the launcher is a CHOOSER OF PLANES, not a
              flat surface list. The business card links to the /espaces directory
              (symmetric to the Flotte list→détail); the control card enters the
              cockpit. Individual business surfaces live in /espaces, never inline. */}
          <section className="mt-14 grid w-full max-w-[1040px] grid-cols-1 gap-7 lg:grid-cols-2">
            <BusinessPlaneCard t={t} role={role} />
            <ControlPlaneCard t={t} role={role} demoOperator={demoLogin?.operator} />
          </section>

          {/* Per-agent footer — showcase, NOT navigation (ADR 0008/0010). PUBLIC
              boundary (ADR 0009): each agent shows its release VERDICT + its own
              STRICT pass rate (a real number that maps to exactly one agent).
              WHICH case failed (the failure category, e.g. PII) is NEVER shown
              here — that lives behind the operator gate, in the cockpit. */}
          {signal ? (
            <div className="mt-9 flex flex-col items-center gap-[12px]">
              <div className="flex flex-wrap items-stretch justify-center gap-[12px]">
                {signal.agents.map((a) => (
                  <AgentVerdict key={a.name} t={t} agent={a} locale={locale} />
                ))}
              </div>
              <p className="text-center text-[11px] leading-[1.4] text-[var(--text-secondary)]">
                {t("signal.perAgentLegend")}
              </p>
            </div>
          ) : (
            <p className="mt-9 max-w-[680px] text-center text-[12px] leading-[1.5] text-[var(--text-secondary)]">
              {t("fleetNote")}
            </p>
          )}
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
      <LogIn className="h-[16px] w-[16px]" />
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
    <div className="mt-7 flex max-w-[760px] flex-col items-center gap-[12px]">
      <span className={neutral}>
        <span className="relative flex h-[7px] w-[7px]" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--success)] opacity-60" />
          <span className="relative inline-flex h-[7px] w-[7px] rounded-full bg-[var(--success)]" />
        </span>
        {t("signal.live")}
      </span>
      {/* Lead with the value: control is active, and how many agents it currently
          holds under review (the agent count is the honest fleet number here). */}
      <div className="flex flex-wrap items-center justify-center gap-x-[8px] gap-y-[4px] text-[13px] leading-[1.3]">
        <span
          className="inline-flex items-center gap-[6px] font-semibold"
          style={{ color: "var(--success)" }}
        >
          <ShieldCheck className="h-[14px] w-[14px]" aria-hidden="true" />
          {t("signal.controlActive")}
        </span>
        <span className="text-[var(--text-secondary)]" aria-hidden="true">
          ·
        </span>
        <span className="text-[var(--text-secondary)]">
          {t("signal.agentsUnderReview", { count: signal.agentsCount })}
        </span>
      </div>
      {/* The only fleet-level verdict number: how many are cleared for production. */}
      {signal.agentsWithRelease > 0 ? (
        <span className="text-[13px] font-semibold leading-[1.3]" style={{ color: rollupColor }}>
          {t("signal.releasableRollup", {
            passed: signal.passedAgents,
            total: signal.agentsWithRelease,
          })}
        </span>
      ) : null}
      {!allReleasable && signal.agentsWithRelease > 0 ? (
        <p className="max-w-[600px] text-center text-[12px] leading-[1.5] text-[var(--text-secondary)]">
          {t("signal.gateContext")}
        </p>
      ) : null}
    </div>
  );
}

// "20260618T083906Z" → localized date, or null if it can't be parsed (never a
// fabricated date).
function fmtRunDate(runAt: string | null, locale: string): string | null {
  if (!runAt) return null;
  const m = runAt.match(/^(\d{4})(\d{2})(\d{2})T/);
  if (!m) return null;
  const dt = new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00Z`);
  return Number.isNaN(dt.getTime()) ? null : dt.toLocaleDateString(locale);
}

// One per-agent verdict tile (public boundary, ADR 0009): release VERDICT + the
// agent's own pass rate (against its OWN set — not comparable across agents) +
// its run date and catalogue version (so the staggered, independent nature is
// visible) + the SOCLE score (the only cross-agent comparator). A "verdict
// périmé" chip when scored against a superseded catalogue. NEVER a failure
// category — the "why" stays operator-only.
function AgentVerdict({ t, agent, locale }: { t: T; agent: LauncherAgentSignal; locale: string }) {
  const released = agent.gatePassed === true;
  const blocked = agent.gatePassed === false;
  const color = released ? "var(--success)" : blocked ? "#F87171" : "var(--text-secondary)";
  const pct = agent.passRate != null ? Math.round(agent.passRate * 100) : null;
  const date = fmtRunDate(agent.runAt, locale);
  // Façade carries business meaning only: the security floor (same cases for all)
  // and when it was evaluated — no internal catalogue version, no "own set" tag.
  const security =
    agent.soclePassed != null && agent.socleTotal != null
      ? t("signal.agentSecurity", { passed: agent.soclePassed, total: agent.socleTotal })
      : null;
  return (
    <div
      className="flex min-w-[188px] flex-col gap-[8px] rounded-[14px] border bg-[color-mix(in_srgb,var(--bg-panel)_42%,transparent)] px-[15px] py-[12px]"
      style={{
        borderColor: agent.verdictStale
          ? "color-mix(in srgb, var(--amber) 50%, transparent)"
          : "var(--border-subtle)",
      }}
    >
      <div className="flex items-center justify-between gap-[8px]">
        <span className="text-[13px] font-semibold leading-none text-[var(--text-primary)]">
          {agent.name}
        </span>
        {agent.verdictStale ? (
          <span
            className="inline-flex items-center rounded-full border px-[6px] py-[2px] text-[9.5px] font-semibold uppercase leading-none tracking-[0.04em]"
            style={{
              color: "var(--amber)",
              borderColor: "color-mix(in srgb, var(--amber) 45%, transparent)",
            }}
          >
            {t("signal.agentStale")}
          </span>
        ) : null}
      </div>
      <span
        className="inline-flex items-center gap-[5px] text-[11.5px] font-semibold leading-none"
        style={{ color }}
      >
        {released ? (
          <CircleCheck className="h-[13px] w-[13px]" aria-hidden="true" />
        ) : blocked ? (
          <ShieldAlert className="h-[13px] w-[13px]" aria-hidden="true" />
        ) : null}
        {t(
          released
            ? "signal.agentReleasable"
            : blocked
              ? "signal.agentBlocked"
              : "signal.agentUnknown",
        )}
      </span>
      {/* Self-explanatory rate: what it measures (réussis), its direction, and
          its verifiable fraction — never a bare "%". */}
      {pct != null && agent.passed != null && agent.total != null ? (
        <span className="text-[12px] font-medium leading-[1.3] text-[var(--text-secondary)]">
          {t("signal.agentRate", { rate: pct, passed: agent.passed, total: agent.total })}
        </span>
      ) : null}
      {security ? (
        <span className="text-[11px] leading-[1.3] text-[var(--text-secondary)]">{security}</span>
      ) : null}
      {date ? (
        <span className="text-[10.5px] leading-[1.3] text-[var(--text-secondary)]">
          {t("signal.agentEvaluatedOn", { date })}
        </span>
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

// One preview row — same gabarit on both plane cards (icon + label + short desc +
// affordance). The trailing affordance is a chevron when the current role may
// enter (deep-link), or a lock when sign-in is required (the row then routes to
// the auth page, never a silent RBAC rebound).
function PreviewRow({
  a,
  icon: Icon,
  title,
  desc,
  href,
  accessible,
}: {
  a: AccentStyle;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
  href: string;
  accessible: boolean;
}) {
  return (
    <li>
      <Link
        href={href}
        className={cn(
          "group/row -mx-[8px] grid grid-cols-[20px_1fr_14px] items-center rounded-[8px] px-[8px] py-[6px] transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)]",
          FOCUS,
        )}
      >
        <Icon className={cn("h-[18px] w-[18px] stroke-[1.6]", a.icon)} />
        <span className="min-w-0 pl-[14px]">
          <span className="block text-[13px] font-semibold leading-[1.2] text-[var(--text-primary)]">
            {title}
          </span>
          <span className="mt-[3px] block truncate text-[11.5px] font-normal leading-[1.25] text-[var(--text-secondary)]">
            {desc}
          </span>
        </span>
        {accessible ? (
          <ChevronRight
            className="h-[15px] w-[15px] stroke-[1.6] text-[var(--text-secondary)] transition-transform group-hover/row:translate-x-[2px] group-hover/row:text-[var(--text-primary)]"
            aria-hidden="true"
          />
        ) : (
          <Lock
            className="h-[13px] w-[13px] stroke-[1.6] text-[var(--text-secondary)]"
            aria-hidden="true"
          />
        )}
      </Link>
    </li>
  );
}

// Business plane (ADR 0013): the two audience surfaces, each a preview row that
// enters its surface (or the auth page if sign-in is required). The CTA leads to
// the full /espaces directory.
function BusinessPlaneCard({ t, role }: { t: T; role: Role | null }) {
  const a = ACCENT.gold;
  return (
    <section
      className={cn(
        "relative flex h-full min-h-[472px] flex-col overflow-hidden rounded-[var(--radius-lg)] border px-[28px] pb-[28px] pt-[28px] backdrop-blur-[2px]",
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
        <ul className="mt-[20px] flex flex-col gap-[10px]">
          {BUSINESS_ROWS.map((row) => (
            <PreviewRow
              key={row.key}
              a={a}
              icon={row.icon}
              title={t(`${row.key}.title`)}
              desc={t(`${row.key}.rowDesc`)}
              href={rowHref(row, role)}
              accessible={row.access(role)}
            />
          ))}
        </ul>
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

// Control plane (ADR 0013): the cockpit — five top-level sections previewed as
// rows (the breadth is the point). Each row enters its section or, when sign-in is
// required, the auth page — never a silent rebound. The CTA leads to the cockpit.
function ControlPlaneCard({
  t,
  role,
  demoOperator,
}: { t: T; role: Role | null; demoOperator?: DemoCred }) {
  const a = ACCENT.cyan;
  return (
    <section
      className={cn(
        "relative flex h-full min-h-[472px] flex-col overflow-hidden rounded-[var(--radius-lg)] border px-[28px] pb-[28px] pt-[28px] backdrop-blur-[2px]",
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
          authNote={demoOperator ? t("demoLogin.note") : t("control.authNote")}
        />
        <ul className="mt-[20px] flex flex-col gap-[10px]">
          {COCKPIT_ROWS.map((row) => (
            <PreviewRow
              key={row.key}
              a={a}
              icon={row.icon}
              title={t(`operator.items.${row.key}.title`)}
              desc={t(`operator.items.${row.key}.desc`)}
              href={rowHref(row, role)}
              accessible={row.access(role)}
            />
          ))}
        </ul>
        {demoOperator ? (
          <div className="mt-auto">
            <DemoEnterButton
              label={t("demoLogin.operator")}
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
