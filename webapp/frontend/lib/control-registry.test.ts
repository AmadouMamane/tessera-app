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
 * The cross-surface half is enforced STRUCTURALLY rather than here, by
 * `control-coherence.test.ts`: all three surfaces now call `readControls()`, and no bar may be
 * declared anywhere else in the tree. Asserting field-by-field equality between three callers
 * of one pure function would test the language, not the cockpit. What is worth testing is that
 * the function itself cannot produce a row whose colour and whose number come from different
 * places — which is what the identity assertion below does.
 *
 * It has already earned that: it caught `calibration` (agreement shown under a κ bar, coloured
 * by `lenient`) and `clusters` (a `—` bar still deciding a pill) during the relocation, both
 * copied faithfully from `signals-table.tsx` and both previously unreported.
 */

import { describe, expect, it } from "vitest";

import {
  CONTROL_IDS,
  type ControlId,
  type ControlPayload,
  controlFmt,
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
  crossTenant: { n_turns: 400, n_leaks: 1, leak_rate: 0.0025, leaks: [] },
  privilege: {
    n_granted: 40,
    n_used: 31,
    n_over_provisioned: 9,
    n_violations: 2,
    utilization_rate: 0.775,
    over_provisioned: [],
    violations: [],
    usage: [],
  },
  inversion: {
    available: true,
    n_memories: 60,
    n_recoverable: 3,
    recovery_rate: 0.05,
    threshold: 0.8,
    matches: [],
  },
  calibration: { available: true, n: 40, kappa: 0.42, agreement: 0.71, lenient: true },
  citations: {
    n_turns: 120,
    n_citations: 300,
    n_unsupported: 21,
    validity_rate: 0.93,
    unsupported_examples: [],
  },
  contradiction: { n_sessions: 30, n_turns: 120, n_contradictions: 3, pairs: [] },
  predictor: {
    n: 80,
    n_predicted_fail: 20,
    n_actual_fail: 24,
    true_positive: 12,
    false_positive: 8,
    false_negative: 12,
    true_negative: 48,
    precision: 0.6,
    recall: 0.5,
  },
  clusters: { available: true, n_failures: 12, k: 4, mean_purity: 0.7, clusters: [] },
  localeFormat: {
    n_turns: 120,
    n_amounts: 90,
    n_violations: 4,
    correctness_rate: 0.9556,
    examples: [],
  },
  cost: {
    n_turns: 120,
    total_tokens: 96_000,
    mean_tokens: 800,
    max_tokens: 4000,
    threshold_tokens: 600,
    estimated_cost_eur: 1.44,
    n_anomalies: 5,
    anomalies: [],
  },
  routing: {
    n: 120,
    mismatches: 9,
    code_switches: 2,
    mismatch_rate: 0.075,
    code_switch_rate: 0.017,
  },
  funnel: {
    n_turns: 120,
    languages: [
      {
        language: "fr",
        n_turns: 60,
        n_sessions: 20,
        mean_score: 0.8,
        single_turn_rate: 0.3,
        low_score_rate: 0.1,
      },
      {
        language: "de",
        n_turns: 60,
        n_sessions: 20,
        mean_score: 0.6,
        single_turn_rate: 0.4,
        low_score_rate: 0.3,
      },
    ],
  },
  anomalies: { n_sessions: 30, n_anomalous: 4, sessions: [] },
  intent: {
    n: 120,
    distribution: { balance: 60, loan: 60 },
    unknown: 7,
    low_confidence: 18,
    low_confidence_rate: 0.15,
  },
};

/** An empty-but-present payload: every source answered, nothing was measured. */
const EMPTY: ControlPayload = {
  toxicity: { n_turns: 0, n_toxic: 0, toxicity_rate: 0, flagged: [] },
  pii: { n_turns: 0, n_with_leak: 0, leak_rate: 0, total_leaked: 0, examples: [] },
  tools: { total: 0, allowed: 0, denied: 0, errored: 0, arg_failures: 0, validity_rate: 0 },
  // The one source that can answer "I could not run": an unavailable probe is not a clean
  // result, and `?? 0` used to make it look like one on `securite-privacy`.
  inversion: { available: false },
};

/**
 * Parse a rendered value or bar back to a ratio: `"73 %"` → 0.73, `"F1 ≥ 0,90"` → 0.9.
 *
 * IT MUST SPEAK THE NOTATION IT JUDGES. Since 2026-08-16 the registry formats through
 * `Intl.NumberFormat` in the reader's language, so the French default renders `0,50 %` — a comma
 * for the decimal and a narrow no-break space (U+202F) before the sign. The previous regex,
 * built for `0.50%`, found `50 %` inside that string and read **fifty percent** where the screen
 * said half a percent. The test then reported a state mismatch, which was true of its own
 * parsing and of nothing else.
 *
 * So: strip the spaces the locale uses to group and to precede the sign, then accept either
 * decimal mark. A parser that only understood one notation would make this whole file a
 * statement about English rendering.
 */
function parseRatio(text: string): number {
  // U+202F narrow no-break, U+00A0 no-break, plain space — all three are grouping or unit
  // spacing in one locale or another, and none of them is part of the number.
  const normalised = text.replace(/[\s  ]/g, "").replace(",", ".");
  const percent = /(-?\d+(?:\.\d+)?)%/.exec(normalised);
  if (percent) return Number(percent[1]) / 100;
  const bare = /(-?\d+(?:\.\d+)?)/.exec(normalised);
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
      // A control with no bar renders "—" and makes no verdict; there is nothing to recompute,
      // and the next test is the one that holds it neutral.
      if (row.target === "—") continue;
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

  it("makes no verdict where it shows no bar", () => {
    // `clusters` counts failure THEMES. Twelve is not worse than four, so there is no
    // threshold — and `signals-table` nonetheless coloured the row from one, rendering the bar
    // as "—" while a hidden `n_failures === 0` decided the pill.
    const clusters = readControl("clusters", PAYLOAD);
    expect(clusters?.target).toBe("—");
    expect(clusters?.state.tone).toBe("neutral");
    expect(clusters?.severity).toBe(0);
    expect(clusters?.value).toBe("12");
  });

  it("never renders the self-contradiction that started this: honoured bar, failing state", () => {
    for (const row of readControls(PAYLOAD)) {
      if (row.noData || row.target === "—") continue;
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
    // The NUMBER is the claim; the notation belongs to the reader's language and is derived
    // from the same formatter the registry uses. A literal "0%" here would be an assertion
    // about English rendering wearing the costume of an assertion about refusals.
    expect(over?.value).toBe(controlFmt("fr").pct(0)); // no legitimate question was turned away
    expect(under?.value).toBe(controlFmt("fr").pct(0.6)); // six of ten forbidden ones were carried out
    expect(over?.metric).not.toBe(under?.metric);
  });

  it("marks the safety face failing and the utility face healthy — not one verdict for both", () => {
    expect(readControl("refusalOver", PAYLOAD)?.state.key).toBe("ok");
    expect(readControl("refusalUnder", PAYLOAD)?.state.key).toBe("fail");
  });

  it("keeps the two firewall views distinct, and each says which view it is", () => {
    const f1 = readControl("firewall", PAYLOAD);
    const bypass = readControl("injectionBypass", PAYLOAD);
    expect(f1?.value).toBe(controlFmt("fr").pct(0.86));
    expect(bypass?.value).toBe(controlFmt("fr").pct(0.24));
    // …and the third number, recall, is still reachable — as DETAIL, not as a rival headline.
    expect(f1?.detail?.values.recall).toBe(controlFmt("fr").pct(0.76));
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

  it("names the measured emptiness where the source can — turns read, nothing of their kind", () => {
    // The quality page's three na rows (served 2026-08-25): each source ANSWERED — the
    // window simply held nothing of the thing it measures. That fact travels as the
    // reading's detail; a bare dash would fold it into "the source said nothing".
    const fmt = controlFmt("fr");
    const slo = readControl("faithfulness", {
      slo: {
        metric: "rag.faithfulness.mean",
        threshold: 0.7,
        target: 0.95,
        n: 0,
        n_good: 0,
        n_bad: 0,
        good_rate: 0,
        error_budget: 0.05,
        budget_consumed: 0,
        budget_remaining: 1,
        burn_rate: 0,
        burn_rate_fast: 0,
        breaching: false,
      },
    });
    expect(slo?.noData).toBe(true);
    expect(slo?.detail).toEqual({ key: "sloEmpty", values: {} });

    const citations = readControl("citations", {
      citations: {
        n_turns: 96,
        n_citations: 0,
        n_unsupported: 0,
        validity_rate: 1,
        unsupported_examples: [],
      },
    });
    expect(citations?.noData).toBe(true);
    expect(citations?.detail).toEqual({
      key: "citationsEmpty",
      values: { turns: fmt.num(96, 0) },
    });

    const locale = readControl("localeFormat", {
      localeFormat: {
        n_turns: 96,
        n_amounts: 0,
        n_violations: 0,
        correctness_rate: 1,
        examples: [],
      },
    });
    expect(locale?.noData).toBe(true);
    expect(locale?.detail).toEqual({
      key: "localeFormatEmpty",
      values: { turns: fmt.num(96, 0) },
    });

    // The negative control: a source that carries no empty-shape stays a plain dash —
    // the detail is never invented for it.
    expect(readControl("toxicity", EMPTY)?.noData).toBe(true);
    expect(readControl("toxicity", EMPTY)?.detail).toBeNull();
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
    // Two bars travel in the payload rather than being chosen here: `slo.target` and
    // `cost.threshold_tokens`. Every other bar is a number this repo picked — ADR 0021's
    // lesson applied on screen: a chosen bar must say it was chosen.
    expect(calibrated).toEqual(["faithfulness", "cost"]);
  });
});
