import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyReasonKey, emptyReasonValues } from "@/lib/eval-empty-reason";
import { readSweep } from "@/lib/eval-sweep";

/**
 * A blind read and a measured absence are different facts, and this view used to print one
 * sentence for both.
 *
 * Four causes collapsed into a single `null`, and the sentence attached to it named
 * `data/eval/` — a bundle the reader stopped opening when the sweep moved to HTTP. So an
 * operator debugging a blank screen was pointed at a file the code never touches, while the
 * screen asserted "no readable sweep" about a directory it may never have managed to ask for.
 *
 * These pin both halves: the classifier really distinguishes the four, and the catalogues carry
 * one sentence for each with no shared fallback to slide back into.
 */

const LOCALES = ["fr", "en", "de"] as const;
const KINDS = ["unreachable", "refused", "contract", "absent"] as const;
const URL = "http://backend.test/observability/eval-sweep";

function messages(locale: string): Record<string, unknown> {
  return JSON.parse(readFileSync(join(process.cwd(), `messages/${locale}.json`), "utf8"));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("why the sweep is missing", () => {
  it("says UNREACHABLE when the request never completed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("ECONNREFUSED"))),
    );
    const result = await readSweep(URL);
    expect(result.ok).toBe(false);
    expect(result.ok === false && result.why.kind).toBe("unreachable");
  });

  it("says REFUSED, with the status, when the backend answered an error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("nope", { status: 503 }))),
    );
    const result = await readSweep(URL);
    expect(result.ok === false && result.why).toEqual({ kind: "refused", status: 503 });
  });

  it("says CONTRACT when the payload is not the shape this build expects", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ available: true, runs: "not-an-array" }), { status: 200 }),
        ),
      ),
    );
    const result = await readSweep(URL);
    expect(result.ok === false && result.why.kind).toBe("contract");
  });

  /**
   * The one case that is a fact about the EVALUATION rather than about the read. It must not be
   * reachable by any of the three above, or the screen would tell an operator there is nothing
   * to see when it simply could not look.
   */
  it("says ABSENT only when the backend answered and declared itself unavailable", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify({ available: false }), { status: 200 })),
      ),
    );
    const result = await readSweep(URL);
    expect(result.ok === false && result.why).toEqual({ kind: "absent" });
  });
});

describe("the sentence each cause resolves to", () => {
  it("gives every cause its own key, and never shares one", () => {
    const keys = KINDS.map((kind) =>
      emptyReasonKey(
        kind === "refused"
          ? { kind, status: 503 }
          : kind === "absent"
            ? { kind }
            : { kind, detail: "x" },
      ),
    );
    expect(new Set(keys).size).toBe(KINDS.length);
    // A successful read with nothing in it is an observed absence, not a fourth failure.
    expect(emptyReasonKey(null)).toBe("absent");
  });

  it("carries the status only where it means something", () => {
    expect(emptyReasonValues({ kind: "refused", status: 401 })).toEqual({ status: 401 });
    expect(emptyReasonValues(null)).toEqual({ status: 0 });
  });

  it.each(LOCALES)("%s holds a distinct sentence for all four causes", (locale) => {
    const catalogue = messages(locale) as {
      eval: {
        sweep: { empty: Record<string, string> };
        catalogue: { empty: Record<string, string> };
      };
    };
    for (const block of [catalogue.eval.sweep.empty, catalogue.eval.catalogue.empty]) {
      // The shared fallback is GONE. While it existed, a missing per-cause key would have
      // silently resolved to the one sentence that named a dead file — the exact failure mode
      // this change removes.
      expect(block.body).toBeUndefined();
      const sentences = KINDS.map((kind) => block[kind]);
      for (const sentence of sentences) expect(sentence?.length ?? 0).toBeGreaterThan(20);
      expect(new Set(sentences).size).toBe(KINDS.length);
    }
    // Only the refusal spends the placeholder, and it must actually contain it.
    expect(catalogue.eval.sweep.empty.refused).toContain("{status}");
    expect(catalogue.eval.catalogue.empty.refused).toContain("{status}");
  });

  it.each(LOCALES)("%s no longer points the operator at the retired bundle", (locale) => {
    const raw = readFileSync(join(process.cwd(), `messages/${locale}.json`), "utf8");
    expect(raw).not.toContain("data/eval");
  });
});
