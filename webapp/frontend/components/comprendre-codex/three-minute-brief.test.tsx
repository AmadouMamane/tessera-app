// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import deMessages from "@/messages/de.json";
import enMessages from "@/messages/en.json";
import frMessages from "@/messages/fr.json";
import { ThreeMinuteBrief, type ThreeMinuteCopy } from "./three-minute-brief";

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const copies = {
  fr: frMessages.comprendreCodex.content as unknown as ThreeMinuteCopy,
  en: enMessages.comprendreCodex.content as unknown as ThreeMinuteCopy,
  de: deMessages.comprendreCodex.content as unknown as ThreeMinuteCopy,
};

afterEach(() => {
  cleanup();
  window.history.replaceState(null, "", "/");
});

describe("Codex three-minute Tessera brief", () => {
  it.each(Object.entries(copies))("keeps the 3-4-3 reading contract in %s", (_locale, copy) => {
    expect(copy.questions).toHaveLength(3);
    expect(copy.timeline.items).toHaveLength(6);
    expect(copy.journey.checks).toHaveLength(4);
    expect(copy.journey.receipt.rows).toHaveLength(4);
    expect(copy.phases.items).toHaveLength(4);
    expect(copy.roles.items).toHaveLength(3);
    expect(copy.honesty.statuses).toHaveLength(3);
    expect(copy.close.verbs).toHaveLength(3);
  });

  it("renders a complete business narrative and two explicit next steps", () => {
    const copy = copies.fr;
    render(<ThreeMinuteBrief copy={copy} />);

    expect(screen.getByRole("heading", { name: copy.heroTitle, level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.journey.title, level: 3 })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: copy.journey.receipt.title, level: 4 }),
    ).toBeInTheDocument();
    expect(screen.getByText(copy.journey.receipt.status)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.roles.title, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.honesty.title, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: copy.close.businessCta })).toHaveAttribute(
      "href",
      "/recouvrement",
    );
    expect(screen.getByRole("link", { name: copy.close.cockpitCta })).toHaveAttribute(
      "href",
      "/select-space",
    );
    expect(screen.getByRole("navigation", { name: copy.timeline.label })).toBeInTheDocument();
    for (const item of copy.timeline.items) {
      expect(screen.getByRole("link", { name: `${item.time} ${item.label}` })).toHaveAttribute(
        "href",
        `#${item.target}`,
      );
    }
    const firstStep = copy.timeline.items[0];
    const secondStep = copy.timeline.items[1];
    if (!firstStep || !secondStep) throw new Error("The timeline needs at least two steps");
    const firstLink = screen.getByRole("link", {
      name: `${firstStep.time} ${firstStep.label}`,
    });
    const secondLink = screen.getByRole("link", {
      name: `${secondStep.time} ${secondStep.label}`,
    });
    expect(firstLink).toHaveAttribute("aria-current", "step");
    fireEvent.click(secondLink);
    expect(secondLink).toHaveAttribute("aria-current", "step");
    expect(firstLink).not.toHaveAttribute("aria-current");
  });

  it("keeps the executive reading free of implementation jargon", () => {
    render(<ThreeMinuteBrief copy={copies.fr} />);
    const rendered = document.body.textContent ?? "";

    expect(rendered).not.toMatch(/LangGraph|pgvector|FastAPI|JSONL|LLM|token/i);
    expect(rendered).toContain("Direction · DRH");
    expect(rendered).toContain("Manager métier");
    expect(rendered).toContain("Risques · IT");
  });

  it("opens and marks a chapter shared as a deep link", async () => {
    Element.prototype.scrollIntoView = vi.fn();
    window.history.replaceState(null, "", "#honesty");
    render(<ThreeMinuteBrief copy={copies.fr} />);

    const evidenceStep = copies.fr.timeline.items.find((item) => item.target === "honesty");
    if (!evidenceStep) throw new Error("The evidence step is required");
    const evidenceLink = screen.getByRole("link", {
      name: `${evidenceStep.time} ${evidenceStep.label}`,
    });

    await waitFor(() => expect(evidenceLink).toHaveAttribute("aria-current", "step"));
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
      block: "start",
      behavior: "auto",
    });
  });

  it("does not leak French component labels into English or German", () => {
    for (const copy of [copies.en, copies.de]) {
      const { unmount } = render(<ThreeMinuteBrief copy={copy} />);
      const rendered = document.body.textContent ?? "";
      expect(rendered).not.toMatch(
        /Sans plan de contrôle|Preuve produite|Un client demande|Exemple illustratif/,
      );
      unmount();
    }
  });
});
