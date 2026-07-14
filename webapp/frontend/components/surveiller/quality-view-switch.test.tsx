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

const LOCALES = ["fr", "de", "en"] as const;

afterEach(cleanup);

async function renderSwitch(locale: (typeof LOCALES)[number], active: "signals" | "evaluations") {
  render(
    <NextIntlClientProvider
      locale={locale}
      messages={MESSAGES[locale] as unknown as AbstractIntlMessages}
    >
      {await QualityViewSwitch({ active, locale })}
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
    // The things the monitoring view does NOT serve — the old orphan's content, named.
    expect(evalDoor).toMatch(/gate de release/);
    expect(evalDoor).toMatch(/plancher mesuré sans aucun modèle/);
    const signalsDoor = texts.find((t) => /Suivi continu/.test(t)) ?? "";
    expect(signalsDoor).toMatch(/SLO/);
  });

  it("marks the active view, so the switch states where the reader IS", async () => {
    await renderSwitch("fr", "evaluations");
    const current = screen
      .getAllByRole("link")
      .filter((l) => l.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]?.textContent ?? "").toMatch(/Évaluations/);
  });
});
