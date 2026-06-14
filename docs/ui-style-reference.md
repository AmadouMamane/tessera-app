# UI style reference — the "premium" cockpit standard

**Status: canonical.** This is the visual standard every Qualité-IA / cockpit page must
reproduce. It is distilled from the **Journal d'audit** page
(`webapp/frontend/components/audit/audit-table.tsx`), which is the **gold reference
implementation** — when a token below is ambiguous, read that file.

The audit page was iterated to a "premium" finish (harmonised control heights, no
layout shift on load, stretchy charts, prefetched first paint). Match it. Earlier
pages (Sécurité 06 … Fiabilité 08) predate this standard and should be aligned to it
over time; their *zone* idea still holds for pages whose normative is zoned, but the
**atoms, heights, skeletons and perf rules below are universal**.

---

## 1. The surface token (one card style everywhere)

Every card / panel / control strip uses exactly:

```
rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3
```

Never invent a second card style. Backgrounds: `--tessera-surface` for cards,
`--tessera-bg` for inset sub-controls (segmented groups, readouts, popovers).

## 2. Harmonised control heights (the #1 "premium" tell)

Every interactive control on a strip is the **same height: `h-9` (36 px)**. Inner
segments are `h-7`; calendar day cells `h-8`. A control strip is:

```
flex min-h-[54px] shrink-0 flex-wrap items-center gap-3
rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2
shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]
```

That inset top-highlight shadow (a 1px white sheen at 3 %) is what reads as "premium".
Popovers/overlays use a soft drop: `shadow-[0_20px_60px_rgba(0,0,0,0.38)]`.

## 3. Period control — fixed order & compact range

The window picker reads, **left → right**: label → segmented `24h / 7 jours / 30 jours`
→ **compact** date-range readout → **"Aller à une date"** button with a calendar popover.

- Segmented presets: `flex h-9 ... p-1`, each button `h-7 rounded px-3 text-xs`.
- Date-range readout is **compact** (`h-9 max-w-[520px] shrink-0`), **never `flex-1`** —
  letting it stretch leaves a big empty gap. It shows `window_start → window_end`
  (`dateStyle: "medium", timeStyle: "short"`).
- "Aller à une date": an `h-9` outline button; the calendar is a **home-made popover
  anchored to it** (`absolute right-0 top-[calc(100%+0.5rem)] z-50 w-[292px]`), not the
  native `<input type=date>`. Picking a day keeps the active preset and **re-anchors the
  real window on that day at local end-of-day**, then refetches the endpoint.
- Active/selected accent (preset & calendar day): `bg-[#123e6a] text-[#d8eaff] ring-1 ring-[#2e72d2]`.

## 4. No layout shift ("la page ne danse pas")

Loading must not change any height. Two rules:

1. **Fixed heights on every container that holds async data.** KPI cards: `h-[108px]`.
   Bottom panels: `h-[142px]`. Inside a KPI card the value row is `h-8`, the trend row
   `h-7` (with `border-t pt-1.5`).
2. **Skeletons mirror the final element's exact box.** e.g. value `Skeleton h-7 w-16`,
   delta `h-4 w-12`, sparkline `h-5 w-full`, range readout `h-4 w-64`. Never swap a
   short skeleton for a taller value.

KPI value typography: `text-[1.55rem] font-semibold leading-none text-white`.

## 5. Charts stretch, strokes don't

Inline SVG charts must fill the card width and keep a constant stroke:

```
preserveAspectRatio="none"   // stretch the viewBox to the box
vectorEffect="non-scaling-stroke"  // 2px line stays 2px when stretched
```

(Forgetting `preserveAspectRatio="none"` is why a chart stays centred in a wide card.)

## 6. Smooth data (no flash, fast first paint)

- React Query: `placeholderData: (prev) => prev` — keep the previous data visible while
  refetching a new window, so the page never blanks.
- **Prefetch on the server** for first paint: the route component fetches the real
  endpoint data and passes it as `initialWindow`/`initialData`, and the client query
  skips the immediate refetch. First load shows real rows, not skeletons.
- Backend: cache JSONL reads + integrity by `(path, mtime, size)` with separate locks;
  compute derived series in a single pass. (Audit first load ≈ 0.11 s cold, 0.06 s warm.)

## 7. What to copy — and the one thing not to

Copy: the tokens above, the metric-card pattern (`MetricGrid`/`DeltaBadge`), the period
control (its calendar popover), `TimelineChart`, the bottom `Panel`/`CountList`.

**Do not** copy audit's backend *placement*: its logic lives inside
`api/routes/audit.py` (legacy, predates the convention). New pages keep the canonical
split — a thin route in `src/tessera/api/routes/observability.py` calling a dedicated
`src/tessera/observability/<area>.py` module (CLAUDE.md). Honesty rules are unchanged:
every panel from a **real signal**, estimates **labelled**, `null` / "pas de données"
when there's no baseline, period-over-period deltas vs the previous window, **never**
fabricated.

> Naming note: audit has a local `PeriodRail` (horizontal window picker) distinct from
> `components/observability/period-rail.tsx` (vertical period *selector*, the "Image 2"
> rail). Two different things — don't confuse them. The horizontal picker here is the
> standard for top-of-page window control; the vertical rail is for window-driven pages
> that put the selector in a right column.

## 8. Reference anchors (in `components/audit/audit-table.tsx`)

| Pattern | Function |
|---|---|
| Window/period control + calendar popover | `PeriodRail` (~L280) |
| KPI metric cards (fixed height, skeletons) | `MetricGrid` (~L457), `DeltaBadge` (~L536) |
| Bottom summary cards | `BottomPanels` / `Panel` (~L881) |
| Stretchy timeline chart | `TimelineChart` (~L960) |
| Click-to-open detail side-sheet | `AuditDetailOverlay` / `AuditDetails` (~L1059) |
