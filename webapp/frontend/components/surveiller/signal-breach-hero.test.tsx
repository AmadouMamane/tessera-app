// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import messages from "@/messages/fr.json";

/**
 * The SLO ribbon on an EMPTY window — the state the whole cockpit shows right after a deploy.
 *
 * Live scores are a ring buffer, so the minute the agent restarts the window holds nothing.
 * `compute_slo` is honest about it (`n: 0`, and `breaching: false` meaning "no evidence of a
 * breach"), but this ribbon read `breaching` and `good_rate` and never `n`. What five cockpit
 * pages then displayed, in production, was:
 *
 *     « Fidélité — 0,0 % des réponses au niveau exigé, objectif de 95,0 % tenu »
 *
 * Two claims, both false, in opposite directions, from the same absence of data — and the
 * reassuring half is the one an operator acts on. This asserts what is on SCREEN rather than
 * what the source contains (ADR 0026 / the localization-honesty pattern next door).
 */

const slo = vi.hoisted(() => ({ data: null as unknown }));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: slo.data }),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/stores/window-store", () => ({
  useWindowStore: (sel: (s: { period: number }) => unknown) => sel({ period: 7 }),
}));

import { SignalBreachHero } from "./signal-breach-hero";

interface Slo {
  metric: string;
  threshold: number;
  target: number;
  n: number;
  n_good: number;
  n_bad: number;
  good_rate: number;
  error_budget: number;
  budget_consumed: number;
  budget_remaining: number;
  burn_rate: number;
  burn_rate_fast: number;
  breaching: boolean;
}

/** Exactly what the backend serves on an empty window (`compute_slo`, n == 0 branch). */
function emptyWindow(overrides: Partial<Slo> = {}): Slo {
  return {
    metric: "faithfulness",
    threshold: 0.8,
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
    ...overrides,
  };
}

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      <TooltipProvider>{node}</TooltipProvider>
    </NextIntlClientProvider>
  );
}

afterEach(cleanup);

describe("the quality-target ribbon on an empty window", () => {
  it.each(["gauge", "slim"] as const)("says nothing was measured (%s)", (variant) => {
    slo.data = emptyWindow();
    render(wrap(<SignalBreachHero variant={variant} />));

    const text = document.body.textContent ?? "";
    // The two claims the operator was shown, neither of which may return. The first is
    // matched as the SHAPE that made it a claim — a percentage immediately followed by
    // "tenu" — not as the bare word, which the honest sentence uses legitimately in
    // "n'est ni tenu ni manqué". A test that banned the word would have forced the fix
    // to be reworded rather than corrected.
    expect(text).not.toMatch(/%\s*tenu/);
    expect(text).not.toMatch(/\b0,0\s?%/);
    // …and what it must say instead: an absence, named.
    expect(text).toMatch(/aucune réponse observée/);
  });

  it("still reports a met target once something HAS been measured", () => {
    // The negative control: without it, a ribbon that rendered the unmeasured sentence
    // unconditionally would pass every assertion above while saying nothing true.
    slo.data = emptyWindow({ n: 40, n_good: 40, good_rate: 1 });
    render(wrap(<SignalBreachHero variant="slim" />));

    expect(screen.getByText(/100,0 %.*tenu/)).toBeTruthy();
  });

  it("still reports a breach once one is measured", () => {
    slo.data = emptyWindow({
      n: 40,
      n_good: 10,
      n_bad: 30,
      good_rate: 0.25,
      breaching: true,
      burn_rate: 15,
      burn_rate_fast: 15,
    });
    render(wrap(<SignalBreachHero variant="slim" />));

    expect(screen.getByText(/sous l'objectif de/)).toBeTruthy();
  });
});
