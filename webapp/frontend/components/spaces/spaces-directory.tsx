"use client";

import {
  Boxes,
  ChevronRight,
  HandCoins,
  LayoutGrid,
  List,
  Lock,
  Search,
  Star,
  UserRound,
} from "lucide-react";
import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

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
  // The ACCESS facet (ADR 0013 amended): a business surface advertises its
  // ACCESS/availability — open to anyone, or sign-in required — NOT the backing
  // agent's eval-gate release verdict (that is control-plane: Flotte / Vue
  // d'ensemble). `authRequired` drives the access chip + CTA.
  authRequired: boolean;
  authNote: string;
  demo: SurfaceDemo | null;
  // False when the CURRENT authenticated role cannot enter this surface (e.g. a
  // `collections` session and the customer product). The card is then shown inert
  // instead of a link that would bounce to the role's own landing (ADR 0013). For
  // an anonymous session this is always true — the auth/demo affordance handles it.
  accessible: boolean;
}

export interface SurfaceGroup {
  key: "external" | "internal";
  label: string;
  desc: string;
  surfaces: SurfaceView[];
}

type Audience = "external" | "internal";
type Filter = "all" | Audience | "favorites";
type ViewMode = "grid" | "list";
type Sort = "az" | "za";
type FlatSurface = SurfaceView & { audience: Audience };

const FAV_KEY = "tessera.spaces.favorites";
const VIEW_KEY = "tessera.spaces.view";

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
    border: "border-[var(--border-cyan)]",
    icon: "text-[var(--cyan)]",
    dot: "var(--cyan)",
    iconBg:
      "linear-gradient(150deg, color-mix(in srgb, var(--cyan) 26%, transparent), color-mix(in srgb, var(--cyan) 6%, transparent))",
  },
};

const SURFACE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  client: UserRound,
  recouvrement: HandCoins,
};

const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--text-primary)_72%,transparent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-app)]";

function readFavorites(): string[] {
  try {
    const raw = localStorage.getItem(FAV_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function FavStar({ on, onToggle, label }: { on: boolean; onToggle: () => void; label: string }) {
  return (
    // A real <button> would nest an interactive inside the card's stretched action
    // button (invalid HTML); a role=button span with keyboard handlers overlays it.
    // biome-ignore lint/a11y/useSemanticElements: intentional overlay control, see above
    <span
      role="button"
      tabIndex={0}
      aria-label={label}
      aria-pressed={on}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onToggle();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          e.stopPropagation();
          onToggle();
        }
      }}
      className={cn(
        "grid h-[24px] w-[24px] cursor-pointer place-items-center rounded-[7px] text-[var(--text-secondary)] transition-colors hover:text-[var(--gold-strong)]",
        FOCUS,
      )}
    >
      <Star
        className={cn(
          "h-[14px] w-[14px]",
          on && "fill-[var(--gold-strong)] text-[var(--gold-strong)]",
        )}
      />
    </span>
  );
}

function SurfaceCard({
  surface,
  favorite,
  onToggleFavorite,
}: { surface: FlatSurface; favorite: boolean; onToggleFavorite: () => void }) {
  const t = useTranslations("spaces");
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const a = ACCENT[surface.audience];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const audienceLabel = surface.audience === "internal" ? t("groupInternal") : t("groupExternal");
  const demo = surface.demo;
  const actionLabel = demo ? demo.label : t("open");

  const enter = async () => {
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
  };

  const actionAria = `${surface.name} — ${actionLabel}`;
  const locked = !surface.accessible;
  return (
    <div
      aria-disabled={locked || undefined}
      className={cn(
        // pt clears the top-right access chip / fav star; box-shadow (not transform)
        // on hover so cards don't jitter as they pass under the cursor while scrolling.
        "group/card relative flex min-h-[200px] flex-col items-center justify-center gap-[14px] overflow-hidden rounded-[20px] border px-[18px] pb-[22px] pt-[42px] text-center transition-[border-color,box-shadow]",
        a.border,
        locked ? "cursor-not-allowed opacity-55" : "hover:shadow-[0_12px_28px_rgba(0,0,0,0.34)]",
        pending && "opacity-70",
      )}
      style={{ background: CARD_BG }}
    >
      {/* Stretched action covers the whole card (no nested interactives). Inert
          when the current role can't enter — no link that would bounce away. */}
      {locked ? null : demo ? (
        <button
          type="button"
          onClick={enter}
          disabled={pending}
          aria-label={actionAria}
          className={cn("absolute inset-0 rounded-[20px]", FOCUS)}
        />
      ) : (
        <Link
          href={surface.href}
          aria-label={actionAria}
          className={cn("absolute inset-0 rounded-[20px]", FOCUS)}
        />
      )}

      {/* Favourite star — sibling above the action, independently clickable. */}
      <span className="absolute top-[12px] left-[12px] z-[2]">
        <FavStar
          on={favorite}
          onToggle={onToggleFavorite}
          label={t(favorite ? "unfavorite" : "favorite")}
        />
      </span>
      {/* ACCESS facet (ADR 0013 amended) — gated surfaces advertise "Connexion
          requise"; open surfaces carry no chip (the "Ouvrir" CTA below says it). */}
      {surface.authRequired ? (
        <span
          className="pointer-events-none absolute top-[12px] right-[12px] z-[2] inline-flex items-center gap-[5px] rounded-full border px-[8px] py-[3px] text-[10px] font-medium"
          style={{
            // Access STATE, not an audience accent — kept neutral slate so it
            // never reads in the warm gold/amber family (Externe + Démonstration).
            color: "var(--text-secondary)",
            borderColor: "color-mix(in srgb, var(--text-primary) 20%, transparent)",
            background: "color-mix(in srgb, var(--text-primary) 7%, transparent)",
          }}
        >
          <Lock className="h-[10px] w-[10px]" aria-hidden="true" />
          {t("authRequired")}
        </span>
      ) : null}

      {/* Visual content — clicks pass through to the stretched action. */}
      <span className="pointer-events-none relative flex flex-col items-center gap-[14px]">
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
      </span>
      {locked ? (
        <span className="pointer-events-none absolute inset-x-0 bottom-[12px] flex items-center justify-center gap-[5px] text-[11px] font-medium text-[var(--text-secondary)]">
          <Lock className="h-[11px] w-[11px]" aria-hidden="true" />
          {t("roleLocked")}
        </span>
      ) : (
        <span className="pointer-events-none absolute inset-x-0 bottom-[12px] text-[11px] font-medium text-[var(--text-secondary)] transition-colors group-hover/card:text-[var(--text-primary)]">
          {actionLabel} →
        </span>
      )}
    </div>
  );
}

function SurfaceRow({
  surface,
  favorite,
  onToggleFavorite,
}: { surface: FlatSurface; favorite: boolean; onToggleFavorite: () => void }) {
  const t = useTranslations("spaces");
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const a = ACCENT[surface.audience];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const audienceLabel = surface.audience === "internal" ? t("groupInternal") : t("groupExternal");
  const demo = surface.demo;

  const enter = async () => {
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
  };

  const actionLabel = demo ? demo.label : t("open");
  const actionAria = `${surface.name} — ${actionLabel}`;
  const locked = !surface.accessible;
  return (
    <div
      aria-disabled={locked || undefined}
      className={cn(
        "group/row relative flex w-full items-center gap-[16px] rounded-[16px] border bg-[color-mix(in_srgb,var(--bg-panel)_42%,transparent)] px-[18px] py-[14px] text-left transition-[border-color]",
        a.border,
        locked && "cursor-not-allowed opacity-55",
        pending && "opacity-70",
      )}
    >
      {locked ? null : demo ? (
        <button
          type="button"
          onClick={enter}
          disabled={pending}
          aria-label={actionAria}
          className={cn("absolute inset-0 rounded-[16px]", FOCUS)}
        />
      ) : (
        <Link
          href={surface.href}
          aria-label={actionAria}
          className={cn("absolute inset-0 rounded-[16px]", FOCUS)}
        />
      )}

      <span
        className={cn(
          "pointer-events-none grid h-[44px] w-[44px] shrink-0 place-items-center rounded-[12px] border",
          a.border,
          a.icon,
        )}
        style={{ background: a.iconBg }}
      >
        <Icon className="h-[21px] w-[21px]" />
      </span>
      <span className="pointer-events-none flex min-w-0 flex-1 flex-col gap-[3px]">
        <span className="flex items-center gap-[8px]">
          <span className="text-[14px] font-semibold leading-none text-[var(--text-primary)]">
            {surface.name}
          </span>
          <span className="inline-flex items-center gap-[5px] text-[11px] text-[var(--text-secondary)]">
            <span
              className="h-[6px] w-[6px] rounded-full"
              style={{ background: a.dot }}
              aria-hidden="true"
            />
            {audienceLabel}
          </span>
        </span>
        <span className="truncate text-[12px] leading-[1.4] text-[var(--text-secondary)]">
          {surface.desc}
        </span>
      </span>
      {/* ACCESS facet (ADR 0013 amended) — gated surfaces advertise "Connexion
          requise"; open surfaces carry no chip (the "Ouvrir" action says it). */}
      {surface.authRequired ? (
        <span
          className="pointer-events-none hidden shrink-0 items-center gap-[6px] rounded-full border px-[10px] py-[3px] text-[11px] font-medium md:inline-flex"
          style={{
            // Access STATE, not an audience accent — neutral slate (see grid card).
            color: "var(--text-secondary)",
            borderColor: "color-mix(in srgb, var(--text-primary) 20%, transparent)",
            background: "color-mix(in srgb, var(--text-primary) 7%, transparent)",
          }}
        >
          <Lock className="h-[11px] w-[11px]" aria-hidden="true" />
          {t("authRequired")}
        </span>
      ) : null}
      <span className="relative z-[2]">
        <FavStar
          on={favorite}
          onToggle={onToggleFavorite}
          label={t(favorite ? "unfavorite" : "favorite")}
        />
      </span>
      {locked ? (
        <span className="pointer-events-none flex shrink-0 items-center gap-[6px] text-[12px] font-medium text-[var(--text-secondary)]">
          <Lock className="h-[12px] w-[12px]" aria-hidden="true" />
          {t("roleLocked")}
        </span>
      ) : (
        <span className="pointer-events-none flex shrink-0 items-center gap-[6px] text-[12px] font-semibold text-[var(--text-primary)]">
          {actionLabel}
          <ChevronRight className="h-[15px] w-[15px] text-[var(--text-secondary)] transition-transform group-hover/row:translate-x-[2px] group-hover/row:text-[var(--text-primary)]" />
        </span>
      )}
    </div>
  );
}

// Directory of business SURFACES — contained premium panel on the Tessera decor.
// Search + audience filters (real counters) + favourites + sort + grid/list. It
// lists SURFACES, never agents; the shape echoes the Flotte agent directory but
// is NOT linked to it (ADR 0013). (No literal "Filtres" button — redundant with
// the always-visible tabs; no "load more" — the surface set is small and whole.)
export function SpacesDirectory({ groups }: { groups: SurfaceGroup[] }) {
  const t = useTranslations("spaces");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [view, setView] = useState<ViewMode>("grid");
  const [sort, setSort] = useState<Sort>("az");
  const [favorites, setFavorites] = useState<string[]>([]);

  // Real, user-owned browser state — never fabricated.
  useEffect(() => {
    setFavorites(readFavorites());
    const v = localStorage.getItem(VIEW_KEY);
    if (v === "grid" || v === "list") setView(v);
  }, []);

  const toggleFavorite = (key: string) => {
    setFavorites((prev) => {
      const next = prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key];
      try {
        localStorage.setItem(FAV_KEY, JSON.stringify(next));
      } catch {
        // ignore disabled storage
      }
      return next;
    });
  };
  const setViewMode = (v: ViewMode) => {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      // ignore
    }
  };

  const all = useMemo<FlatSurface[]>(
    () => groups.flatMap((g) => g.surfaces.map((s) => ({ ...s, audience: g.key }))),
    [groups],
  );
  const favSet = new Set(favorites);
  const counts = {
    all: all.length,
    external: all.filter((s) => s.audience === "external").length,
    internal: all.filter((s) => s.audience === "internal").length,
    favorites: all.filter((s) => favSet.has(s.key)).length,
  };

  const q = query.trim().toLowerCase();
  const shown = all
    .filter((s) => {
      if (filter === "external" || filter === "internal") return s.audience === filter;
      if (filter === "favorites") return favSet.has(s.key);
      return true;
    })
    .filter((s) => !q || s.name.toLowerCase().includes(q) || s.desc.toLowerCase().includes(q))
    // External surfaces first (the customer-facing space leads — Espace client),
    // then internal; the A→Z / Z→A sort is the secondary key within each audience.
    .sort((x, y) => {
      const rank = (s: FlatSurface) => (s.audience === "external" ? 0 : 1);
      if (rank(x) !== rank(y)) return rank(x) - rank(y);
      return sort === "az" ? x.name.localeCompare(y.name) : y.name.localeCompare(x.name);
    });

  const FILTERS: Array<{ key: Filter; label: string; count: number }> = [
    { key: "all", label: t("filterAll"), count: counts.all },
    { key: "external", label: t("filterExternal"), count: counts.external },
    { key: "internal", label: t("filterInternal"), count: counts.internal },
    { key: "favorites", label: t("filterFavorites"), count: counts.favorites },
  ];

  return (
    <div
      className="flex w-full max-w-[1040px] flex-col gap-[18px] rounded-[24px] border border-[var(--border-subtle)] p-[22px] backdrop-blur-[3px]"
      style={{
        background:
          "linear-gradient(160deg, color-mix(in srgb, var(--panel) 82%, transparent), color-mix(in srgb, var(--panel-soft) 70%, transparent))",
        boxShadow: "0 18px 50px rgba(0,0,0,0.36), inset 0 1px 0 rgba(255,255,255,0.04)",
      }}
    >
      {/* Row 1 — search + grid/list toggle. */}
      <div className="flex flex-wrap items-center gap-[10px]">
        <div className="relative min-w-[220px] flex-1">
          <Search className="-translate-y-1/2 absolute top-1/2 left-[12px] h-[15px] w-[15px] text-[var(--text-secondary)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className={cn(
              "h-[42px] w-full rounded-[12px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_55%,transparent)] pr-[14px] pl-[36px] text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-secondary)] focus:border-[color-mix(in_srgb,var(--text-primary)_30%,transparent)]",
              FOCUS,
            )}
          />
        </div>
        <div className="inline-flex rounded-[11px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_55%,transparent)] p-[3px]">
          {(["grid", "list"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setViewMode(v)}
              aria-label={v === "grid" ? t("viewGrid") : t("viewList")}
              aria-pressed={view === v}
              className={cn(
                "grid h-[34px] w-[34px] place-items-center rounded-[8px] transition-colors",
                FOCUS,
                view === v
                  ? "bg-[color-mix(in_srgb,var(--text-primary)_12%,transparent)] text-[var(--text-primary)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
              )}
            >
              {v === "grid" ? (
                <LayoutGrid className="h-[16px] w-[16px]" />
              ) : (
                <List className="h-[16px] w-[16px]" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Row 2 — audience tabs (left) + sort (right). */}
      <div className="flex flex-wrap items-center justify-between gap-[10px]">
        <div className="flex flex-wrap gap-[8px]">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={cn(
                "inline-flex items-center gap-[7px] rounded-full border px-[13px] py-[7px] text-[12px] font-medium transition-colors",
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
        <label className="inline-flex items-center gap-[8px] text-[11px] text-[var(--text-secondary)]">
          {t("sortLabel")}
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as Sort)}
            className={cn(
              "h-[34px] rounded-[10px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_55%,transparent)] px-[10px] text-[12px] text-[var(--text-primary)] outline-none",
              FOCUS,
            )}
          >
            <option value="az">{t("sortAZ")}</option>
            <option value="za">{t("sortZA")}</option>
          </select>
        </label>
      </div>

      {shown.length === 0 ? (
        <p className="rounded-[16px] border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_45%,transparent)] px-[18px] py-[24px] text-center text-[13px] text-[var(--text-secondary)]">
          {t("noMatch")}
        </p>
      ) : view === "grid" ? (
        <div className="grid grid-cols-2 gap-[16px] sm:grid-cols-3 lg:grid-cols-4">
          {shown.map((s) => (
            <SurfaceCard
              key={s.key}
              surface={s}
              favorite={favSet.has(s.key)}
              onToggleFavorite={() => toggleFavorite(s.key)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-[10px]">
          {shown.map((s) => (
            <SurfaceRow
              key={s.key}
              surface={s}
              favorite={favSet.has(s.key)}
              onToggleFavorite={() => toggleFavorite(s.key)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
