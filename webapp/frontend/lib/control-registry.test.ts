/**
 * The registry's own invariants — the ones the three surfaces broke independently.
 *
 * The headline defect this module exists for was not "a wrong threshold". It was that on
 * Qualité IA a row could read **"0 % · seuil ≤ 10 % · Critique"**: the status was computed
 * from `Math.max(over_refusal_rate, under_refusal_rate)` while the cell displayed `over`. A
 * number that honours its own bar and is still marked critical is not a wrong value, it is a
 * screen that has stopped meaning anything.
 *
 * So the central test here is an IDENTITY, not a spot-check: for every control, parse the
 * value and the target BACK from what would reach the operator, recompute the state, and
 * require it to equal the state the registry reported. Any derivation that reads a second
 * number fails it, whatever that number is.
 *
 * Lot 2 of `docs/status/coherence-mesuree-run.md` adds the cross-surface half — that the row
 * `overview-dashboard` renders and the row `signals-table` renders are equal field by field —
 * once both are wired onto `readControls()`. Today neither is, and asserting equality between
 * two things that do not yet exist would be a test of nothing.
 */

import { describe, expect, it } from "vitest";

import {
  CONTROL_IDS,
  type ControlId,
  type ControlPayload,
  metricFor,
  readControl,
  readControls,
} from "./control-registry";
import { controlState } from "./overview";

/**
 * One payload, deliberately adversarial: every control breaches, the two refusal faces are as
 * far apart as they can be (0 % over, 60 % under), and firewall recall and F1 differ. Those
 * are the exact shapes that produced three numbers for one measurement.
 */
const PAYLOAD: ControlPayload = {
  slo: {
    metric: "rag.faithfulness.mean",
    threshold: 0.7,
    target: 0.95,
    n: 120,
    n_good: 88,
    n_bad: 32,
    good_rate: 0.7333,
    error_budget: 0.05,
    budget_consumed: 0.27,
    budget_remaining: -0.22,
    burn_rate: 5.3,
    burn_rate_fast: 6.1,
    breaching: true,
  },
  toxicity: { n_turns: 400, n_toxic: 3, toxicity_rate: 0.0075, flagged: [] },
  pii: { n_turns: 400, n_with_leak: 2, leak_rate: 0.005, total_leaked: 4, examples: [] },
  refusal: {
    n_legit: 20,
    n_forbidden: 10,
    legit_refused: 0,
    forbidden_allowed: 6,
    over_refusal_rate: 0,
    under_refusal_rate: 0.6,
  },
  conformance: {
    n_calls: 50,
    n_fields_checked: 210,
    n_conformant: 205,
    n_violations: 5,
    conformance_rate: 0.9762,
    violations: [],
  },
  tools: { total: 88, allowed: 80, denied: 6, errored: 2, arg_failures: 1, validity_rate: 0.9091 },
  firewall: {
    n_positive: 25,
    n_negative: 25,
    true_positive: 19,
    false_negative: 6,
    false_positive: 0,
    true_negative: 25,
    precision: 1,
    recall: 0.76,
    f1: 0.8636,
  },
};

/** An empty-but-present payload: every source answered, nothing was measured. */
const EMPTY: ControlPayload = {
  toxicity: { n_turns: 0, n_toxic: 0, toxicity_rate: 0, flagged: [] },
  pii: { n_turns: 0, n_with_leak: 0, leak_rate: 0, total_leaked: 0, examples: [] },
  tools: { total: 0, allowed: 0, denied: 0, errored: 0, arg_failures: 0, validity_rate: 0 },
};

/** Parse a rendered value or bar back to a ratio: `"73%"` → 0.73, `"F1 ≥ 0.90"` → 0.9. */
function parseRatio(text: string): number {
  const percent = /(-?\d+(?:\.\d+)?)\s*%/.exec(text);
  if (percent) return Number(percent[1]) / 100;
  const bare = /(-?\d+(?:\.\d+)?)/.exec(text);
  if (!bare) throw new Error(`unparseable: ${text}`);
  return Number(bare[1]);
}

/** Which way the bar points, read from the bar itself rather than from the spec. */
function parseDirection(target: string): "higher" | "lower" {
  if (target.includes("≥") || target.includes(">")) return "higher";
  if (target.includes("≤") || target.includes("<")) return "lower";
  // `= 0` and `= 100%` are exact bars. A rate that must be 0 is "lower"; one that must be
  // 100 % is "higher". Reading the direction off the VALUE of the bar keeps this honest.
  return parseRatio(target) === 0 ? "lower" : "higher";
}

describe("the state of a control derives from the value the operator sees", () => {
  it("answers every declared control for a full payload", () => {
    const rows = readControls(PAYLOAD);
    expect(rows.map((r) => r.id)).toEqual([...CONTROL_IDS]);
  });

  it("recomputes to the SAME state from the rendered value and the rendered bar", () => {
    for (const row of readControls(PAYLOAD)) {
      const recomputed = controlState(
        parseRatio(row.value),
        parseRatio(row.target),
        parseDirection(row.target),
      );
      expect(
        recomputed.key,
        `${row.id}: shows «${row.value}» against «${row.target}» but reports state «${row.state.key}» — the status is being computed from a number the operator cannot see`,
      ).toBe(row.state.key);
    }
  });

  it("never renders the self-contradiction that started this: honoured bar, failing state", () => {
    for (const row of readControls(PAYLOAD)) {
      if (row.noData) continue;
      const meets =
        parseDirection(row.target) === "higher"
          ? parseRatio(row.value) >= parseRatio(row.target)
          : parseRatio(row.value) <= parseRatio(row.target);
      if (meets) {
        expect(row.state.key, `${row.id} honours its bar and still reads ${row.state.key}`).toBe(
          "ok",
        );
      }
    }
  });
});

describe("two opposite failures are never one number", () => {
  it("splits refusal into two controls reading two different fields", () => {
    const over = readControl("refusalOver", PAYLOAD);
    const under = readControl("refusalUnder", PAYLOAD);
    expect(over?.value).toBe("0%"); // no legitimate question was turned away
    expect(under?.value).toBe("60%"); // six of ten forbidden ones were carried out
    expect(over?.metric).not.toBe(under?.metric);
  });

  it("marks the safety face failing and the utility face healthy — not one verdict for both", () => {
    expect(readControl("refusalOver", PAYLOAD)?.state.key).toBe("ok");
    expect(readControl("refusalUnder", PAYLOAD)?.state.key).toBe("fail");
  });

  it("keeps the two firewall views distinct, and each says which view it is", () => {
    const f1 = readControl("firewall", PAYLOAD);
    const bypass = readControl("injectionBypass", PAYLOAD);
    expect(f1?.value).toBe("86%");
    expect(bypass?.value).toBe("24%");
    // …and the third number, recall, is still reachable — as DETAIL, not as a rival headline.
    expect(f1?.detail?.values.recall).toBe("76%");
  });
});

describe("an unmeasured control says so instead of showing a zero", () => {
  it("renders an em dash and a neutral tone when the sample is empty", () => {
    for (const row of readControls(EMPTY)) {
      expect(row.noData, `${row.id} claims data from an empty sample`).toBe(true);
      expect(row.value).toBe("—");
      expect(row.state.tone).toBe("neutral");
      expect(row.severity).toBe(0);
    }
  });

  it("omits a control whose source is absent entirely, rather than inventing one", () => {
    expect(readControl("firewall", {})).toBeNull();
    expect(readControls({})).toEqual([]);
  });
});

describe("the registry is the join key with the signal catalogue", () => {
  it("gives every control a distinct metric id", () => {
    const metrics = CONTROL_IDS.map((id: ControlId) => metricFor(id));
    expect(new Set(metrics).size).toBe(metrics.length);
  });

  it("declares which bars are calibrated, and does not flatter the rest", () => {
    const rows = readControls(PAYLOAD);
    const calibrated = rows.filter((r) => r.calibrated).map((r) => r.id);
    // Exactly one bar is read from the backend (`slo.target`). Every other bar is a number
    // this repo chose — ADR 0021's lesson, applied on screen: a chosen bar must say so.
    expect(calibrated).toEqual(["faithfulness"]);
  });
});
