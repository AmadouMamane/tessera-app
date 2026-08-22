// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/fr.json";

/**
 * The per-language slices of the judged plane, on SCREEN — real fr catalogue. What must
 * hold, all inherited from the hero it refines: a language nobody spoke reads "no rated
 * responses" (never 0,0 %); a thin sample leads with its counts and withholds the rate; a
 * publishable sample carries its rate WITH its n; and the whole band steps aside when the
 * plane itself is unmeasured (the hero already owns that state).
 */

const slo = vi.hoisted(() => ({ data: null as unknown, isError: false }));

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: slo.data, isError: slo.isError }),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/stores/window-store", () => ({
  useWindowStore: (sel: (s: { period: number }) => unknown) => sel({ period: 7 }),
}));

import { LanguageRateBand } from "./language-rate-band";

interface Slice {
  n: number;
  n_good: number;
  good_rate: number;
}

function served(byLanguage: Record<string, Slice>, n = 200): unknown {
  return { n, by_language: byLanguage };
}

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      {node}
    </NextIntlClientProvider>
  );
}

afterEach(() => {
  cleanup();
  slo.data = null;
  slo.isError = false;
});

describe("the per-language rate band", () => {
  it("gives each language its honest state: rate with n, counts on a thin sample, none on zero", () => {
    slo.data = served({
      fr: { n: 150, n_good: 141, good_rate: 0.94 },
      de: { n: 12, n_good: 9, good_rate: 0.75 },
      en: { n: 0, n_good: 0, good_rate: 0 },
    });
    render(wrap(<LanguageRateBand />));
    const text = document.body.textContent ?? "";
    // Publishable sample: the rate travels WITH its n.
    expect(text).toMatch(/94,0\s?% au niveau exigé · 150 réponses notées/u);
    // Thin sample: counts lead, no rate — 75 % over 12 turns is fabricated precision.
    expect(text).toMatch(/9\/12 réponses au niveau exigé/);
    // Nobody spoke English in the window: a fact, not a 0,0 %.
    expect(text).toMatch(/aucune réponse notée/);
    expect(text).not.toMatch(/0,0\s?%/u);
  });

  it("steps aside when the plane itself is unmeasured — the hero owns that state", () => {
    slo.data = served({ fr: { n: 0, n_good: 0, good_rate: 0 } }, 0);
    const { container } = render(wrap(<LanguageRateBand />));
    expect(container.textContent).toBe("");
  });

  it("steps aside on an older payload without the field (no invented slices)", () => {
    slo.data = { n: 200 };
    const { container } = render(wrap(<LanguageRateBand />));
    expect(container.textContent).toBe("");
  });

  it("names a FAILED read", () => {
    slo.isError = true;
    render(wrap(<LanguageRateBand />));
    expect(document.body.textContent).toMatch(/Taux par langue illisibles/);
  });
});
