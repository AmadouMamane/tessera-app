// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/fr.json";

/**
 * The answer-quality rating band (ADR 0017 §Amendment 4) on SCREEN — real fr catalogue,
 * the fixture shaped exactly like `/observability/quality-regimes`. What must hold:
 *
 *  · the subtitle states the honest scope: cross-cutting controls cover EVERY agent,
 *    only the answer-rating method differs — the band must never read as "this agent is
 *    outside quality altogether";
 *  · each declared method renders as ITS OWN row with counts and its agents, in plain
 *    words (no "barème", no "population" — operator feedback, 2026-08-21);
 *  · the business row carries COUNTS and their since-when, never a rate — the hero owns
 *    the page's only percentage;
 *  · a declared blind spot renders its localized reason, not a silent gap;
 *  · at fleet scale the band stays legible: names cap with a "+N more" overflow — 200
 *    agents render as counts, never as 200 names.
 */

const regimes = vi.hoisted(() => ({ data: null as unknown, isError: false }));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: regimes.data, isError: regimes.isError }),
}));

import { QualityRegimeBand } from "./quality-regime-band";

interface Entry {
  agent_id: string;
  name: string;
  regime: "llm_judged" | "business_scored" | "unscored";
  reason_key: string | null;
  observable: boolean;
  business: {
    runs_total: number;
    signals_declared: number;
    signals_scored: number;
    signals_unknown: number;
    signals_not_applicable: number;
  } | null;
  judged: { responses_total: number } | null;
}

/** Exactly what the backend serves for the shipped registry. */
function servedFleet(): { regimes: Entry[]; as_of: null; window: { period_days: null } } {
  return {
    regimes: [
      {
        agent_id: "support-client",
        name: "Support Client",
        regime: "llm_judged",
        reason_key: null,
        observable: true,
        business: null,
        judged: { responses_total: 120 },
      },
      {
        agent_id: "onboarding",
        name: "Onboarding",
        regime: "llm_judged",
        reason_key: null,
        observable: true,
        business: null,
        judged: { responses_total: 34 },
      },
      {
        agent_id: "recouvrement",
        name: "Recouvrement",
        regime: "business_scored",
        reason_key: null,
        observable: true,
        business: {
          runs_total: 67,
          signals_declared: 10,
          signals_scored: 6,
          signals_unknown: 2,
          signals_not_applicable: 2,
        },
        judged: null,
      },
      {
        agent_id: "hello-agent",
        name: "Hello Agent",
        regime: "unscored",
        reason_key: "quality_regime.reason.demo_no_reference",
        observable: true,
        business: null,
        judged: null,
      },
      {
        agent_id: "turn-agent",
        name: "Turn Agent",
        regime: "unscored",
        reason_key: "quality_regime.reason.demo_no_reference",
        observable: false,
        business: null,
        judged: null,
      },
      {
        agent_id: "duplex-agent",
        name: "Duplex Agent",
        regime: "unscored",
        reason_key: "quality_regime.reason.demo_no_reference",
        observable: true,
        business: null,
        judged: null,
      },
    ],
    as_of: null,
    window: { period_days: null },
  };
}

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      {node}
    </NextIntlClientProvider>
  );
}

afterEach(cleanup);

describe("the answer-quality rating band", () => {
  it("states that cross-cutting controls cover every agent, then one row per method", () => {
    regimes.data = servedFleet();
    const { container } = render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    // The judged plane carries its own COUNT, in its own unit (responses, all history) —
    // every card holds a figure, none holds a rate (the hero owns the page's only one).
    expect(text).toMatch(/154 réponses notées par le juge/);
    // Every chip is a door: business chips open the Métier view (asserted next door), the
    // other chips open the agent's page — "watched on the cockpit" is one click to prove.
    expect(container.innerHTML).toMatch(/agents\/support-client/);
    expect(container.innerHTML).toMatch(/agents\/hello-agent/);
    // The honest-scope sentence: the band must never read as "recouvrement is outside
    // quality altogether" — cross-cutting controls cover the whole fleet.
    expect(text).toMatch(/couvrent tous les agents/);
    expect(text).toMatch(/Réponses notées par un juge IA/);
    expect(text).toMatch(/Support Client/);
    expect(text).toMatch(/Onboarding/);
    expect(text).toMatch(/Exécutions vérifiées par des contrôles métier/);
    expect(text).toMatch(/Réponses non notées/);
    // The declared blind spot renders ITS reason in the reader's language — never a gap.
    expect(text).toMatch(/rien contre quoi noter/);
    // …and unrated NEVER reads as unseen: two of the three demo agents publish their
    // activity, and the card says so with the count (operator feedback, 2026-08-21).
    expect(text).toMatch(/2 de ces agents publient déjà leur activité/);
    // Operator feedback 2026-08-21: screen language stays human — no registry jargon.
    expect(text).not.toMatch(/barème|population|régime/i);
  });

  it("states the business method as counts with their since-when, and links the Métier view", () => {
    regimes.data = servedFleet();
    const { container } = render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    expect(text).toMatch(/67 exécutions contrôlées/);
    expect(text).toMatch(/10 contrôles/);
    expect(text).toMatch(/6 évalués/);
    // A count that spans all history says so — a bare figure would read as "this period".
    expect(text).toMatch(/depuis le début/);
    expect(container.innerHTML).toMatch(/agents\/recouvrement\/metier/);
    // NEVER a rate: a percentage here would invite the cross-method comparison the
    // two-rulers rule forbids (insights 361-363). The hero owns the page's only rate.
    expect(text).not.toMatch(/%/);
  });

  it("renders no row for a method nobody declares", () => {
    const fleet = servedFleet();
    fleet.regimes = fleet.regimes.filter((entry) => entry.regime === "llm_judged");
    regimes.data = fleet;
    render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    expect(text).toMatch(/Réponses notées par un juge IA/);
    expect(text).not.toMatch(/Exécutions vérifiées/);
    expect(text).not.toMatch(/Réponses non notées/);
  });

  it("stays legible with a 200-agent fleet: counts and overflows, never 200 names", () => {
    const fleet = servedFleet();
    const llm: Entry[] = Array.from({ length: 120 }, (_, i) => ({
      agent_id: `llm-${i + 1}`,
      name: `Agent ${String(i + 1).padStart(3, "0")}`,
      regime: "llm_judged" as const,
      reason_key: null,
      observable: true,
      business: null,
      judged: { responses_total: 5 },
    }));
    // 30 business-scored agents, 10 runs each: the card must speak at the level of its
    // POPULATION — one 300-run total, never thirty six-figure sentences (the per-agent
    // detail is each Métier view's job, reached through its chip).
    const business: Entry[] = Array.from({ length: 30 }, (_, i) => ({
      agent_id: `biz-${i + 1}`,
      name: `Métier ${String(i + 1).padStart(3, "0")}`,
      regime: "business_scored" as const,
      reason_key: null,
      observable: true,
      business: {
        runs_total: 10,
        signals_declared: 10,
        signals_scored: 6,
        signals_unknown: 2,
        signals_not_applicable: 2,
      },
      judged: null,
    }));
    const unscored: Entry[] = Array.from({ length: 50 }, (_, i) => ({
      agent_id: `demo-${i + 1}`,
      name: `Démo ${String(i + 1).padStart(3, "0")}`,
      regime: "unscored" as const,
      reason_key: "quality_regime.reason.demo_no_reference",
      observable: false,
      business: null,
      judged: null,
    }));
    fleet.regimes = [...llm, ...business, ...unscored];
    regimes.data = fleet;
    const { container } = render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    // Each row leads with its COUNT, shows a handful of names, and folds the rest.
    expect(text).toMatch(/120 agents/);
    expect(text).toMatch(/Agent 004/);
    expect(text).not.toMatch(/Agent 005/);
    expect(text).toMatch(/\+116 autres/);
    expect(text).toMatch(/30 agents/);
    expect(text).toMatch(/\+26 autres/);
    expect(text).toMatch(/50 agents/);
    expect(text).toMatch(/\+46 autres/);
    // ONE population-level total per plane — judged responses on the judge card, checked
    // runs on the business card — and not a single per-agent six-figure sentence.
    expect(text).toMatch(/600 réponses notées par le juge/);
    expect(text.match(/réponses notées par le juge/g)?.length).toBe(1);
    expect(text).toMatch(/300 exécutions contrôlées en tout/);
    expect(text.match(/exécutions contrôlées/g)?.length).toBe(1);
    expect(text).not.toMatch(/contrôles ·/);
    // The chips are the per-agent doors: each links to that agent's Métier view.
    expect(container.innerHTML).toMatch(/agents\/biz-1\/metier/);
    // One shared blind-spot reason renders ONCE, not 50 times.
    expect(text.match(/rien contre quoi noter/g)?.length).toBe(1);
  });

  it("reserves the section's shape while pending, and claims no method or count", () => {
    // The skeleton kills the layout jump (the section used to render nothing, then push
    // the page down) — but it must stay CLAIMLESS: static chrome only, no method row, no
    // figure, no agent name invented while the read is in flight.
    regimes.data = null;
    regimes.isError = false;
    const { container } = render(wrap(<QualityRegimeBand />));
    const text = container.textContent ?? "";
    expect(text).toMatch(/Comment la qualité est notée/);
    expect(text).not.toMatch(/Réponses notées|Exécutions vérifiées|Réponses non notées/);
    expect(text).not.toMatch(/\d/);
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
    expect(container.querySelectorAll(".animate-pulse").length).toBe(3);
  });

  it("names the blind spot when the read FAILED — never a silent absence", () => {
    // A failed read is not an empty result: the band vanishing on error would recreate the
    // defect it exists to fix. The blind state says "could not read" and asserts no method.
    regimes.data = null;
    regimes.isError = true;
    render(wrap(<QualityRegimeBand />));
    const text = document.body.textContent ?? "";
    expect(text).toMatch(/Impossible de lire qui est noté comment/);
    expect(text).not.toMatch(/Réponses notées|Exécutions vérifiées|Réponses non notées/);
    regimes.isError = false;
  });
});
