import { describe, expect, it } from "vitest";

import type { ComponentPhase } from "@/lib/api/schemas";
import { componentsInTimeline, segmentsFor } from "@/lib/phase-timeline";

const SINCE = "2026-08-07T08:00:00+00:00";
const UNTIL = "2026-08-07T09:00:00+00:00";

const phase = (
  component: string,
  verdict: string,
  since: string,
  until: string,
  n = 3,
): ComponentPhase => ({ component, verdict, since, until, n_observations: n });

describe("segmentsFor", () => {
  it("projects a phase onto the window as percentages", () => {
    const segments = segmentsFor(
      [phase("clickhouse", "fail", "2026-08-07T08:15:00+00:00", "2026-08-07T08:30:00+00:00")],
      "clickhouse",
      SINCE,
      UNTIL,
    );
    expect(segments).toHaveLength(1);
    expect(segments[0]?.leftPct).toBeCloseTo(25);
    expect(segments[0]?.widthPct).toBeCloseTo(25);
    expect(segments[0]?.seconds).toBeCloseTo(900);
  });

  it("does NOT stretch a segment over unwatched time — the hole stays a hole", () => {
    // Two phases with a 30-minute gap between them: whatever the segments cover must leave
    // the gap uncovered. Rendering fills only segments; the track shows through the hole.
    const segments = segmentsFor(
      [
        phase("redis", "ok", SINCE, "2026-08-07T08:10:00+00:00"),
        phase("redis", "ok", "2026-08-07T08:40:00+00:00", UNTIL),
      ],
      "redis",
      SINCE,
      UNTIL,
    );
    const covered = segments.reduce((total, s) => total + s.widthPct, 0);
    expect(covered).toBeCloseTo((10 / 60 + 20 / 60) * 100, 5);
  });

  it("keeps a point observation as a zero-width segment rather than dropping it", () => {
    const instant = "2026-08-07T08:30:00+00:00";
    const segments = segmentsFor(
      [phase("minio", "fail", instant, instant, 1)],
      "minio",
      SINCE,
      UNTIL,
    );
    expect(segments).toHaveLength(1);
    expect(segments[0]?.widthPct).toBe(0);
    expect(segments[0]?.leftPct).toBeCloseTo(50);
  });

  it("clamps a phase that leaks past the window instead of painting over it", () => {
    const segments = segmentsFor(
      [phase("grafana", "ok", "2026-08-07T07:00:00+00:00", "2026-08-07T10:00:00+00:00")],
      "grafana",
      SINCE,
      UNTIL,
    );
    expect(segments[0]?.leftPct).toBe(0);
    expect(segments[0]?.widthPct).toBe(100);
  });

  it("drops an unparseable instant rather than drawing a guessed bar", () => {
    expect(segmentsFor([phase("redis", "ok", "not-a-date", UNTIL)], "redis", SINCE, UNTIL)).toEqual(
      [],
    );
  });

  it("returns nothing for an empty or inverted window", () => {
    expect(segmentsFor([phase("redis", "ok", SINCE, UNTIL)], "redis", UNTIL, SINCE)).toEqual([]);
  });

  it("orders segments left to right whatever order they arrive in", () => {
    const segments = segmentsFor(
      [
        phase("redis", "ok", "2026-08-07T08:40:00+00:00", UNTIL),
        phase("redis", "fail", SINCE, "2026-08-07T08:10:00+00:00"),
      ],
      "redis",
      SINCE,
      UNTIL,
    );
    expect(segments.map((s) => s.verdict)).toEqual(["fail", "ok"]);
  });
});

describe("componentsInTimeline", () => {
  it("lists each component once, alphabetically", () => {
    const rows = componentsInTimeline([
      phase("redis", "ok", SINCE, UNTIL),
      phase("minio", "ok", SINCE, UNTIL),
      phase("redis", "fail", SINCE, UNTIL),
    ]);
    expect(rows).toEqual(["minio", "redis"]);
  });
});
