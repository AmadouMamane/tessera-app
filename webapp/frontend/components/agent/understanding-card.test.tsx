// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { UnderstandingSummary } from "@/lib/api/schemas";
import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

import { UnderstandingCard } from "./understanding-card";

/**
 * The understanding plane on SCREEN (ADR 0053, ADR 0017 §A5.3). What must hold:
 *
 *  · COUNTS only — this ruler never shares a denominator with the business signals
 *    beside it, so no percent sign may ever render here;
 *  · every failure is NAMED by kind, in the reader's language, with its count;
 *  · `null` (no classified turns) renders NOTHING — an absent plane, not an empty score;
 *  · all three locales render real strings, never a message-key path (a format failure
 *    prints the key path, and only a render sees it).
 */

const SUMMARY: UnderstandingSummary = {
  observed: 24,
  window: 200,
  total_rows: 74,
  verdicts: 22,
  agree: 12,
  disagree: 10,
  failures: { timeout: 2 },
  latency_ms_p50: 2301.3,
  latest_at: "2026-08-24T11:58:22.482+00:00",
  latest_mode: "active",
  latest_model: "gemma3:27b",
};

function mount(node: ReactNode, messages: unknown = fr) {
  return render(
    <NextIntlClientProvider
      locale="fr"
      timeZone="Europe/Paris"
      messages={messages as unknown as AbstractIntlMessages}
    >
      {node}
    </NextIntlClientProvider>,
  );
}

afterEach(cleanup);

describe("UnderstandingCard", () => {
  it("renders counts, the named failure, the model and the active mode — and no percent", () => {
    const { container } = mount(<UnderstandingCard data={SUMMARY} />);
    const text = container.textContent ?? "";
    expect(text).toContain("Compréhension du langage");
    // The arithmetic is GIVEN, never left to the reader (operator feedback 2026-08-24):
    // observed, verdicts, agree and disagree all appear on one line, and the failures
    // line closes the sum (22 read + 2 without a reading = 24 analysed).
    expect(text).toContain("24 messages analysés");
    expect(text).toContain("22 lus par le modèle");
    expect(text).toContain("12");
    expect(text).toContain("2 fois, le modèle n'a pas donné de lecture");
    expect(text).toContain("délai dépassé 2");
    // The latency names WHAT it times — the model's reading of the text, not the turn.
    expect(text).toContain("lecture du texte");
    expect(text).toContain("gemma3:27b");
    expect(text).toContain("le modèle lit et décide");
    expect(text).not.toContain("%");
    expect(text).not.toContain("agentMetier.understanding");
  });

  it("says observation when the latest row ran in shadow mode", () => {
    const { container } = mount(<UnderstandingCard data={{ ...SUMMARY, latest_mode: "shadow" }} />);
    expect(container.textContent).toContain("en observation");
  });

  it("renders nothing at all for an absent plane", () => {
    const { container } = mount(<UnderstandingCard data={null} />);
    expect(container.textContent).toBe("");
  });

  it("renders real strings in every locale, never a key path", () => {
    for (const messages of [en, de]) {
      const { container, unmount } = mount(<UnderstandingCard data={SUMMARY} />, messages);
      const text = container.textContent ?? "";
      expect(text).not.toContain("agentMetier.understanding");
      expect(text).not.toContain("%");
      unmount();
    }
  });
});
