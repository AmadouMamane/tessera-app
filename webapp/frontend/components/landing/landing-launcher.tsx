"use client";

import {
  Activity,
  ArrowRight,
  Boxes,
  Fingerprint,
  ListChecks,
  Lock,
  LockOpen,
  ShieldBan,
  ShieldCheck,
} from "lucide-react";
import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { Fragment, useEffect, useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { AppHeader } from "@/components/layout/app-header";
import { DemoBadge } from "@/components/layout/demo-badge";
import { Link, useRouter } from "@/i18n/navigation";
import type { Role } from "@/lib/auth/accounts";
import { demoLoginNeeded } from "@/lib/auth/roles";
import { cn } from "@/lib/cn";
import {
  type Pillar,
  type PillarKey,
  type PillarSignal,
  type PillarTone,
  launcherPillars,
} from "@/lib/launcher-pillars";
import { fetchLauncherSignal } from "@/lib/launcher-signal-client";
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
  "--border-rose": "rgba(244, 114, 182, 0.32)",
  "--text-primary": "#F8FAFC",
  "--text-secondary": "#A6B3C8",
  "--champagne": "#D6B66A",
  "--champagne-strong": "#F4C76A",
  "--gold": "var(--champagne)",
  "--gold-strong": "var(--champagne-strong)",
  "--cyan": "#2DD4BF",
  "--cyan-soft": "#67E8F9",
  "--rose": "#F472B6",
  "--rose-strong": "#F9A8D4",
  "--amber": "#F59E0B",
  "--amber-soft": "#FBBF24",
  "--success": "#22C55E",
  "--danger": "#F87171",
  "--indigo": "#818CF8",
  "--violet": "#C084FC",
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

function Orientation() {
  const t = useTranslations("comprendre");
  return (
    <>
      <p className="mt-[14px] max-w-[38rem] text-[13px] leading-[1.6] text-[var(--text-secondary)]">
        {t("launcherOrientation")}
      </p>
      <Link
        href="/comprendre"
        className="mt-[10px] rounded-sm text-[12px] text-[var(--text-secondary)] underline decoration-dotted underline-offset-4 outline-none transition-colors hover:text-[var(--text-primary)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        {t("launcherLink")}
      </Link>
    </>
  );
}

export function LandingLauncher({
  signal,
  demoLogin,
  sessionRole = null,
}: {
  signal: LauncherSignal | null;
  demoLogin: DemoLogin | null;
  // The server-verified role of the CURRENT session (null = anonymous). The
  // demo 1-click login must never clobber a session that can already enter.
  sessionRole?: Role | null;
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
        {/* Unified header (docs/design/header-normative.md) — launcher variant:
            brand only at left, the global cluster (langue · thème · compte) at
            right, no contextual cluster. The launcher IS the plane chooser, so
            no PRODUIT/COCKPIT toggle and a labelled DEMO session (not a login). */}
        <AppHeader plan="launcher" />
        <main className="flex flex-1 flex-col items-center justify-start px-6 pt-[110px] pb-36">
          <section className="flex w-full flex-col items-center text-center">
            {/* ADR 0013 — this is a labelled demo launcher, NOT the product's
                front door. Make the "démonstration" framing explicit and visible. */}
            <DemoBadge className="mb-[36px]" />
            <h1 className="font-sans text-[30px] font-semibold leading-[1.1] tracking-[-0.02em] text-[var(--text-primary)]">
              {t("demoTitle")}
            </h1>
            {/* The second door to /comprendre. One sentence, one link, nothing else: this
                page's job is to make you choose a world, not to explain the product on the
                spot. Anyone who wants the explanation first can take the link. */}
            <Orientation />
            <SignalBand t={t} signal={signal} />
          </section>

          {/* Two PLANES (ADR 0013): the launcher is a CHOOSER OF PLANES, not a
              flat surface list. The business card links to the /espaces directory
              (symmetric to the Flotte list→détail); the control card enters the
              cockpit. Individual business surfaces live in /espaces, never inline. */}
          <section className="mt-14 grid w-full max-w-[1220px] grid-cols-1 gap-7 lg:grid-cols-2">
            {/* Cockpit FIRST = the thesis (control plane is the value; business
                apps are deliberately thin). Primary card; the métier card is
                secondary (outline CTA), so the hierarchy matches the order. */}
            <ControlPlaneCard t={t} demoOperator={demoLogin?.operator} sessionRole={sessionRole} />
            <BusinessPlaneCard t={t} />
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
// passed demo credentials (off in production). A session that can ALREADY enter
// the target is navigated as-is: the demo login is for the anonymous visitor,
// never a silent downgrade of a real session (e.g. superadmin → seeded admin).
function DemoEnterButton({
  label,
  cred,
  target,
  accent,
  sessionRole,
}: {
  label: string;
  cred: DemoCred;
  target: "/recouvrement" | "/surveiller/vue-ensemble";
  accent: Accent;
  sessionRole: Role | null;
}) {
  const a = ACCENT[accent];
  const router = useRouter();
  const [pending, setPending] = useState(false);
  async function enter() {
    setPending(true);
    if (!demoLoginNeeded(sessionRole, target)) {
      router.push(target);
      router.refresh();
      return;
    }
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

// Real public-safe signal band (ADR 0009). It presents Tessera's four product
// pillars — Supervise · Secure · Evaluate · Prove — each under its REAL system
// state (or a single honest "indisponible" when there is no signal at all). Every
// value is the live signal: the real agent count, the guard's OWN activity
// counters, the release gate's OWN ready verdict, and the audit chain's OWN
// integrity verdict. Nothing is hardcoded, nothing claims a "prêt"/"vérifiée"
// the source did not actually produce, and the "temps réel" claim is witnessed
// by client polling + a visible freshness stamp, not asserted.
const PILLAR_ICON: Record<PillarKey, typeof ShieldCheck> = {
  supervise: Activity,
  secure: ShieldCheck,
  evaluate: ListChecks,
  prove: Fingerprint,
};

// One capability, one hue — carried by the ICON, never the words (the dataviz
// doctrine that reconciled the two operator calls of 2026-07-21: "une couleur
// par fonctionnalité" ET "pas trop coloré" — text wears text tokens, the mark
// beside it carries identity). The quartet is computed, not eyeballed:
// validated on the navy surface for CVD separation (worst adjacent ΔE 18.9
// deutan), normal-vision floor (23.9 ≥ 15), chroma and 3:1 contrast; the
// chart-mark lightness band is waived — these are text-labelled 14px icons,
// and the label is the secondary encoding. Status hues (green/amber/red) stay
// reserved for verdicts and appear in no capability slot.
const PILLAR_ACCENT: Record<PillarKey, string> = {
  supervise: "var(--cyan)",
  secure: "var(--indigo)",
  evaluate: "var(--champagne)",
  prove: "var(--violet)",
};

// Tone → STATE accent. Colour on a state line is INFORMATION, never decoration:
// the kickers' words sit in quiet slate, and only a real verdict recolours —
// amber for a release verdict put back in play, green/red for the audit
// chain's own verification state.
const TONE_COLOR: Record<PillarTone, string> = {
  live: "var(--text-secondary)",
  guard: "var(--text-secondary)",
  govern: "var(--text-secondary)",
  stale: "var(--amber)",
  verified: "var(--success)",
  unverified: "var(--danger)",
  neutral: "var(--text-secondary)",
};

//: Freshness after which the "temps réel" claim visibly ages (dot dims, stamp
//: switches to minutes) — three missed polls, not a guess.
const STALE_AFTER_MS = 90_000;

function PillarColumn({
  t,
  pillar,
  freshness,
  dimmed = false,
}: {
  t: T;
  pillar: Pillar;
  /** Relative age of the data ("à l'instant", "il y a 2 min") — supervise/prove. */
  freshness?: string;
  /** True when the last successful fetch is older than STALE_AFTER_MS. */
  dimmed?: boolean;
}) {
  // next-intl types t() against literal keys; the pillar keys are computed, so we
  // read through a loosened call. The keys are real — the render test proves no
  // raw "signal.*" leaks to the screen.
  const tr = t as unknown as (key: string, values?: Record<string, number>) => string;
  const Icon = PILLAR_ICON[pillar.key];
  const accent = TONE_COLOR[pillar.tone];
  const title = tr(pillar.titleKey);
  const state = tr(pillar.stateKey, pillar.stateVars);
  // A capability NAME is a name, never a verdict: every kicker sits in the same
  // quiet slate. Only a STATE that carries a real verdict recolours — the audit
  // chain's verification (green/red) and a release verdict put back in play
  // (amber). Counts stay primary so a held-back agent is never painted red.
  const titleColor = "var(--text-secondary)";
  const stateColor =
    pillar.key === "prove" || pillar.tone === "stale" ? accent : "var(--text-primary)";
  return (
    <div className="flex flex-1 flex-col items-center gap-[7px] px-[12px] py-[15px] text-center">
      {/* One complete accessible label — the SR hears "name : state" as a unit
          (§8); the visible title/state are decorative duplicates, so the meaning
          never rides on colour or icon alone. The ⓘ button stays OUTSIDE the
          aria-hidden spans: it is interactive, not decoration. */}
      <span className="sr-only">{`${title} : ${state}${freshness ? ` · ${freshness}` : ""}`}</span>
      {/* items-start + a 1px nudge keep the ⓘ hugging the FIRST line of the
          kicker: centred against a wrapped two-line title it floats mid-air,
          visually detached from the words it explains. Softened at rest
          (opacity) so the kicker row stays calm; full presence on hover/focus. */}
      <span className="flex items-start justify-center gap-[5px]">
        <span
          aria-hidden="true"
          className={cn(
            "flex items-center justify-center gap-[7px] font-semibold text-[10.5px] uppercase leading-[1.25] tracking-[0.11em]",
            dimmed && "opacity-60",
          )}
          style={{ color: titleColor }}
        >
          <Icon
            className="h-[14px] w-[14px] shrink-0 stroke-[1.9]"
            style={{ color: PILLAR_ACCENT[pillar.key] }}
          />
          {title}
        </span>
        {/* Public landing: the popover DESCRIBES the capability, nothing more.
            "Calcul"/"Source" are cockpit vocabulary — an operator's questions,
            not a visitor's (operator call, 2026-07-21). The provenance story
            lives one click away on /comprendre. */}
        <MetricInfo
          className="mt-[-1px] opacity-55 hover:opacity-100 focus-visible:opacity-100"
          title={title}
          what={tr(`signal.info.${pillar.key}.what`)}
        />
      </span>
      <span
        aria-hidden="true"
        className="font-medium text-[13px] leading-[1.35]"
        style={{ color: stateColor }}
      >
        {state}
        {freshness ? (
          <span
            className={cn(
              "text-[11px] text-[var(--text-secondary)] tracking-[0.01em]",
              dimmed ? "opacity-60" : "opacity-75",
            )}
          >
            {` · ${freshness}`}
          </span>
        ) : null}
      </span>
    </div>
  );
}

export function SignalBand({
  t,
  signal,
  pollMs = 30_000,
}: {
  t: T;
  signal: LauncherSignal | null;
  /** Client polling interval; 0 disables (tests, static rendering). */
  pollMs?: number;
}) {
  // The SSR signal seeds the band; polling keeps it real afterwards. On a failed
  // poll the last honest state stays and the freshness stamp ages visibly —
  // "temps réel" degrades in the open instead of silently lying.
  const [live, setLive] = useState<PillarSignal | null>(signal);
  const [fetchedAt, setFetchedAt] = useState<number>(() => Date.now());
  const [now, setNow] = useState<number>(() => Date.now());
  // A NEW server prop reseeds the band (client navigation, rerender with fresh
  // data) — without this, the state initializer would pin the first signal
  // forever and a later prop would be silently ignored.
  useEffect(() => {
    setLive(signal);
    setFetchedAt(Date.now());
  }, [signal]);
  useEffect(() => {
    if (pollMs <= 0) return;
    const poll = setInterval(() => {
      void fetchLauncherSignal().then((next) => {
        if (next) {
          setLive(next);
          setFetchedAt(Date.now());
        }
      });
    }, pollMs);
    const tick = setInterval(() => setNow(Date.now()), 10_000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [pollMs]);
  const pillars = launcherPillars(live);
  if (!pillars || !live) {
    return (
      <div className="mt-7 inline-flex items-center gap-[7px] rounded-full border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_70%,transparent)] px-[12px] py-[6px] text-[12px] leading-none text-[var(--text-secondary)]">
        <span
          className="h-[7px] w-[7px] rounded-full bg-[var(--text-secondary)] opacity-50"
          aria-hidden="true"
        />
        {t("signal.unavailable")}
      </div>
    );
  }
  const ageMs = Math.max(0, now - fetchedAt);
  const dimmed = ageMs > STALE_AFTER_MS;
  const freshness = dimmed
    ? t("signal.minutesAgo", { m: Math.max(1, Math.round(ageMs / 60_000)) })
    : t("signal.justNow");
  // The socle line appears ONLY when the gate is really holding some agents back
  // (real blocked count) — it explains why "prêts < total", never a blanket claim.
  const showSocle = live.agentsWithRelease > 0 && live.passedAgents < live.agentsWithRelease;
  return (
    <div className="mt-8 flex w-full max-w-[1120px] flex-col items-center gap-[16px]">
      {/* One bounded band, four capability columns — compact, stacks on mobile,
          never four big cards. The freshness stamp rides on the two columns whose
          claim is temporal (supervise: "temps réel"; prove: "à tout instant").
          Desktop separators are inset gradient hairlines (fading at both ends) —
          a full-height rule cuts the band into boxes; a faded filet reads as one
          surface. Mobile keeps the plain stacked divide. */}
      <div className="flex w-full flex-col divide-y divide-[var(--border-subtle)] overflow-hidden rounded-[16px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-panel)_55%,transparent)] backdrop-blur-[2px] sm:flex-row sm:divide-y-0">
        {pillars.map((pillar, index) => (
          <Fragment key={pillar.key}>
            {index > 0 ? (
              <span
                aria-hidden="true"
                className="my-[9px] hidden w-px shrink-0 self-stretch bg-gradient-to-b from-transparent via-[color-mix(in_srgb,var(--text-secondary)_30%,transparent)] to-transparent sm:block"
              />
            ) : null}
            <PillarColumn
              t={t}
              pillar={pillar}
              freshness={
                pillar.key === "supervise" || pillar.key === "prove" ? freshness : undefined
              }
              dimmed={dimmed}
            />
          </Fragment>
        ))}
      </div>
      {showSocle ? (
        <p className="flex items-center gap-[7px] text-center text-[12px] leading-[1.5] text-[var(--text-secondary)]">
          <ShieldBan className="h-[13px] w-[13px] shrink-0" aria-hidden="true" />
          {t("signal.gateContext")}
        </p>
      ) : null}
    </div>
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
    <div className="max-w-[540px]">
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
function ControlPlaneCard({
  t,
  demoOperator,
  sessionRole,
}: { t: T; demoOperator?: DemoCred; sessionRole: Role | null }) {
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
              sessionRole={sessionRole}
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
