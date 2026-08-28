"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type Period = { days: number; anchor: string | null };
export type PeriodItem = { stamp: string; label: string };

/**
 * Vertical period selector (the "Image 2" rail): pick an analysis window — a
 * length (presets) and an upper-bound day from a clickable timeline — to
 * recompute a window-based page (cost, reliability, model comparison). Distinct
 * from {@link TemporalRail}, which time-travels to an *instant* for state pages.
 *
 * Generic: the caller supplies the timeline items and labels, so it is shared by
 * Fiabilité & coût and (later) Comparaison modèles rather than coupled to one
 * data source.
 */
export function PeriodRail({
  title,
  items,
  presets,
  value,
  onApply,
  labels,
  window,
}: {
  title: string;
  items: PeriodItem[];
  presets: { value: number; label: string }[];
  value: Period;
  onApply: (p: Period) => void;
  labels: { selected: string; from: string; apply: string; noData: string };
  /**
   * The window the data was actually computed over, as the server states it. Supply it
   * whenever the payload carries its own bounds.
   *
   * Without it the rail reconstructs "from" by walking `days - 1` items back through the
   * timeline — which silently assumes one item per day. It held while every window was
   * daily; a 24 h window is 24 hourly items, so `days - 1` landed on index 0 and the rail
   * announced `X → X`, a window of zero length, for a window that was real. A control may
   * state the window it was handed; it may not re-derive one.
   */
  window?: { from: string; to: string };
}) {
  const [days, setDays] = useState(value.days);
  const [anchor, setAnchor] = useState<string | null>(value.anchor);
  // Keep local controls in sync when the page resets the period externally.
  useEffect(() => {
    setDays(value.days);
    setAnchor(value.anchor);
  }, [value.days, value.anchor]);

  const selected = anchor ?? items[0]?.stamp ?? null;
  const derivedIdx = Math.min(items.length - 1, Math.max(0, days - 1));
  const newest = window?.to ?? items[0]?.label ?? "—";
  const startLabel =
    window?.from ?? (items.length ? (items[derivedIdx]?.label ?? items.at(-1)?.label ?? "—") : "—");
  // A length the caller does not offer cannot be *shown* as chosen: a native <select> whose
  // value matches no <option> silently displays the first one, so the control would claim a
  // window the page is not using. Say the truth instead of picking a neighbour.
  const knownPreset = presets.some((p) => p.value === days);

  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-4">
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-[0.8rem]">{title}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2 pt-1">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{labels.selected}</span>
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-xs"
              >
                {knownPreset ? null : <option value={days}>{`${days} j`}</option>}
                {presets.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            {items.length === 0 ? (
              <p className="py-2 text-xs text-[var(--muted-foreground)]">{labels.noData}</p>
            ) : (
              <ol className="flex max-h-[260px] flex-col overflow-y-auto">
                {items.map((it, i) => {
                  const sel = it.stamp === selected;
                  const last = i === items.length - 1;
                  return (
                    <li key={it.stamp} className="flex items-stretch gap-2">
                      <div className="flex flex-col items-center">
                        <button
                          type="button"
                          onClick={() => setAnchor(it.stamp)}
                          aria-label={it.label}
                          className={`h-3 w-3 rounded-full border-2 ${
                            sel
                              ? "border-[var(--tessera-green)] bg-[var(--tessera-green)]"
                              : "border-[var(--border)] bg-[var(--card)]"
                          }`}
                        />
                        {last ? null : <span className="w-px flex-1 bg-[var(--border)]" />}
                      </div>
                      <button
                        type="button"
                        onClick={() => setAnchor(it.stamp)}
                        className={`mb-1.5 flex-1 rounded-md px-2 py-1 text-left text-xs tabular-nums ${
                          sel
                            ? "bg-[var(--tessera-green)]/15 font-medium text-[var(--tessera-text)]"
                            : "text-[var(--muted-foreground)] hover:bg-[var(--tessera-muted)]/40"
                        }`}
                      >
                        {it.label}
                      </button>
                    </li>
                  );
                })}
              </ol>
            )}

            <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--border)] px-2 py-1.5 text-xs text-[var(--muted-foreground)]">
              <span>{labels.from}</span>
              <span className="tabular-nums text-[var(--foreground)]">
                {startLabel} → {newest}
              </span>
            </div>

            <button
              type="button"
              onClick={() => onApply({ days, anchor })}
              className="rounded-md bg-[var(--tessera-green)] px-3 py-1.5 text-xs font-medium text-[var(--tessera-text-strong)] hover:brightness-110"
            >
              {labels.apply}
            </button>
          </CardContent>
        </Card>
      </div>
    </aside>
  );
}
