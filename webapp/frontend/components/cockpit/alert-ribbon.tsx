"use client";

import { BellOff } from "lucide-react";
import { type ComponentType, type ReactNode, useState } from "react";

import { Truncate } from "@/components/ui/truncate";
import { cn } from "@/lib/cn";

/**
 * Severity of an alert ribbon. `critical`/`warning` raise an active breach;
 * `ok` is the honest "all clear" state (quieter, never red); `info` is neutral.
 */
export type RibbonSeverity = "critical" | "warning" | "ok" | "info";

/** Presentation variant — see the two builders below. */
export type RibbonVariant = "gauge" | "slim";

interface SeverityStyle {
  /** Band: top/bottom hairline + layered tint wash (never a flat block). */
  band: string;
  /** The 3px left accent rail at the bleed edge — the severity's signature. */
  accent: string;
  /** Icon chip background + ring. */
  iconWrap: string;
  /** Icon glyph colour. */
  iconColor: string;
  /** Eyebrow (category label) colour. */
  eyebrow: string;
  /** Title (the statement) colour. */
  title: string;
  /** Gauge fill gradient (left→right). */
  gaugeFill: string;
  /** Status dot / pulse colour (Tailwind bg-… ready). */
  dot: string;
}

/** Every severity now paints from the SAME six variables — `.tessera-ribbon` in
 *  globals.css sets them per `data-severity`, and swaps the whole set under "Clair".
 *  Naming a colour here is what made this band a dark slab on a light page. */
const RIBBON: SeverityStyle = {
  band: "tessera-ribbon",
  accent:
    "bg-[linear-gradient(to_bottom,var(--ribbon-bright),var(--ribbon-base)_55%,color-mix(in_oklab,var(--ribbon-base)_40%,transparent))]",
  iconWrap:
    "bg-[color-mix(in_oklab,var(--ribbon-base)_12%,transparent)] ring-1 ring-inset ring-[color-mix(in_oklab,var(--ribbon-base)_30%,transparent)]",
  iconColor: "text-[var(--ribbon-bright)]",
  eyebrow: "text-[var(--ribbon-eyebrow)]",
  title: "text-[var(--ribbon-title)]",
  gaugeFill: "bg-[linear-gradient(to_right,var(--ribbon-base),var(--ribbon-bright))]",
  dot: "bg-[var(--ribbon-base)]",
};

/** A 0..1 ratio for the gauge: the observed value and the threshold it must clear. */
export interface RibbonGauge {
  /** Observed value (0..1), e.g. the SLO good rate. */
  value: number;
  /** Threshold (0..1) the value must meet — drawn as a tick on the track. */
  threshold: number;
  /** Short caption to the right of the bar (e.g. the burn rate + counts). */
  caption?: ReactNode;
  /** Label for the threshold tick (e.g. "seuil 80,0 %"), shown beneath it. */
  thresholdLabel?: string;
}

interface BaseProps {
  severity: RibbonSeverity;
  icon: ComponentType<{ className?: string }>;
  /** Small category label above the statement (e.g. "Signal franchi (SLO)"). */
  eyebrow: string;
  /** The statement itself (e.g. "Fidélité — 45,5 % < seuil 80,0 %"). */
  title: ReactNode;
  /** Optional trailing action (a remediation link/button). */
  action?: ReactNode;
}

const clampPct = (n: number) => Math.max(0, Math.min(100, n * 100));

/**
 * AlertRibbon — the shared, premium full-bleed alert band for cockpit pages.
 *
 * Two variants:
 *  · `gauge` — a band carrying a real error/SLO **budget gauge** in the body, so the
 *    horizontal space reads as information (fill vs threshold tick), never dead space.
 *  · `slim`  — a single-line **status line**: a pulsing severity dot, the statement
 *    inline, supporting meta, and a trailing action. Minimal height, premium restraint.
 *
 * It is presentational: the consumer supplies the real strings/gauge and never lets
 * the ribbon fabricate a value.
 */
export function AlertRibbon(
  props:
    | (BaseProps & {
        variant?: "gauge";
        gauge?: RibbonGauge;
        meta?: ReactNode;
        pulse?: boolean;
        /** Tooltip/aria for the "stop pulsing" control (rendered when `pulse`). */
        pulseStopLabel?: string;
      })
    | (BaseProps & { variant: "slim"; meta?: ReactNode }),
) {
  if (props.variant === "slim") return <SlimRibbon {...props} />;
  return <GaugeRibbon {...props} />;
}

/** Shared band shell: full-bleed `-mx-3`, severity accent rail, top sheen, wash. */
function RibbonShell({
  severity,
  className,
  children,
}: {
  severity: RibbonSeverity;
  className?: string;
  children: ReactNode;
}) {
  const s = RIBBON;
  return (
    <section className={cn("relative overflow-hidden rounded-xl", s.band)} data-severity={severity}>
      <span className={cn("absolute inset-y-0 left-0 w-[3px]", s.accent)} aria-hidden />
      <span
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[var(--ribbon-glint)]"
        aria-hidden
      />
      <div className={className}>{children}</div>
    </section>
  );
}

/** Variant `gauge` — band with the statement + a budget gauge filling the body. */
function GaugeRibbon({
  severity,
  icon: Icon,
  eyebrow,
  title,
  action,
  gauge,
  meta,
  pulse,
  pulseStopLabel,
}: BaseProps & {
  gauge?: RibbonGauge;
  meta?: ReactNode;
  pulse?: boolean;
  pulseStopLabel?: string;
}) {
  const s = RIBBON;
  // The pulse can be silenced (acknowledged) at runtime via a VISIBLE control (a
  // hover-only affordance was not discoverable).
  const [pulsing, setPulsing] = useState(true);
  const showPulse = Boolean(pulse) && pulsing;
  // The green threshold value is printed on the marker only when it sits over the
  // unfilled (dark) track — i.e. while breaching — so it never blends into the fill.
  const showThresholdValue = gauge?.thresholdLabel != null && gauge.value < gauge.threshold;

  return (
    <RibbonShell
      severity={severity}
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5 px-4 pt-3.5 pb-1.5 sm:px-5"
    >
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        <span className="relative grid h-7 w-7 shrink-0 place-items-center" aria-hidden>
          {/* Pulsing halo — a slow expanding ring so the alert reads as live. */}
          {showPulse ? (
            <span
              className={cn(
                "absolute inline-flex h-7 w-7 animate-ping rounded-lg opacity-30 [animation-duration:1.8s]",
                s.dot,
              )}
            />
          ) : null}
          <span className={cn("relative grid h-7 w-7 place-items-center rounded-lg", s.iconWrap)}>
            <Icon className={cn("h-3.5 w-3.5", s.iconColor)} />
          </span>
        </span>
        <div className="min-w-0 flex-1">
          {/* Eyebrow + statement on ONE line, so the band stays thin. */}
          <div className="flex min-w-0 items-baseline gap-2">
            <span
              className={cn(
                "shrink-0 text-[9.5px] font-medium uppercase tracking-[0.14em]",
                s.eyebrow,
              )}
            >
              {eyebrow}
            </span>
            <Truncate className={cn("min-w-0 text-[0.85rem] font-semibold leading-tight", s.title)}>
              {title}
            </Truncate>
          </div>
          {gauge ? (
            /* WRAPS, AND RESERVES ITS OWN HEADROOM (fixed 2026-08-01).
             *
             * Two faults met here, and both were measured before being touched.
             * (a) The track was `min-w-0 flex-1` beside a `shrink-0` caption, so
             *     the caption won every squeeze: 344px of track at 1728, 277 at
             *     1280, 21 at 1024, and ZERO at 768 and below. A gauge 0px wide
             *     is not a discreet gauge, it is an absent one that still claims
             *     to show a ratio.
             * (b) The threshold label is positioned at `left: <threshold>%` of that
             *     track. At 0px width, 95% of 0 is 0 — so "95,0 %" was drawn at the
             *     track's own left edge, one line up, exactly on top of the eyebrow
             *     "OBJECTIF DE QUALITÉ". It never escaped that line at any width; it
             *     merely sat far enough to the RIGHT to miss the title. That is a
             *     collision avoided by luck, not by layout.
             *
             * So the row now wraps, the track keeps a floor it cannot be squeezed
             * below, and the label lives in padding reserved for it on this row
             * instead of reaching into the row above. */
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 pt-4">
              {/* The empty track is a touch lighter than the band so the unfilled
                  extent reads — but discreet (no outline, no bright fill). */}
              <div className="relative h-[4px] min-w-[140px] flex-1 basis-[180px] overflow-visible rounded-full bg-[var(--ribbon-track)]">
                <div
                  className={cn("absolute inset-y-0 left-0 rounded-full", s.gaugeFill)}
                  style={{ width: `${clampPct(gauge.value)}%` }}
                />
                {/* Green threshold marker + its value as ONE centred stack at the
                    threshold x — the value (top) and the vertical marker (below) are
                    both centred on the same axis, so the number is always perfectly
                    centred on the marker regardless of glyph width. */}
                <div
                  className="pointer-events-none absolute -top-[16px] -bottom-1 flex -translate-x-1/2 flex-col items-center"
                  style={{ left: `${clampPct(gauge.threshold)}%` }}
                >
                  {showThresholdValue ? (
                    <span className="mb-1 whitespace-nowrap text-[9px] font-semibold leading-none tabular-nums text-[var(--tessera-fg-success)]">
                      {gauge.thresholdLabel}
                    </span>
                  ) : null}
                  <span className="w-0.5 flex-1 rounded-full bg-[var(--tessera-fg-success)] shadow-[0_0_6px_color-mix(in_oklab,var(--tessera-fg-success)_70%,transparent)]" />
                </div>
              </div>
              {gauge.caption ? (
                <span className="min-w-0 text-[11px] tabular-nums text-[var(--tessera-text-muted)]">
                  {gauge.caption}
                </span>
              ) : null}
            </div>
          ) : meta ? (
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">{meta}</div>
          ) : null}
        </div>
      </div>
      {/* Wraps: the shell already wraps this whole group onto its own line at
          narrow widths, but the two controls together need ~300px and a phone
          leaves ~280px, so the CTA ran 18px past the band. */}
      {action || (showPulse && pulseStopLabel) ? (
        <div className="flex flex-wrap items-center gap-2 self-center">
          {/* Visible, discreet acknowledge control — clearly secondary to the CTA,
              but discoverable (a hover-only affordance was not). Silences the pulse. */}
          {showPulse && pulseStopLabel ? (
            <button
              type="button"
              onClick={() => setPulsing(false)}
              title={pulseStopLabel}
              className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[11px] font-medium text-[var(--tessera-text-muted)] transition-colors hover:bg-[var(--ribbon-hover)] hover:text-[var(--tessera-text)]"
            >
              <BellOff className="h-3.5 w-3.5" />
              {pulseStopLabel}
            </button>
          ) : null}
          {action}
        </div>
      ) : null}
    </RibbonShell>
  );
}

/** Variant `slim` — one-line status line: pulse dot · statement · meta · action. */
function SlimRibbon({ severity, title, action, meta }: BaseProps & { meta?: ReactNode }) {
  const s = RIBBON;
  return (
    <RibbonShell severity={severity} className="flex items-center gap-3 px-4 py-2 sm:px-5">
      <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden>
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
            s.dot,
          )}
        />
        <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", s.dot)} />
      </span>
      <Truncate className={cn("min-w-0 text-[0.85rem] font-semibold", s.title)}>{title}</Truncate>
      {meta ? (
        <span className="hidden shrink-0 items-center gap-1.5 text-[11px] text-[var(--tessera-text-muted)] sm:flex">
          <span aria-hidden>·</span>
          {meta}
        </span>
      ) : null}
      {action ? <div className="ml-auto shrink-0">{action}</div> : null}
    </RibbonShell>
  );
}

/**
 * A compact, lacquered chip for ribbon `meta` (e.g. the burn rate). Tabular-nums
 * keeps numbers from jittering. Tone defaults to the neutral muted surface; pass a
 * severity tone to tie a number to the alert's colour (e.g. a red burn rate).
 */
export function RibbonChip({
  icon: Icon,
  tone = "neutral",
  children,
}: {
  icon?: ComponentType<{ className?: string }>;
  tone?: "neutral" | "critical" | "warning";
  children: ReactNode;
}) {
  const toneClass =
    tone === "critical"
      ? "border-[color-mix(in_oklab,var(--ribbon-base)_40%,transparent)] bg-[color-mix(in_oklab,var(--ribbon-base)_12%,transparent)] text-[var(--ribbon-title)]"
      : tone === "warning"
        ? "border-amber-400/40 bg-amber-400/12 text-[var(--ribbon-title)]"
        : "border-[var(--ribbon-border)] bg-[var(--ribbon-track)] text-[var(--tessera-text-muted)]";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10.5px] font-medium tabular-nums",
        toneClass,
      )}
    >
      {Icon ? <Icon className="h-3 w-3 shrink-0" aria-hidden /> : null}
      {children}
    </span>
  );
}
