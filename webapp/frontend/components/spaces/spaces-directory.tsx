"use client";

import {
  Boxes,
  ChevronDown,
  ChevronRight,
  HandCoins,
  LayoutGrid,
  List,
  Lock,
  Search,
  Star,
  UserRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

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
  // False when the CURRENT authenticated role cannot enter this surface (e.g. a
  // `collections` session and the customer product). The card is then shown inert
  // instead of a link that would bounce to the role's own landing (ADR 0013). For
  // an anonymous session this is always true — each protected surface owns its
  // login redirect and post-login return.
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

const ACCENT: Record<Audience, { border: string; icon: string; dot: string; iconBg: string }> = {
  external: {
    // Rose (not gold) so the customer-facing surface never reads in the warm
    // gold/amber family shared by the "Démonstration" eyebrow and the access
    // badge; stays distinct from the internal teal/cyan (Console recouvrement).
    border: "border-[var(--border-rose)]",
    icon: "text-[var(--rose-strong)]",
    dot: "var(--rose-strong)",
    iconBg:
      "linear-gradient(150deg, color-mix(in srgb, var(--rose) var(--launcher-icon-wash), transparent), color-mix(in srgb, var(--rose) var(--launcher-icon-wash-soft), transparent))",
  },
  internal: {
    border: "border-[var(--border-cyan)]",
    icon: "text-[var(--cyan)]",
    dot: "var(--cyan)",
    iconBg:
      "linear-gradient(150deg, color-mix(in srgb, var(--cyan) var(--launcher-icon-wash), transparent), color-mix(in srgb, var(--cyan) var(--launcher-icon-wash-soft), transparent))",
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
        "grid h-[24px] w-[24px] cursor-pointer place-items-center rounded-md text-[var(--text-secondary)] transition-colors hover:text-[var(--gold-strong)]",
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
  const a = ACCENT[surface.audience];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const audienceLabel = surface.audience === "internal" ? t("groupInternal") : t("groupExternal");
  const actionLabel = t("open");

  const actionAria = `${surface.name} — ${actionLabel}`;
  const locked = !surface.accessible;
  return (
    <div
      aria-disabled={locked || undefined}
      className={cn(
        // Left-aligned and substantial: the tile now carries the surface's own DESCRIPTION,
        // which the directory already had and only showed in list mode. Two surfaces spread
        // across four thin centred columns read as an unfinished page; two real cards read
        // as a directory. Elevation on hover comes from a token (box-shadow, never
        // transform, so cards don't jitter under a scrolling cursor).
        "launcher-tile group/card relative flex min-h-[188px] flex-col gap-[12px] overflow-hidden rounded-xl border px-[16px] pt-[16px] pb-[14px]",
        a.border,
        locked && "cursor-not-allowed opacity-55",
      )}
    >
      {/* Stretched action covers the whole card (no nested interactives). Inert
          when the current role can't enter — no link that would bounce away. */}
      {locked ? null : (
        <Link
          href={surface.href}
          aria-label={actionAria}
          className={cn("absolute inset-0 rounded-xl", FOCUS)}
        />
      )}

      <div className="pointer-events-none relative flex items-start justify-between gap-[10px]">
        <span
          className={cn(
            "grid h-[44px] w-[44px] place-items-center rounded-xl border",
            a.border,
            a.icon,
          )}
          style={{ background: a.iconBg }}
        >
          <Icon className="h-[21px] w-[21px]" />
        </span>
        {/* Favourite star — sibling above the action, independently clickable. */}
        <span className="pointer-events-auto z-[2]">
          <FavStar
            on={favorite}
            onToggle={onToggleFavorite}
            label={t(favorite ? "unfavorite" : "favorite")}
          />
        </span>
      </div>

      {/* Visual content — clicks pass through to the stretched action. */}
      <div className="pointer-events-none relative flex flex-1 flex-col gap-[6px]">
        <span className="flex flex-wrap items-center gap-x-[10px] gap-y-[4px]">
          <span className="text-[15px] font-semibold leading-[1.2] text-[var(--text-primary)]">
            {surface.name}
          </span>
          <span className="inline-flex items-center gap-[6px] text-xs text-[var(--text-secondary)]">
            <span
              className="h-[6px] w-[6px] rounded-full"
              style={{ background: a.dot }}
              aria-hidden="true"
            />
            {audienceLabel}
          </span>
        </span>
        <span className="text-[12.5px] leading-[1.45] text-[var(--text-secondary)]">
          {surface.desc}
        </span>
      </div>

      <div className="pointer-events-none relative flex flex-wrap items-center justify-between gap-[8px]">
        {/* ACCESS facet (ADR 0013 amended) — gated surfaces advertise "Connexion
            requise"; open surfaces carry no chip (the "Ouvrir" CTA says it). */}
        {surface.authRequired ? (
          <span
            className="inline-flex items-center gap-[5px] rounded-full border px-[8px] py-[3px] text-xs font-medium"
            style={{
              color: "var(--amber-soft)",
              borderColor: "color-mix(in srgb, var(--amber-soft) 42%, transparent)",
              background: "color-mix(in srgb, var(--amber-soft) 12%, transparent)",
            }}
          >
            <Lock className="h-[10px] w-[10px]" aria-hidden="true" />
            {t("authRequired")}
          </span>
        ) : (
          <span />
        )}
        {locked ? (
          <span className="inline-flex items-center gap-[5px] text-xs font-medium text-[var(--text-secondary)]">
            <Lock className="h-[11px] w-[11px]" aria-hidden="true" />
            {t("roleLocked")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-[5px] text-xs font-semibold text-[var(--text-secondary)] transition-colors group-hover/card:text-[var(--text-primary)]">
            {actionLabel}
            <ChevronRight className="h-[13px] w-[13px] transition-transform group-hover/card:translate-x-[2px]" />
          </span>
        )}
      </div>
    </div>
  );
}

function SurfaceRow({
  surface,
  favorite,
  onToggleFavorite,
}: { surface: FlatSurface; favorite: boolean; onToggleFavorite: () => void }) {
  const t = useTranslations("spaces");
  const a = ACCENT[surface.audience];
  const Icon = SURFACE_ICON[surface.key] ?? Boxes;
  const audienceLabel = surface.audience === "internal" ? t("groupInternal") : t("groupExternal");

  const actionLabel = t("open");
  const actionAria = `${surface.name} — ${actionLabel}`;
  const locked = !surface.accessible;
  return (
    <div
      aria-disabled={locked || undefined}
      className={cn(
        "launcher-tile group/row relative flex w-full items-center gap-[16px] rounded-xl border px-[18px] py-[14px] text-left",
        a.border,
        locked && "cursor-not-allowed opacity-55",
      )}
    >
      {locked ? null : (
        <Link
          href={surface.href}
          aria-label={actionAria}
          className={cn("absolute inset-0 rounded-xl", FOCUS)}
        />
      )}

      <span
        className={cn(
          "pointer-events-none grid h-[44px] w-[44px] shrink-0 place-items-center rounded-xl border",
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
          <span className="inline-flex items-center gap-[5px] text-xs text-[var(--text-secondary)]">
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
          className="pointer-events-none hidden shrink-0 items-center gap-[6px] rounded-full border px-[10px] py-[3px] text-xs font-medium md:inline-flex"
          style={{
            color: "var(--amber-soft)",
            borderColor: "color-mix(in srgb, var(--amber-soft) 42%, transparent)",
            background: "color-mix(in srgb, var(--amber-soft) 12%, transparent)",
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
      className="flex w-full max-w-[1040px] flex-col gap-[18px] rounded-2xl border border-[var(--border-subtle)] p-[22px] backdrop-blur-[3px]"
      style={{
        // Both were literals, and both were black: a 50 px halo at 36 % around the panel and
        // an inset white glint. On the night-blue themes that is depth; on a #fafafa page it
        // is a grey bruise. Tokenised, so "Clair" gets the Cloudflare arrangement instead —
        // a white panel separated by its LINE and a one-pixel lift.
        background: "var(--launcher-panel-bg)",
        boxShadow: "var(--launcher-panel-shadow)",
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
              "h-[42px] w-full rounded-xl border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_55%,transparent)] pr-[14px] pl-[36px] text-[13px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-secondary)] focus:border-[color-mix(in_srgb,var(--text-primary)_30%,transparent)]",
              FOCUS,
            )}
          />
        </div>
        <div className="inline-flex rounded-xl border border-[var(--border-subtle)] bg-[color-mix(in_srgb,var(--bg-app)_55%,transparent)] p-[3px]">
          {(["grid", "list"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setViewMode(v)}
              aria-label={v === "grid" ? t("viewGrid") : t("viewList")}
              aria-pressed={view === v}
              className={cn(
                "grid h-[34px] w-[34px] place-items-center rounded-lg transition-colors",
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
              <span className="rounded-full bg-[color-mix(in_srgb,var(--text-primary)_10%,transparent)] px-[7px] text-xs tabular-nums">
                {f.count}
              </span>
            </button>
          ))}
        </div>
        <label className="inline-flex items-center gap-[8px] text-xs text-[var(--text-secondary)]">
          {t("sortLabel")}
          {/* The native chrome of a <select> is the one control on this page that ignores
              the design system entirely — a grey OS bevel next to tokenised pills. Stripped
              with appearance-none and given the same hairline + our own chevron. */}
          <span className="relative inline-flex items-center">
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as Sort)}
              className={cn(
                "h-[34px] appearance-none rounded-lg border border-[var(--border-subtle)] bg-[var(--launcher-tile-bg)] pr-[28px] pl-[10px] text-[12px] text-[var(--text-primary)] outline-none transition-colors hover:border-[color-mix(in_srgb,var(--text-primary)_28%,transparent)]",
                FOCUS,
              )}
            >
              <option value="az">{t("sortAZ")}</option>
              <option value="za">{t("sortZA")}</option>
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-[9px] h-[13px] w-[13px] text-[var(--text-secondary)]"
              aria-hidden="true"
            />
          </span>
        </label>
      </div>

      {shown.length === 0 ? (
        <p className="launcher-tile rounded-xl border border-[var(--border-subtle)] px-[18px] py-[24px] text-center text-[13px] text-[var(--text-secondary)]">
          {t("noMatch")}
        </p>
      ) : view === "grid" ? (
        // Two surfaces stretched over four narrow columns left three quarters of the panel
        // empty and each tile too thin to say anything. Cards, not thumbnails — and TWO
        // columns, not three: a third track would put the hole back at 1440. A future third
        // surface wraps to a second row, which is what a directory is supposed to do.
        <div className="grid grid-cols-1 gap-[14px] sm:grid-cols-2">
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
