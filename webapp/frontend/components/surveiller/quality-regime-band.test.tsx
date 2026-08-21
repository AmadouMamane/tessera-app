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
  business: {
    runs_total: number;
    signals_declared: number;
    signals_scored: number;
    signals_unknown: number;
    signals_not_applicable: number;
  } | null;
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
        business: null,
      },
      {
        agent_id: "onboarding",
        name: "Onboarding",
        regime: "llm_judged",
        reason_key: null,
        business: null,
      },
      {
        agent_id: "recouvrement",
        name: "Recouvrement",
        regime: "business_scored",
        reason_key: null,
        business: {
          runs_total: 67,
          signals_declared: 10,
          signals_scored: 6,
          signals_unknown: 2,
          signals_not_applicable: 2,
        },
      },
      {
        agent_id: "hello-agent",
        name: "Hello Agent",
        regime: "unscored",
        reason_key: "quality_regime.reason.demo_no_reference",
        business: null,
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
    render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    // The honest-scope sentence: the band must never read as "recouvrement is outside
    // quality altogether" — cross-cutting controls cover the whole fleet.
    expect(text).toMatch(/couvrent tous les agents/);
    expect(text).toMatch(/Réponses notées par un juge IA/);
    expect(text).toMatch(/Support Client · Onboarding/);
    expect(text).toMatch(/Exécutions vérifiées par des contrôles métier/);
    expect(text).toMatch(/Réponses non notées/);
    // The declared blind spot renders ITS reason in the reader's language — never a gap.
    expect(text).toMatch(/rien contre quoi noter/);
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
    const llm: Entry[] = Array.from({ length: 150 }, (_, i) => ({
      agent_id: `llm-${i + 1}`,
      name: `Agent ${String(i + 1).padStart(3, "0")}`,
      regime: "llm_judged" as const,
      reason_key: null,
      business: null,
    }));
    const unscored: Entry[] = Array.from({ length: 49 }, (_, i) => ({
      agent_id: `demo-${i + 1}`,
      name: `Démo ${String(i + 1).padStart(3, "0")}`,
      regime: "unscored" as const,
      reason_key: "quality_regime.reason.demo_no_reference",
      business: null,
    }));
    const business = fleet.regimes.find((entry) => entry.regime === "business_scored");
    if (!business) throw new Error("fixture must contain a business_scored entry");
    fleet.regimes = [...llm, business, ...unscored];
    regimes.data = fleet;
    render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    // The row leads with its COUNT, shows a handful of names, and folds the rest.
    expect(text).toMatch(/150 agents/);
    expect(text).toMatch(/Agent 004/);
    expect(text).not.toMatch(/Agent 005/);
    expect(text).toMatch(/\+146 autres/);
    expect(text).toMatch(/49 agents/);
    expect(text).toMatch(/\+45 autres/);
    // One shared blind-spot reason renders ONCE, not 49 times.
    expect(text.match(/rien contre quoi noter/g)?.length).toBe(1);
  });

  it("renders nothing at all before the declaration is read (no invented rows)", () => {
    regimes.data = null;
    regimes.isError = false;
    const { container } = render(wrap(<QualityRegimeBand />));
    expect(container.textContent).toBe("");
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
