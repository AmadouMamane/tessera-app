"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  Flag,
  History,
  Milestone,
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
import { Truncate } from "@/components/ui/truncate";
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
  // PREVIEW vs ACTIVE instant. While hovering/dragging the scrubber the cursor is a
  // PREVIEW ("Aperçu au {T}") — local only: it never touches selectedAt, so the
  // command bar, micro-line, URL and PROUVER link stay on the committed (active)
  // instant. On release the preview is committed to selectedAt ("État au {T}"). A
  // ref mirrors it so the pointer-up handler reads the latest drag position.
  const [previewAt, setPreviewAt] = useState<number | null>(null);
  const previewRef = useRef<number | null>(null);
  const setPreview = useCallback((at: number | null) => {
    previewRef.current = at;
    setPreviewAt(at);
  }, []);
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
  // Only the two references with a real source on this surface resolve to a value;
  // the rest (none / previous_period / baseline / previous_release) have no
  // computable baseline here, so they show NO delta — never a fake vs-target number
  // dressed up under another label (matches the bar's disabled-with-reason chip).
  const baseline =
    compare === "target" ? (sloTarget ?? null) : compare === "now" ? presentScore : null;
  // Score nearest the focused instant (present included), for the vs-baseline delta.
  const nearestScore = scorePoints.reduce<{ v: number; d: number } | null>((best, p) => {
    const d = Math.abs(p.at - currentT);
    return !best || d < best.d ? { v: p.v, d } : best;
  }, null);
  const baselineDelta = baseline != null && nearestScore != null ? nearestScore.v - baseline : null;

  function instantFromClientX(clientX: number): number {
    const el = trackRef.current;
    if (!el) return end;
    const rect = el.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return viewStart + frac * span;
  }
  // Commit an instant as the ACTIVE one (propagates to selectedAt → command bar /
  // micro-line / URL / PROUVER), and KEEP the active mode honest (registre §1/§3:
  // mode == content). In Live the playhead stays at "maintenant"; the moment a PAST
  // instant is committed (drag, click, keyboard, event-jump) the reading flips to
  // Historique — Live + "État au {passé}" is forbidden. At/after the right edge means
  // "back to live" (null), which never promotes, so returning to the present stays
  // Live. Every scrub/seek path routes through here, so there is a single rule.
  function applyInstant(at: number | null) {
    const norm = at != null && at >= end - 1000 ? null : at;
    if (norm != null && mode === "live") onModeChange("history");
    setSelectedAt(norm);
  }
  function step(dir: -1 | 1) {
    const nextT = Math.min(end, Math.max(viewStart, currentT + dir * stepUnit));
    applyInstant(nextT);
  }
  // Event nearest the focused instant (present included), for the detail panel.
  const nearest =
    events.reduce<{ ev: TimelineReport["events"][number]; d: number } | null>((best, ev) => {
      const d = Math.abs(new Date(ev.at).getTime() - currentT);
      return !best || d < best.d ? { ev, d } : best;
    }, null)?.ev ?? null;

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
    applyInstant(at);
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
      // Instrument surface (sr01-strip): a rail is a temporal control instrument,
      // visually distinct from the page's content cards — same lacquered chrome
      // as the SURVEILLER command bar, in compact form.
      <section className="sr01-strip flex min-h-[46px] flex-wrap items-center gap-3 rounded-2xl px-3 py-2 backdrop-blur-md">
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
          className="h-8 border-[#9a5f18] bg-transparent px-4 text-[var(--tessera-fg-warning)] hover:bg-[#3e260c]/35"
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
  // The playhead follows the PREVIEW while dragging, else the active instant.
  const displayAt = previewAt ?? currentT;
  const handlePos = railPos(new Date(displayAt).toISOString(), viewStart, span);
  // Real data may begin after the window start; when so, a "début données" marker
  // sits where it starts. Computed once so the window-bound labels can also stay
  // clear of it and the playhead.
  const showDataStart = !!timeline && dataStart > viewStart + span * 0.01;
  // "À un instant" before a day is picked: the rail shows an honest empty state
  // (no live "now" framing) — so the right window bound stays unlabelled until an
  // instant is chosen. Derived; false on the standalone rail (no `reading`).
  const awaitingInstant = reading === "asof" && selectedAt == null && !anchored;
  // The focused instant outranks the window bounds: when its label would sit on
  // top of a bound (playhead pinned to an edge) we drop that bound so the instant
  // never collides with "début période" / "maintenant" (registre §5).
  const headActive = previewAt != null || selectedAt != null;
  const hideStartBound = headActive && handlePos < 14;
  // Hide "maintenant" when the focused-instant label would sit on it, OR while
  // awaiting an instant (no live framing yet).
  const hideEndBound = (headActive && handlePos > 86) || awaitingInstant;
  // The "début données" label shares the playhead's label row, so when the focused
  // instant lands on top of the data-start marker we drop that (secondary) label —
  // the gold instant label wins (registre §5: priority to the selected instant).
  const dataStartPos = showDataStart
    ? railPos(new Date(dataStart).toISOString(), viewStart, span)
    : null;
  const hideDataStartLabel =
    headActive && dataStartPos != null && Math.abs(handlePos - dataStartPos) < 12;
  // SR-01 (signal) gets the temporal-instrument signature — a cool cyan axis and a
  // champagne-haloed selected instant. The execution transport (XT-01 replay)
  // keeps its existing neutral look untouched, so this stays gated on `isSignal`.
  const isSignal = transport === "signal";
  const instantActive = isSignal && selectedAt != null && previewAt == null;

  // SR-01 event navigation (signal transport only) — a labelled "Événements"
  // capsule, NOT a player. Defined once and placed by context: anchored under the
  // axis (in the legend row) when embedded in the command bar, otherwise inline
  // with the labeled controls on the standalone rail. Never rendered for the
  // execution transport (XT-01 keeps its cassette).
  const signalNav = (
    <SignalEventNavigation
      t={t}
      prevDisabled={prevEventT == null}
      nextDisabled={nextEventT == null}
      noEvents={events.length === 0}
      onPrev={() => seekToEvent(prevEventT)}
      onNext={() => seekToEvent(nextEventT)}
    />
  );

  return (
    <section
      className={cn(
        embedded
          ? "pt-0"
          : // Standalone expanded rail: the same lacquered instrument surface as
            // the SURVEILLER command bar (sr01-strip) — a rail must read as the
            // page's temporal instrument, never as one more content card.
            "sr01-strip sr01-strip-expanded rounded-2xl p-4 backdrop-blur-md",
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
        ) : embedded ? null : (
          // Embedded (SR-01 command bar): the nav is anchored under the axis in the
          // legend row, so it is NOT rendered here (the row would otherwise hold a
          // single lone capsule floating top-right). Standalone rail keeps it inline.
          signalNav
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
        className="relative mt-3 h-[3.25rem] cursor-pointer select-none"
        onPointerDown={(e) => {
          setPlaying(false);
          trackRef.current?.setPointerCapture(e.pointerId);
          // Start a PREVIEW (not committed yet) — drag refines it.
          setPreview(instantFromClientX(e.clientX));
        }}
        onPointerMove={(e) => {
          if (e.buttons === 1) setPreview(instantFromClientX(e.clientX));
        }}
        onPointerUp={(e) => {
          trackRef.current?.releasePointerCapture?.(e.pointerId);
          // Release COMMITS the preview as the active instant.
          const at = previewRef.current;
          setPreview(null);
          if (at != null) applyInstant(at);
        }}
        onPointerCancel={() => setPreview(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") step(1);
          if (e.key === "ArrowLeft") step(-1);
        }}
      >
        {/* No diffuse glow/halo under the axis (removed on purpose): a premium-black
            instrument keeps its shine on the crisp axis line itself + the champagne
            instant, never a pool of light around the timeline. */}
        {/* The active temporal axis — for SR-01 (signal) a fine, luminous cyan thread
            (bright core, faint glow + a crisp dark underline so it lifts off the
            glow) so it reads as the page's precious time axis, not a card border. The
            execution transport keeps the neutral rail. */}
        <div
          className={cn(
            "pointer-events-none absolute inset-x-0 top-2.5 rounded-full",
            isSignal
              ? "h-px bg-[linear-gradient(90deg,rgba(96,194,242,0.06),rgba(96,194,242,0.40)_22%,rgba(170,222,250,0.82)_50%,rgba(96,194,242,0.40)_78%,rgba(96,194,242,0.06))] shadow-[0_0_15px_rgba(96,194,242,0.34),0_0_1px_rgba(255,255,255,0.36),0_1px_0_rgba(0,0,0,0.45),inset_0_1px_0_rgba(255,255,255,0.18)]"
              : "h-0.5 bg-[linear-gradient(90deg,#363d48,#454e5d)]",
          )}
        />
        {/* Window-bound ticks + labels — anchored to the axis ends so the window's
            extent reads as the axis itself (registre §4), not as labels floating
            beneath it. Each is a discreet tick crossing the line with its date
            just under it; faint, so the focused instant always stays dominant.
            The right end is "maintenant" when live / the anchored date otherwise,
            and is shown ONLY here — no second floating bounds row below the axis. */}
        {!hideStartBound ? (
          <>
            <span className="pointer-events-none absolute left-0 top-1.5 h-2.5 w-px bg-[var(--tessera-border-strong)]" />
            <span className="pointer-events-none absolute left-0 top-5 whitespace-nowrap text-[0.6rem] tabular-nums text-[var(--muted-foreground)] opacity-70">
              {fmtDay(viewStart)}
            </span>
          </>
        ) : null}
        {!hideEndBound ? (
          <>
            <span className="pointer-events-none absolute right-0 top-1.5 h-2.5 w-px bg-[var(--tessera-border-strong)]" />
            <span className="pointer-events-none absolute right-0 top-5 whitespace-nowrap text-[0.6rem] tabular-nums text-[var(--muted-foreground)] opacity-70">
              {anchored ? fmtDay(end) : t("now")}
            </span>
          </>
        ) : null}
        {/* Data-availability marker — where real data BEGINS, NOT a period bound
            (those are the discreet dates at the axis ends) and NOT a comparison
            baseline. Styled distinctly (hollow ring + data glyph + tooltip). */}
        {showDataStart ? (
          <RailMarker
            pos={dataStartPos ?? 0}
            label={t("dataStart")}
            title={t("dataStartTooltip")}
            hideLabel={hideDataStartLabel}
            signal={isSignal}
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
              onSeek={() => applyInstant(new Date(ev.at).getTime())}
            />
          );
        })}
        {/* the moving head — a slim downward caret crowning a thin gold stem.
            The single time readout lives in the "Tu regardes" box. */}
        <div
          className="pointer-events-none absolute top-0 -translate-x-1/2 transition-opacity"
          style={{
            left: `${handlePos}%`,
            opacity: previewAt != null || selectedAt != null ? 1 : 0.6,
          }}
        >
          {/* Champagne tick on the axis — the single most legible point once an
              instant is committed (a glowing halo, not while previewing). */}
          {instantActive ? (
            <span className="absolute left-1/2 top-1.5 h-2 w-2 -translate-x-1/2 rounded-full bg-[radial-gradient(circle_at_35%_30%,#fdecca,#e4c178_72%)] shadow-[0_0_0_1px_rgba(255,242,208,0.66),0_0_0_3px_rgba(231,199,127,0.16),0_0_18px_rgba(233,201,128,0.36)]" />
          ) : null}
          {/* stem centred vertically on the timeline track (10–14px → centre 12px) */}
          <span className="absolute left-1/2 top-1.5 h-3 w-px -translate-x-1/2 bg-gold-400" />
          <span className="absolute left-1/2 top-[-1px] h-0 w-0 -translate-x-1/2 border-l-[5px] border-r-[5px] border-t-[7px] border-l-transparent border-r-transparent border-t-gold-400 drop-shadow-[0_1px_2px_rgba(0,0,0,0.45)]" />
        </div>
        {/* Playhead label, AT the playhead and edge-aware (anchored right in the
            last third so the pill never overflows). PREVIEW while hovering/dragging
            ("Aperçu au {T}", muted) — never "Instant sélectionné"; the committed
            ACTIVE instant otherwise ("Instant sélectionné · {T}", gold). Only one
            of the two ever shows, so two timestamps are never active at once. */}
        {previewAt != null ? (
          <span
            className="pointer-events-none absolute top-7 z-10 flex flex-col whitespace-nowrap leading-tight"
            style={
              handlePos > 65
                ? { right: `${100 - handlePos}%` }
                : { left: `${handlePos}%`, transform: "translateX(-50%)" }
            }
          >
            <span className="text-[0.55rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {t("previewLabel")}
            </span>
            <span className="tabular-nums text-[0.62rem] font-semibold text-gold-200/80">
              {fmtInstant(previewAt)}
            </span>
          </span>
        ) : selectedAt != null ? (
          <span
            title={t("selectedInstant")}
            className="pointer-events-none absolute top-7 z-10 flex flex-col whitespace-nowrap leading-tight"
            style={
              handlePos > 65
                ? { right: `${100 - handlePos}%` }
                : { left: `${handlePos}%`, transform: "translateX(-50%)" }
            }
          >
            <span
              className={cn(
                "text-[0.55rem] font-medium uppercase tracking-wide text-gold-400/80",
                isSignal && "[text-shadow:0_0_12px_rgba(232,201,130,0.24)]",
              )}
            >
              {t("selectedInstant")}
            </span>
            <span
              className={cn(
                "tabular-nums text-[0.62rem] font-semibold",
                isSignal
                  ? "text-gold-200 [text-shadow:0_0_16px_rgba(232,201,130,0.26)]"
                  : "text-gold-300",
              )}
            >
              {fmtInstant(currentT)}
            </span>
          </span>
        ) : null}
      </div>

      {/* Legend — what the scrubber ticks mean. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.62rem] text-[var(--muted-foreground)]">
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
        {/* Event navigation anchored here (embedded) — directly under the axis,
            paired with the legend, so it reads as a timeline control, not a lone
            floating capsule above the rail. */}
        {embedded ? signalNav : null}
      </div>

      {/* Detail panel = the SELECTED-event detail only. Embedded (SR-01 command
          bar), when nothing is selected the synthetic state already lives in the
          micro-line, so the panel is hidden — no redundant "État live" / "Sur la
          période" / "choose an instant" line. A chosen instant shows "État au {T} ·
          Événement sélectionné · …". The standalone rail (no command bar) keeps the
          state line so it is never information-less. */}
      {embedded && selectedAt == null ? null : (
        <div
          className={cn(
            "mt-1 flex items-center gap-3 rounded-md border px-3 py-1.5 text-xs",
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
              <Truncate
                full={`${selectedAt != null ? `${t("selectedEvent")} · ` : ""}${nearest.label}${nearest.detail && nearest.kind !== "guard_denial" ? ` · ${nearest.detail}` : ""}`}
              >
                {selectedAt != null ? (
                  <span className="opacity-70">{t("selectedEvent")} · </span>
                ) : null}
                {nearest.label}
                {nearest.detail && nearest.kind !== "guard_denial" ? (
                  <span className="opacity-70"> · {nearest.detail}</span>
                ) : null}
              </Truncate>
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
  renderTrigger,
  popoverClassName,
}: {
  selectedDate: Date;
  onPick: (anchorEnd: string | null) => void;
  /** Earliest day with real data; earlier days render disabled. */
  minDate?: Date;
  /** Trigger label override (e.g. "Aller à un instant" in À-un-instant reading). */
  label?: string;
  /**
   * Custom trigger — when provided, replaces the default outline button entirely
   * (same popover/calendar/bounds). Lets the "État au" command-bar chip BE the
   * single point-in-time picker, so there is no duplicate "Aller à un instant"
   * button elsewhere.
   */
  renderTrigger?: (state: { open: boolean; toggle: () => void }) => ReactNode;
  /** Popover anchor override (defaults to left-aligned under the trigger). */
  popoverClassName?: string;
}) {
  const t = useTranslations("overview.time");
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen((o) => !o);

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
      {renderTrigger ? (
        renderTrigger({ open, toggle })
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={open}
          className="h-9 gap-2"
          onClick={toggle}
        >
          <CalendarDays className="h-4 w-4" />
          {label ?? t("goToDate")}
        </Button>
      )}
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
          className={cn(
            "sr01-menu",
            popoverClassName ?? "absolute left-0 top-[calc(100%+0.5rem)] z-50",
          )}
        />
      ) : null}
    </div>
  );
}

type Translate = ReturnType<typeof useTranslations>;

/**
 * SR-01 transport — signal **event** navigation (no player). A labelled
 * "Événements" capsule with previous / next arrows that jump the cursor to the
 * adjacent real signal event; never a video-player cassette (that is execution
 * replay, XT-01). The explicit label + the arrows-only shape make the function
 * unmistakable (browse events ≠ replay). Used on every SURVEILLER surface.
 */
function SignalEventNavigation({
  t,
  prevDisabled,
  nextDisabled,
  noEvents,
  onPrev,
  onNext,
}: {
  t: Translate;
  prevDisabled: boolean;
  nextDisabled: boolean;
  /** No navigable event in the window → a disabled, labelled capsule + reason. */
  noEvents: boolean;
  onPrev: () => void;
  onNext: () => void;
}) {
  // Empty window: an honest disabled capsule with the reason in a tooltip — never a
  // dead pair of arrows that could read as a broken player.
  if (noEvents) {
    return (
      <span
        title={t("noEventsInWindow")}
        className="ml-auto flex h-8 shrink-0 cursor-not-allowed items-center gap-2 whitespace-nowrap rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface)]/40 px-3 text-[0.7rem] font-medium text-[var(--tessera-text-muted)] opacity-60"
      >
        <Milestone className="h-3.5 w-3.5" />
        {t("eventsBrowse")}
      </span>
    );
  }
  return (
    <span className="ml-auto flex h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-cyan-400/15 bg-cyan-400/[0.04] py-1 pl-3 pr-1 text-[0.7rem] text-[var(--tessera-text-muted)] shadow-[inset_0_1px_0_rgba(170,228,255,0.04)]">
      <span className="flex items-center gap-1.5 text-[var(--tessera-text-muted)]">
        <Milestone className="h-3.5 w-3.5 text-cyan-300/55" />
        {t("eventsBrowse")}
      </span>
      <span className="mx-1 h-3.5 w-px bg-cyan-400/10" />
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

/**
 * Data-availability marker on the axis — marks where real data BEGINS for the
 * current scope. Deliberately distinct from the period bounds (thin ticks + faint
 * dates at the axis ENDS) and the event ticks (filled colour): a hollow slate ring
 * with a connector to a small data-glyph label, plus an explanatory tooltip. It is
 * secondary to the champagne selected-instant marker, never a window bound.
 */
function RailMarker({
  pos,
  label,
  title,
  hideLabel,
  signal,
}: {
  pos: number;
  label: string;
  /** Tooltip clarifying this marks data availability, not a period bound. */
  title: string;
  /** Drop the label (keep the ring) when the focused instant would collide with it. */
  hideLabel?: boolean;
  /**
   * SR-01 (signal) gives the marker a cool cyan-slate tint so it belongs to the
   * temporal axis, while staying a clearly SECONDARY, desaturated marker beside the
   * champagne selected instant. The execution transport keeps the neutral slate.
   */
  signal?: boolean;
}) {
  return (
    <>
      {/* hollow ring sitting ON the axis — reads as a boundary of availability, not
          a filled event nor a thin period tick. cursor-help + title = the tooltip. */}
      <span
        title={title}
        className={cn(
          "absolute top-1 z-10 h-3 w-3 -translate-x-1/2 cursor-help rounded-full bg-[var(--tessera-bg)]",
          signal
            ? "border border-[rgba(124,188,220,0.55)] shadow-[0_0_0_3px_rgba(96,160,200,0.14)]"
            : "border border-slate-300/70 shadow-[0_0_0_3px_rgba(130,140,153,0.12)]",
        )}
        style={{ left: `${pos}%` }}
      />
      {hideLabel ? null : (
        <>
          {/* connector — keeps the label attached to its tick on the axis. */}
          <span
            className={cn(
              "pointer-events-none absolute top-4 h-2.5 w-px -translate-x-1/2",
              signal ? "bg-[rgba(124,188,220,0.32)]" : "bg-slate-400/35",
            )}
            style={{ left: `${pos}%` }}
          />
          <span
            title={title}
            className={cn(
              "absolute top-[1.7rem] flex -translate-x-1/2 cursor-help items-center gap-1 whitespace-nowrap text-[0.6rem] font-medium",
              signal ? "text-[rgba(150,200,228,0.85)]" : "text-slate-300/90",
            )}
            style={{ left: `${pos}%` }}
          >
            <Database
              className={cn(
                "h-2.5 w-2.5",
                signal ? "text-[rgba(124,188,220,0.9)]" : "text-[var(--tessera-text-muted)]",
              )}
              aria-hidden
            />
            {label}
          </span>
        </>
      )}
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

/**
 * The natural comparison default for each reading (registre §12). Switching the
 * reading applies it, so the comparison is never a silent "Aucun" nor a foreign
 * lens carried across: Maintenant → objectif cible, À un instant → Maintenant,
 * Historique → période précédente. A default that is not currently computable is
 * shown disabled-with-reason by the bar — it is never downgraded to "Aucun".
 */
export function readingDefaultCompare(reading: Reading): string {
  return reading === "live" ? "target" : reading === "asof" ? "now" : "previous_period";
}

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
    // Honour an explicit deep-link comparison; otherwise apply the reading's
    // default (never leak a foreign/stale "Aucun" from the shared store).
    setCompare(u.compare ?? readingDefaultCompare(u.reading));
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
  // ISO instant fed to the as-of-T-capable QUERIES — debounced via committedAt so a
  // scrub fires one request per settle, never one per move. À un instant reads the
  // scrubbed instant within the anchored window (falling back to the window end
  // before the first scrub); Historique reads the scrubbed instant; Live = null.
  const asOf =
    reading === "asof"
      ? committedAt != null
        ? new Date(committedAt).toISOString()
        : anchorEnd
      : reading === "historique" && committedAt != null
        ? new Date(committedAt).toISOString()
        : null;
  // The single ACTIVE instant the user is viewing — for DISPLAY and the URL. Read
  // from the IMMEDIATE cursor (selectedAt), not the debounced query value, so the
  // bar's "État au", the micro-line, the timeline and the URL never show two
  // different active instants (registre §4). Falls back to the anchored window end
  // in À un instant before the first scrub; null in Live / unscrubbed Historique.
  const activeAt =
    reading === "asof"
      ? selectedAt != null
        ? new Date(selectedAt).toISOString()
        : anchorEnd
      : reading === "historique" && selectedAt != null
        ? new Date(selectedAt).toISOString()
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
      // The active instant (immediate), so a shared link reopens on the exact
      // instant the bar/timeline show — never the debounced query value.
      asof: reading === "asof" ? activeAt : null,
      at: reading === "historique" ? activeAt : null,
      to: reading === "historique" ? anchorEnd : null,
      compare,
      expanded,
    });
  }, [reading, periodKey, anchorEnd, activeAt, compare, expanded]);
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
        setCompare(s.compare ?? readingDefaultCompare(s.reading));
        setExpanded(s.expanded);
      },
      [setAnchorEnd, setPeriodKey, setCompare],
    ),
  );
  // Switch the reading (the "Lecture" control), clearing what no longer applies.
  function setReading(next: Reading) {
    setReadingState(next);
    // Each reading carries its own comparison default (registre §12) — a user
    // switch never keeps a foreign lens nor silently falls to "Aucun".
    setCompare(readingDefaultCompare(next));
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
    activeAt,
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
