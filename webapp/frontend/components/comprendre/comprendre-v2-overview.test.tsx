// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ComprendreResponse } from "@/lib/api/schemas";
import messages from "@/messages/fr.json";

const fetchComprendreFacts = vi.hoisted(() => vi.fn());
vi.mock("@/lib/comprendre-client", () => ({ fetchComprendreFacts }));
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={typeof href === "string" ? href : undefined} {...props}>
      {children}
    </a>
  ),
}));

import { ComprendreV2Overview } from "@/components/comprendre/comprendre-v2-overview";

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      {node}
    </NextIntlClientProvider>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("the comprendre live facts bind each backend field once", () => {
  it("renders distinct controlled and blocked counts from one T3 payload", () => {
    fetchComprendreFacts.mockResolvedValue(null);
    const facts: ComprendreResponse = {
      available: true,
      generated_at: "2026-07-22T10:30:00+00:00",
      fleet: {
        observed_agents: null,
        last_signal_at: null,
        is_silent: null,
        window_hours: 24,
      },
      guard: {
        controlled_today: 3,
        blocked_today: 1,
        since: "2026-07-22T00:00:00+02:00",
      },
      evaluations: { ready_agents: 2, review_agents: 4 },
      audit: { last_verified_at: "2026-07-22T10:24:00+00:00" },
    };

    render(wrap(<ComprendreV2Overview initialFacts={facts} />));

    expect(screen.getByText("3 échanges contrôlés aujourd'hui · 1 bloqués")).toBeTruthy();
    expect(screen.queryByText("3 échanges contrôlés aujourd'hui · 3 bloqués")).toBeNull();
  });
});
