"use client";

import { ArrowRight, Boxes, Lock, LogIn, UsersRound } from "lucide-react";
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

const HEALTH_DOT: Record<SurfaceView["healthTone"], string> = {
  good: "var(--success)",
  warn: "var(--amber)",
  crit: "#F87171",
  unknown: "var(--text-secondary)",
};

const GROUP_ICON = { external: UsersRound, internal: Boxes } as const;

// 1-click seeded-account login (demo mode only): opens a REAL next-auth session
// then navigates — it satisfies the guard by logging in, never a bypass.
function DemoEnter({ surface }: { surface: SurfaceView }) {
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
      className="flex h-[42px] items-center justify-center gap-[9px] rounded-[12px] border border-[var(--border-amber)] text-[13px] font-semibold leading-none text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--text-primary)_72%,transparent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-app)] disabled:opacity-70"
      style={{
        background:
          "linear-gradient(180deg, rgba(245,158,11,0.24), rgba(120,72,12,0.72) 55%, rgba(60,38,8,0.92))",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
      }}
    >
      <LogIn className="h-[16px] w-[16px]" />
      {demo.label}
    </button>
  );
}

function SurfaceCard({ surface, labels }: { surface: SurfaceView; labels: DirectoryLabels }) {
  const external = !surface.authRequired;
  const accentBorder = external ? "border-[var(--border-gold)]" : "border-[var(--border-amber)]";
  const accentTone = external ? "text-[var(--gold-strong)]" : "text-[var(--amber-soft)]";
  return (
    <div
      className={cn(
        "flex flex-col gap-[12px] rounded-[16px] border bg-[color-mix(in_srgb,var(--bg-panel)_55%,transparent)] p-[18px]",
        accentBorder,
      )}
    >
      <div className="flex items-start justify-between gap-[10px]">
        <span className="text-[15px] font-semibold text-[var(--text-primary)]">{surface.name}</span>
        {/* Public-safe health: verdict tone + label, never a failure category. */}
        <span className="inline-flex shrink-0 items-center gap-[6px] text-[11px] text-[var(--text-secondary)]">
          <span
            className="h-[8px] w-[8px] rounded-full"
            style={{ background: HEALTH_DOT[surface.healthTone] }}
            aria-hidden="true"
          />
          {surface.healthLabel}
        </span>
      </div>
      <p className="text-[12px] leading-[1.45] text-[var(--text-secondary)]">{surface.desc}</p>
      {surface.authRequired ? (
        <span
          className={cn("inline-flex items-center gap-[5px] text-[11px] font-medium", accentTone)}
        >
          <Lock className="h-[12px] w-[12px]" />
          {surface.demo ? surface.authNote : labels.authRequired}
        </span>
      ) : null}
      {/* Guarded surface in demo mode → 1-click real login; otherwise a plain link
          (which hits the layout guard if unauthenticated — never a bypass). */}
      {surface.demo ? (
        <DemoEnter surface={surface} />
      ) : (
        <Link
          href={surface.href}
          className={cn(
            "flex h-[42px] items-center justify-center gap-[9px] rounded-[12px] border text-[13px] font-semibold leading-none text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--text-primary)_72%,transparent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-app)]",
            accentBorder,
          )}
          style={
            external
              ? ({
                  background:
                    "linear-gradient(180deg, rgba(214,182,106,0.30), rgba(88,62,24,0.78) 58%, rgba(42,31,18,0.92))",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
                } as CSSProperties)
              : ({
                  background:
                    "linear-gradient(180deg, rgba(245,158,11,0.24), rgba(120,72,12,0.72) 55%, rgba(60,38,8,0.92))",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 18px rgba(0,0,0,0.18)",
                } as CSSProperties)
          }
        >
          {labels.open}
          <ArrowRight className="h-[16px] w-[16px] stroke-[1.8]" />
        </Link>
      )}
    </div>
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
    <div className="flex w-full max-w-[1040px] flex-col gap-[28px]">
      {groups.map((group) => {
        const GroupIcon = group.key === "internal" ? GROUP_ICON.internal : GROUP_ICON.external;
        return (
          <section key={group.key} className="flex flex-col gap-[14px]">
            <div className="flex items-center gap-[10px]">
              <GroupIcon
                className="h-[16px] w-[16px] text-[var(--text-secondary)]"
                aria-hidden="true"
              />
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[var(--text-primary)]">
                {group.label}
              </h2>
              <span className="text-[12px] text-[var(--text-secondary)]">· {group.desc}</span>
            </div>
            <div className="grid grid-cols-1 gap-[14px] sm:grid-cols-2">
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
