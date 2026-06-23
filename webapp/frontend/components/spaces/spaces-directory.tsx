"use client";

import { Boxes, ChevronRight, HandCoins, Lock, Search, UserRound, UsersRound } from "lucide-react";
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

type Accent = "gold" | "amber";
type Filter = "all" | "external" | "internal";

const ACCENT: Record<Accent, { border: string; icon: string; pill: CSSProperties; hover: string }> =
  {
    gold: {
      border: "border-[var(--border-gold)]",
      icon: "text-[var(--gold-strong)]",
      pill: {
        color: "var(--gold-strong)",
        borderColor: "color-mix(in srgb, var(--gold-strong) 38%, transparent)",
        background: "color-mix(in srgb, var(--gold-strong) 10%, transparent)",
      },
      hover: "hover:border-[color-mix(in_srgb,var(--gold-strong)_45%,transparent)]",
    },
    amber: {
      border: "border-[var(--border-amber)]",
      icon: "text-[var(--amber-soft)]",
      pill: {
        color: "var(--amber-soft)",
        borderColor: "color-mix(in srgb, var(--amber-soft) 38%, transparent)",
        background: "color-mix(in srgb, var(--amber-soft) 10%, transparent)",
      },
      hover: "hover:border-[color-mix(in_srgb,var(--amber-soft)_45%,transparent)]",
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

const ROW =
  "group/row relative flex w-full items-center gap-[16px] rounded-[16px] border bg-[color-mix(in_srgb,var(--bg-panel)_42%,transparent)] px-[18px] py-[14px] text-left transition-colors";

function RowInner({
  surface,
  accent,
  audienceLabel,
  actionLabel,
}: {
  surface: SurfaceView;
  accent: Accent;
  audienceLabel: string;
  actionLabel: string;
}) {
  const a = ACCENT[accent];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const hc = HEALTH[surface.healthTone];
  return (
    <>
      <span
        className={cn(
          "grid h-[44px] w-[44px] shrink-0 place-items-center rounded-[12px] border",
          a.border,
          a.icon,
        )}
        style={{ background: "color-mix(in srgb, var(--bg-app) 45%, transparent)" }}
      >
        <Icon className="h-[21px] w-[21px]" />
      </span>

      <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
        <span className="flex flex-wrap items-center gap-[8px]">
          <span className="text-[14px] font-semibold leading-none text-[var(--text-primary)]">
            {surface.name}
          </span>
          <span
            className="rounded-full border px-[8px] py-[2px] text-[10px] font-semibold uppercase tracking-[0.08em]"
            style={a.pill}
          >
            {audienceLabel}
          </span>
          {surface.authRequired ? (
            <span
              className="inline-flex items-center gap-[4px] text-[10px] font-medium"
              style={{ color: a.pill.color }}
            >
              <Lock className="h-[10px] w-[10px]" />
              {surface.authNote}
            </span>
          ) : null}
        </span>
        <span className="truncate text-[12px] leading-[1.4] text-[var(--text-secondary)]">
          {surface.desc}
        </span>
      </span>

      {/* Public-safe verdict — dot + label, never a failure category. */}
      <span
        className="hidden shrink-0 items-center gap-[6px] rounded-full border px-[10px] py-[3px] text-[11px] font-medium md:inline-flex"
        style={{
          color: hc,
          borderColor: `color-mix(in srgb, ${hc} 42%, transparent)`,
          background: `color-mix(in srgb, ${hc} 12%, transparent)`,
        }}
      >
        <span
          className="h-[6px] w-[6px] rounded-full"
          style={{ background: hc }}
          aria-hidden="true"
        />
        {surface.healthLabel}
      </span>

      <span className="flex shrink-0 items-center gap-[6px] text-[12px] font-semibold text-[var(--text-primary)]">
        {actionLabel}
        <ChevronRight className="h-[15px] w-[15px] text-[var(--text-secondary)] transition-transform group-hover/row:translate-x-[2px] group-hover/row:text-[var(--text-primary)]" />
      </span>
    </>
  );
}

// One premium surface ROW. The whole row is the affordance: a guarded surface in
// demo mode does a 1-click real seeded login then navigates (never a bypass);
// otherwise it is a plain link (which hits the layout RBAC guard if
// unauthenticated). The action label reads "Ouvrir" / "Entrer en démo".
function SurfaceRow({ surface, group }: { surface: SurfaceView; group: SurfaceGroup["key"] }) {
  const t = useTranslations("spaces");
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const accent: Accent = group === "internal" ? "amber" : "gold";
  const a = ACCENT[accent];
  const audienceLabel = group === "internal" ? t("groupInternal") : t("groupExternal");
  const demo = surface.demo;

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
        className={cn(ROW, a.border, a.hover, FOCUS, "disabled:opacity-70")}
      >
        <RowInner
          surface={surface}
          accent={accent}
          audienceLabel={audienceLabel}
          actionLabel={demo.label}
        />
      </button>
    );
  }
  return (
    <Link href={surface.href} className={cn(ROW, a.border, a.hover, FOCUS)}>
      <RowInner
        surface={surface}
        accent={accent}
        audienceLabel={audienceLabel}
        actionLabel={t("open")}
      />
    </Link>
  );
}

// Directory of business SURFACES grouped by audience — search + audience filters
// (with real counters) + premium rows. It lists SURFACES, never agents; the
// shape echoes the Flotte agent directory but is NOT linked to it (ADR 0013).
export function SpacesDirectory({ groups }: { groups: SurfaceGroup[] }) {
  const t = useTranslations("spaces");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(() => {
    const ext = groups.find((g) => g.key === "external")?.surfaces.length ?? 0;
    const int = groups.find((g) => g.key === "internal")?.surfaces.length ?? 0;
    return { all: ext + int, external: ext, internal: int };
  }, [groups]);

  const q = query.trim().toLowerCase();
  const shown = groups
    .filter((g) => filter === "all" || g.key === filter)
    .map((g) => ({
      ...g,
      surfaces: q
        ? g.surfaces.filter(
            (s) => s.name.toLowerCase().includes(q) || s.desc.toLowerCase().includes(q),
          )
        : g.surfaces,
    }))
    .filter((g) => g.surfaces.length > 0);

  const FILTERS: Array<{ key: Filter; label: string; count: number }> = [
    { key: "all", label: t("filterAll"), count: counts.all },
    { key: "external", label: t("filterExternal"), count: counts.external },
    { key: "internal", label: t("filterInternal"), count: counts.internal },
  ];

  return (
    <div className="flex w-full max-w-[1040px] flex-col gap-[22px]">
      {/* Toolbar — search + audience filters with real counters. */}
      <div className="flex flex-wrap items-center gap-[10px]">
        <div className="relative min-w-[220px] flex-1">
          <Search className="-translate-y-1/2 absolute top-1/2 left-[12px] h-[15px] w-[15px] text-[var(--text-secondary)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className={cn(
              "h-[40px] w-full rounded-[12px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_60%,transparent)] pr-[14px] pl-[36px] text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-secondary)] focus:border-[color-mix(in_srgb,var(--text-primary)_30%,transparent)]",
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
                "inline-flex items-center gap-[7px] rounded-full border px-[14px] py-[8px] text-[12px] font-medium transition-colors",
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
        <p className="rounded-[16px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-panel)_42%,transparent)] px-[18px] py-[20px] text-center text-[13px] text-[var(--text-secondary)]">
          {t("noMatch")}
        </p>
      ) : (
        shown.map((group) => {
          const GroupIcon = group.key === "internal" ? Boxes : UsersRound;
          const groupColor = group.key === "internal" ? "var(--amber-soft)" : "var(--gold-strong)";
          return (
            <section key={group.key} className="flex flex-col gap-[12px]">
              <div className="flex items-center gap-[12px]">
                <span
                  className="grid h-[26px] w-[26px] place-items-center rounded-[8px] border"
                  style={{
                    color: groupColor,
                    borderColor: `color-mix(in srgb, ${groupColor} 38%, transparent)`,
                    background: `color-mix(in srgb, ${groupColor} 10%, transparent)`,
                  }}
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
                  style={{
                    color: groupColor,
                    borderColor: `color-mix(in srgb, ${groupColor} 38%, transparent)`,
                    background: `color-mix(in srgb, ${groupColor} 10%, transparent)`,
                  }}
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
              <div className="flex flex-col gap-[10px]">
                {group.surfaces.map((surface) => (
                  <SurfaceRow key={surface.key} surface={surface} group={group.key} />
                ))}
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}
