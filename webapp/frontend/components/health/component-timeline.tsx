"use client";

import { useFormatter, useTranslations } from "next-intl";

import { humanSeconds } from "@/components/health/observability-shared";
import type { ComponentPhase } from "@/lib/api/schemas";
import { segmentsFor } from "@/lib/phase-timeline";

/**
 * One component's recorded phases, drawn on the window (ADR 0052 §Amendment 1.2).
 *
 * The track is the window; a segment is a phase; **everything unpainted is time nobody
 * watched**, deliberately left as the empty track rather than bridged — the hole is the
 * information. Colours are the page's one status vocabulary (`observability-shared`), never a
 * categorical palette; identity never rides on colour alone (each segment carries its verdict,
 * instants and duration in its tooltip, and the row's détail column says the same in words).
 */
const FILL: Record<string, string> = {
  ok: "bg-[var(--tessera-green)]/85",
  fail: "bg-[var(--tessera-fg-danger)]",
  blind: "bg-[var(--tessera-fg-warning)]",
  skip: "bg-[var(--muted-foreground)]/50",
};

export function ComponentTimeline({
  phases,
  component,
  since,
  until,
  days,
}: {
  phases: ComponentPhase[];
  component: string;
  since: string;
  until: string;
  /** The window length — picks how a segment tooltip spells an instant. */
  days: number;
}) {
  const t = useTranslations("health.history");
  const format = useFormatter();
  const segments = segmentsFor(phases, component, since, until);

  const instant = (iso: string) =>
    format.dateTime(
      new Date(iso),
      days === 1
        ? { hour: "2-digit", minute: "2-digit" }
        : { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" },
    );

  const summary =
    segments.length === 0
      ? t("timelineEmpty", { component })
      : t("timelineSummary", {
          component,
          parts: segments
            .map((s) => `${t(`state.${s.verdict}`)} ${humanSeconds(s.seconds)}`)
            .join(", "),
        });

  return (
    <div
      role="img"
      aria-label={summary}
      className="relative h-2 w-full min-w-[6rem] overflow-hidden rounded-full bg-[var(--tessera-muted)]/50"
      title={segments.length === 0 ? summary : undefined}
    >
      {segments.map((segment) => (
        <span
          key={`${segment.since}-${segment.until}-${segment.verdict}`}
          title={t("segmentTitle", {
            verdict: t(`state.${segment.verdict}`),
            from: instant(segment.since),
            to: instant(segment.until),
            duration: humanSeconds(segment.seconds),
            n: segment.n_observations,
          })}
          className={`absolute inset-y-0 ${FILL[segment.verdict] ?? FILL.blind}`}
          style={{
            left: `${segment.leftPct}%`,
            width: `${segment.widthPct}%`,
            // One real look must not be invisible: a point phase keeps a 2px tick.
            minWidth: "2px",
          }}
        />
      ))}
    </div>
  );
}
