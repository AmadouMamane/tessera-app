// @vitest-environment jsdom
//
// `/eval` was an ORPHAN: zero inbound links in the whole application. No sidebar entry, no
// command-palette action, no cross-page link — the only two references to the route anywhere
// in the frontend were its own tab strip linking to itself. It held the case set, the runs,
// the model comparison, the measured null floor and the model's contribution over it, and it
// was reachable only by typing the URL.
//
// A page nobody can reach is a page that does not exist, and nothing failed when it happened
// — which is why it stayed that way. These tests are the guard: the door must render, it must
// point at /eval, and it must say what is behind it.
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { EvalDoor } from "@/components/surveiller/eval-door";
import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

const LOCALES = [
  ["fr", fr],
  ["de", de],
  ["en", en],
] as const;

afterEach(cleanup);

describe("the way in to /eval", () => {
  it.each(LOCALES)("renders a link to /eval in %s", (locale, messages) => {
    render(
      <NextIntlClientProvider
        locale={locale}
        messages={messages as unknown as AbstractIntlMessages}
      >
        <EvalDoor />
      </NextIntlClientProvider>,
    );
    const link = screen.getByRole("link");
    // next-intl's Link prefixes the locale; what matters is that it resolves to /eval.
    expect(link.getAttribute("href")).toMatch(/\/eval$/);
  });

  it("says what is behind the door, not just that a door exists", () => {
    render(
      <NextIntlClientProvider locale="fr" messages={fr as unknown as AbstractIntlMessages}>
        <EvalDoor />
      </NextIntlClientProvider>,
    );
    const text = screen.getByRole("link").textContent ?? "";
    // The three things /surveiller/qualite-ia does NOT serve and used to promise.
    expect(text).toMatch(/Évaluations/);
    expect(text).toMatch(/gate de release/);
    expect(text).toMatch(/plancher mesuré sans aucun modèle/);
  });

  it("the page's own subtitle no longer promises what it does not serve", () => {
    // The subtitle said "Évaluations, régressions, hallucinations…" over an SLO dashboard.
    // The page that promised the evaluations was not the page that had them.
    const subtitle = (fr as unknown as { quality: { subtitle: string } }).quality.subtitle;
    expect(subtitle).not.toMatch(/Évaluations, régressions/);
    for (const [, messages] of LOCALES) {
      const sub = (messages as unknown as { quality: { subtitle: string } }).quality.subtitle;
      expect(sub.length).toBeGreaterThan(0);
    }
  });
});
