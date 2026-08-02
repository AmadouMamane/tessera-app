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
 * operator that the cockpit's figures are decorative. So the derivation moved HERE. All three
 * surfaces now read it — `overview-dashboard`, `signals-table` and `security-dashboard` — and
 * `control-coherence.test.ts` refuses any new inline bar anywhere in the tree.
 *
 * The eleven quality-only signals came too, though none of them had drifted. Having one reader
 * is not a property, it is a moment: it is exactly the state all seven divergent controls were
 * in the day before a second surface needed the same number and wrote it out again.
 *
 * ## What the identity assertion caught while this was being written
 *
 * Two more of the same defect, neither previously reported:
 *
 * · **calibration** displayed `agreement` (71 %) under a bar reading `κ ≥ 0.60`, coloured by a
 *   third field entirely (`lenient`). Three numbers, one row, none judging another. It now
 *   shows κ — the thing its bar is about — with agreement on the detail line.
 * · **clusters** rendered its bar as `—` and still coloured the row from a hidden
 *   `n_failures === 0`. Failure THEMES have no threshold (twelve is not worse than four), so it
 *   is declared `informational`: no bar, no verdict, count still on screen.
 *
 * Both were copied faithfully from `signals-table.tsx` during the move and caught by
 * `control-registry.test.ts` minutes later. That is the argument for the assertion: an auditor
 * reading the same lines had already missed them twice.
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
 * owed on screen, so the ⓘ can say "seuil déclaré" instead of implying a measurement. Two bars
 * travel in the payload rather than being picked here — `slo.target` and
 * `cost.threshold_tokens`. Every other one is this repo's choice, and the registry says so
 * rather than flattening the difference.
 */

import { type ControlState, controlState } from "./overview";

import type {
  AnomalyReport,
  Calibration,
  CitationSummary,
  ClusterReport,
  ConformanceReport,
  ContradictionReport,
  CostReport,
  CrossTenantReport,
  FirewallEfficacy,
  FunnelReport,
  IntentReport,
  InversionReport,
  LocaleFormatSummary,
  PIILeakSummary,
  PredictorEvaluation,
  PrivilegeReport,
  RefusalReport,
  RoutingReport,
  SLOReport,
  ToolValidity,
  ToxicityReport,
} from "./api/schemas";

/** The payload every control reads from — exactly what the three surfaces already fetch. */
export interface ControlPayload {
  slo?: SLOReport;
  toxicity?: ToxicityReport;
  pii?: PIILeakSummary;
  refusal?: RefusalReport;
  conformance?: ConformanceReport;
  tools?: ToolValidity;
  firewall?: FirewallEfficacy;
  crossTenant?: CrossTenantReport;
  privilege?: PrivilegeReport;
  inversion?: InversionReport;
  calibration?: Calibration;
  citations?: CitationSummary;
  contradiction?: ContradictionReport;
  predictor?: PredictorEvaluation;
  clusters?: ClusterReport;
  localeFormat?: LocaleFormatSummary;
  cost?: CostReport;
  routing?: RoutingReport;
  funnel?: FunnelReport;
  anomalies?: AnomalyReport;
  intent?: IntentReport;
}

/** Canonical control ids. `refusalOver`/`refusalUnder` replace the collapsed `refusal`. */
export type ControlId =
  | "faithfulness"
  | "errorBudget"
  | "toxicity"
  | "pii"
  | "refusalOver"
  | "refusalUnder"
  | "conformance"
  | "tools"
  | "firewall"
  | "injectionBypass"
  | "crossTenant"
  | "leastPrivilege"
  | "embeddingInversion"
  | "calibration"
  | "citations"
  | "contradiction"
  | "predictor"
  | "clusters"
  | "localeFormat"
  | "cost"
  | "routing"
  | "funnel"
  | "anomalies"
  | "intent";

export const CONTROL_IDS: readonly ControlId[] = [
  "faithfulness",
  "errorBudget",
  "toxicity",
  "pii",
  "refusalOver",
  "refusalUnder",
  "conformance",
  "tools",
  "firewall",
  "injectionBypass",
  "crossTenant",
  "leastPrivilege",
  "embeddingInversion",
  "calibration",
  "citations",
  "contradiction",
  "predictor",
  "clusters",
  "localeFormat",
  "cost",
  "routing",
  "funnel",
  "anomalies",
  "intent",
] as const;

/**
 * WHY a control has no value — four situations that were one word.
 *
 * "Indisponible" pooled all of these, and they demand four different actions:
 *
 * · `no-sample` — the reader works, the window is empty. Wait, or widen the window.
 * · `read-failed` — the source answered "I could not measure" (`available: false`).
 *   Investigate the source. Rendering this as `0 %` — which `?? 0` did on `securite-privacy`
 *   — turns a failed probe into the best possible result.
 * · `no-reader` — the catalogue declares the signal; no code reads it. Build the reader.
 * · `planned` — declared as a design intention, never implemented. Nothing to fix today.
 *
 * The condition that produced the `na` always knew which one it was; the row had nowhere to
 * put it. ADR 0026's corollary: a witness that cannot see reports a blind spot — and saying
 * *where* the blindness is, is the whole content of that report.
 */
export type Unavailability = "no-sample" | "read-failed" | "no-reader" | "planned";

/** One control's measurement at a point in time, or its honest absence. */
export interface ControlReading {
  id: ControlId;
  /** The catalogue metric id — the same string the signals registry shows. */
  metric: string;
  /** The ONE displayed number, already formatted. `"—"` when unmeasured. */
  value: string;
  /**
   * The same number as `value`, unformatted — what a curve plots.
   *
   * Exposed so a sparkline reads the ratio the row DISPLAYS rather than re-deriving one from
   * the payload. That is the identity the whole registry is built on, extended to the time
   * axis: a curve drawn from a second derivation is exactly how a falling line came to sit
   * above a rising number, with both defensible in isolation.
   */
  ratio: number | null;
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
  /** Why there is no value. `null` exactly when `noData` is false. */
  unavailable: Unavailability | null;
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
  /** Absent target ⇒ read from the payload (`faithfulness`, `cost`), or informational. */
  target?: { value: number; text: string; direction: "higher" | "lower" };
  /**
   * No bar, therefore no verdict. The value is reported and stays neutral.
   *
   * This is not the same as an uncalibrated bar. `calibrated: false` says "this threshold is a
   * number we chose"; `informational` says "there is no threshold, and a coloured pill here
   * would be inventing one". `clusters` is the only control in that position.
   */
  informational?: boolean;
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
  /**
   * Why the sample is empty, when the source can distinguish it from "nothing happened".
   *
   * Three sources carry an `available` flag — the judge calibration, the failure clusterer and
   * the embedding-inversion probe — and `available: false` means the measurement did not run.
   * That is NOT an empty window, and folding it into one is how an unrun probe came to render
   * as `0 %` on `securite-privacy`: the most reassuring number a security control can show,
   * from a check that never happened.
   */
  unavailable?: Unavailability;
}

const pct = (v: number, digits = 0): string => `${(v * 100).toFixed(digits)}%`;
/** A burn rate is a multiple of the error budget, not a share of anything. */
const times = (v: number): string => `${v.toFixed(1)}×`;

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
        detail: {
          key: "sample",
          values: { good: String(slo.n_good), n: String(slo.n) },
        },
        target: {
          value: slo.target,
          text: `≥ ${pct(slo.target)}`,
          direction: "higher",
        },
      };
    },
  },

  // The SLO's second, genuinely different alarm — and the reason `faithfulness` above does NOT
  // read `slo.breaching`. `breaching` is a multi-window burn-rate test (`burn_rate > 1` AND
  // `burn_rate_fast > 1`, `observability/slo.py:117`), not a restatement of `good_rate ≥ target`.
  // Vue d'ensemble used it to override the faithfulness state, which is precisely the shape this
  // module forbids: a row showing 73 % against ≥ 95 % and coloured by a number nowhere on screen.
  // It is a real signal, so it is not dropped — it becomes its own control, showing the value
  // that actually decides. `breaching` is true exactly when `min(burn, burn_fast) > 1`, so the
  // displayed number and the backend's verdict cannot disagree.
  errorBudget: {
    metric: "rag.slo.burn_rate",
    impactKey: "rag",
    asOfCapable: true,
    calibrated: false,
    target: { value: 1, text: "≤ 1.0×", direction: "lower" },
    read: (d) => {
      const slo = d.slo;
      if (!slo) return null;
      const deciding = Math.min(slo.burn_rate, slo.burn_rate_fast);
      return {
        ratio: deciding,
        text: times(deciding),
        n: slo.n,
        severity: Math.min(deciding / 4, 1),
        detail: {
          key: "burn",
          values: {
            slow: times(slo.burn_rate),
            fast: times(slo.burn_rate_fast),
            remaining: pct(slo.budget_remaining),
          },
        },
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
        detail: {
          key: "count",
          values: { hit: String(x.n_toxic), n: String(x.n_turns) },
        },
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
        detail: {
          key: "count",
          values: { hit: String(p.n_with_leak), n: String(p.n_turns) },
        },
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
        detail: {
          key: "count",
          values: { hit: String(r.legit_refused), n: String(r.n_legit) },
        },
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
          values: {
            hit: String(r.forbidden_allowed),
            n: String(r.n_forbidden),
          },
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

  // The three controls `securite-privacy` derived alone. They are not duplicated anywhere yet,
  // which is exactly why they belong here BEFORE they are: the divergence this module exists to
  // undo began the same way — one surface, one derivation, then a second surface needing the
  // same number and writing it again. Declaring them costs nothing and closes that path.
  crossTenant: {
    metric: "privacy.cross_tenant.rate",
    impactKey: "privacy",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0, text: "= 0", direction: "lower" },
    read: (d) => {
      const x = d.crossTenant;
      if (!x) return null;
      return {
        ratio: x.leak_rate,
        text: pct(x.leak_rate, 2),
        n: x.n_turns,
        severity: Math.min(x.leak_rate * 20, 1),
        detail: {
          key: "count",
          values: { hit: String(x.n_leaks), n: String(x.n_turns) },
        },
      };
    },
  },

  leastPrivilege: {
    metric: "security.least_privilege.over_provisioned_rate",
    impactKey: "tools",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.05, text: "≤ 5%", direction: "lower" },
    read: (d) => {
      const p = d.privilege;
      if (!p) return null;
      const rate = p.n_granted > 0 ? p.n_over_provisioned / p.n_granted : 0;
      return {
        ratio: rate,
        text: pct(rate),
        n: p.n_granted,
        detail: {
          key: "count",
          values: { hit: String(p.n_over_provisioned), n: String(p.n_granted) },
        },
      };
    },
  },

  // `recovery_rate` is optional in the schema and `available` can be false — the one control
  // here whose source can answer "I could not measure". It says so (`n: 0` ⇒ a `noData` reading)
  // instead of rendering the `?? 0` that made an unread probe look like a clean result.
  embeddingInversion: {
    metric: "privacy.embedding_inversion.recovery_rate",
    impactKey: "privacy",
    asOfCapable: false,
    calibrated: false,
    target: { value: 0, text: "= 0", direction: "lower" },
    read: (d) => {
      const inv = d.inversion;
      if (!inv) return null;
      const n = inv.available ? (inv.n_memories ?? 0) : 0;
      const rate = inv.recovery_rate ?? 0;
      return {
        ratio: rate,
        text: pct(rate),
        n,
        severity: Math.min(rate * 5, 1),
        detail: {
          key: "count",
          values: { hit: String(inv.n_recoverable ?? 0), n: String(n) },
        },
        unavailable: inv.available ? undefined : "read-failed",
      };
    },
  },

  // ── The eleven quality-only signals ────────────────────────────────────────────────────
  //
  // These have ONE reader today — the Qualité IA registry table — so none of them had drifted.
  // That is not a reason to leave them out; it is the state every one of the seven divergent
  // controls was in before a second surface needed the same number and wrote it again. The
  // divergence class has no cheap cure once it exists, and a very cheap one before.
  //
  // Their bars are unchanged from `signals-table.tsx`, deliberately: this move is about WHERE a
  // bar is declared, not about revising any of them. Changing a threshold while relocating it
  // would make the diff unreadable and the ratchet's "the debt shrank" claim unverifiable.

  // The row that carried THREE numbers. `signals-table` displayed `agreement` (71 %) under a
  // bar reading `κ ≥ 0.60`, coloured by a third field entirely (`lenient`), with κ relegated to
  // the sample column. Nothing on the row judged anything else on the row. The relocation kept
  // the bar and made the value match it: κ is what `κ ≥ 0.60` is about, so κ is what is shown,
  // and agreement — a real, useful number — moves to the detail line.
  //
  // This was found by `control-registry.test.ts` while the move was being made, not before it:
  // the identity assertion is what turns "these three surfaces disagree" from something an
  // auditor has to notice into something the suite cannot pass without.
  calibration: {
    metric: "judge.cohen_kappa",
    impactKey: "quality",
    asOfCapable: false,
    calibrated: false,
    target: { value: 0.6, text: "κ ≥ 0.60", direction: "higher" },
    read: (d) => {
      const a = d.calibration;
      if (!a) return null;
      // `available: false` means the judge could not be scored at all, not "scored zero".
      const n = a.available ? (a.n ?? 1) : 0;
      const kappa = a.kappa ?? 0;
      return {
        ratio: kappa,
        text: kappa.toFixed(2),
        n,
        severity: Math.max(0, 0.6 - kappa),
        detail: {
          key: "agreement",
          values: { agreement: pct(a.agreement ?? 0) },
        },
        unavailable: a.available ? undefined : "read-failed",
      };
    },
  },

  citations: {
    metric: "citation.validity",
    impactKey: "rag",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.95, text: "≥ 95%", direction: "higher" },
    read: (d) => {
      const c = d.citations;
      if (!c) return null;
      return {
        ratio: c.validity_rate,
        text: pct(c.validity_rate),
        n: c.n_citations,
        severity: 1 - c.validity_rate,
        detail: {
          key: "count",
          values: { hit: String(c.n_unsupported), n: String(c.n_citations) },
        },
      };
    },
  },

  // A count, not a rate: the bar is `= 0` and the displayed number is the count itself, so
  // `controlState` compares like with like. Rendering `3` against `= 0` is honest; rendering
  // `3` against `≤ 5%` would not be.
  contradiction: {
    metric: "answer.contradiction",
    impactKey: "rag",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0, text: "= 0", direction: "lower" },
    read: (d) => {
      const c = d.contradiction;
      if (!c) return null;
      return {
        ratio: c.n_contradictions,
        text: String(c.n_contradictions),
        n: c.n_turns,
        severity: Math.min(c.n_contradictions / 5, 1),
        detail: { key: "sessions", values: { n: String(c.n_sessions) } },
      };
    },
  },

  predictor: {
    metric: "failure.predictor.precision",
    impactKey: "quality",
    asOfCapable: false,
    calibrated: false,
    target: { value: 0.7, text: "≥ 70%", direction: "higher" },
    read: (d) => {
      const p = d.predictor;
      if (!p) return null;
      return {
        ratio: p.precision,
        text: pct(p.precision),
        n: p.n,
        severity: 1 - p.precision,
        detail: { key: "recall", values: { recall: pct(p.recall) } },
      };
    },
  },

  // The one control with no bar at all: clustering surfaces THEMES among failures. Twelve
  // clusters is not worse than four, it is a different shape of the same failures, and there is
  // no number at which it becomes a defect.
  //
  // `signals-table` rendered its threshold as `—` and still coloured the row (`!available ?
  // "na" : n_failures === 0 ? "ok" : "warn"`), so a bar the operator could not see was deciding
  // a verdict the operator could. Declaring it informational is the honest form: no bar, no
  // verdict, and the count still on screen where it is useful.
  clusters: {
    metric: "failure.clusters",
    impactKey: "quality",
    asOfCapable: false,
    calibrated: false,
    informational: true,
    read: (d) => {
      const c = d.clusters;
      if (!c) return null;
      const n = c.available ? Math.max(c.n_failures ?? 0, 1) : 0;
      return {
        ratio: c.n_failures ?? 0,
        text: String(c.n_failures ?? 0),
        n,
        detail: { key: "themes", values: { n: String(c.k ?? 0) } },
        unavailable: c.available ? undefined : "read-failed",
      };
    },
  },

  localeFormat: {
    metric: "locale.format.rate",
    impactKey: "quality",
    asOfCapable: true,
    calibrated: false,
    target: { value: 1, text: "= 100%", direction: "higher" },
    read: (d) => {
      const l = d.localeFormat;
      if (!l) return null;
      return {
        ratio: l.correctness_rate,
        text: pct(l.correctness_rate),
        n: l.n_amounts,
        severity: 1 - l.correctness_rate,
        detail: {
          key: "count",
          values: { hit: String(l.n_violations), n: String(l.n_amounts) },
        },
      };
    },
  },

  // Tokens, against a threshold the backend computes and ships in the payload — so this is the
  // SECOND calibrated bar in the table, and it says so.
  cost: {
    metric: "cost.tokens.mean",
    impactKey: "quality",
    asOfCapable: true,
    calibrated: true,
    read: (d) => {
      const c = d.cost;
      if (!c) return null;
      return {
        ratio: c.mean_tokens,
        text: `${Math.round(c.mean_tokens)} tok`,
        n: c.n_turns,
        severity: c.n_anomalies > 0 ? 0.3 : 0,
        detail: {
          key: "cost",
          values: {
            eur: c.estimated_cost_eur.toFixed(2),
            anomalies: String(c.n_anomalies),
          },
        },
        target: {
          value: c.threshold_tokens,
          text: `≤ ${Math.round(c.threshold_tokens)}`,
          direction: "lower",
        },
      };
    },
  },

  routing: {
    metric: "routing.mismatch.rate",
    impactKey: "quality",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.95, text: "≥ 95%", direction: "higher" },
    read: (d) => {
      const r = d.routing;
      if (!r) return null;
      return {
        ratio: 1 - r.mismatch_rate,
        text: pct(1 - r.mismatch_rate),
        n: r.n,
        severity: r.mismatch_rate,
        detail: {
          key: "count",
          values: { hit: String(r.mismatches), n: String(r.n) },
        },
      };
    },
  },

  funnel: {
    metric: "funnel.low_score.rate",
    impactKey: "quality",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.9, text: "≥ 90%", direction: "higher" },
    read: (d) => {
      const f = d.funnel;
      if (!f) return null;
      const langs = f.languages ?? [];
      // The WORST language, not the mean: an average hides the one locale that is broken.
      const worst = langs.reduce((m, l) => Math.max(m, l.low_score_rate), 0);
      return {
        ratio: 1 - worst,
        text: pct(1 - worst),
        n: langs.length,
        severity: worst,
        detail: { key: "turns", values: { n: String(f.n_turns) } },
      };
    },
  },

  anomalies: {
    metric: "session.anomaly.count",
    impactKey: "quality",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0, text: "= 0", direction: "lower" },
    read: (d) => {
      const a = d.anomalies;
      if (!a) return null;
      return {
        ratio: a.n_anomalous,
        text: String(a.n_anomalous),
        n: a.n_sessions,
        severity: Math.min(a.n_anomalous / 5, 1),
        detail: {
          key: "count",
          values: { hit: String(a.n_anomalous), n: String(a.n_sessions) },
        },
      };
    },
  },

  intent: {
    metric: "intent.low_confidence.rate",
    impactKey: "quality",
    asOfCapable: true,
    calibrated: false,
    target: { value: 0.9, text: "≥ 90%", direction: "higher" },
    read: (d) => {
      const i = d.intent;
      if (!i) return null;
      return {
        ratio: 1 - i.low_confidence_rate,
        text: pct(1 - i.low_confidence_rate),
        n: i.n,
        severity: i.low_confidence_rate,
        detail: { key: "unknown", values: { n: String(i.unknown) } },
      };
    },
  },
};

const NEUTRAL: ControlState = { key: "ok", tone: "neutral" };
/** How a control with no threshold renders its bar column. */
const NO_BAR = "—";

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
  if (target === undefined && !spec.informational) return null;

  const bar = target?.text ?? NO_BAR;

  if (sample.n <= 0 || sample.ratio === null) {
    return {
      id,
      metric: spec.metric,
      value: "—",
      ratio: null,
      target: bar,
      state: NEUTRAL,
      severity: 0,
      detail: null,
      impactKey: spec.impactKey,
      asOfCapable: spec.asOfCapable,
      calibrated: spec.calibrated,
      noData: true,
      // The reader's own answer wins: only it can tell "the probe did not run" from "the
      // window is empty". Absent that, an empty sample is an empty window.
      unavailable: sample.unavailable ?? "no-sample",
    };
  }

  return {
    id,
    metric: spec.metric,
    value: sample.text,
    ratio: sample.ratio,
    target: bar,
    // The state is derived from the SAME ratio the `value` renders. That identity is the whole
    // point: the previous signals-table computed its status from `max(over, under)` while
    // displaying `over`, so a row could read "0 % · seuil ≤ 10 % · Critique". A control with no
    // bar reaches neither branch of a verdict: it stays neutral rather than being coloured by a
    // threshold the operator was never shown.
    state: target ? controlState(sample.ratio, target.value, target.direction) : NEUTRAL,
    severity: target ? (sample.severity ?? Math.min(Math.abs(sample.ratio - target.value), 1)) : 0,
    detail: sample.detail,
    impactKey: spec.impactKey,
    asOfCapable: spec.asOfCapable,
    calibrated: spec.calibrated,
    noData: false,
    unavailable: null,
  };
}

/**
 * Every control the payload can answer, in canonical order.
 *
 * `ids` selects a surface's subset. A surface chooses WHICH controls it shows — that is an
 * editorial decision and a legitimate one. It does not get to choose what any of them MEANS.
 */
export function readControls(
  payload: ControlPayload,
  ids: readonly ControlId[] = CONTROL_IDS,
): ControlReading[] {
  return ids
    .map((id) => readControl(id, payload))
    .filter((row): row is ControlReading => row !== null);
}

/** The metric id a control declares — the join key with the signal catalogue. */
export function metricFor(id: ControlId): string {
  return SPECS[id].metric;
}

/** One bucket of a control series, as the backend sends it. */
export interface ControlSeriesBucket {
  index: number;
  since: string;
  until: string;
  payload: Record<string, unknown>;
}

/**
 * A control's curve: the ratio each bucket reports, in window order.
 *
 * Every point goes through `readControl` — the same function that produced the number the
 * curve sits under, given that bucket's payload instead of the window's. Nothing is derived
 * here, so the two cannot disagree; that is the entire design, and it is why this lives in
 * the registry rather than in a chart component.
 *
 * A bucket the control cannot answer contributes `null`, and `MetricSparkline` draws that as
 * a break in the line. Two different silences map to it and both must: a bucket whose window
 * held no traffic (`noData`), and a bucket whose source is missing altogether (`readControl`
 * returns `null`). Neither is a zero, and rendering either as one would turn a quiet week into
 * a perfect score on exactly the controls where that reads best — a leak rate, a toxicity rate.
 */
export function readControlSeries(
  buckets: readonly ControlSeriesBucket[],
  id: ControlId,
): (number | null)[] {
  return buckets.map((bucket) => {
    const reading = readControl(id, bucket.payload as ControlPayload);
    return reading === null || reading.noData ? null : reading.ratio;
  });
}

/**
 * True when a curve is worth drawing: at least two measured points.
 *
 * One point is not a trend, and a flat line through a single measurement claims the value held
 * for the whole window. The caller shows the honest "not enough history yet" label instead.
 */
export function hasDrawableCurve(values: readonly (number | null)[]): boolean {
  return values.filter((v) => v !== null).length > 1;
}

/**
 * How wide one bucket of a series is, in hours — the number that explains an empty cell.
 *
 * Read off the report's own bounds rather than the period key, because the two can disagree:
 * the backend chooses the count from the window (`buckets_for_window`), so a front that
 * derived the width from `days / 8` would print a confident wrong number the day that
 * choice changes. `null` when the report has no window to slice.
 */
export function bucketWidthHours(series?: {
  since: string | null;
  until: string | null;
  n_buckets: number;
}): number | null {
  if (!series || series.n_buckets <= 0 || !series.since || !series.until) return null;
  const span = Date.parse(series.until) - Date.parse(series.since);
  if (!Number.isFinite(span) || span <= 0) return null;
  return span / series.n_buckets / 3_600_000;
}
