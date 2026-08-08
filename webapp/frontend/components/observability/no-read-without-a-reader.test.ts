import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Two reads on the Qualité IA page cost a request nobody was waiting for.
 *
 *  - **`ai-act` polled every 30 s for a button.** Nothing on the page rendered it; its single
 *    consumer was the evidence bundle, which most sessions never generate. So every open tab
 *    asked the backend twice a minute, indefinitely, in case someone clicked. It is fetched at
 *    click time now — one request when it is wanted, and fresher than a 30-second-old cache.
 *
 *  - **the SLO was read twice.** The breach ribbon and the dashboard ask the same endpoint with
 *    the same arguments; only the ribbon's private key `slo-hero` made them two requests. Two
 *    reads of one endpoint are also two numbers that can disagree, which is the more expensive
 *    half: this page has already shipped that defect twice under other names.
 *
 * Both are invisible to every rendering test — the screen looks identical — so they are held
 * here, by reading the source. A performance property with no witness comes back.
 */

const DASHBOARD = readFileSync(
  join(process.cwd(), "components/observability/observability-dashboard.tsx"),
  "utf8",
);
const HERO = readFileSync(
  join(process.cwd(), "components/surveiller/signal-breach-hero.tsx"),
  "utf8",
);

describe("no standing poll for a read nothing renders", () => {
  it("does not keep `ai-act` as a polled query", () => {
    // The shape that was wrong: a `useQuery` for it, alive for the whole session.
    expect(DASHBOARD).not.toMatch(/const aiAct = useQuery\(/);
  });

  it("fetches it on demand, inside the evidence handler", () => {
    const handler = DASHBOARD.slice(
      DASHBOARD.indexOf("async function downloadQualityEvidence"),
      DASHBOARD.indexOf("return (", DASHBOARD.indexOf("async function downloadQualityEvidence")),
    );
    expect(handler).toContain("fetchQuery");
    expect(handler).toContain('queryKey: ["ai-act", asOf]');
    // A failed section leaves a hole in the pack; it must never make the pack WRONG, and it
    // must never stop the download of the sections that did answer.
    expect(handler).toContain(".catch(() => null)");
  });
});

describe("one endpoint, one key", () => {
  it("reads the SLO under the shared key, not a private one", () => {
    expect(HERO).not.toContain('"slo-hero"');
    expect(HERO).toContain('queryKey: ["slo", null, scope, period]');
  });

  /**
   * The `null` is the live instant, and it is what the dashboard's key holds while the operator
   * is not scrubbing (`asOf` is `null` in live mode, `asOf ?? undefined` on the wire). Pin both
   * halves: a later change to either side that breaks the match would silently restore the
   * second request, and nothing on screen would look different.
   */
  it("matches the dashboard's key shape, so the two observers share one cache entry", () => {
    expect(DASHBOARD).toContain('queryKey: ["slo", asOf, scope, period]');
    expect(DASHBOARD).toContain("fetchSLO(signal, asOf ?? undefined, scope, period)");
    expect(HERO).toContain("fetchSLO(signal, undefined, scope, period)");
  });
});
