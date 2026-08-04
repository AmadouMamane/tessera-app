// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import type { LocalizationReport } from "@/lib/api/schemas";
import messages from "@/messages/fr.json";

import { PredictiveSignals } from "./overview-exec";

// This test used to `readFileSync` the component and assert its SOURCE contained the string
// "!localization.available || localization.measured === false". That is ADR 0026's exact
// anti-pattern: it interrogated the neighbourhood rather than the thing. It went green on a
// character sequence — so it would have gone red on a rename that changed nothing, and green
// on that same guard sitting in a branch React never reaches. What matters is what an
// operator SEES, so that is what is asked here.

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      <TooltipProvider>{node}</TooltipProvider>
    </NextIntlClientProvider>
  );
}

function report(overrides: Partial<LocalizationReport> = {}): LocalizationReport {
  return {
    available: true,
    unreadable: [],
    default_locale: "fr",
    n_default_keys: 100,
    measured: true,
    n_locales: 2,
    locales: [
      {
        locale: "de",
        n_keys: 90,
        n_missing: 10,
        completeness: 0.9,
        fallback_rate: 0.1,
        missing_sample: [],
      },
      {
        locale: "en",
        n_keys: 95,
        n_missing: 5,
        completeness: 0.95,
        fallback_rate: 0.05,
        missing_sample: [],
      },
    ],
    ...overrides,
  };
}

function renderRow(localization: LocalizationReport | undefined) {
  render(
    wrap(
      <PredictiveSignals
        series={undefined}
        risk={undefined}
        drift={undefined}
        predictor={undefined}
        intent={undefined}
        localization={localization}
        loading={false}
      />,
    ),
  );
}

const UNMEASURED = messages.quality.pred.langsUnmeasured;

afterEach(() => cleanup());

describe("localization signal honesty", () => {
  it("names an unreadable catalogue instead of showing a dash", () => {
    // The route reported 100 % complete in production for its ENTIRE life: it resolved the
    // catalogues under `webapp/`, which the agent image does not ship, swallowed every failure
    // into `{}`, and divided by an empty reference. `available: false` is the backend saying
    // "I could not look". A caller that renders it as an empty list republishes the lie.
    renderRow(report({ available: false, reason: "catalogues_unreadable", locales: [] }));
    expect(screen.getByText(UNMEASURED)).toBeTruthy();
  });

  it("names an unmeasured report even when the transport succeeded", () => {
    // The second way to be blind: the files opened, and there was no reference key set.
    renderRow(report({ measured: false, locales: [] }));
    expect(screen.getByText(UNMEASURED)).toBeTruthy();
  });

  it("draws the real gaps when the report is genuinely measured", () => {
    // The negative control. Without it a component that ALWAYS printed "unreadable" would pass
    // both assertions above while hiding every real measurement behind a warning.
    renderRow(report());
    expect(screen.queryByText(UNMEASURED)).toBeNull();
    expect(screen.getByText("DE")).toBeTruthy();
    expect(screen.getByText("10%")).toBeTruthy(); // 1 - 0.9 completeness
  });
});
