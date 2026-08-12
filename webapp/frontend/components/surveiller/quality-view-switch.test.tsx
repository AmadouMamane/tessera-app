// @vitest-environment jsdom
//
// Successor of eval-door.test.tsx, same doctrine. `/eval` was an ORPHAN — zero inbound links
// in the whole application — and the EvalDoor banner was the guard that kept a way in alive.
// The eval screen now lives ON /surveiller/qualite-ia (its `?vue=evaluations` view), so the
// way in is this switch, and the guard moves with it: the door to the evaluations view must
// render, it must resolve to the merged page, and it must SAY what is behind it — a door
// labelled "other view" hides the screen it guards exactly like no door at all.
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider, createTranslator } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

const MESSAGES = { fr, de, en } as const;

vi.mock("next-intl/server", () => ({
  getTranslations: async ({ locale, namespace }: { locale: string; namespace: string }) =>
    createTranslator({
      locale,
      messages: MESSAGES[locale as keyof typeof MESSAGES] as never,
      namespace: namespace as never,
    }),
}));

import { QualityViewSwitch } from "@/components/surveiller/quality-view-switch";
import type { ReleaseControl } from "@/lib/api/schemas";

const LOCALES = ["fr", "de", "en"] as const;

afterEach(cleanup);

/** A minimal payload: one agent cleared, one blocked, one never evaluated. */
const CONTROL: ReleaseControl = {
  available: true,
  agents: [
    {
      agent_id: "a",
      name: "A",
      decision: {
        allowed: true,
        has_run: true,
        blocked_by: null,
        observability_level: "L2",
        required_level: "L2",
        floor_regressions: [],
      },
    },
    {
      agent_id: "b",
      name: "B",
      decision: {
        allowed: false,
        has_run: true,
        blocked_by: "null_floor",
        observability_level: "L2",
        required_level: "L2",
        floor_regressions: ["08_x"],
      },
    },
    {
      agent_id: "c",
      name: "C",
      decision: {
        allowed: false,
        has_run: false,
        blocked_by: null,
        observability_level: null,
        required_level: null,
        floor_regressions: [],
      },
    },
  ],
} as unknown as ReleaseControl;

async function renderSwitch(
  locale: (typeof LOCALES)[number],
  active: "signals" | "evaluations",
  control: ReleaseControl | null = null,
) {
  render(
    <NextIntlClientProvider
      locale={locale}
      messages={MESSAGES[locale] as unknown as AbstractIntlMessages}
    >
      {await QualityViewSwitch({ active, locale, control })}
    </NextIntlClientProvider>,
  );
}

describe("the way in to the evaluations view", () => {
  it.each(LOCALES)("renders a door resolving to ?vue=evaluations in %s", async (locale) => {
    await renderSwitch(locale, "signals");
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    const doors = links.map((l) => l.getAttribute("href") ?? "");
    // next-intl's Link prefixes the locale; what matters is the merged page + the view param.
    expect(doors.some((h) => /\/surveiller\/qualite-ia\?vue=evaluations$/.test(h))).toBe(true);
    expect(doors.some((h) => /\/surveiller\/qualite-ia$/.test(h))).toBe(true);
  });

  it("says what is behind each door, not just that doors exist", async () => {
    await renderSwitch("fr", "signals");
    const texts = screen.getAllByRole("link").map((l) => l.textContent ?? "");
    const evalDoor = texts.find((t) => /Évaluations/.test(t)) ?? "";
    // The old orphan's content is named in operator language, without delivery shorthand.
    expect(evalDoor).toMatch(/Jeu de cas/);
    expect(evalDoor).toMatch(/résultat sans modèle/);
    expect(evalDoor).toMatch(/comparaisons/);
    // The judge's reliability and the run archive crossed to this side; a door that did not
    // name them would be under-promising exactly what an operator came looking for.
    expect(evalDoor).toMatch(/exécutions passées/);
    expect(evalDoor).toMatch(/fiabilité du juge/);
    const signalsDoor = texts.find((t) => /Suivi continu/.test(t)) ?? "";
    expect(signalsDoor).toMatch(/Objectifs/);
    // …and this door may no longer claim it. It said "fiabilité de l'évaluation" while the
    // tab measuring it sat on the other view — the assertion below is the pair of the one
    // above, and the two together are what keep the switch from advertising the same content
    // on both sides.
    expect(signalsDoor).not.toMatch(/fiabilité/);
    expect(signalsDoor).toMatch(/temps réel/);
  });

  it("marks the active view, so the switch states where the reader IS", async () => {
    await renderSwitch("fr", "evaluations");
    const current = screen
      .getAllByRole("link")
      .filter((l) => l.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]?.textContent ?? "").toMatch(/Évaluations/);
  });

  it("looks like a door: the inactive view says Ouvrir, the active one says where you are", async () => {
    // Operator feedback (2026-08-12): two bordered cards with no verb read as static summaries —
    // nothing said they could be entered. The affordance is now words, not only a hover style.
    await renderSwitch("fr", "signals");
    const texts = screen.getAllByRole("link").map((l) => l.textContent ?? "");
    const evalDoor = texts.find((t) => /Évaluations/.test(t)) ?? "";
    const signalsDoor = texts.find((t) => /Suivi continu/.test(t)) ?? "";
    expect(evalDoor).toMatch(/Ouvrir/);
    expect(signalsDoor).toMatch(/Vue ouverte/);
  });
});

describe("the go-live verdict at door size", () => {
  it("rides on the evaluations door: ready, blocked and never-evaluated counts", async () => {
    await renderSwitch("fr", "signals", CONTROL);
    const texts = screen.getAllByRole("link").map((l) => l.textContent ?? "");
    const evalDoor = texts.find((t) => /Évaluations/.test(t)) ?? "";
    expect(evalDoor).toMatch(/1\/3 agents peuvent être mis en ligne/);
    expect(evalDoor).toMatch(/1 bloqué/);
    expect(evalDoor).toMatch(/1 jamais évalué/);
  });

  it("says 'unreachable' when the payload could not be read — never a quiet green", async () => {
    await renderSwitch("fr", "signals", null);
    const texts = screen.getAllByRole("link").map((l) => l.textContent ?? "");
    const evalDoor = texts.find((t) => /Évaluations/.test(t)) ?? "";
    expect(evalDoor).toMatch(/injoignable/);
    expect(evalDoor).not.toMatch(/peuvent être mis en ligne/);
  });
});
