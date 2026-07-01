"use client";

import { BellOff } from "lucide-react";
import { type ComponentType, type ReactNode, useState } from "react";

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

const SEVERITY: Record<RibbonSeverity, SeverityStyle> = {
  critical: {
    band: "border border-[#e0566f]/35 bg-[#1f0e16] bg-[radial-gradient(130%_150%_at_0%_0%,rgba(224,86,111,0.22),transparent_58%)]",
    accent: "bg-gradient-to-b from-[#ff9bb0] via-[#e0566f] to-[#e0566f]/40",
    iconWrap: "bg-[#e0566f]/12 ring-1 ring-inset ring-[#e0566f]/30",
    iconColor: "text-[#ff9bb0]",
    eyebrow: "text-[#ff9bb0]/70",
    title: "text-[#ffb3c2]",
    gaugeFill: "bg-gradient-to-r from-[#e0566f] to-[#ff9bb0]",
    dot: "bg-[#e0566f]",
  },
  warning: {
    band: "border border-amber-400/35 bg-[#1d1606] bg-[radial-gradient(130%_150%_at_0%_0%,rgba(251,191,36,0.18),transparent_58%)]",
    accent: "bg-gradient-to-b from-amber-300 via-amber-400 to-amber-400/40",
    iconWrap: "bg-amber-400/12 ring-1 ring-inset ring-amber-400/30",
    iconColor: "text-amber-300",
    eyebrow: "text-amber-200/70",
    title: "text-amber-100",
    gaugeFill: "bg-gradient-to-r from-amber-400 to-amber-200",
    dot: "bg-amber-400",
  },
  ok: {
    band: "border border-[#3fb37f]/30 bg-[#0e1f17] bg-[radial-gradient(130%_150%_at_0%_0%,rgba(63,179,127,0.16),transparent_58%)]",
    accent: "bg-gradient-to-b from-[#7fe3b3] via-[#3fb37f] to-[#3fb37f]/40",
    iconWrap: "bg-[#3fb37f]/12 ring-1 ring-inset ring-[#3fb37f]/30",
    iconColor: "text-[#7fe3b3]",
    eyebrow: "text-[#7fe3b3]/70",
    title: "text-[#a8edc9]",
    gaugeFill: "bg-gradient-to-r from-[#3fb37f] to-[#7fe3b3]",
    dot: "bg-[#3fb37f]",
  },
  info: {
    band: "border border-sky-400/30 bg-[#0c1722] bg-[radial-gradient(130%_150%_at_0%_0%,rgba(96,194,242,0.16),transparent_58%)]",
    accent: "bg-gradient-to-b from-sky-300 via-sky-400 to-sky-400/40",
    iconWrap: "bg-sky-400/12 ring-1 ring-inset ring-sky-400/30",
    iconColor: "text-sky-300",
    eyebrow: "text-sky-200/70",
    title: "text-sky-100",
    gaugeFill: "bg-gradient-to-r from-sky-400 to-sky-200",
    dot: "bg-sky-400",
  },
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
  const s = SEVERITY[severity];
  return (
    <section className={cn("relative overflow-hidden rounded-xl", s.band)}>
      <span className={cn("absolute inset-y-0 left-0 w-[3px]", s.accent)} aria-hidden />
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-white/10" aria-hidden />
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
  const s = SEVERITY[severity];
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
            <span
              className={cn("min-w-0 truncate text-[0.85rem] font-semibold leading-tight", s.title)}
            >
              {title}
            </span>
          </div>
          {gauge ? (
            <div className="mt-2 flex items-center gap-3">
              {/* The empty track is a touch lighter than the band so the unfilled
                  extent reads — but discreet (no outline, no bright fill). */}
              <div className="relative h-[4px] min-w-0 flex-1 overflow-visible rounded-full bg-white/[0.13]">
                <div
                  className={cn("absolute inset-y-0 left-0 rounded-full", s.gaugeFill)}
                  style={{ width: `${clampPct(gauge.value)}%` }}
                />
                {/* Green threshold marker + its value as ONE centred stack at the
                    threshold x — the value (top) and the vertical marker (below) are
                    both centred on the same axis, so the number is always perfectly
                    centred on the marker regardless of glyph width. */}
                <div
                  className="pointer-events-none absolute -top-[26px] -bottom-1 flex -translate-x-1/2 flex-col items-center"
                  style={{ left: `${clampPct(gauge.threshold)}%` }}
                >
                  {showThresholdValue ? (
                    <span className="mb-1 whitespace-nowrap text-[9px] font-semibold leading-none tabular-nums text-[#7fe3b3]">
                      {gauge.thresholdLabel}
                    </span>
                  ) : null}
                  <span className="w-0.5 flex-1 rounded-full bg-[#7fe3b3] shadow-[0_0_6px_rgba(127,227,179,0.7)]" />
                </div>
              </div>
              {gauge.caption ? (
                <span className="shrink-0 text-[11px] tabular-nums text-[var(--tessera-text-muted)]">
                  {gauge.caption}
                </span>
              ) : null}
            </div>
          ) : meta ? (
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">{meta}</div>
          ) : null}
        </div>
      </div>
      {action || (showPulse && pulseStopLabel) ? (
        <div className="flex shrink-0 items-center gap-2 self-center">
          {/* Visible, discreet acknowledge control — clearly secondary to the CTA,
              but discoverable (a hover-only affordance was not). Silences the pulse. */}
          {showPulse && pulseStopLabel ? (
            <button
              type="button"
              onClick={() => setPulsing(false)}
              title={pulseStopLabel}
              className="inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-[11px] font-medium text-[var(--tessera-text-muted)] transition-colors hover:bg-white/[0.06] hover:text-[var(--tessera-text)]"
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
  const s = SEVERITY[severity];
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
      <p className={cn("min-w-0 truncate text-[0.85rem] font-semibold", s.title)}>{title}</p>
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
      ? "border-[#e0566f]/40 bg-[#e0566f]/12 text-[#ffb3c2]"
      : tone === "warning"
        ? "border-amber-400/40 bg-amber-400/12 text-amber-100"
        : "border-white/10 bg-white/[0.04] text-[var(--tessera-text-muted)]";
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
