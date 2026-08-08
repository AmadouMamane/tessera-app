import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The judge rail printed three reassuring things over an unread endpoint.
 *
 * Seen by holding every `/api/observability/**` request open and screenshotting the page:
 *
 *   Résumé du risque de calibration    0 /100 · faible   (green)
 *   Dérive juge                        —        Pass     (green)
 *   Top catégories en désaccord        "Aucun désaccord juge ↔ humain."
 *
 * None of the three had been measured. The mechanism was the same each time: a missing number
 * coalesced to `0` and the `0` was then compared against a threshold, so the ABSENCE of a
 * reading entered the verdict as a very good reading.
 *
 * Note which way the accidents fell. `(kappa ?? 0) >= 0.8` and `(agreement ?? 0) >= 0.8` failed
 * SAFE — 0 misses the bar, so those two showed "à surveiller". `(driftDiv ?? 0) < 0.1` failed
 * OPEN — 0 clears the bar, so that one showed a green Pass. Nobody chose either; the direction
 * was decided by which way the comparison happened to point. That is the tell: a missing input
 * is not a value, so the comparison must not be reached at all.
 *
 * This is ADR 0026 on a governance surface, and the more dangerous half of it: a blank screen
 * tells an operator to go and look, while "low calibration risk" tells them not to.
 */

const RAIL = readFileSync(
  join(process.cwd(), "components/observability/judge-calibration.tsx"),
  "utf8",
);
const LOCALES = ["fr", "en", "de"] as const;

describe("no verdict without a reading", () => {
  it("never coalesces a missing gate input into a threshold comparison", () => {
    for (const pattern of [
      "(kappa ?? 0) >= 0.8",
      "(agreement ?? 0) >= 0.8",
      "(driftDiv ?? 0) < 0.1",
    ]) {
      expect(RAIL).not.toContain(pattern);
    }
  });

  it("makes a gate three-state, so an unread input is neither pass nor watch", () => {
    expect(RAIL).toContain("pass: boolean | null");
    for (const guard of [
      "pass: kappa == null ? null : kappa >= 0.8",
      "pass: agreement == null ? null : agreement >= 0.8",
      "pass: driftDiv == null ? null : driftDiv < 0.1",
    ]) {
      expect(RAIL).toContain(guard);
    }
    // …and the badge spends that third state rather than folding it into one of the two.
    expect(RAIL).toContain('g.pass == null ? "neutral"');
  });

  /**
   * The composite risk score. Its fallback was `0`, which is not "no risk" — it is "no terms",
   * and `0` is the single most reassuring value the scale can hold.
   */
  it("has no risk score when the composite has no terms", () => {
    expect(RAIL).toMatch(/const risk = factors\.length[\s\S]{0,160}: null;/);
    expect(RAIL).toContain("risk == null ? MUTED :");
    expect(RAIL).toContain('{risk ?? "—"}');
  });

  it("only claims 'no disagreements' after actually reading them", () => {
    expect(RAIL).toContain('data == null ? tq("judge.disagreementsUnread")');
  });
});

describe("the sentences that say it", () => {
  it.each(LOCALES)("%s can say 'not measured' and 'could not be read'", (locale) => {
    const judge = (
      JSON.parse(
        readFileSync(join(process.cwd(), `messages/${locale}.json`), "utf8") as string,
      ) as {
        quality: { judge: Record<string, string> };
      }
    ).quality.judge;
    expect(judge.notMeasured).toBeTruthy();
    expect(judge.disagreementsUnread).toBeTruthy();
    // The unread sentence must not read as a result: it says the reading failed, and says that
    // the answer is therefore unknown. A bare "—" would be the same hole in prettier clothes.
    expect(judge.disagreementsUnread?.length ?? 0).toBeGreaterThan(30);
    expect(judge.notMeasured).not.toBe(judge.pass);
    expect(judge.notMeasured).not.toBe(judge.watch);
  });
});
