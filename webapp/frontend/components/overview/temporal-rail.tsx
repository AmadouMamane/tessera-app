"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Flag,
  History,
  Pause,
  PlayCircle,
  RotateCcw,
  SkipBack,
  SkipForward,
} from "lucide-react";
import { useTranslations } from "next-intl";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchTimeline } from "@/lib/api/client";
import type { TimelineReport } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { type OverviewTone, dotBg } from "@/lib/overview";
import { setTemporalContext } from "@/lib/temporal-context";

function railPos(at: string, start: number, span: number): number {
  const v = new Date(at).getTime();
  if (!Number.isFinite(v) || span <= 0) return 100;
  return Math.min(100, Math.max(0, ((v - start) / span) * 100));
}

// Fixed-length date/time formatters: with tabular-nums the rendered width stays
// constant as the value changes, so the "viewing-at" label never jitters.
export function fmtStamp(ms: number): string {
  return new Date(ms).toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

const PERIODS: { key: string; ms: number }[] = [
  { key: "h24", ms: 24 * 3600_000 },
  { key: "d7", ms: 7 * 24 * 3600_000 },
  { key: "d30", ms: 30 * 24 * 3600_000 },
];

export function TemporalRail({
  mode,
  liveStatus,
  timeline,
  sloTarget,
  selectedAt,
  onSelectedAtChange,
  periodKey,
  onPeriodChange,
  onModeChange,
}: {
  mode: "live" | "replay";
  liveStatus: string;
  timeline?: TimelineReport;
  sloTarget?: number;
  // Controlled by the page so the focused instant T drives every block (ADR 0011).
  selectedAt: number | null;
  onSelectedAtChange: Dispatch<SetStateAction<number | null>>;
  periodKey: string;
  onPeriodChange: (period: string) => void;
  onModeChange: (mode: "live" | "replay") => void;
}) {
  const t = useTranslations("overview.time");
  const [compare, setCompare] = useState("target");
  // T being viewed and the period live at page level now; these are the rail's
  // write handles into them.
  const setSelectedAt = onSelectedAtChange;
  const setPeriodKey = onPeriodChange;
  const [playing, setPlaying] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  // The visible axis spans the chosen period, ending "now" — so 24h / 7d / 30d
  // each render a distinct scale. Real data may begin later than the window
  // start (we only have ~38h of history), marked by `dataStart`.
  const end = timeline ? new Date(timeline.window_end).getTime() : Date.now();
  const periodMs = PERIODS.find((p) => p.key === periodKey)?.ms ?? 7 * 24 * 3600_000;
  const rawStart = timeline ? new Date(timeline.window_start).getTime() : end - periodMs;
  const viewStart = end - periodMs;
  const span = Math.max(1, end - viewStart);
  const dataStart = Math.max(rawStart, viewStart);
  const events = (timeline?.events ?? []).filter((e) => {
    const v = new Date(e.at).getTime();
    return v >= viewStart && v <= end;
  });
  const currentT = selectedAt ?? end;
  // Prev/next move by a natural, perceptible unit: 1 h in 24h view, 1 day otherwise.
  const stepUnit = periodKey === "h24" ? 3600_000 : 24 * 3600_000;

  // Real quality points, used for the baseline-delta comparison (#201).
  const scorePoints = events
    .filter((e) => e.kind === "score")
    .map((e) => ({
      at: new Date(e.at).getTime(),
      v: Number.parseFloat(e.label.replace(/[^0-9.]/g, "")),
    }))
    .filter((p) => Number.isFinite(p.v));
  // Natural, computable baselines: the quality target (SLO), or the present value.
  const presentScore = scorePoints.length
    ? scorePoints.reduce((best, p) => (Math.abs(p.at - end) < Math.abs(best.at - end) ? p : best)).v
    : null;
  const baseline =
    compare === "none" ? null : compare === "now" ? presentScore : (sloTarget ?? 0.8); // "target"
  // Score nearest the focused instant (present included), for the vs-baseline delta.
  const nearestScore = scorePoints.reduce<{ v: number; d: number } | null>((best, p) => {
    const d = Math.abs(p.at - currentT);
    return !best || d < best.d ? { v: p.v, d } : best;
  }, null);
  const baselineDelta = baseline != null && nearestScore != null ? nearestScore.v - baseline : null;

  function seekToClientX(clientX: number) {
    const el = trackRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const at = viewStart + frac * span;
    setSelectedAt(at >= end - 1000 ? null : at);
  }
  function step(dir: -1 | 1) {
    const nextT = Math.min(end, Math.max(viewStart, currentT + dir * stepUnit));
    setSelectedAt(nextT >= end - 1000 ? null : nextT);
  }
  // Event nearest the focused instant (present included), for the detail panel.
  const nearest =
    events.reduce<{ ev: TimelineReport["events"][number]; d: number } | null>((best, ev) => {
      const d = Math.abs(new Date(ev.at).getTime() - currentT);
      return !best || d < best.d ? { ev, d } : best;
    }, null)?.ev ?? null;

  // Playback: sweep T across the window; reaching the end returns to live.
  useEffect(() => {
    if (!playing || mode !== "replay") return;
    const id = window.setInterval(() => {
      setSelectedAt((cur) => {
        const from = cur ?? dataStart;
        const nextT = from + span / 90;
        return nextT >= end ? null : nextT;
      });
    }, 60);
    return () => window.clearInterval(id);
  }, [playing, mode, dataStart, span, end, setSelectedAt]);
  useEffect(() => {
    if (selectedAt == null && playing) setPlaying(false);
  }, [selectedAt, playing]);

  // Compact Live rail (default): real-time badge, period, last update, Relire à T.
  if (mode === "live") {
    const last = timeline ? new Date(timeline.window_end) : null;
    return (
      <section className="flex min-h-[42px] flex-wrap items-center gap-3 border-y border-[var(--tessera-border)] bg-transparent px-1 py-2">
        <Badge className="rounded-md border-[#005c42] bg-[#003f30] px-3 py-1 text-[#7ff0b6]">
          {t("live")}
        </Badge>
        <span className="flex items-center gap-2 text-sm text-[var(--tessera-text)]">
          <span className="h-2 w-2 rounded-full bg-[var(--tessera-green)] shadow-[0_0_10px_rgba(0,200,120,0.85)]" />
          {t("realtime")}
        </span>
        <span className="h-5 w-px bg-[var(--tessera-border)]" />
        <span className="text-sm text-[var(--tessera-text-muted)]">
          {t("period")} :{" "}
          <span className="font-semibold text-[var(--tessera-text)]">{t(periodKey)}</span>
        </span>
        {last ? (
          <span className="hidden text-xs text-[var(--tessera-text-muted)] md:inline">
            {t("lastUpdate")} {last.toLocaleTimeString()}
          </span>
        ) : null}
        <span className="ml-auto hidden text-xs text-[var(--tessera-text-muted)] lg:inline">
          {liveStatus}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 border-[#9a5f18] bg-transparent px-4 text-[#f0a23a] hover:bg-[#3e260c]/35"
          onClick={() => onModeChange("replay")}
        >
          <History className="h-4 w-4" />
          {t("replayAtT")}
        </Button>
      </section>
    );
  }

  // Expanded time-travel rail: period · viewing-at-T · compare-to-baseline ·
  // playback, then an interactive scrubber over the real lineage timeline (#201).
  const handlePos = railPos(new Date(currentT).toISOString(), viewStart, span);

  return (
    <section className="rounded-md border border-[#9a5f18]/60 bg-[var(--tessera-surface)] p-4 shadow-[var(--shadow-card)]">
      {/* Auto-sized controls (no wrap); only the "viewing-at" value is fixed-width
          so dragging the scrubber never reflows this row. */}
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 px-3 text-xs text-[var(--muted-foreground)]">
          <Clock3 className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("period")}
          <select
            value={periodKey}
            onChange={(e) => {
              setPeriodKey(e.target.value);
              setSelectedAt(null);
            }}
            className="cursor-pointer rounded bg-transparent font-semibold text-[var(--foreground)] outline-none"
          >
            {PERIODS.map((p) => (
              <option key={p.key} value={p.key} className="bg-[var(--card)]">
                {t(p.key)}
              </option>
            ))}
          </select>
        </label>
        <span
          className={cn(
            "flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border px-3 text-xs",
            selectedAt == null
              ? "border-[var(--border)] bg-[var(--muted)]/30 text-[var(--muted-foreground)]"
              : "border-gold-500/50 bg-gold-500/10 text-gold-200",
          )}
        >
          <Flag className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("viewingAt")}
          <b className="font-semibold tabular-nums text-[var(--foreground)]">
            {selectedAt == null ? t("nowLive") : fmtStamp(currentT)}
          </b>
        </span>
        <label className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 px-3 text-xs text-[var(--muted-foreground)]">
          <ArrowLeftRight className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {t("compareTo")}
          <select
            value={compare}
            onChange={(e) => setCompare(e.target.value)}
            className="cursor-pointer rounded bg-transparent font-semibold text-[var(--foreground)] outline-none"
          >
            <option value="target" className="bg-[var(--card)]">
              {t("baselineTarget")}
            </option>
            <option value="now" className="bg-[var(--card)]">
              {t("baselineNow")}
            </option>
            <option value="none" className="bg-[var(--card)]">
              {t("noBaseline")}
            </option>
          </select>
        </label>
        <span className="ml-auto flex h-9 shrink-0 items-center gap-1 rounded-lg border border-[var(--border)] px-2 text-[var(--muted-foreground)]">
          <PlaybackButton
            label={t("first")}
            onClick={() => {
              setPlaying(false);
              setSelectedAt(viewStart);
            }}
          >
            <SkipBack className="h-3.5 w-3.5" />
          </PlaybackButton>
          <PlaybackButton
            label={t("prev")}
            onClick={() => {
              setPlaying(false);
              step(-1);
            }}
          >
            <ChevronLeft className="h-4 w-4" />
          </PlaybackButton>
          <PlaybackButton
            label={playing ? t("pause") : t("play")}
            active={playing}
            onClick={() => {
              if (selectedAt == null) setSelectedAt(dataStart);
              setPlaying((p) => !p);
            }}
          >
            {playing ? (
              <Pause className="h-4 w-4 text-gold-400" />
            ) : (
              <PlayCircle className="h-4 w-4 text-gold-400" />
            )}
          </PlaybackButton>
          <PlaybackButton
            label={t("next")}
            onClick={() => {
              setPlaying(false);
              step(1);
            }}
          >
            <ChevronRight className="h-4 w-4" />
          </PlaybackButton>
          <PlaybackButton
            label={t("now")}
            onClick={() => {
              setPlaying(false);
              setSelectedAt(null);
            }}
          >
            <SkipForward className="h-3.5 w-3.5" />
          </PlaybackButton>
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-9"
          onClick={() => {
            setPlaying(false);
            onModeChange("live");
          }}
        >
          <RotateCcw className="h-4 w-4" />
          {t("exitReplay")}
        </Button>
      </div>

      {/* Interactive scrubber — click or drag to pick T; markers are real events. */}
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label={t("viewingAt")}
        aria-valuemin={viewStart}
        aria-valuemax={end}
        aria-valuenow={currentT}
        aria-valuetext={selectedAt == null ? t("nowLive") : new Date(currentT).toLocaleString()}
        className="relative mt-6 h-14 cursor-pointer select-none"
        onPointerDown={(e) => {
          setPlaying(false);
          trackRef.current?.setPointerCapture(e.pointerId);
          seekToClientX(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) seekToClientX(e.clientX);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") step(1);
          if (e.key === "ArrowLeft") step(-1);
        }}
      >
        <div className="pointer-events-none absolute inset-x-0 top-2.5 h-0.5 rounded-full bg-[linear-gradient(90deg,#363d48,#454e5d)]" />
        {/* "real data begins here" marker — this is where the timeline data
            starts, NOT the comparison baseline. The baseline (target / present)
            is a value, shown in the detail-panel delta, so it has no fixed point
            on the time axis; pinning a "baseline" dot here was misleading. */}
        {timeline && dataStart > viewStart + span * 0.01 ? (
          <RailMarker
            pos={railPos(new Date(dataStart).toISOString(), viewStart, span)}
            label={t("dataStart")}
            variant="baseline"
          />
        ) : null}
        {/* event markers (click to seek): quality scores are labelled, guard
            noise stays a faint tick with a tooltip. */}
        {events.map((ev, i) => {
          // Only annotate lineage changes (deploy / judge) — scores and guard
          // noise stay as coloured ticks so labels never overlap.
          const annotated = ev.kind === "model_change" || ev.kind === "judge_change";
          // Guard denials carry no useful detail (target is always "user_input").
          const detail = ev.kind === "guard_denial" ? "" : ev.detail;
          return (
            <RailEvent
              key={`${ev.at}-${ev.kind}-${i}`}
              pos={railPos(ev.at, viewStart, span)}
              tone={ev.tone as OverviewTone}
              label={annotated ? ev.label : ""}
              dim={ev.kind === "guard_denial"}
              title={`${fmtStamp(new Date(ev.at).getTime())} · ${ev.label}${detail ? ` · ${detail}` : ""}`}
              onSeek={() => setSelectedAt(new Date(ev.at).getTime())}
            />
          );
        })}
        {/* the moving head — a slim downward caret crowning a thin gold stem.
            The single time readout lives in the "Tu regardes" box. */}
        <div
          className="pointer-events-none absolute top-0 -translate-x-1/2 transition-opacity"
          style={{ left: `${handlePos}%`, opacity: selectedAt == null ? 0.6 : 1 }}
        >
          {/* stem centred vertically on the timeline track (10–14px → centre 12px) */}
          <span className="absolute left-1/2 top-1.5 h-3 w-px -translate-x-1/2 bg-gold-400" />
          <span className="absolute left-1/2 top-[-1px] h-0 w-0 -translate-x-1/2 border-l-[5px] border-r-[5px] border-t-[7px] border-l-transparent border-r-transparent border-t-gold-400 drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)]" />
        </div>
        {selectedAt == null ? (
          <span
            className="pointer-events-none absolute top-7 -translate-x-1/2 whitespace-nowrap text-[0.65rem] font-medium text-gold-400"
            style={{ left: "96%" }}
          >
            {t("now")}
          </span>
        ) : null}
      </div>

      {/* Legend — what the scrubber ticks mean. */}
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.62rem] text-[var(--muted-foreground)]">
        <span className="font-medium text-[var(--foreground)]">{t("legendScores")} :</span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-0.5 rounded bg-emerald-400" />
          {t("legendGood")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-0.5 rounded bg-orange-400" />
          {t("legendFair")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-0.5 rounded bg-red-400" />
          {t("legendBad")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-px bg-red-400 opacity-40" />
          {t("legendGuard")}
        </span>
      </div>

      {/* Detail panel — always shown in replay: "live state" at the present,
          "state at the replayed instant" when paused. Reflects the focused
          event so stepping prev/next gives clear feedback even when ticks cluster. */}
      <div
        className={cn(
          "mt-2 flex items-center gap-3 rounded-md border px-3 py-2 text-xs",
          selectedAt == null
            ? "border-emerald-500/30 bg-emerald-500/5"
            : "border-gold-500/30 bg-gold-500/5",
        )}
      >
        <Badge tone={selectedAt == null ? "success" : "gold"} className="shrink-0">
          {selectedAt == null ? t("liveState") : t("relitAtBadge")}
        </Badge>
        {/* The focused-event label takes the flexible middle and truncates, so a
            varying count (e.g. "Garde — 22 refus") never shifts the badge/button
            on the right. */}
        {nearest ? (
          <span className="flex min-w-0 flex-1 items-center gap-2 text-[var(--muted-foreground)]">
            <span
              className={cn("h-2 w-2 shrink-0 rounded-full", dotBg[nearest.tone as OverviewTone])}
            />
            <span className="truncate">
              {nearest.label}
              {nearest.detail && nearest.kind !== "guard_denial" ? (
                <span className="opacity-70"> · {nearest.detail}</span>
              ) : null}
            </span>
          </span>
        ) : (
          <span className="min-w-0 flex-1 truncate text-[var(--muted-foreground)]">
            {t("noEventNear")}
          </span>
        )}
        {baselineDelta != null && baseline != null ? (
          <Badge tone={baselineDelta >= 0 ? "success" : "danger"} className="shrink-0 tabular-nums">
            {baselineDelta >= 0 ? "+" : ""}
            {baselineDelta.toFixed(2)} {t("vsBaseline")} {baseline.toFixed(2)}
          </Badge>
        ) : null}
        {selectedAt != null ? (
          <button
            type="button"
            className="shrink-0 whitespace-nowrap text-blue-300 hover:underline"
            onClick={() => {
              setPlaying(false);
              setSelectedAt(null);
            }}
          >
            {t("backToNow")} →
          </button>
        ) : null}
      </div>
    </section>
  );
}

function PlaybackButton({
  label,
  onClick,
  active,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={label}
      onClick={onClick}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded text-[var(--foreground)] transition-all hover:bg-[var(--muted)] active:scale-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500/50",
        active && "bg-gold-500/20 text-gold-300",
      )}
    >
      {children}
    </button>
  );
}

function RailMarker({
  pos,
  label,
  variant,
}: {
  pos: number;
  label: string;
  variant: "baseline";
}) {
  return (
    <>
      <div
        className="pointer-events-none absolute top-1.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-slate-400 shadow-[0_0_0_4px_rgba(130,140,153,0.15)]"
        style={{ left: `${pos}%`, opacity: variant === "baseline" ? 1 : 0.8 }}
      />
      <span
        className="pointer-events-none absolute top-7 -translate-x-1/2 whitespace-nowrap text-[0.65rem] text-[var(--muted-foreground)]"
        style={{ left: `${pos}%` }}
      >
        {label}
      </span>
    </>
  );
}

function RailEvent({
  pos,
  tone,
  label,
  title,
  dim,
  onSeek,
}: {
  pos: number;
  tone: OverviewTone;
  label: string;
  title: string;
  dim?: boolean;
  onSeek: () => void;
}) {
  return (
    <button
      type="button"
      className="absolute top-1 flex -translate-x-1/2 flex-col items-center"
      style={{ left: `${pos}%` }}
      title={title}
      onPointerDown={(e) => {
        e.stopPropagation();
        onSeek();
      }}
    >
      <span
        className={cn(
          "rounded transition-all",
          dotBg[tone] ?? dotBg.info,
          dim ? "h-2.5 w-px opacity-40 hover:opacity-80" : "h-4 w-0.5 hover:w-1",
        )}
      />
      {label ? (
        <span className="mt-1.5 max-w-[7rem] truncate text-[0.6rem] font-medium text-[var(--foreground)]">
          {label}
        </span>
      ) : null}
    </button>
  );
}

/**
 * Shared temporal state for the cockpit (ADR 0011). One focused instant T drives
 * every block on the page; the cursor (selectedAt) moves continuously while the
 * value fed to the backend (committedAt) is debounced so dragging fires one
 * request per settle, not one per pixel (the backend is rate-limited). null = live.
 */
export function useTemporalState() {
  const [mode, setMode] = useState<"live" | "replay">("live");
  const [selectedAt, setSelectedAt] = useState<number | null>(null);
  const [committedAt, setCommittedAt] = useState<number | null>(null);
  const [periodKey, setPeriodKey] = useState("d7");
  useEffect(() => {
    const id = window.setTimeout(() => setCommittedAt(selectedAt), 250);
    return () => window.clearTimeout(id);
  }, [selectedAt]);
  // ISO instant fed to the as-of-T-capable queries. null in live mode → the
  // backend reads the live buffer; set → it recomputes ≤ T.
  const asOf =
    mode === "replay" && committedAt != null ? new Date(committedAt).toISOString() : null;
  const historyMode = asOf != null;
  // Mirror the temporal context so the topbar evidence pack is scoped to (period, asOf).
  useEffect(() => {
    setTemporalContext({ asOf, period: periodKey });
  }, [asOf, periodKey]);
  function changeMode(next: "live" | "replay") {
    if (next === "live") setSelectedAt(null);
    setMode(next);
  }
  return {
    mode,
    changeMode,
    selectedAt,
    setSelectedAt,
    committedAt,
    periodKey,
    setPeriodKey,
    asOf,
    historyMode,
  };
}

/**
 * The rails own axis stays live (the full scrubbable window); moving its cursor
 * sets selectedAt, which re-reads the other blocks "à T". Shared by both pages.
 */
export function useRailTimeline() {
  return useQuery({
    queryKey: ["rail-timeline"],
    queryFn: ({ signal }) => fetchTimeline(signal),
    placeholderData: keepPreviousData,
    // The timeline is an append-only history that barely moves; keep it fresh
    // across navigation between the temporal pages instead of refetching on every
    // mount, and slow the background poll right down.
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}
