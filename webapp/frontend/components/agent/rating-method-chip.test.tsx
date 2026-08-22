// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/fr.json";

/**
 * The command-bar rating-method chip — real fr catalogue. What must hold: each declared
 * method renders its two-word label and links to the quality page where the methods are
 * explained; a FAILED read is named (never an absence that reads as "no method"); an
 * undeclared id renders nothing; and the screen language stays human (no registry jargon).
 */

const regime = vi.hoisted(() => ({
  entry: undefined as unknown,
  isError: false,
}));

vi.mock("@/lib/use-quality-regime", () => ({
  useDeclaredQualityRegime: () => ({ entry: regime.entry, isError: regime.isError }),
}));

import type { QualityRegimeEntry } from "@/lib/api/schemas";

import { RatingMethodChip } from "./rating-method-chip";

function entryOf(kind: QualityRegimeEntry["regime"]): QualityRegimeEntry {
  return {
    agent_id: "recouvrement",
    name: "Recouvrement",
    regime: kind,
    reason_key: null,
    observable: true,
    business: null,
    judged: null,
  };
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
  regime.entry = undefined;
  regime.isError = false;
});

describe("the rating-method chip", () => {
  it("names each declared method and links to the quality page", () => {
    for (const [kind, label] of [
      ["llm_judged", "Qualité : juge IA"],
      ["business_scored", "Qualité : contrôles métier"],
      ["unscored", "Qualité : non notée"],
    ] as const) {
      regime.entry = entryOf(kind);
      const { container, unmount } = render(wrap(<RatingMethodChip agentId="recouvrement" />));
      const text = container.textContent ?? "";
      expect(text).toContain(label);
      expect(container.innerHTML).toMatch(/surveiller\/qualite-ia/);
      // Screen language stays human — the dossier's vocabulary never reaches the chip.
      expect(text).not.toMatch(/barème|population|régime/i);
      unmount();
    }
  });

  it("names a FAILED read instead of vanishing", () => {
    regime.isError = true;
    const { container } = render(wrap(<RatingMethodChip agentId="recouvrement" />));
    expect(container.textContent).toContain("Qualité : illisible");
    // The blind state asserts no method and opens no door.
    expect(container.querySelector("a")).toBeNull();
  });

  it("renders nothing for an id the registry does not declare", () => {
    regime.entry = undefined;
    const { container } = render(wrap(<RatingMethodChip agentId="nobody" />));
    expect(container.textContent).toBe("");
  });
});
