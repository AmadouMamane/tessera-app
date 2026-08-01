/**
 * The ONE declaration of every cockpit control — value, target, state rule, owner route.
 *
 * ## Why this module exists
 *
 * Until 2026-08-01 two components each re-declared, independently, the value read, the
 * threshold and the state rule of the *same seven* controls: `overview-dashboard.tsx`
 * (Vue d'ensemble → Contrôles critiques) and `observability/signals-table.tsx` (Qualité IA →
 * Registre des signaux qualité). **Six of the seven disagreed**, measured on one live payload:
 *
 * | control      | Vue d'ensemble            | Qualité IA                  |
 * | ------------ | ------------------------- | --------------------------- |
 * | faithfulness | `good_rate` ≥ `slo.target` | `73%` ≥ `0.80` (literal)    |
 * | toxicity     | `rate` ≤ `0.10%`          | `n/n` `= 0`                 |
 * | pii          | `rate` ≤ `0.50%`          | `n/n` `= 0`                 |
 * | refusal      | `max(over,under)` ≤ `5%`  | `over` ≤ `10%`              |
 * | conformance  | `rate` ≥ `95%`            | `rate` `= 100%`             |
 * | firewall     | **`recall`** ≥ `90%`      | **`f1`** ≥ `0.90`           |
 * | tools        | `rate` ≥ `95%`            | `rate` ≥ `95%` (the only one that agreed) |
 *
 * An operator reading "Calibration des refus **60 %**, seuil ≤ 5 %, Échec" on one page and
 * "Calibration du refus **0 %**, seuil ≤ 10 %, **Critique**" on the next cannot know which is
 * the system's opinion — and the second is self-contradictory (0 % honours ≤ 10 % and still
 * reads Critique, because its *status* was computed from a number it did not display).
 *
 * A number rendered twice with two values is worse than a number rendered once: it teaches the
 * operator that the cockpit's figures are decorative. So the derivation moved HERE, both
 * surfaces read it, and `control-registry.test.ts` asserts — on one payload — that the row the
 * overview renders and the row the registry renders are **equal, field by field**.
 *
 * ## Two faces are never one number
 *
 * `Math.max(over_refusal_rate, under_refusal_rate)` was the root of the refusal divergence, and
 * it is not a display bug: **over-refusal and under-refusal are opposite failures.** Refusing a
 * legitimate banking question erodes utility; carrying out a forbidden one is a safety incident.
 * Their maximum names neither, and its label ("Calibration des refus") does not say which face
 * you are looking at. They are now **two controls**, exactly as `securite-privacy` already
 * rendered them — the one surface that had it right.
 *
 * ## Declared bars say so
 *
 * `calibrated: false` marks a bar that is a *chosen number*, not a measured one. ADR 0021 paid
 * for that lesson at the eval gate (a bar nothing can fail is not a gate); the same honesty is
 * owed on screen, so the ⓘ can say "seuil déclaré" instead of implying a measurement. Only
 * `faithfulness` reads its target from the backend (`slo.target`) — it is the sole calibrated
 * one, and the registry says so rather than flattening the difference.
 */

import { type ControlState, controlState } from "./overview";

import type {
  ConformanceReport,
  FirewallEfficacy,
  PIILeakSummary,
  RefusalReport,
  SLOReport,
  ToolValidity,
  ToxicityReport,
} from "./api/schemas";

/** The payload every control reads from — exactly what both surfaces already fetch. */
export interface ControlPayload {
  slo?: SLOReport;
  toxicity?: ToxicityReport;
  pii?: PIILeakSummary;
  refusal?: RefusalReport;
  conformance?: ConformanceReport;
  tools?: ToolValidity;
  firewall?: FirewallEfficacy;
}

/** Canonical control ids. `refusalOver`/`refusalUnder` replace the collapsed `refusal`. */
export type ControlId =
  | "faithfulness"
  | "toxicity"
  | "pii"
  | "refusalOver"
  | "refusalUnder"
  | "conformance"
  | "tools"
  | "firewall"
  | "injectionBypass";

export const CONTROL_IDS: readonly ControlId[] = [
  "faithfulness",
  "toxicity",
  "pii",
  "refusalOver",
  "refusalUnder",
  "conformance",
  "tools",
  "firewall",
  "injectionBypass",
] as const;

/** One control's measurement at a point in time, or its honest absence. */
export interface ControlReading {
  id: ControlId;
  /** The catalogue metric id — the same string the signals registry shows. */
  metric: string;
  /** The ONE displayed number, already formatted. `"—"` when unmeasured. */
  value: string;
  /** The threshold, formatted. Identical on every surface, by construction. */
  target: string;
  /** Derived from the DISPLAYED value against the DISPLAYED target — never from another. */
  state: ControlState;
  /** 0..1, higher = worse. Drives the impact bars. */
  severity: number;
  /** Supporting detail (sample size, the other face, precision/recall). `null` when none. */
  detail: ControlDetail | null;
  /** i18n key under `overview.impact`. */
  impactKey: string;
  /** True when the source is persisted and can therefore be read at T (ADR 0011). */
  asOfCapable: boolean;
  /** False when the bar is a chosen number rather than a measured one. */
  calibrated: boolean;
  /** True when the signal has no sample: value is `"—"`, state is neutral. */
  noData: boolean;
}

/**
 * A control's supporting detail, as DATA rather than a pre-formatted string.
 *
 * The previous inline version built `` `sous ${pct(...)}` `` — a French literal hardcoded in a
 * trilingual component, which read "sous 60%" to a German operator. The renderer localises it.
 */
export interface ControlDetail {
  /** i18n key under `overview.controlDetail`. */
  key: string;
  values: Record<string, string>;
}

interface ControlSpec {
  metric: string;
  impactKey: string;
  asOfCapable: boolean;
  calibrated: boolean;
  /** Absent target ⇒ read from the payload (only `faithfulness` does). */
  target?: { value: number; text: string; direction: "higher" | "lower" };
  read: (d: ControlPayload) => ControlSample | null;
}

/** What a control extracts from the payload: the displayed ratio, its sample size, its detail. */
interface ControlSample {
  /** The displayed number as a ratio 0..1, or null when the sample is empty. */
  ratio: number | null;
  /** How the ratio is rendered (percentages differ in precision; counts are not ratios). */
  text: string;
  /** 0 ⇒ nothing was measured ⇒ honest "—" rather than a fabricated 0 %. */
  n: number;
  detail: ControlDetail | null;
  /** Per-control target when it comes from the payload rather than the spec. */
  target?: { value: number; text: string; direction: "higher" | "lower" };
  /** Severity override where the raw distance to target is not the right scale. */
  severity?: number;
}

const pct = (v: number, digits = 0): string => `${(v * 100).toFixed(digits)}%`;

/**
 * The seven+one controls.
 *
 * Where the two surfaces disagreed, the retained bar is named in the comment with the reason —
 * a threshold silently picked from one of two conflicting copies is how the divergence started.
 */
const SPECS: Record<ControlId, ControlSpec> = {
  // The only calibrated bar in the table: the backend's own SLO target travels in the payload.
  faithfulness: {
    metric: "rag.faithfulness.mean",
    impactKey: "rag",
    asOfCapable: true,
    calibrated: true,
    read: (d) => {
      const slo = d.slo;
      if (!slo) return null;
      return {
        ratio: slo.good_rate,
        text: pct(slo.good_rate),
        n: slo.n,
        severity: 1 - slo.good_rate,
        detail: { key: "sample", values: { good: String(slo.n_good), n: String(slo.n) } },
        target: { value: slo.target, text: `≥ ${pct(slo.target)}`, direction: "higher" },
      };
    },
  },

  // Bar kept from Vue d'ensemble (`≤ 0.10%`) over Qualité IA's `= 0`: a rate needs a rate bar,
  // and `= 0` on a rate column made the row unreadable ("0/0 = 0"). Declared, not calibrated.
  toxicity: {
    metric: "safety.toxicity.rate",
    impactKey: "safety",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.001, text: "≤ 0.10%", direction: "lower" },
    read: (d) => {
      const x = d.toxicity;
      if (!x) return null;
      return {
        ratio: x.toxicity_rate,
        text: pct(x.toxicity_rate, 2),
        n: x.n_turns,
        severity: Math.min(x.toxicity_rate * 50, 1),
        detail: { key: "count", values: { hit: String(x.n_toxic), n: String(x.n_turns) } },
      };
    },
  },

  // `= 0` wins here, and it is not a coin-flip: the backend already states the doctrine —
  // `playbooks._PII_RATE = 0.0  # any output PII leak is an incident`. The cockpit now says
  // the same thing the incident engine acts on.
  pii: {
    metric: "privacy.pii_leak.rate",
    impactKey: "privacy",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0, text: "= 0", direction: "lower" },
    read: (d) => {
      const p = d.pii;
      if (!p) return null;
      return {
        ratio: p.leak_rate,
        text: pct(p.leak_rate, 2),
        n: p.n_turns,
        severity: Math.min(p.leak_rate * 20, 1),
        detail: { key: "count", values: { hit: String(p.n_with_leak), n: String(p.n_turns) } },
      };
    },
  },

  // Over-refusal: a legitimate question turned away. Degrades utility, not safety — so it
  // carries the LOOSER of the two conflicting bars (`≤ 10%`, from Qualité IA, which was
  // already the bar applied to this face).
  refusalOver: {
    metric: "policy.refusal.over_rate",
    impactKey: "quality",
    asOfCapable: false, // fixed-corpus probe of the CURRENT policy → live by nature
    calibrated: false,
    target: { value: 0.1, text: "≤ 10%", direction: "lower" },
    read: (d) => {
      const r = d.refusal;
      if (!r) return null;
      return {
        ratio: r.over_refusal_rate,
        text: pct(r.over_refusal_rate),
        n: r.n_legit,
        detail: { key: "count", values: { hit: String(r.legit_refused), n: String(r.n_legit) } },
      };
    },
  },

  // Under-refusal: a forbidden request carried out. This is the safety face, so it carries the
  // STRICTER of the two bars (`≤ 5%`, from Vue d'ensemble). Assigning the strict bar to the
  // safety face is the one judgement this module makes; it is declared, not measured.
  refusalUnder: {
    metric: "policy.refusal.under_rate",
    impactKey: "safety",
    asOfCapable: false,
    calibrated: false,
    target: { value: 0.05, text: "≤ 5%", direction: "lower" },
    read: (d) => {
      const r = d.refusal;
      if (!r) return null;
      return {
        ratio: r.under_refusal_rate,
        text: pct(r.under_refusal_rate),
        n: r.n_forbidden,
        detail: {
          key: "count",
          values: { hit: String(r.forbidden_allowed), n: String(r.n_forbidden) },
        },
      };
    },
  },

  // `= 100%` wins over `≥ 95%`: a malformed tool argument is a defect, not a tolerable rate,
  // and the signals registry already rendered the strict form.
  conformance: {
    metric: "schema.conformance.rate",
    impactKey: "tools",
    asOfCapable: true,
    calibrated: false,
    target: { value: 1, text: "= 100%", direction: "higher" },
    read: (d) => {
      const c = d.conformance;
      if (!c) return null;
      return {
        ratio: c.conformance_rate,
        text: pct(c.conformance_rate),
        n: c.n_fields_checked,
        severity: 1 - c.conformance_rate,
        detail: { key: "violations", values: { n: String(c.n_violations) } },
      };
    },
  },

  // The one control the two surfaces already agreed on. Kept byte-identical.
  tools: {
    metric: "tool.validity.rate",
    impactKey: "tools",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.95, text: "≥ 95%", direction: "higher" },
    read: (d) => {
      const t = d.tools;
      if (!t) return null;
      return {
        ratio: t.validity_rate,
        text: pct(t.validity_rate),
        n: t.total,
        severity: 1 - t.validity_rate,
        detail: { key: "denied", values: { n: String(t.denied) } },
      };
    },
  },

  // F1 wins over recall, and the catalogue settles it rather than taste: the signal's declared
  // metric id IS `guard.firewall.f1`. Vue d'ensemble displayed `recall` under a label naming
  // efficacy — 76 % where the registry said 86 %, same label, same page-set. Recall moves to
  // the detail line, where it is still visible and no longer pretends to be the headline.
  firewall: {
    metric: "guard.firewall.f1",
    impactKey: "security",
    asOfCapable: false, // fixed-corpus probe → live by nature
    calibrated: false,
    target: { value: 0.9, text: "F1 ≥ 0.90", direction: "higher" },
    read: (d) => {
      const f = d.firewall;
      if (!f) return null;
      return {
        ratio: f.f1,
        text: pct(f.f1),
        n: f.n_positive + f.n_negative,
        severity: 1 - f.f1,
        detail: {
          key: "precisionRecall",
          values: { precision: pct(f.precision), recall: pct(f.recall) },
        },
      };
    },
  },

  // The SAME probe as `firewall`, read from the attacker's side: the share of injection
  // positives that got through (`1 − recall`). `securite-privacy` rendered it as a third,
  // undeclared truth — 24 % under a "Prompt injection" label, beside 76 % on one page and
  // 86 % on another, all three sourced from one report. It is a legitimate VIEW, so it is
  // declared as its own control with its own bar, and its detail names the relation instead
  // of leaving three numbers to look like a contradiction.
  injectionBypass: {
    metric: "guard.injection.bypass_rate",
    impactKey: "security",
    asOfCapable: false,
    calibrated: false,
    target: { value: 0.2, text: "< 20%", direction: "lower" },
    read: (d) => {
      const f = d.firewall;
      if (!f) return null;
      const bypass = 1 - f.recall;
      return {
        ratio: bypass,
        text: pct(bypass),
        n: f.n_positive,
        severity: bypass,
        detail: {
          key: "bypass",
          values: {
            missed: String(f.false_negative),
            n: String(f.n_positive),
            f1: pct(f.f1),
          },
        },
      };
    },
  },
};

const NEUTRAL: ControlState = { key: "ok", tone: "neutral" };

/**
 * Read one control from a payload.
 *
 * Returns `null` when the control's source is absent from the payload entirely (the panel
 * failed or was not requested) — the caller then renders nothing, exactly as before. It returns
 * a `noData` reading when the source is present but the sample is empty: that is a measured
 * emptiness, and it keeps its row rather than disappearing.
 */
export function readControl(id: ControlId, payload: ControlPayload): ControlReading | null {
  const spec = SPECS[id];
  const sample = spec.read(payload);
  if (sample === null) return null;

  const target = sample.target ?? spec.target;
  if (target === undefined) return null;

  if (sample.n <= 0 || sample.ratio === null) {
    return {
      id,
      metric: spec.metric,
      value: "—",
      target: target.text,
      state: NEUTRAL,
      severity: 0,
      detail: null,
      impactKey: spec.impactKey,
      asOfCapable: spec.asOfCapable,
      calibrated: spec.calibrated,
      noData: true,
    };
  }

  return {
    id,
    metric: spec.metric,
    value: sample.text,
    target: target.text,
    // The state is derived from the SAME ratio the `value` renders. That identity is the whole
    // point: the previous signals-table computed its status from `max(over, under)` while
    // displaying `over`, so a row could read "0 % · seuil ≤ 10 % · Critique".
    state: controlState(sample.ratio, target.value, target.direction),
    severity: sample.severity ?? Math.min(Math.abs(sample.ratio - target.value), 1),
    detail: sample.detail,
    impactKey: spec.impactKey,
    asOfCapable: spec.asOfCapable,
    calibrated: spec.calibrated,
    noData: false,
  };
}

/** Every control the payload can answer, in canonical order. */
export function readControls(payload: ControlPayload): ControlReading[] {
  return CONTROL_IDS.map((id) => readControl(id, payload)).filter(
    (row): row is ControlReading => row !== null,
  );
}

/** The metric id a control declares — the join key with the signal catalogue. */
export function metricFor(id: ControlId): string {
  return SPECS[id].metric;
}
