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
import { useWindowStore } from "@/lib/stores/window-store";
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

// Minute-precision instant (full year), for the selected-event "État au {T}"
// badge — a focused instant must always carry a clear, readable date/time
// (registre §4: never a metric without a clear instant).
function fmtInstant(ms: number): string {
  return new Date(ms).toLocaleString(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
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
  reading,
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
  embedded = false,
  compare: compareProp,
  onCompareChange,
  viewLabel,
  transport = "signal",
}: {
  mode: "live" | "history";
  /**
   * The human reading (registre §4): "asof" needs an instant before any state can
   * be reconstructed, so the rail must know it to render the honest empty state
   * ("Instant non sélectionné") instead of a live/score panel. Optional — the
   * standalone rail (other SURVEILLER pages) omits it and keeps the two-valued mode.
   */
  reading?: Reading;
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
  /**
   * When embedded inside the SignalCommandBar, the rail renders ONLY the scrubber
   * panel (timeline · legend · detail · playback) — the labeled controls (mode /
   * période / comparer / aller-à-une-date / exit) live in the command bar, so they
   * are never duplicated. Default false = the standalone full rail.
   */
  embedded?: boolean;
  /** Controlled baseline ("target"|"now"|"none"); when set the command bar owns it. */
  compare?: string;
  onCompareChange?: (value: string) => void;
  /**
   * Mode-specific "Vue" badge text computed by the command bar (Maintenant / État
   * au {T} / Période {from} → {to}). When provided it overrides the raw instant so
   * the badge never duplicates "Lecture" nor shows a single instant in Historique.
   */
  viewLabel?: string;
  /**
   * Which transport the rail renders (registre des rails temporels):
   * - "signal" (default, **SR-01** / SURVEILLER + monitoring) — event-level
   *   navigation only (Événement précédent/suivant); NO video-player cassette,
   *   no replay — it scrubs persisted signals as-of-T.
   * - "execution" (**XT-01** home: AGIR / Replay) — the legitimate replay cassette
   *   (début · précédent · play/pause · suivant · fin) over the run's steps. This
   *   stays OFF every SURVEILLER surface; only AGIR/Replay opts in.
   */
  transport?: "signal" | "execution";
}) {
  const t = useTranslations("overview.time");
  // Playback state — only ever used by the execution (XT-01) transport; the signal
  // transport never plays (registre §replay = AGIR only).
  const [playing, setPlaying] = useState(false);
  const [compareLocal, setCompareLocal] = useState("target");
  const compare = compareProp ?? compareLocal;
  const setCompare = onCompareChange ?? setCompareLocal;
  // T being viewed lives at page level; this is the rail's write handle into it.
  const setSelectedAt = onSelectedAtChange;
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
  // Real-or-honest-empty: each baseline resolves to a value only when its source
  // is actually computable (the SLO target, or a present score). No hardcoded
  // fallback (the old `?? 0.8` fabricated a target when none was known) — an
  // uncomputable baseline is null, so the delta badge is simply hidden.
  const baseline =
    compare === "none" ? null : compare === "now" ? presentScore : (sloTarget ?? null); // "target"
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

  // "À un instant" before a day is picked: signals can't be reconstructed yet, so
  // the rail shows an honest empty state (no score, no computed state, no PROUVER
  // link, no live framing) — only the prompt to choose an instant. Derived, never
  // a hidden flag. When `reading` is omitted (standalone rail) this stays false.
  const awaitingInstant = reading === "asof" && selectedAt == null && !anchored;
  // A genuine LIVE snapshot (green "État live") only when the present is what's on
  // screen: no instant scrubbed AND the reading is Maintenant. Historique without a
  // scrub reads the current end-of-period state under a neutral label (registre §9).
  const liveSnapshot = selectedAt == null && mode === "live";

  // Event-level navigation (signals, not a video player): jump the cursor to the
  // real event immediately before / after the focused instant. This replaces the
  // cassette transport — SR-01 navigates signals, it never replays an execution.
  const eventTimes = events
    .map((e) => new Date(e.at).getTime())
    .filter((v) => Number.isFinite(v))
    .sort((a, b) => a - b);
  const prevEventT = eventTimes.filter((v) => v < currentT - 1000).pop() ?? null;
  const nextEventT = eventTimes.find((v) => v > currentT + 1000) ?? null;
  function seekToEvent(at: number | null) {
    if (at == null) return;
    setSelectedAt(at >= end - 1000 ? null : at);
  }

  // Execution-transport playback (XT-01 only): sweep T across the run; reaching the
  // end stops at the latest. The signal transport never plays — this is inert there.
  useEffect(() => {
    if (transport !== "execution" || !playing || mode !== "history") return;
    const id = window.setInterval(() => {
      setSelectedAt((cur) => {
        const from = cur ?? dataStart;
        const nextT = from + span / 90;
        return nextT >= end ? null : nextT;
      });
    }, 60);
    return () => window.clearInterval(id);
  }, [transport, playing, mode, dataStart, span, end, setSelectedAt]);
  useEffect(() => {
    if (selectedAt == null && playing) setPlaying(false);
  }, [selectedAt, playing]);

  // Compact Live rail (default): real-time badge, period, last update, Relire à T.
  // Skipped when embedded in the command bar (which renders only the panel body).
  if (mode === "live" && !embedded) {
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
    <section
      className={cn(
        embedded
          ? "pt-1"
          : "rounded-md border border-[#9a5f18]/60 bg-[var(--tessera-surface)] p-4 shadow-[var(--shadow-card)]",
      )}
    >
      {/* Auto-sized controls (no wrap); only the "viewing-at" value is fixed-width
          so dragging the scrubber never reflows this row. Embedded: the labeled
          controls live in the command bar, so only viewing-at + playback show. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Active mode — always shown (registre §1/§5), so the page never sits in
            history without a visible indicator. */}
        {embedded ? null : (
          <span className="flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border border-gold-500/50 bg-gold-500/10 px-3 text-xs font-semibold text-gold-200">
            <History className="h-3.5 w-3.5 shrink-0 text-gold-400" />
            {modeLabel}
            {compare !== "none" ? (
              <span className="font-medium text-gold-300/80">· {t("modeCompared")}</span>
            ) : null}
          </span>
        )}
        {/* Period selector ONLY when the rail owns the window; otherwise the top
            toolbar control is the single owner (CONTRAT RAIL). */}
        {!embedded && onPeriodChange ? (
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
        {/* "Vue :" badge — only on the standalone rail; embedded, the command bar's
            contextual header carries the reading + short title, so repeating it here
            would duplicate "Lecture"/"Vue" (registre §14). */}
        {embedded ? null : (
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
              {viewLabel ?? (selectedAt == null ? t("nowLive") : fmtStamp(currentT))}
            </b>
          </span>
        )}
        {embedded ? null : (
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
        )}
        {/* Transport — two DISTINCT registres, never mixed:
            · "signal" (SR-01 / SURVEILLER) → event navigation only (no player).
            · "execution" (XT-01 / AGIR·Replay) → the legitimate replay cassette. */}
        {transport === "execution" ? (
          <ExecutionReplayControls
            t={t}
            playing={playing}
            anchored={anchored}
            atStart={selectedAt == null}
            onFirst={() => {
              setPlaying(false);
              setSelectedAt(viewStart);
            }}
            onPrev={() => {
              setPlaying(false);
              step(-1);
            }}
            onPlayPause={() => {
              if (selectedAt == null) setSelectedAt(dataStart);
              setPlaying((p) => !p);
            }}
            onNext={() => {
              setPlaying(false);
              step(1);
            }}
            onLatest={() => {
              setPlaying(false);
              setSelectedAt(null);
            }}
          />
        ) : (
          <SignalEventNavigation
            t={t}
            prevDisabled={prevEventT == null}
            nextDisabled={nextEventT == null}
            onPrev={() => seekToEvent(prevEventT)}
            onNext={() => seekToEvent(nextEventT)}
          />
        )}
        {/* "Aller à une date" — the COARSE jump (moves the window END to an absolute
            past day, today/future = live). Only on the standalone rail when wired;
            embedded, the command bar renders it below the panel. */}
        {!embedded && onPickDate ? (
          <GoToDateButton
            selectedDate={new Date(currentT)}
            onPick={onPickDate}
            minDate={minPickDate}
          />
        ) : null}
        {embedded ? null : (
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
        )}
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
        {/* event markers (click to seek): NO inline labels — they overlapped when
            events clustered (registre §15). Every event is a coloured tick with a
            full tooltip on hover; the default-visible labels stay just "début
            données" / the focused instant (playhead) / "maintenant". */}
        {events.map((ev, i) => {
          // Guard denials carry no useful detail (target is always "user_input").
          const detail = ev.kind === "guard_denial" ? "" : ev.detail;
          return (
            <RailEvent
              key={`${ev.at}-${ev.kind}-${i}`}
              pos={railPos(ev.at, viewStart, span)}
              tone={ev.tone as OverviewTone}
              label=""
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
        {/* The active instant T, labelled AT the playhead so it is immediately
            obvious which marker is selected (not just a bare tick on the right).
            Edge-aware: anchored right when T sits in the last third so the pill
            never overflows the track. */}
        {selectedAt != null ? (
          <span
            title={t("selectedInstant")}
            className="pointer-events-none absolute top-7 z-10 flex flex-col whitespace-nowrap leading-tight"
            style={
              handlePos > 65
                ? { right: `${100 - handlePos}%` }
                : { left: `${handlePos}%`, transform: "translateX(-50%)" }
            }
          >
            <span className="text-[0.55rem] font-medium uppercase tracking-wide text-gold-400/80">
              {t("selectedInstant")}
            </span>
            <span className="tabular-nums text-[0.62rem] font-semibold text-gold-300">
              {fmtInstant(currentT)}
            </span>
          </span>
        ) : null}
        {selectedAt == null && !awaitingInstant ? (
          // Pinned flush to the right edge (not centred at 96%) so it never
          // overlaps the rightmost event/data-start label. Hidden while awaiting an
          // instant: there's no "now" framing until a point in time is chosen.
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

      {/* Detail panel. "À un instant" before a day is picked shows an HONEST empty
          state — no score, no computed state, no live framing (registre §6); only
          the prompt to choose an instant. Otherwise: "live state" at the present,
          "state at the chosen instant" when scrubbing, reflecting the focused event.
          The single "Revenir au direct" lives in the command bar (registre §11), so
          this panel no longer carries its own back-to-now link. */}
      {awaitingInstant ? (
        <div className="mt-2 flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--muted)]/20 px-3 py-2 text-xs text-[var(--muted-foreground)]">
          <Flag className="h-3.5 w-3.5 shrink-0 text-gold-400/70" />
          <span className="min-w-0 truncate">{t("microPickInstant")}</span>
        </div>
      ) : (
        <div
          className={cn(
            "mt-2 flex items-center gap-3 rounded-md border px-3 py-2 text-xs",
            selectedAt != null
              ? "border-gold-500/30 bg-gold-500/5"
              : liveSnapshot
                ? "border-emerald-500/30 bg-emerald-500/5"
                : "border-[var(--border)] bg-[var(--muted)]/20",
          )}
        >
          {/* A chosen instant ALWAYS carries its date/time (registre §2/§4): the
              badge reads "État au {timestamp}", never a bare "État à l'instant" — so
              "Garde — 22 refus" is never shown without a clear instant. "État live"
              only in Maintenant (§8/§9); Historique unscrubbed reads the current
              end-of-period state under the neutral "Sur la période" label. */}
          <Badge
            tone={selectedAt != null ? "gold" : liveSnapshot ? "success" : "neutral"}
            className="shrink-0 tabular-nums"
          >
            {selectedAt != null
              ? t("microStateAt", { time: fmtInstant(currentT) })
              : liveSnapshot
                ? t("liveState")
                : t("periodState")}
          </Badge>
          {/* The focused-event label takes the flexible middle and truncates, so a
              varying count (e.g. "Garde — 22 refus") never shifts the badge on the
              right. A scrubbed instant prefixes "Événement sélectionné ·" so the line
              reads "État au {T} · Événement sélectionné · Garde — 22 refus". */}
          {nearest ? (
            <span className="flex min-w-0 flex-1 items-center gap-2 text-[var(--muted-foreground)]">
              <span
                className={cn("h-2 w-2 shrink-0 rounded-full", dotBg[nearest.tone as OverviewTone])}
              />
              <span className="truncate">
                {selectedAt != null ? (
                  <span className="opacity-70">{t("selectedEvent")} · </span>
                ) : null}
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
            <Badge
              tone={baselineDelta >= 0 ? "success" : "danger"}
              className="shrink-0 tabular-nums"
            >
              {baselineDelta >= 0 ? "+" : ""}
              {baselineDelta.toFixed(2)} {t("vsBaseline")} {baseline.toFixed(2)}
            </Badge>
          ) : null}
        </div>
      )}
    </section>
  );
}

/**
 * The "Aller à une date" calendar, folded into the SR-01 signal scrubber. It owns only its
 * own popover (open/close + outside-click); the shared `CalendarPopover` renders
 * the grid. Picking a day emits its end-of-day instant — or null when the day is
 * today/future, which the page reads as "back to live".
 */
export function GoToDateButton({
  selectedDate,
  onPick,
  minDate,
  label,
}: {
  selectedDate: Date;
  onPick: (anchorEnd: string | null) => void;
  /** Earliest day with real data; earlier days render disabled. */
  minDate?: Date;
  /** Trigger label override (e.g. "Aller à un instant" in À-un-instant reading). */
  label?: string;
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
        {label ?? t("goToDate")}
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
          // Left-aligned: the button sits at the LEFT of the command-bar panel, so
          // right-0 made the 292px calendar extend left under the sidebar (clipping
          // the month header). left-0 keeps it inside the content area.
          className="absolute left-0 top-[calc(100%+0.5rem)] z-50"
        />
      ) : null}
    </div>
  );
}

type Translate = ReturnType<typeof useTranslations>;

/**
 * SR-01 transport — signal **event** navigation (no player). Two buttons that jump
 * the cursor to the previous / next real signal event; never a video-player
 * cassette (that is execution replay, XT-01). Used on every SURVEILLER + monitoring
 * surface.
 */
function SignalEventNavigation({
  t,
  prevDisabled,
  nextDisabled,
  onPrev,
  onNext,
}: {
  t: Translate;
  prevDisabled: boolean;
  nextDisabled: boolean;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <span className="ml-auto flex h-9 shrink-0 items-center gap-1 rounded-lg border border-[var(--border)] px-1 text-[var(--muted-foreground)]">
      <EventNavButton label={t("eventPrev")} disabled={prevDisabled} onClick={onPrev}>
        <ChevronLeft className="h-4 w-4" />
      </EventNavButton>
      <EventNavButton label={t("eventNext")} disabled={nextDisabled} onClick={onNext}>
        <ChevronRight className="h-4 w-4" />
      </EventNavButton>
    </span>
  );
}

/**
 * XT-01 transport — the legitimate execution-replay cassette (début · précédent ·
 * play/pause · suivant · fin). Distinct from SR-01's event navigation and rendered
 * ONLY by the execution transport (AGIR / Replay), never on a SURVEILLER surface.
 */
function ExecutionReplayControls({
  t,
  playing,
  anchored,
  atStart,
  onFirst,
  onPrev,
  onPlayPause,
  onNext,
  onLatest,
}: {
  t: Translate;
  playing: boolean;
  anchored: boolean;
  atStart: boolean;
  onFirst: () => void;
  onPrev: () => void;
  onPlayPause: () => void;
  onNext: () => void;
  onLatest: () => void;
}) {
  return (
    <span className="ml-auto flex h-9 shrink-0 items-center gap-1 rounded-lg border border-[var(--border)] px-2 text-[var(--muted-foreground)]">
      <TransportButton label={t("first")} onClick={onFirst}>
        <SkipBack className="h-3.5 w-3.5" />
      </TransportButton>
      <TransportButton label={t("prev")} onClick={onPrev}>
        <ChevronLeft className="h-4 w-4" />
      </TransportButton>
      <TransportButton
        label={playing ? t("pause") : t("play")}
        active={playing}
        onClick={onPlayPause}
      >
        {playing ? (
          <Pause className="h-4 w-4 text-gold-400" />
        ) : (
          <PlayCircle className="h-4 w-4 text-gold-400" />
        )}
      </TransportButton>
      <TransportButton label={t("next")} onClick={onNext}>
        <ChevronRight className="h-4 w-4" />
      </TransportButton>
      <TransportButton
        label={anchored ? t("latest") : t("now")}
        disabled={atStart}
        onClick={onLatest}
      >
        <SkipForward className="h-3.5 w-3.5" />
      </TransportButton>
    </span>
  );
}

/** A single event-navigation button (previous / next signal event). */
function EventNavButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded text-[var(--foreground)] transition-all hover:bg-[var(--muted)] active:scale-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500/50 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}

/** A single replay-cassette transport button (XT-01). */
function TransportButton({
  label,
  onClick,
  active,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded text-[var(--foreground)] transition-all hover:bg-[var(--muted)] active:scale-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold-500/50 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent",
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
/** SR-01 reading mode (registre §4): how the page reads the signal series. */
export type Reading = "live" | "asof" | "historique";

export function useTemporalState() {
  // The WINDOW (duration + absolute end) and the comparison lens are the shared
  // GLOBAL window dimensions (registre §5/§8, one owner) — read here so they follow
  // the user across every SURVEILLER page AND mirror into the URL below.
  const periodKey = useWindowStore((s) => s.period);
  const setPeriodKey = useWindowStore((s) => s.setPeriod);
  const anchorEnd = useWindowStore((s) => s.anchorEnd);
  const setAnchorEnd = useWindowStore((s) => s.setAnchorEnd);
  const compare = useWindowStore((s) => s.compare);
  const setCompare = useWindowStore((s) => s.setCompare);
  // The temporal NAVIGATION (reading + instant T + period + compare + expanded) is
  // the URL — the reproducible source of truth (registre §1/§5): a shared link
  // reopens on the exact same view, and the reading always matches the address bar.
  // Start at the live default on BOTH the server and the first client render, then
  // hydrate the whole temporal state from the URL in a mount-only effect. Reading
  // the URL during render (useState init) would diverge server (no window → live)
  // from client (params) → a hydration mismatch; deferring it to an effect is
  // SSR-safe at the cost of a one-frame live flash on a deep-link.
  const [reading, setReadingState] = useState<Reading>("live");
  const [selectedAt, setSelectedAt] = useState<number | null>(null);
  const [committedAt, setCommittedAt] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<boolean>(false);
  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only hydrate.
  useEffect(() => {
    const u = readTemporalUrl();
    if (u.period) setPeriodKey(u.period);
    if (u.compare) setCompare(u.compare);
    const instant = u.reading === "asof" ? u.asof : u.at;
    const at = instant ? Date.parse(instant) : null;
    setSelectedAt(at);
    setCommittedAt(at);
    if (u.reading === "asof" && u.asof) setAnchorEnd(u.asof);
    else if (u.reading === "historique" && u.to) setAnchorEnd(u.to);
    setReadingState(u.reading);
    setExpanded(u.expanded);
  }, []);
  useEffect(() => {
    const id = window.setTimeout(() => setCommittedAt(selectedAt), 250);
    return () => window.clearTimeout(id);
  }, [selectedAt]);
  const windowEnd = anchorEnd != null ? Date.parse(anchorEnd) : undefined;
  // Legacy two-valued mode kept for the scrubber panel: live vs everything else.
  const mode: "live" | "history" = reading === "live" ? "live" : "history";
  // ISO instant fed to the as-of-T-capable queries: As-of reads the anchored day;
  // Historique reads the scrubbed instant; Live reads the live buffer (null).
  const asOf =
    reading === "asof"
      ? anchorEnd
      : reading === "historique" && committedAt != null
        ? new Date(committedAt).toISOString()
        : null;
  const historyMode = asOf != null;
  // Mirror the temporal context so the evidence pack/report is scoped to (period, asOf).
  useEffect(() => {
    setTemporalContext({ asOf, period: periodKey });
  }, [asOf, periodKey]);
  // The URL is the source of truth: mirror the WHOLE reproducible state into it.
  // Skip the very first run (the URL already reflects the initial state) so we
  // never strip the params we just read before the store-restore commits.
  const didMount = useRef(false);
  useEffect(() => {
    if (!didMount.current) {
      didMount.current = true;
      return;
    }
    writeTemporalUrl({
      reading,
      period: periodKey,
      asof: reading === "asof" ? anchorEnd : null,
      at:
        reading === "historique" && committedAt != null
          ? new Date(committedAt).toISOString()
          : null,
      to: reading === "historique" ? anchorEnd : null,
      compare,
      expanded,
    });
  }, [reading, periodKey, anchorEnd, committedAt, compare, expanded]);
  useTemporalUrlPopstate(
    useCallback(
      (s: TemporalUrlState) => {
        const instant = s.reading === "asof" ? s.asof : s.at;
        const at = instant ? Date.parse(instant) : null;
        setSelectedAt(at);
        setCommittedAt(at);
        setAnchorEnd(s.reading === "asof" ? s.asof : s.reading === "historique" ? s.to : null);
        setReadingState(s.reading);
        setPeriodKey(s.period ?? "d7");
        setCompare(s.compare ?? "target");
        setExpanded(s.expanded);
      },
      [setAnchorEnd, setPeriodKey, setCompare],
    ),
  );
  // Switch the reading (the "Lecture" control), clearing what no longer applies.
  function setReading(next: Reading) {
    setReadingState(next);
    if (next === "live") {
      setSelectedAt(null);
      setCommittedAt(null);
      setAnchorEnd(null);
    } else if (next === "historique") {
      setAnchorEnd(null); // scrub from now over the period
    }
    // "asof" keeps the anchor; the user picks the day via "Aller à une date".
  }
  // "Aller à une date" (As-of): move the window END to the picked day, or clear it
  // (today/future) → back to live.
  function pickDate(nextAnchorEnd: string | null) {
    setAnchorEnd(nextAnchorEnd);
    if (nextAnchorEnd == null) {
      setSelectedAt(null);
      setReadingState("live");
    } else {
      setSelectedAt(Date.parse(nextAnchorEnd));
      setReadingState("asof");
    }
  }
  // Back-compat with the scrubber panel's live/history toggle.
  function changeMode(next: "live" | "history") {
    setReading(next === "live" ? "live" : "historique");
  }
  return {
    mode,
    reading,
    setReading,
    changeMode,
    selectedAt,
    setSelectedAt,
    committedAt,
    periodKey,
    setPeriodKey,
    anchorEnd,
    windowEnd,
    pickDate,
    asOf,
    historyMode,
    compare,
    setCompare,
    expanded,
    setExpanded,
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
