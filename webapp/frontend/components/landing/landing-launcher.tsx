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
import { useTranslations } from "next-intl";
import type { CSSProperties, ReactNode } from "react";
import { Fragment, useEffect, useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { LauncherWaves } from "@/components/landing/launcher-waves";
import { AppHeader } from "@/components/layout/app-header";
import { DemoBadge } from "@/components/layout/demo-badge";
import { Link } from "@/i18n/navigation";
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

type Accent = "gold" | "cyan" | "amber";
const CARD_BG = "var(--launcher-card-bg)";

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
    button: "border-[var(--border-gold)] text-[var(--launcher-btn-ink)]",
    buttonStyle: {
      background: "var(--launcher-btn-gold)",
      boxShadow: "var(--launcher-btn-shadow)",
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
    button: "border-[var(--border-cyan)] text-[var(--launcher-btn-ink)]",
    buttonStyle: {
      background: "var(--launcher-btn-cyan)",
      boxShadow: "var(--launcher-btn-shadow)",
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
    button: "border-[var(--border-amber)] text-[var(--launcher-btn-ink)]",
    buttonStyle: {
      background: "var(--launcher-btn-amber)",
      boxShadow: "var(--launcher-btn-shadow)",
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

export function LandingLauncher({ signal }: { signal: LauncherSignal | null }) {
  const t = useTranslations("landing");

  return (
    <div className="launcher-surface relative min-h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
      {/* The base fills the whole viewport at any width. Night-blue under the dark
          themes, pale under "Clair" — the gradient is a token now, so the theme
          class reaches it (it could not reach an inline style attribute). */}
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{ background: "var(--launcher-backdrop)" }}
      />
      {/* One continuous full-width wave band at the foot of the page. */}
      <LauncherWaves />
      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Unified header (docs/design/header-normative.md) — launcher variant:
            brand only at left, the global cluster (langue · thème · compte) at
            right, no contextual cluster. The launcher IS the plane chooser, so
            no PRODUIT/COCKPIT toggle. The DEMO label describes the environment;
            account access remains available independently. */}
        <AppHeader plan="launcher" auth="optional" />
        <main className="relative flex flex-1 flex-col items-center justify-start px-6 pt-[56px] pb-20 sm:pt-[80px] lg:pt-[104px]">
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
            <ControlPlaneCard t={t} />
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
  const showSocle = (live.evaluationBuckets?.review ?? 0) > 0;
  return (
    <div className="mt-8 flex w-full max-w-[1120px] flex-col items-center gap-[16px]">
      {/* One bounded band, four capability columns — compact, stacks on mobile,
          never four big cards. The freshness stamp rides on the two columns whose
          claim is temporal (supervise: "temps réel"; prove: "à tout instant").
          Desktop separators are inset gradient hairlines (fading at both ends) —
          a full-height rule cuts the band into boxes; a faded filet reads as one
          surface. Mobile keeps the plain stacked divide. */}
      <div className="flex w-full flex-col divide-y divide-[var(--border-subtle)] overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-panel)_55%,transparent)] backdrop-blur-[2px] lg:flex-row lg:divide-y-0">
        {pillars.map((pillar, index) => (
          <Fragment key={pillar.key}>
            {index > 0 ? (
              <span
                aria-hidden="true"
                className="my-[9px] hidden w-px shrink-0 self-stretch bg-gradient-to-b from-transparent via-[color-mix(in_srgb,var(--text-secondary)_30%,transparent)] to-transparent lg:block"
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
    <div className="mt-[18px] mb-[22px] flex flex-wrap gap-[8px] border-t border-[var(--border-subtle)] pt-[14px]">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-[6px] rounded-lg border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)] px-[10px] py-[5px] text-[12px] font-medium leading-none text-[var(--text-secondary)]"
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
        "relative flex h-full flex-col overflow-hidden rounded-xl border px-[28px] pb-[28px] pt-[28px] backdrop-blur-[2px]",
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
        {/* SECONDARY, at last. The card comment above has said "outline CTA" since ADR 0013
            and the code shipped a gold gradient — brown under "Clair". A neutral surface
            with a hairline is what a second action looks like, and it lets the cockpit CTA
            beside it actually read as the primary one. */}
        <Link
          href="/espaces"
          className={cn(
            "launcher-btn-secondary mt-auto flex h-[46px] items-center justify-center gap-[10px] rounded-lg border text-[14px] font-semibold leading-none tracking-[0.01em]",
            FOCUS,
          )}
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
function ControlPlaneCard({ t }: { t: T }) {
  const a = ACCENT.cyan;
  return (
    <section
      className={cn(
        "relative flex h-full flex-col overflow-hidden rounded-xl border px-[28px] pb-[28px] pt-[28px] backdrop-blur-[2px]",
        a.border,
      )}
      style={{ ...a.cardStyle, background: CARD_BG }}
    >
      <CardGlow />
      <div className="pointer-events-none absolute top-[24px] right-[22px] hidden scale-[0.74] opacity-[0.18] xl:block">
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
        <Link
          href="/surveiller/vue-ensemble"
          className={cn(
            "mt-auto flex h-[46px] items-center justify-center gap-[10px] rounded-lg border text-[14px] font-semibold leading-none tracking-[0.01em]",
            a.button,
            FOCUS,
          )}
          style={a.buttonStyle}
        >
          <Lock className="h-[15px] w-[15px]" />
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
      <div className="row-span-2 rounded-md border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] p-[14px]">
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
      <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] p-[12px]">
        <div className="flex items-center gap-[13px]">
          <div className="h-[49px] w-[49px] rounded-full border-[10px] border-[var(--border-subtle)] border-l-[var(--cyan)] border-t-[var(--cyan-soft)]" />
          <div className="flex flex-col gap-[9px]">
            <span className="h-[5px] w-[43px] rounded-full bg-[var(--border-subtle)]" />
            <span className="h-[5px] w-[32px] rounded-full bg-[var(--border-subtle)]" />
            <span className="h-[5px] w-[47px] rounded-full bg-[var(--border-subtle)]" />
          </div>
        </div>
      </div>
      <div className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-panel-soft)] p-[12px]">
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
