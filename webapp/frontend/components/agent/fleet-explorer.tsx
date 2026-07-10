"use client";

import {
  Activity,
  ArrowRight,
  Calendar,
  FlaskConical,
  LayoutGrid,
  List,
  Lock,
  Search,
  Send,
  Star,
  Users,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { agentIcon } from "@/components/agent/agent-icon";
import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import type { Fleet } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { levelBadgeView } from "@/lib/level-badge";

type FleetAgent = NonNullable<Fleet["agents"]>[number];
type Filter = "all" | "external" | "internal" | "favorites" | "recent";
type ViewMode = "grid" | "list";

const FAV_KEY = "tessera.fleet.favorites";
const RECENT_KEY = "tessera.fleet.recents";
const VIEW_KEY = "tessera.fleet.view";

const HEALTH_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  warn: "bg-amber-400",
  crit: "bg-red-400",
};

// Release verdict tone — colour tied to gate conformity (eval-gate-policy §6).
const RELEASE_TONE: Record<string, string> = {
  good: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  crit: "border-red-500/40 bg-red-500/10 text-red-300",
  bad: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  muted:
    "border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] text-[var(--tessera-text-muted)]",
};

// "20260618T083906Z" → localized date, or null if unparseable (never fabricated).
function fmtRunDate(runAt: string | null | undefined, locale: string): string | null {
  if (!runAt) return null;
  const m = runAt.match(/^(\d{4})(\d{2})(\d{2})T/);
  if (!m) return null;
  const dt = new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00Z`);
  return Number.isNaN(dt.getTime()) ? null : dt.toLocaleDateString(locale);
}

const isExternal = (a: FleetAgent) => a.audience === "customer";

// A platform witness (hello-agent, turn-agent) is not a banking agent. The manifest already
// says so with a `demo` tag — unchanged, it is the declaration; the card must say it too, or
// the fleet count silently inflates the demo, which the honest-positioning rule forbids.
const isPlatformWitness = (a: FleetAgent) => (a.tags ?? []).includes("demo");

function readList(key: string): string[] {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

// The rich agent directory (cockpit). Recycles the surface-picker mockup's CRAFT —
// search, audience filters + real counters, grid/list, scale 1→100+ — but here
// listing every agent is CORRECT: this is governance, and a click opens the
// agent's WORKSPACE (synthèse), never a chat. The customer chat lives in /produit
// behind the supervisor; there is no agent picker on the business plane (ADR 0013).
export function FleetExplorer({ agents }: { agents: FleetAgent[] }) {
  const t = useTranslations("fleet");
  const tBusiness = useTranslations("businessSignal");
  const locale = useLocale();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [view, setView] = useState<ViewMode>("grid");
  const [favorites, setFavorites] = useState<string[]>([]);
  const [recents, setRecents] = useState<string[]>([]);

  // Real, user-owned browser state — never fabricated.
  useEffect(() => {
    setFavorites(readList(FAV_KEY));
    setRecents(readList(RECENT_KEY));
    const v = localStorage.getItem(VIEW_KEY);
    if (v === "grid" || v === "list") setView(v);
  }, []);

  const toggleFavorite = (id: string) => {
    setFavorites((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try {
        localStorage.setItem(FAV_KEY, JSON.stringify(next));
      } catch {
        // ignore quota / disabled storage
      }
      return next;
    });
  };

  const recordRecent = (id: string) => {
    const next = [id, ...recents.filter((x) => x !== id)].slice(0, 20);
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch {
      // ignore
    }
  };

  const setViewMode = (v: ViewMode) => {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      // ignore
    }
  };

  const counts = useMemo(() => {
    const favSet = new Set(favorites);
    const recSet = new Set(recents);
    return {
      all: agents.length,
      external: agents.filter(isExternal).length,
      internal: agents.filter((a) => !isExternal(a)).length,
      favorites: agents.filter((a) => favSet.has(a.id)).length,
      recent: agents.filter((a) => recSet.has(a.id)).length,
    };
  }, [agents, favorites, recents]);

  const visible = useMemo(() => {
    const favSet = new Set(favorites);
    const recOrder = new Map(recents.map((id, i) => [id, i]));
    let list = agents.filter((a) => {
      if (filter === "external") return isExternal(a);
      if (filter === "internal") return !isExternal(a);
      if (filter === "favorites") return favSet.has(a.id);
      if (filter === "recent") return recOrder.has(a.id);
      return true;
    });
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.owner.toLowerCase().includes(q) ||
          a.id.toLowerCase().includes(q),
      );
    }
    if (filter === "recent") {
      list = [...list].sort((x, y) => (recOrder.get(x.id) ?? 0) - (recOrder.get(y.id) ?? 0));
    }
    return list;
  }, [agents, filter, query, favorites, recents]);

  const FILTERS: Array<{ key: Filter; label: string; count: number }> = [
    { key: "all", label: t("filterAll"), count: counts.all },
    { key: "external", label: t("filterExternal"), count: counts.external },
    { key: "internal", label: t("filterInternal"), count: counts.internal },
    { key: "favorites", label: t("filterFavorites"), count: counts.favorites },
    { key: "recent", label: t("filterRecent"), count: counts.recent },
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* Toolbar — search · filters + counters · grid/list toggle. */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="-translate-y-1/2 absolute top-1/2 left-2.5 h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="h-9 w-full rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] pr-3 pl-8 text-[0.78rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)] focus:border-[#7c5cf5]/60"
          />
        </div>
        <div className="inline-flex rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-0.5">
          {(["grid", "list"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setViewMode(v)}
              aria-label={v === "grid" ? t("viewGrid") : t("viewList")}
              aria-pressed={view === v}
              className={cn(
                "grid h-8 w-8 place-items-center rounded-md transition-colors",
                view === v
                  ? "bg-[var(--tessera-surface-2)] text-[var(--tessera-text)]"
                  : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {v === "grid" ? <LayoutGrid className="h-4 w-4" /> : <List className="h-4 w-4" />}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[0.72rem] font-medium transition-colors",
              filter === f.key
                ? "border-[#7c5cf5]/60 bg-[#7c5cf5]/12 text-[var(--tessera-text)]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {f.label}
            <span className="rounded-full bg-[var(--tessera-surface-2)] px-1.5 text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
              {f.count}
            </span>
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6 text-center text-[0.78rem] text-[var(--tessera-text-muted)]">
          {t("noMatch")}
        </p>
      ) : view === "grid" ? (
        <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((a) => (
            <AgentCard
              key={a.id}
              agent={a}
              external={isExternal(a)}
              favorite={favorites.includes(a.id)}
              onToggleFavorite={() => toggleFavorite(a.id)}
              onOpen={() => recordRecent(a.id)}
              locale={locale}
              t={t}
              tBusiness={tBusiness}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {visible.map((a) => (
            <AgentRow
              key={a.id}
              agent={a}
              external={isExternal(a)}
              favorite={favorites.includes(a.id)}
              onToggleFavorite={() => toggleFavorite(a.id)}
              onOpen={() => recordRecent(a.id)}
              t={t}
              tBusiness={tBusiness}
            />
          ))}
        </div>
      )}
    </div>
  );
}

type T = ReturnType<typeof useTranslations<"fleet">>;
type TBusiness = ReturnType<typeof useTranslations<"businessSignal">>;

function AudienceBadge({ external, t }: { external: boolean; t: T }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[0.6rem] font-medium uppercase tracking-[0.05em]",
        external
          ? "border-sky-500/40 bg-sky-500/10 text-sky-300"
          : "border-amber-500/40 bg-amber-500/10 text-amber-300",
      )}
    >
      {external ? <Users className="h-2.5 w-2.5" /> : <Lock className="h-2.5 w-2.5" />}
      {external ? t("audienceExternal") : t("audienceInternal")}
    </span>
  );
}

// The neutral chip: states a fact about the agent without ranking it. Shared so the contract
// chips read as the same family as the witness chip, and stay that way.
const NEUTRAL_CHIP =
  "inline-flex items-center gap-1 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-1.5 py-0.5 text-[0.6rem] font-medium uppercase tracking-[0.05em] text-[var(--tessera-text-muted)]";

// "Témoin plateforme", never "Démonstration": that word is reserved for the surface pill
// (headers spec §5), and a second use with a different meaning would collide.
function WitnessChip({ t }: { t: T }) {
  return (
    <span title={t("witnessBadgeHint")} className={NEUTRAL_CHIP}>
      <FlaskConical className="h-2.5 w-2.5" />
      {t("witnessBadge")}
    </span>
  );
}

// The agent's two structural contracts, both computed server-side from its manifest:
// `observable` = it declares telemetry capabilities (ADR 0017 §3), `testable` = it declares an
// invocation binding other than `none` (ADR 0019 §1). Never keyed on an agent id — a chip that
// switched on one would be a hardcoded fleet, and a foreign agent would arrive without it.
//
// Absence is the honest state: an agent promising neither shows neither chip, rather than two
// greyed ones implying it fell short of something it never claimed.
function ContractChips({ agent, t }: { agent: FleetAgent; t: T }) {
  return (
    <>
      {agent.observable ? (
        <span title={t("observableChipHint")} className={NEUTRAL_CHIP}>
          <Activity className="h-2.5 w-2.5" />
          {t("observableChip")}
        </span>
      ) : null}
      {agent.testable ? (
        <span title={t("testableChipHint")} className={NEUTRAL_CHIP}>
          <Send className="h-2.5 w-2.5" />
          {t("testableChip")}
        </span>
      ) : null}
    </>
  );
}

// ADR 0017 §4 — the observability level badge (L0–L2 in Phase B). Computed from passing
// facts server-side; `null`/absent when the agent has no AgentSpec manifest yet, so it
// renders nothing (honest-empty) rather than a misleading "L0".
//
// When the manifest declares a higher rung than the facts prove, the badge shows the
// DECLARED rung in a muted variant and names it as declared. The tooltip distinguishes the
// two silences: `unverifiable` (the metrics store is off or unreachable — nobody can check)
// from `dormant` (the store was read and this agent has emitted nothing). Never says
// "recent": the evidence query is an unwindowed cumulative counter (see turn_evidence.py).
// No agent-specific condition lives here — the gap is data, computed server-side.
function LevelBadge({ agent, t }: { agent: FleetAgent; t: T }) {
  const view = levelBadgeView(agent);
  if (view.kind === "none") return null;

  if (view.kind === "declared") {
    const hint =
      view.evidence === "dormant"
        ? t("levelDormantHint", { level: view.level })
        : t("levelUnverifiableHint", { level: view.level });
    return (
      <span
        title={hint}
        className="inline-flex items-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-[0.05em] text-[var(--tessera-text-muted)]"
      >
        {t("levelDeclaredNoEvidence", { level: view.level })}
      </span>
    );
  }

  return (
    <span
      title={t("observabilityLevel", { level: view.level })}
      className="inline-flex items-center rounded-full border border-[#7c5cf5]/40 bg-[#7c5cf5]/10 px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-[0.05em] text-[#b9a6ff]"
    >
      {view.level}
    </span>
  );
}

function FavButton({ favorite, onToggle, t }: { favorite: boolean; onToggle: () => void; t: T }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={favorite ? t("unfavorite") : t("favorite")}
      aria-pressed={favorite}
      className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-[var(--tessera-text-muted)] transition-colors hover:text-amber-300"
    >
      <Star className={cn("h-3.5 w-3.5", favorite && "fill-amber-300 text-amber-300")} />
    </button>
  );
}

function ReleaseChip({ agent, t }: { agent: FleetAgent; t: T }) {
  if (!agent.release || !agent.release.available) {
    return (
      <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("releaseNotRun")}</span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[0.62rem] font-medium",
        RELEASE_TONE[agent.release.verdict_tone] ?? RELEASE_TONE.muted,
      )}
    >
      {agent.release.verdict_label}
    </span>
  );
}

function BusinessSignalLabel({ agent, tBusiness }: { agent: FleetAgent; tBusiness: TBusiness }) {
  const signal = agent.north_star;
  if (!signal) return null;
  const value = typeof signal.value_pct === "number" ? `${Math.round(signal.value_pct)}%` : "—";
  const label = tBusiness.has(signal.key) ? tBusiness(signal.key) : signal.key;
  return (
    <span
      className="inline-flex min-w-0 items-center gap-1 rounded-md border border-emerald-500/35 bg-emerald-500/10 px-1.5 py-0.5 text-[0.6rem] font-medium text-emerald-200"
      title={`${label} · ${value}`}
    >
      <span className="truncate">{label}</span>
      <span className="shrink-0 tabular-nums text-emerald-100">{value}</span>
    </span>
  );
}

function PendingBusinessChip({ agent, t }: { agent: FleetAgent; t: T }) {
  const n = agent.pending_business_items ?? 0;
  if (n <= 0) return null;
  return (
    <span className="inline-flex items-center rounded-md border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 text-[0.6rem] font-medium text-amber-200">
      {t("pendingBusinessItems", { n })}
    </span>
  );
}

function StaleChip({ t }: { t: T }) {
  return (
    <span className="inline-flex items-center rounded-md border border-amber-500/45 px-1.5 py-0.5 text-[0.58rem] font-semibold uppercase tracking-[0.04em] text-amber-300">
      {t("stale")}
    </span>
  );
}

// Pass rate (0..100) EXACTLY as the report/cockpit show it — summary passed/total
// of THIS agent's own run. `null` when the summary is unavailable.
function passPct(agent: FleetAgent): number | null {
  const r = agent.release;
  if (!r?.available || r.summary_passed == null || !r.summary_total) return null;
  return Math.round((r.summary_passed / r.summary_total) * 100);
}

// Governance facet (ADR 0013): the card LEADS with the eval-gate verdict + the
// agent's own pass rate (n/N) + the shared security floor (X/18) + the run date —
// the same per-agent eval detail the launcher used to show, which lives HERE now.
// Observable KPIs (volume, latency, escalation, handoffs) are NOT repeated: those
// are the monitoring facet, on the Vue d'ensemble per-agent breakdown.
function AgentCard({
  agent,
  external,
  favorite,
  onToggleFavorite,
  onOpen,
  locale,
  t,
  tBusiness,
}: {
  agent: FleetAgent;
  external: boolean;
  favorite: boolean;
  onToggleFavorite: () => void;
  onOpen: () => void;
  locale: string;
  t: T;
  tBusiness: TBusiness;
}) {
  const r = agent.release;
  const pct = passPct(agent);
  const date = fmtRunDate(r?.run_at, locale);
  const Icon = agentIcon(agent.id);
  return (
    <div className="group flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 transition-colors hover:border-[#7c5cf5]/50">
      <div className="flex items-start justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 text-[#b9a6ff]" />
          <span className="truncate font-semibold">{agent.name}</span>
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <span
            className={cn("h-2 w-2 rounded-full", HEALTH_DOT[agent.health] ?? "bg-amber-400")}
            title={agent.health}
          />
          <FavButton favorite={favorite} onToggle={onToggleFavorite} t={t} />
        </span>
      </div>
      {agent.description ? (
        <p className="-mt-1.5 line-clamp-2 text-[0.72rem] leading-snug text-[var(--tessera-text-muted)]">
          {agent.description}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-1.5">
        <AudienceBadge external={external} t={t} />
        {isPlatformWitness(agent) ? <WitnessChip t={t} /> : null}
        <ContractChips agent={agent} t={t} />
        <LevelBadge agent={agent} t={t} />
        <BusinessSignalLabel agent={agent} tBusiness={tBusiness} />
        <PendingBusinessChip agent={agent} t={t} />
        <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">{agent.owner}</span>
      </div>
      {/* Eval-gate verdict — leads the card. */}
      <div className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <ReleaseChip agent={agent} t={t} />
          {r?.verdict_stale ? <StaleChip t={t} /> : null}
        </div>
        {pct != null && r?.summary_passed != null && r.summary_total != null ? (
          <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
            {t("evalRate", { rate: pct, passed: r.summary_passed, total: r.summary_total })}
          </p>
        ) : null}
        {r?.socle_passed != null && r.socle_total != null ? (
          <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
            {t("socleSecurity", { passed: r.socle_passed, total: r.socle_total })}
          </p>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-2 border-[var(--tessera-border)] border-t pt-2">
        {date ? (
          <span className="inline-flex items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
            <Calendar className="h-3 w-3 shrink-0" />
            {t("evaluatedOn", { date })}
          </span>
        ) : (
          <span />
        )}
        <Link
          href={agentPath(agent.id, "synthese")}
          onClick={onOpen}
          className="inline-flex items-center gap-1 text-[0.66rem] font-medium text-[#b9a6ff] hover:text-white"
        >
          {t("govern")} <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}

function AgentRow({
  agent,
  external,
  favorite,
  onToggleFavorite,
  onOpen,
  t,
  tBusiness,
}: {
  agent: FleetAgent;
  external: boolean;
  favorite: boolean;
  onToggleFavorite: () => void;
  onOpen: () => void;
  t: T;
  tBusiness: TBusiness;
}) {
  const Icon = agentIcon(agent.id);
  return (
    <div className="group flex items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2.5 transition-colors hover:border-[#7c5cf5]/50">
      <span
        className={cn("h-2 w-2 shrink-0 rounded-full", HEALTH_DOT[agent.health] ?? "bg-amber-400")}
      />
      <Icon className="h-4 w-4 shrink-0 text-[#b9a6ff]" />
      <span className="w-[160px] shrink-0 truncate font-semibold" title={agent.description}>
        {agent.name}
      </span>
      <AudienceBadge external={external} t={t} />
      {isPlatformWitness(agent) ? <WitnessChip t={t} /> : null}
      <ContractChips agent={agent} t={t} />
      <LevelBadge agent={agent} t={t} />
      <BusinessSignalLabel agent={agent} tBusiness={tBusiness} />
      <PendingBusinessChip agent={agent} t={t} />
      <span className="hidden truncate text-[0.66rem] text-[var(--tessera-text-muted)] md:inline">
        {agent.owner}
      </span>
      {(() => {
        const r = agent.release;
        const pct = passPct(agent);
        return pct != null && r?.summary_passed != null && r.summary_total != null ? (
          <span
            className="ml-auto hidden text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)] sm:inline"
            title={t("evalRate", { rate: pct, passed: r.summary_passed, total: r.summary_total })}
          >
            {r.summary_passed}/{r.summary_total}
          </span>
        ) : (
          <span className="ml-auto" />
        );
      })()}
      <ReleaseChip agent={agent} t={t} />
      <FavButton favorite={favorite} onToggle={onToggleFavorite} t={t} />
      <Link
        href={agentPath(agent.id, "synthese")}
        onClick={onOpen}
        className="inline-flex shrink-0 items-center gap-1 text-[0.66rem] font-medium text-[#b9a6ff] hover:text-white"
      >
        {t("govern")} <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  );
}
