// @vitest-environment jsdom
//
// Two rungs, and the screen has to say which one it is showing.
//
// On 2026-08-05 an operator read "Niveau L3" on the Métier page of an agent the release gate
// holds at L0, and asked the obvious question. Neither number was wrong: this page answers a
// CONTRACT question ("what does the manifest reach?") and the gate answers an EVIDENCE one
// ("what do observed facts support?"). What was wrong is that one badge rendered one of them
// under a name that could be read as either — so a declaration passed for a measurement, which
// is the class of over-claim this repository treats as non-negotiable.
//
// The fix is a legend, never making the gate read the declaration. These tests pin both halves:
// the gap is rendered when there is one, and NOT manufactured when there is none.
import { cleanup, render, screen } from "@testing-library/react";
import { createTranslator } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import { LevelBadge } from "@/components/agent/agent-metier";
import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

const MESSAGES = { fr, de, en } as const;

function t(locale: keyof typeof MESSAGES) {
  return createTranslator({
    locale,
    messages: MESSAGES[locale],
    namespace: "agentMetier",
  }) as unknown as Parameters<typeof LevelBadge>[0]["t"];
}

afterEach(cleanup);

describe("the L-level badge names which rung it shows", () => {
  it("renders BOTH rungs when the declared one outruns the proven one", () => {
    render(<LevelBadge declared="L3" computed="L0" t={t("fr")} />);
    const badge = screen.getByText(/déclaré/);
    expect(badge.textContent).toContain("L3");
    expect(badge.textContent).toContain("L0");
    expect(badge.textContent).toContain("prouvé");
  });

  it("carries the explanation, so the gap is legible without leaving the page", () => {
    render(<LevelBadge declared="L3" computed="L0" t={t("fr")} />);
    const hint = screen.getByText(/déclaré/).getAttribute("title") ?? "";
    expect(hint).toContain("porte de mise en ligne");
  });

  it("says it in every locale — the gap is not a French-only disclosure", () => {
    render(<LevelBadge declared="L3" computed="L0" t={t("de")} />);
    expect(screen.getByText(/deklariert/).textContent).toContain("nachgewiesen");
    cleanup();
    render(<LevelBadge declared="L3" computed="L0" t={t("en")} />);
    expect(screen.getByText(/declared/).textContent).toContain("proven");
  });

  it("shows ONE rung when they agree — a legend that always fires is noise", () => {
    render(<LevelBadge declared="L3" computed="L3" t={t("fr")} />);
    expect(screen.getByText("Niveau L3")).toBeDefined();
    expect(screen.queryByText(/déclaré/)).toBeNull();
  });

  it("shows ONE rung when the proven one is unknown, rather than inventing a gap", () => {
    // `computed === null` means the resolver had nothing to say — an un-manifested agent, or a
    // store that did not answer. Rendering "L3 déclaré · — prouvé" would dress an absence as a
    // measured shortfall, which is the same defect wearing the opposite sign.
    render(<LevelBadge declared="L3" computed={null} t={t("fr")} />);
    expect(screen.getByText("Niveau L3")).toBeDefined();
    expect(screen.queryByText(/prouvé/)).toBeNull();
  });
});
