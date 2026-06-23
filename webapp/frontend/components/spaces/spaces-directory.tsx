"use client";

import { ArrowRight, Boxes, HandCoins, Lock, LogIn, UserRound, UsersRound } from "lucide-react";
import { signIn } from "next-auth/react";
import type { CSSProperties } from "react";
import { useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

// Demo-mode seeded credentials for a guarded surface (off in prod → undefined).
export interface SurfaceDemo {
  username: string;
  password: string;
  label: string;
}

export interface SurfaceView {
  key: string;
  href: string;
  name: string;
  desc: string;
  authRequired: boolean;
  authNote: string;
  // Public-safe health (ADR 0009): release verdict tone + label of the surface's
  // backing agent(s) — never a per-failure category, never an agent list.
  healthTone: "good" | "warn" | "crit" | "unknown";
  healthLabel: string;
  demo: SurfaceDemo | null;
}

export interface SurfaceGroup {
  key: "external" | "internal";
  label: string;
  desc: string;
  surfaces: SurfaceView[];
}

export interface DirectoryLabels {
  authRequired: string;
  open: string;
}

const CARD_BG =
  "linear-gradient(145deg, var(--panel) 0%, var(--panel-soft) 56%, rgba(2,8,23,0.94) 100%)";

type Accent = "gold" | "amber";

const ACCENT: Record<
  Accent,
  { border: string; emblem: string; pill: string; buttonStyle: CSSProperties; shadow: string }
> = {
  gold: {
    border: "border-[var(--border-gold)]",
    emblem: "text-[var(--gold-strong)]",
    pill: "text-[var(--gold-strong)]",
    buttonStyle: {
      background:
        "linear-gradient(180deg, rgba(214,182,106,0.30), rgba(88,62,24,0.78) 58%, rgba(42,31,18,0.92))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
    },
    shadow: "0 10px 30px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04)",
  },
  amber: {
    border: "border-[var(--border-amber)]",
    emblem: "text-[var(--amber-soft)]",
    pill: "text-[var(--amber-soft)]",
    buttonStyle: {
      background:
        "linear-gradient(180deg, rgba(245,158,11,0.24), rgba(120,72,12,0.72) 55%, rgba(60,38,8,0.92))",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
    },
    shadow: "0 10px 30px rgba(0,0,0,0.32), inset 0 1px 0 rgba(255,255,255,0.04)",
  },
};

const HEALTH: Record<SurfaceView["healthTone"], string> = {
  good: "var(--success)",
  warn: "var(--amber)",
  crit: "#F87171",
  unknown: "var(--text-secondary)",
};

const SURFACE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  client: UserRound,
  recouvrement: HandCoins,
};

const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--text-primary)_72%,transparent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-app)]";

function CardGlow() {
  return (
    <div
      className="pointer-events-none absolute inset-0"
      style={{
        background:
          "radial-gradient(circle at 82% 6%, rgba(248,250,252,0.035), transparent 34%), linear-gradient(180deg, rgba(255,255,255,0.014), transparent 30%)",
      }}
    />
  );
}

function tone(color: string, fill: number, border: number): CSSProperties {
  return {
    color,
    borderColor: `color-mix(in srgb, ${color} ${border}%, transparent)`,
    background: `color-mix(in srgb, ${color} ${fill}%, transparent)`,
  };
}

// 1-click seeded-account login (demo mode only): opens a REAL next-auth session
// then navigates — it satisfies the guard by logging in, never a bypass.
function DemoEnter({ surface, accent }: { surface: SurfaceView; accent: Accent }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const demo = surface.demo;
  if (!demo) return null;
  async function enter() {
    if (!demo) return;
    setPending(true);
    const res = await signIn("credentials", {
      username: demo.username,
      password: demo.password,
      redirect: false,
    });
    if (res && !res.error) {
      router.push(surface.href);
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
        "flex h-[42px] w-full items-center justify-center gap-[9px] rounded-[12px] border text-[13px] font-semibold leading-none text-[var(--text-primary)] transition-[filter] hover:enabled:brightness-110 disabled:opacity-70 md:w-[188px]",
        ACCENT[accent].border,
        FOCUS,
      )}
      style={ACCENT[accent].buttonStyle}
    >
      <LogIn className="h-[16px] w-[16px]" />
      {demo.label}
    </button>
  );
}

function SurfaceCard({ surface, labels }: { surface: SurfaceView; labels: DirectoryLabels }) {
  const accent: Accent = surface.authRequired ? "amber" : "gold";
  const a = ACCENT[accent];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const hc = HEALTH[surface.healthTone];
  const strip =
    accent === "amber"
      ? "linear-gradient(90deg, transparent, rgba(245,158,11,0.55), transparent)"
      : "linear-gradient(90deg, transparent, rgba(214,182,106,0.55), transparent)";
  return (
    <article
      className={cn(
        "relative flex flex-col gap-[18px] overflow-hidden rounded-[var(--radius-lg)] border px-[24px] py-[22px] backdrop-blur-[2px] md:flex-row md:items-center md:gap-[22px]",
        a.border,
      )}
      style={{ background: CARD_BG, boxShadow: a.shadow }}
    >
      <CardGlow />
      {/* Accent strip — a quiet premium cue of the surface's audience. */}
      <span
        className="pointer-events-none absolute inset-x-0 top-0 h-[2px]"
        style={{ background: strip }}
        aria-hidden="true"
      />
      {/* Emblem */}
      <span
        className={cn(
          "relative grid h-[56px] w-[56px] shrink-0 place-items-center rounded-[16px] border",
          a.border,
          a.emblem,
        )}
        style={{ background: "color-mix(in srgb, var(--bg-app) 45%, transparent)" }}
      >
        <Icon className="h-[26px] w-[26px]" />
      </span>

      {/* Identity + description */}
      <div className="relative min-w-0 flex-1">
        <span className="block text-[16px] font-semibold leading-none text-[var(--text-primary)]">
          {surface.name}
        </span>
        <p className="mt-[10px] max-w-[480px] text-[12.5px] leading-[1.5] text-[var(--text-secondary)]">
          {surface.desc}
        </p>
        {surface.authRequired ? (
          <span
            className={cn(
              "mt-[10px] inline-flex items-center gap-[5px] text-[11px] font-medium",
              a.pill,
            )}
          >
            <Lock className="h-[12px] w-[12px]" />
            {surface.demo ? surface.authNote : labels.authRequired}
          </span>
        ) : null}
      </div>

      {/* Status + action (right rail) — the public-safe verdict over the CTA.
          1-click demo login on a guarded surface, else a plain link. */}
      <div className="relative flex shrink-0 flex-col gap-[12px] md:items-end">
        <span
          className="inline-flex items-center gap-[6px] self-start rounded-full border px-[10px] py-[3px] text-[11px] font-medium md:self-end"
          style={tone(hc, 12, 42)}
        >
          <span
            className="h-[6px] w-[6px] rounded-full"
            style={{ background: hc }}
            aria-hidden="true"
          />
          {surface.healthLabel}
        </span>
        {surface.demo ? (
          <DemoEnter surface={surface} accent={accent} />
        ) : (
          <Link
            href={surface.href}
            className={cn(
              "flex h-[42px] w-full items-center justify-center gap-[9px] rounded-[12px] border text-[13px] font-semibold leading-none text-[var(--text-primary)] transition-[filter] hover:brightness-110 md:w-[170px]",
              a.border,
              FOCUS,
            )}
            style={a.buttonStyle}
          >
            {labels.open}
            <ArrowRight className="h-[16px] w-[16px] stroke-[1.8]" />
          </Link>
        )}
      </div>
    </article>
  );
}

// Directory of business SURFACES grouped by audience (external / internal) —
// symmetric to the Flotte agent directory (list → surface). It lists SURFACES,
// never agents. Built to scale: more internal consoles drop into their group.
export function SpacesDirectory({
  groups,
  labels,
}: { groups: SurfaceGroup[]; labels: DirectoryLabels }) {
  return (
    <div className="flex w-full max-w-[1040px] flex-col gap-[30px]">
      {groups.map((group) => {
        const GroupIcon = group.key === "internal" ? Boxes : UsersRound;
        const groupColor = group.key === "internal" ? "var(--amber-soft)" : "var(--gold-strong)";
        return (
          <section key={group.key} className="flex flex-col gap-[14px]">
            <div className="flex items-center gap-[12px]">
              <span
                className="grid h-[26px] w-[26px] place-items-center rounded-[8px] border"
                style={{ ...tone(groupColor, 10, 38) }}
              >
                <GroupIcon className="h-[14px] w-[14px]" aria-hidden="true" />
              </span>
              <h2
                className="text-[12px] font-semibold uppercase tracking-[0.16em]"
                style={{ color: groupColor }}
              >
                {group.label}
              </h2>
              <span
                className="rounded-full border px-[7px] py-[1px] text-[10px] font-semibold tabular-nums"
                style={{ ...tone(groupColor, 10, 38) }}
              >
                {group.surfaces.length}
              </span>
              <span className="text-[12px] text-[var(--text-secondary)]">{group.desc}</span>
              <span
                className="ml-[4px] h-px flex-1"
                style={{ background: "var(--border-subtle)" }}
                aria-hidden="true"
              />
            </div>
            <div className="grid grid-cols-1 gap-[16px]">
              {group.surfaces.map((surface) => (
                <SurfaceCard key={surface.key} surface={surface} labels={labels} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
