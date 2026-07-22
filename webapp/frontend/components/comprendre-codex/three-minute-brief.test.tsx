// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
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

afterEach(cleanup);

describe("Codex three-minute Tessera brief", () => {
  it.each(Object.entries(copies))("keeps the 3-4-3 reading contract in %s", (_locale, copy) => {
    expect(copy.questions).toHaveLength(3);
    expect(copy.journey.checks).toHaveLength(4);
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
  });

  it("keeps the executive reading free of implementation jargon", () => {
    render(<ThreeMinuteBrief copy={copies.fr} />);
    const rendered = document.body.textContent ?? "";

    expect(rendered).not.toMatch(/LangGraph|pgvector|FastAPI|JSONL|LLM|token/i);
    expect(rendered).toContain("Direction · DRH");
    expect(rendered).toContain("Manager métier");
    expect(rendered).toContain("Risques · IT");
  });

  it("does not leak French component labels into English or German", () => {
    for (const copy of [copies.en, copies.de]) {
      const { unmount } = render(<ThreeMinuteBrief copy={copy} />);
      const rendered = document.body.textContent ?? "";
      expect(rendered).not.toMatch(/Sans plan de contrôle|Preuve produite|Un client demande/);
      unmount();
    }
  });
});
