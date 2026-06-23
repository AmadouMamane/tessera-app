"use client";

import { Boxes, HandCoins, Lock, Search, UserRound } from "lucide-react";
import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import type { CSSProperties } from "react";
import { useMemo, useState } from "react";

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

type Audience = "external" | "internal";
type Filter = "all" | Audience;
type FlatSurface = SurfaceView & { audience: Audience };

const CARD_BG =
  "linear-gradient(160deg, var(--panel) 0%, var(--panel-soft) 60%, rgba(2,8,23,0.94) 100%)";

const ACCENT: Record<Audience, { border: string; icon: string; dot: string; iconBg: string }> = {
  external: {
    border: "border-[var(--border-gold)]",
    icon: "text-[var(--gold-strong)]",
    dot: "var(--gold-strong)",
    iconBg:
      "linear-gradient(150deg, color-mix(in srgb, var(--gold-strong) 26%, transparent), color-mix(in srgb, var(--gold-strong) 6%, transparent))",
  },
  internal: {
    border: "border-[var(--border-amber)]",
    icon: "text-[var(--amber-soft)]",
    dot: "var(--amber-soft)",
    iconBg:
      "linear-gradient(150deg, color-mix(in srgb, var(--amber-soft) 26%, transparent), color-mix(in srgb, var(--amber-soft) 6%, transparent))",
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

const CARD =
  "group/card relative flex min-h-[188px] flex-col items-center justify-center gap-[14px] overflow-hidden rounded-[20px] border px-[18px] py-[22px] text-center transition-[border-color,transform] hover:-translate-y-[2px]";

function CardInner({
  surface,
  audience,
  audienceLabel,
  actionLabel,
}: {
  surface: SurfaceView;
  audience: Audience;
  audienceLabel: string;
  actionLabel: string;
}) {
  const a = ACCENT[audience];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const hc = HEALTH[surface.healthTone];
  return (
    <>
      {/* Discreet corner: guard + public verdict dot — honest, never a category. */}
      <span className="absolute top-[12px] right-[12px] flex items-center gap-[7px]">
        {surface.authRequired ? (
          <Lock className="h-[12px] w-[12px] text-[var(--text-secondary)]" aria-hidden="true" />
        ) : null}
        <span
          className="h-[8px] w-[8px] rounded-full"
          style={{ background: hc }}
          title={surface.healthLabel}
          aria-label={surface.healthLabel}
        />
      </span>

      <span
        className={cn(
          "grid h-[60px] w-[60px] place-items-center rounded-[18px] border",
          a.border,
          a.icon,
        )}
        style={{ background: a.iconBg }}
      >
        <Icon className="h-[28px] w-[28px]" />
      </span>

      <span className="flex flex-col items-center gap-[8px]">
        <span className="text-[15px] font-semibold leading-none text-[var(--text-primary)]">
          {surface.name}
        </span>
        <span className="inline-flex items-center gap-[6px] text-[12px] text-[var(--text-secondary)]">
          <span
            className="h-[6px] w-[6px] rounded-full"
            style={{ background: a.dot }}
            aria-hidden="true"
          />
          {audienceLabel}
        </span>
      </span>

      {/* Action revealed on hover — keeps the card clean by default. */}
      <span className="absolute inset-x-0 bottom-[12px] text-[11px] font-medium text-[var(--text-secondary)] opacity-0 transition-opacity group-hover/card:opacity-100">
        {actionLabel} →
      </span>
    </>
  );
}

// One premium surface CARD. The whole card is the affordance: a guarded surface in
// demo mode does a 1-click real seeded login then navigates (never a bypass);
// otherwise a plain link (which hits the layout RBAC guard if unauthenticated).
function SurfaceCard({ surface }: { surface: FlatSurface }) {
  const t = useTranslations("spaces");
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const a = ACCENT[surface.audience];
  const audienceLabel = surface.audience === "internal" ? t("groupInternal") : t("groupExternal");
  const demo = surface.demo;

  const style: CSSProperties = { background: CARD_BG };
  if (demo) {
    const enter = async () => {
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
    };
    return (
      <button
        type="button"
        onClick={enter}
        disabled={pending}
        className={cn(CARD, a.border, FOCUS, "disabled:opacity-70")}
        style={style}
      >
        <CardInner
          surface={surface}
          audience={surface.audience}
          audienceLabel={audienceLabel}
          actionLabel={demo.label}
        />
      </button>
    );
  }
  return (
    <Link href={surface.href} className={cn(CARD, a.border, FOCUS)} style={style}>
      <CardInner
        surface={surface}
        audience={surface.audience}
        audienceLabel={audienceLabel}
        actionLabel={t("open")}
      />
    </Link>
  );
}

// Directory of business SURFACES — search + audience filters (real counters) + a
// grid of premium cards. It lists SURFACES, never agents; the shape echoes the
// Flotte agent directory but is NOT linked to it (ADR 0013).
export function SpacesDirectory({ groups }: { groups: SurfaceGroup[] }) {
  const t = useTranslations("spaces");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const all = useMemo<FlatSurface[]>(
    () => groups.flatMap((g) => g.surfaces.map((s) => ({ ...s, audience: g.key }))),
    [groups],
  );
  const counts = useMemo(
    () => ({
      all: all.length,
      external: all.filter((s) => s.audience === "external").length,
      internal: all.filter((s) => s.audience === "internal").length,
    }),
    [all],
  );

  const q = query.trim().toLowerCase();
  const shown = all.filter((s) => {
    if (filter !== "all" && s.audience !== filter) return false;
    if (q && !(s.name.toLowerCase().includes(q) || s.desc.toLowerCase().includes(q))) return false;
    return true;
  });

  const FILTERS: Array<{ key: Filter; label: string; count: number }> = [
    { key: "all", label: t("filterAll"), count: counts.all },
    { key: "external", label: t("filterExternal"), count: counts.external },
    { key: "internal", label: t("filterInternal"), count: counts.internal },
  ];

  return (
    <div className="flex w-full max-w-[1040px] flex-col gap-[20px]">
      {/* Toolbar — search + audience filters with real counters. */}
      <div className="flex flex-wrap items-center gap-[10px]">
        <div className="relative min-w-[220px] flex-1">
          <Search className="-translate-y-1/2 absolute top-1/2 left-[12px] h-[15px] w-[15px] text-[var(--text-secondary)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className={cn(
              "h-[42px] w-full rounded-[12px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_60%,transparent)] pr-[14px] pl-[36px] text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-secondary)] focus:border-[color-mix(in_srgb,var(--text-primary)_30%,transparent)]",
              FOCUS,
            )}
          />
        </div>
        <div className="flex flex-wrap gap-[8px]">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={cn(
                "inline-flex items-center gap-[7px] rounded-full border px-[14px] py-[9px] text-[12px] font-medium transition-colors",
                FOCUS,
                filter === f.key
                  ? "border-[color-mix(in_srgb,var(--text-primary)_28%,transparent)] bg-[color-mix(in_srgb,var(--text-primary)_8%,transparent)] text-[var(--text-primary)]"
                  : "border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
              )}
            >
              {f.label}
              <span className="rounded-full bg-[color-mix(in_srgb,var(--text-primary)_10%,transparent)] px-[7px] text-[10px] tabular-nums">
                {f.count}
              </span>
            </button>
          ))}
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="rounded-[18px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-panel)_42%,transparent)] px-[18px] py-[24px] text-center text-[13px] text-[var(--text-secondary)]">
          {t("noMatch")}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-[16px] sm:grid-cols-3 lg:grid-cols-4">
          {shown.map((surface) => (
            <SurfaceCard key={surface.key} surface={surface} />
          ))}
        </div>
      )}
    </div>
  );
}
