// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { bucketLabel, windowBoundLabel } from "@/components/reliability/reliability-dashboard";

import { type PeriodItem, PeriodRail } from "./period-rail";

afterEach(() => cleanup());

const LABELS = { selected: "Fenêtre", from: "Du", apply: "Ouvrir", noData: "—" };
const PRESETS = [
  { value: 1, label: "24 heures" },
  { value: 7, label: "7 jours" },
  { value: 14, label: "14 jours" },
];

function hourlyItems(): PeriodItem[] {
  return Array.from({ length: 24 }, (_, i) => ({
    stamp: `2026-08-04T${String(i).padStart(2, "0")}:00:00+00:00`,
    label: `04/08 ${String(i).padStart(2, "0")}:00`,
  })).reverse();
}

/**
 * The rail used to reconstruct its lower bound by walking `days - 1` items back through the
 * timeline — an assumption of one item per day that held only while every window was daily.
 * A 24 h window is 24 hourly items, so `days - 1` landed on index 0 and the rail announced a
 * window of zero length for a window that was real.
 */
describe("the period rail states the window it was handed", () => {
  it("prints the server's bounds rather than re-deriving them from the item count", () => {
    render(
      <PeriodRail
        title="Période"
        items={hourlyItems()}
        presets={PRESETS}
        value={{ days: 1, anchor: null }}
        onApply={() => undefined}
        labels={LABELS}
        window={{ from: "03/08 19:00", to: "04/08 19:00" }}
      />,
    );
    expect(screen.getByText("03/08 19:00 → 04/08 19:00")).toBeTruthy();
  });

  it("without server bounds it still shows a window, and a 24 h one no longer collapses", () => {
    // Negative control for the fix above: this is the path other callers keep. With 24 hourly
    // items and days=1 the derived bound is items[0] — the newest — which is exactly the
    // "X → X" the server-stated window exists to replace. Pinned so the difference between
    // the two paths is a fact in this file rather than a claim in a comment.
    render(
      <PeriodRail
        title="Période"
        items={hourlyItems()}
        presets={PRESETS}
        value={{ days: 1, anchor: null }}
        onApply={() => undefined}
        labels={LABELS}
      />,
    );
    expect(screen.getByText("04/08 23:00 → 04/08 23:00")).toBeTruthy();
  });

  it("shows the selected length as selected — never a neighbour it happens to offer", () => {
    render(
      <PeriodRail
        title="Période"
        items={hourlyItems()}
        presets={PRESETS}
        value={{ days: 1, anchor: null }}
        onApply={() => undefined}
        labels={LABELS}
      />,
    );
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("1");
  });

  it("names a length no preset offers instead of silently displaying the first option", () => {
    // A native <select> whose value matches no <option> renders the FIRST one. Before the
    // 24 h preset existed, the rail therefore read "7 jours" while the page queried 1 day.
    render(
      <PeriodRail
        title="Période"
        items={hourlyItems()}
        presets={[{ value: 7, label: "7 jours" }]}
        value={{ days: 3, anchor: null }}
        onApply={() => undefined}
        labels={LABELS}
      />,
    );
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("3");
    expect(screen.getByRole("option", { name: "3 j" })).toBeTruthy();
  });
});

describe("a bucket is labelled at the grain it was measured at", () => {
  it("carries the hour when the window is read hourly", () => {
    expect(bucketLabel("2026-08-04T19:00:00+00:00", "hour")).toBe("04/08 19:00");
  });

  it("drops it when the window is read daily — a day has no hour to show", () => {
    expect(bucketLabel("2026-08-04T00:00:00+00:00", "day")).toBe("04/08");
  });

  it("returns an unparseable stamp unchanged rather than inventing a date", () => {
    expect(bucketLabel("not-a-date", "hour")).toBe("not-a-date");
  });

  it("says '—' for an absent bound instead of formatting an empty string", () => {
    expect(windowBoundLabel(undefined, "day")).toBe("—");
    expect(windowBoundLabel("2026-08-04T19:00:00+00:00", "hour")).toBe("04/08 19:00");
  });
});
