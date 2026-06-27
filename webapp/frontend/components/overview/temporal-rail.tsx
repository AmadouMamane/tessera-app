"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  CalendarDays,
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
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { CalendarPopover } from "@/components/cockpit/calendar-popover";
import { endOfLocalDay } from "@/components/cockpit/window-control";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fetchDataRange, fetchTimeline } from "@/lib/api/client";
import type { TimelineReport } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { type OverviewTone, dotBg } from "@/lib/overview";
import { setTemporalContext } from "@/lib/temporal-context";
import {
  type TemporalUrlState,
  readTemporalUrl,
  useTemporalUrlPopstate,
  writeTemporalUrl,
} from "@/lib/temporal-url";

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

// Date-only (no time), for the scrubber's window-bound labels.
function fmtDay(ms: number): string {
  return new Date(ms).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
}

const PERIODS: { key: string; ms: number }[] = [
  { key: "h24", ms: 24 * 3600_000 },
  { key: "d7", ms: 7 * 24 * 3600_000 },
  { key: "d30", ms: 30 * 24 * 3600_000 },
];

/**
 * SR-01 · Signal Scrubber Rail (registre des rails temporels §4) — the temporal
 * backbone of SURVEILLER. Substrat S4 (signal series), composant C4.
 *
 * Contract (registre §5): `Rail({ code: "SR-01", scope, time: { mode }, source: S4 })`.
 * Modes are Live · Historique · Comparé (baseline) · À une date — all **signal**
 * navigation. It NEVER replays an execution: re-running a turn/trace is XT-01,
 * which lives on AGENT/Console and AGIR only (registre §3 «Replay = AGIR»). The
 * active mode is always displayed and derives from the URL (deep-link), never from
 * a hidden local state; the window DURATION is the shared global window, read here,
 * never duplicated (registre §8). The rail code is internal — never shown in the UI.
 */
export const SR_01_CODE = "SR-01" as const;

export function TemporalRail({
  mode,
  liveStatus,
  timeline,
  sloTarget,
  selectedAt,
  onSelectedAtChange,
  periodKey,
  onPeriodChange,
  windowEnd,
  onPickDate,
  onModeChange,
}: {
  mode: "live" | "history";
  liveStatus: string;
  timeline?: TimelineReport;
  sloTarget?: number;
  // Controlled by the page so the focused instant T drives every block (ADR 0011).
  selectedAt: number | null;
  onSelectedAtChange: Dispatch<SetStateAction<number | null>>;
  periodKey: string;
  /**
   * When provided, the rail OWNS the window: it renders the period selector (the
   * single owner on that page). When OMITTED, the window is owned externally by
   * the page's top toolbar control (CONTRAT RAIL) — the rail then reads
   * `periodKey` as input and shows no period selector, so it can never duplicate.
   */
  onPeriodChange?: (period: string) => void;
  /**
   * Absolute window END (ms) when the page anchors the window to a past date.
   * Defaults to the timeline's end (≈ now). The rail reads it; it never sets it
   * directly — it asks via `onPickDate`.
   */
  windowEnd?: number;
  /**
   * When provided, the rail renders the "Aller à une date" calendar (history mode):
   * picking a day emits its end-of-day ISO instant, or null when the day is
   * today/future (= back to live). The page moves the window END accordingly.
   */
  onPickDate?: (anchorEnd: string | null) => void;
  onModeChange: (mode: "live" | "history") => void;
}) {
  const t = useTranslations("overview.time");
  const [compare, setCompare] = useState("target");
  // T being viewed lives at page level; this is the rail's write handle into it.
  const setSelectedAt = onSelectedAtChange;
  const [playing, setPlaying] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  // Honest lower bound for the calendar: days before the earliest real data are
  // disabled (picking them would land on an empty window). Only fetched/used when
  // the calendar is wired (onPickDate).
  const dataRange = useDataRange();
  const minPickDate =
    onPickDate && dataRange.data?.start ? new Date(dataRange.data.start) : undefined;

  // The visible axis spans the chosen period, ending "now" — so 24h / 7d / 30d
  // each render a distinct scale. Real data may begin later than the window
  // start (we only have ~38h of history), marked by `dataStart`.
  // Window end: an externally anchored past date when given, else the timeline's
  // end (≈ now). The axis spans `periodKey` backwards from here.
  const end = windowEnd ?? (timeline ? new Date(timeline.window_end).getTime() : Date.now());
  // When the window ends on a past date, the right edge is NOT "now" but that
  // anchored day — so the cassette's ▶| and the panel link read "le plus récent"
  // (this window's latest point), not "maintenant" (which only "Revenir au direct"
  // reaches). The axis end label then shows the actual date, not "maintenant".
  const anchored = windowEnd != null;
  // Active mode, ALWAYS displayed (registre §1/§5) and derived from the position —
  // never hidden, never an implicit history switch: "À une date" when the window
  // is anchored, "Historique" while scrubbing, else "Live". A baseline comparison
  // adds "Comparé" so the framing in force is legible at a glance.
  const modeLabel = anchored
    ? t("modeAtDate")
    : selectedAt != null
      ? t("modeHistory")
      : t("modeLive");
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
    if (!playing || mode !== "history") return;
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
        {/* Period shown here only when the rail OWNS the window; when an external
            top control owns it, the period lives there (no duplication). */}
        {onPeriodChange ? (
          <>
            <span className="h-5 w-px bg-[var(--tessera-border)]" />
            <span className="text-sm text-[var(--tessera-text-muted)]">
              {t("period")} :{" "}
              <span className="font-semibold text-[var(--tessera-text)]">{t(periodKey)}</span>
            </span>
          </>
        ) : null}
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
          onClick={() => onModeChange("history")}
        >
          <History className="h-4 w-4" />
          {t("replayAtT")}
        </Button>
      </section>
    );
  }

  // Expanded time-travel rail, grouped by nature: position (viewing-at-T) · lens
  // (compare-to-baseline) · transport (fine scrub/playback + the coarse "go to a
  // date" jump, kept together) · exit, then an interactive scrubber over the real
  // lineage timeline (#201).
  const handlePos = railPos(new Date(currentT).toISOString(), viewStart, span);

  return (
    <section className="rounded-md border border-[#9a5f18]/60 bg-[var(--tessera-surface)] p-4 shadow-[var(--shadow-card)]">
      {/* Auto-sized controls (no wrap); only the "viewing-at" value is fixed-width
          so dragging the scrubber never reflows this row. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Active mode — always shown (registre §1/§5), so the page never sits in
            history without a visible indicator. */}
        <span className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-gold-500/50 bg-gold-500/10 px-3 text-xs font-semibold text-gold-200">
          <History className="h-3.5 w-3.5 shrink-0 text-gold-400" />
          {modeLabel}
          {compare !== "none" ? (
            <span className="font-medium text-gold-300/80">· {t("modeCompared")}</span>
          ) : null}
        </span>
        {/* Period selector ONLY when the rail owns the window; otherwise the top
            toolbar control is the single owner (CONTRAT RAIL). */}
        {onPeriodChange ? (
          <label className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-[var(--border)] bg-[var(--muted)]/30 px-3 text-xs text-[var(--muted-foreground)]">
            <Clock3 className="h-3.5 w-3.5 shrink-0 text-gold-400" />
            {t("period")}
            <select
              value={periodKey}
              onChange={(e) => {
                onPeriodChange(e.target.value);
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
        ) : null}
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
            label={anchored ? t("latest") : t("now")}
            onClick={() => {
              setPlaying(false);
              setSelectedAt(null);
            }}
          >
            <SkipForward className="h-3.5 w-3.5" />
          </PlaybackButton>
        </span>
        {/* "Aller à une date" sits next to the transport: it's the COARSE jump
            (moves the window END to an absolute past day, today/future = live),
            sibling to the cassette's fine scrub and to its "now" absolute jump.
            Use it to reach the right week, then scrub/play within. Only when wired. */}
        {onPickDate ? (
          <GoToDateButton
            selectedDate={new Date(currentT)}
            onPick={onPickDate}
            minDate={minPickDate}
          />
        ) : null}
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
          // Pinned flush to the right edge (not centred at 96%) so it never
          // overlaps the rightmost event/data-start label.
          <span className="pointer-events-none absolute top-7 right-0 whitespace-nowrap text-[0.65rem] font-medium text-gold-400">
            {anchored ? t("latest") : t("now")}
          </span>
        ) : null}
      </div>

      {/* Window bounds — the visible span's start → end. Restores the range
          readout we lost when the calendar moved out of the top toolbar bar: the
          right edge reads "maintenant" when live, the anchored date otherwise. */}
      <div className="mt-1 flex justify-between text-[0.6rem] tabular-nums text-[var(--muted-foreground)]">
        <span>{fmtDay(viewStart)}</span>
        <span>{anchored ? fmtDay(end) : t("now")}</span>
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
            {anchored ? t("latest") : t("backToNow")} →
          </button>
        ) : null}
      </div>
    </section>
  );
}

/**
 * The "Aller à une date" calendar, folded into the SR-01 signal scrubber. It owns only its
 * own popover (open/close + outside-click); the shared `CalendarPopover` renders
 * the grid. Picking a day emits its end-of-day instant — or null when the day is
 * today/future, which the page reads as "back to live".
 */
function GoToDateButton({
  selectedDate,
  onPick,
  minDate,
}: {
  selectedDate: Date;
  onPick: (anchorEnd: string | null) => void;
  /** Earliest day with real data; earlier days render disabled. */
  minDate?: Date;
}) {
  const t = useTranslations("overview.time");
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    function closeOnOutsidePointer(event: MouseEvent) {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-expanded={open}
        className="h-9 gap-2"
        onClick={() => setOpen((o) => !o)}
      >
        <CalendarDays className="h-4 w-4" />
        {t("goToDate")}
      </Button>
      {open ? (
        <CalendarPopover
          selectedDate={selectedDate}
          // Honest bounds: future days are meaningless for a window END
          // (today/future = live), and days before the earliest real data would
          // land on an empty window — both render disabled.
          minDate={minDate}
          maxDate={new Date()}
          onPick={(value) => {
            const eod = endOfLocalDay(value);
            if (!eod) return;
            // A day at/after today means "now" → clear the anchor (live window).
            onPick(eod.getTime() >= Date.now() ? null : eod.toISOString());
            setOpen(false);
          }}
          labels={{ prevMonth: t("prevMonth"), nextMonth: t("nextMonth") }}
          className="absolute right-0 top-[calc(100%+0.5rem)] z-50"
        />
      ) : null}
    </div>
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
  // Initial temporal state is the URL, not a private default (registre §1/§5): a
  // shared SR-01 link reopens on the same instant/window, and the mode shown
  // always matches the address bar. Period (the window duration) stays the shared
  // global window, not a URL param (registre §8 — one window owner).
  const url0 = readTemporalUrl();
  const url0At = url0.asof ? Date.parse(url0.asof) : null;
  const [mode, setMode] = useState<"live" | "history">(url0.asof || url0.win ? "history" : "live");
  const [selectedAt, setSelectedAt] = useState<number | null>(url0At);
  const [committedAt, setCommittedAt] = useState<number | null>(url0At);
  const [periodKey, setPeriodKey] = useState("d7");
  // Absolute window END (ISO, end of the picked day), or null = now (live). Set by
  // the rail's "Aller à une date" calendar so any temporal page can move its window
  // over a long history — not just the overview (which keeps its own toolbar-shared
  // anchor in the window store). The duration (periodKey) spans backwards from here.
  const [anchorEnd, setAnchorEnd] = useState<string | null>(url0.win);
  useEffect(() => {
    const id = window.setTimeout(() => setCommittedAt(selectedAt), 250);
    return () => window.clearTimeout(id);
  }, [selectedAt]);
  // Anchoring the window in the past is inherently historical → replay.
  const anchoredPast = anchorEnd != null;
  const effectiveMode: "live" | "history" = anchoredPast ? "history" : mode;
  const windowEnd = anchorEnd != null ? Date.parse(anchorEnd) : undefined;
  // ISO instant fed to the as-of-T-capable queries: a scrubbed instant wins, else
  // the window END when anchored, else null (live → backend reads the live buffer).
  const asOf =
    effectiveMode === "history" && committedAt != null
      ? new Date(committedAt).toISOString()
      : anchorEnd;
  const historyMode = asOf != null;
  // Mirror the temporal context so the topbar evidence pack is scoped to (period, asOf).
  useEffect(() => {
    setTemporalContext({ asOf, period: periodKey });
  }, [asOf, periodKey]);
  // The URL is the source of truth: mirror the committed instant + anchor into it
  // (deep-link), and follow back/forward so the state never drifts from the bar.
  useEffect(() => {
    writeTemporalUrl({
      asof: committedAt != null ? new Date(committedAt).toISOString() : null,
      win: anchorEnd,
    });
  }, [committedAt, anchorEnd]);
  useTemporalUrlPopstate(
    useCallback((s: TemporalUrlState) => {
      const at = s.asof ? Date.parse(s.asof) : null;
      setSelectedAt(at);
      setCommittedAt(at);
      setAnchorEnd(s.win);
      setMode(s.asof || s.win ? "history" : "live");
    }, []),
  );
  // Returning to live clears both the focused instant AND the past anchor.
  function changeMode(next: "live" | "history") {
    if (next === "live") {
      setSelectedAt(null);
      setAnchorEnd(null);
    }
    setMode(next);
  }
  // "Aller à une date": move the window END to the picked day and land the cursor
  // there (replay), or clear the anchor for today/future (live).
  function pickDate(nextAnchorEnd: string | null) {
    setAnchorEnd(nextAnchorEnd);
    if (nextAnchorEnd == null) {
      setSelectedAt(null);
      setMode("live");
    } else {
      setSelectedAt(Date.parse(nextAnchorEnd));
      setMode("history");
    }
  }
  return {
    mode: effectiveMode,
    changeMode,
    selectedAt,
    setSelectedAt,
    committedAt,
    periodKey,
    setPeriodKey,
    windowEnd,
    pickDate,
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

/**
 * Honest data-availability bounds for the "Aller à une date" calendar — the
 * earliest instant the cockpit holds real as-of-T data, so days before it render
 * disabled (picking them would land on an empty window). Shared across the rail.
 */
export function useDataRange() {
  return useQuery({
    queryKey: ["data-range"],
    queryFn: ({ signal }) => fetchDataRange(signal),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}
