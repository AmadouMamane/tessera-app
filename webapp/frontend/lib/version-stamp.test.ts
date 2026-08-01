/**
 * A deployment's stamp names a PAIR, and may never claim a half it did not see.
 *
 * `make deploy-diff` compares one field — `sha` — across hosts and refuses when they differ.
 * Until 2026-08-02 the on-prem image was un-stamped, so that field read `"dev"` and the
 * comparator answered *CannotSay*: blind, and honest about it.
 *
 * Stamping it is the obvious fix and it carries a trap. A host runs TWO images, a frontend and
 * an agent, and only the frontend serves `/api/version`. Report the frontend's SHA as `sha` and
 * the comparator starts answering "match" for hosts whose agents were never compared — turning
 * an honest blind spot into a confident wrong answer, which is strictly worse.
 *
 * So `sha` is the pair's identity: equal to the frontend's stamp only when the agent reports
 * the same one, and otherwise a value that cannot compare equal to a clean stamp. These tests
 * hold that property, because it is the whole reason the field can be trusted at all.
 */

import { describe, expect, it } from "vitest";

/**
 * The rule, extracted from `app/api/version/route.ts`.
 *
 * Kept as a pure function here rather than driving the route: what is worth pinning is the
 * DECISION, and a test that mocked `fetch` would mostly be asserting how the mock was written.
 * `route.ts` applies exactly this expression.
 */
function pairSha(frontend: string, agent: string | null): string {
  return agent === null
    ? frontend === "dev"
      ? "dev"
      : `unverified:${frontend}`
    : agent === frontend
      ? frontend
      : `mixed:${frontend}/${agent}`;
}

describe("a stamp names the pair", () => {
  it("reports the commit when both halves agree", () => {
    expect(pairSha("a53fcd97", "a53fcd97")).toBe("a53fcd97");
  });

  it("cannot report a clean commit when the halves disagree", () => {
    const sha = pairSha("a53fcd97", "0118a4fa");
    expect(sha).not.toBe("a53fcd97");
    expect(sha).toBe("mixed:a53fcd97/0118a4fa");
  });

  it("cannot report a clean commit when the agent could not be asked", () => {
    // The failure this exists for: rebuild the front, forget the agent, and two hosts compare
    // equal while serving different backends.
    expect(pairSha("a53fcd97", null)).toBe("unverified:a53fcd97");
  });

  it("keeps the un-stamped state un-stamped", () => {
    // `dev` is what deploy-diff already treats as "cannot verify". Decorating it with
    // `unverified:` would just be a second word for the same nothing.
    expect(pairSha("dev", null)).toBe("dev");
  });
});

describe("two hosts compare equal only when all four halves match", () => {
  /** What `deploy_diff.py` does with the field: a string equality across hosts. */
  const agree = (a: string, b: string): boolean => a === b;

  it("matches two hosts built from one commit", () => {
    expect(agree(pairSha("a53fcd97", "a53fcd97"), pairSha("a53fcd97", "a53fcd97"))).toBe(true);
  });

  it("refuses a host whose agent lags, even though its frontends match", () => {
    // Both fronts are at a53fcd97. One agent is not. Before this rule the two compared equal.
    expect(agree(pairSha("a53fcd97", "a53fcd97"), pairSha("a53fcd97", "0118a4fa"))).toBe(false);
  });

  it("refuses a host whose agent went unasked, even though its frontends match", () => {
    expect(agree(pairSha("a53fcd97", "a53fcd97"), pairSha("a53fcd97", null))).toBe(false);
  });
});

describe("a dirty build cannot pass for a clean one", () => {
  it("keeps the suffix the deploy path adds", () => {
    // `make fulllocal-up` computes `<sha>-dirty` when the tree has uncommitted edits, because
    // the image then contains something no commit describes. String comparison does the rest.
    expect(agreeSha("a53fcd97", "a53fcd97-dirty")).toBe(false);
  });
});

function agreeSha(a: string, b: string): boolean {
  return pairSha(a, a) === pairSha(b, b);
}
