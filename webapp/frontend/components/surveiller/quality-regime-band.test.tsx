// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/fr.json";

/**
 * The grouped-population band (ADR 0017 §Amendment 4) on SCREEN — real fr catalogue, the
 * fixture shaped exactly like `/observability/quality-regimes`. What must hold:
 *
 *  · each declared regime renders as ITS OWN row, naming its population noun (réponses /
 *    exécutions) and its agents;
 *  · the business row carries COUNTS and the all-history window, never a rate — the only
 *    percentage on the quality page belongs to the hero, whose population it names;
 *  · a declared blind spot renders its localized reason, not a silent gap;
 *  · a regime with no agents renders no row (rows are data, never furniture).
 */

const regimes = vi.hoisted(() => ({ data: null as unknown }));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: regimes.data }),
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

/** Exactly what the backend serves for the shipped registry (counts from the demo ledger). */
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
          runs_total: 20,
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

describe("the grouped quality-regime band", () => {
  it("renders one row per declared regime, each naming its population and agents", () => {
    regimes.data = servedFleet();
    render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    expect(text).toMatch(/Réponses jugées par le juge LLM/);
    expect(text).toMatch(/Support Client · Onboarding/);
    expect(text).toMatch(/Exécutions scorées par le barème métier/);
    expect(text).toMatch(/Plan non scoré/);
    // The declared blind spot renders ITS reason in the reader's language — never a gap.
    expect(text).toMatch(/aucun barème n'a de référent/);
  });

  it("states the business plane as counts with their window, and links the Métier view", () => {
    regimes.data = servedFleet();
    const { container } = render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    expect(text).toMatch(/20 exécutions/);
    expect(text).toMatch(/10 signaux/);
    expect(text).toMatch(/6 scorés/);
    // A count that spans all history says so — a bare figure would read as "this period".
    expect(text).toMatch(/depuis l'origine/);
    expect(container.innerHTML).toMatch(/agents\/recouvrement\/metier/);
    // NEVER a rate: a percentage here would invite the cross-plane comparison the
    // two-rulers rule forbids (insights 361-363). The hero owns the page's only rate.
    expect(text).not.toMatch(/%/);
  });

  it("renders no row for a regime nobody declares", () => {
    const fleet = servedFleet();
    fleet.regimes = fleet.regimes.filter((entry) => entry.regime === "llm_judged");
    regimes.data = fleet;
    render(wrap(<QualityRegimeBand />));

    const text = document.body.textContent ?? "";
    expect(text).toMatch(/Réponses jugées par le juge LLM/);
    expect(text).not.toMatch(/Exécutions scorées/);
    expect(text).not.toMatch(/Plan non scoré/);
  });

  it("renders nothing at all before the declaration is read (no invented planes)", () => {
    regimes.data = null;
    const { container } = render(wrap(<QualityRegimeBand />));
    expect(container.textContent).toBe("");
  });
});
