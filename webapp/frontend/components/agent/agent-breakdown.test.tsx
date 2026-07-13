// @vitest-environment jsdom
//
// The "Total org (dédup)" footer used to close with "(handoff = 1)" — a sentence about
// handoffs computed from a table that had never been asked about handoffs. Found live:
// the S1 journal attested 34 transfers over 34 conversations while `shared_conversations`
// read 0, and the footer rendered "0 dédoublonnées" as though a reconciliation had
// happened. These tests pin the honest footer: when the journal's claim and the store's
// answer disagree, the gap is STATED; when they agree, that is said too; and the wire
// schema carries the three reconciliation fields (zod strips undeclared keys, so a missing
// declaration would silently re-arm the bug).
import { cleanup, render, screen } from "@testing-library/react";
import { createTranslator } from "next-intl";
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

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { FleetSchema } from "@/lib/api/schemas";

afterEach(cleanup);

/** A wire-shaped fleet payload, parsed through the REAL schema — never a hand-typed object. */
function fleetFromWire(reconciliation: {
  handoff_events: number;
  handoff_conversations: number;
  handoff_conversations_seen_shared: number;
}) {
  return FleetSchema.parse({
    available: true,
    agents: [
      {
        id: "support-client",
        name: "Support Client",
        owner: "ops",
        conversations: 274,
        turns: 300,
        messages: 600,
        escalation_rate: 26.8,
        latency_ms: 4600,
        handoffs_in: 0,
        handoffs_out: 34,
        health: "green",
        release: null,
      },
    ],
    org: { conversations: 415, turns: 483 },
    naive_sum_conversations: 415,
    shared_conversations: 0,
    dedup_saved: 0,
    ...reconciliation,
  });
}

describe("the handoff reconciliation line under Total org (dédup)", () => {
  it("the schema carries the reconciliation fields — zod must not strip them", () => {
    const fleet = fleetFromWire({
      handoff_events: 34,
      handoff_conversations: 34,
      handoff_conversations_seen_shared: 0,
    });
    expect(fleet.handoff_events).toBe(34);
    expect(fleet.handoff_conversations).toBe(34);
    expect(fleet.handoff_conversations_seen_shared).toBe(0);
  });

  it("states the gap when the journal attests journeys the store cannot see shared", async () => {
    const fleet = fleetFromWire({
      handoff_events: 34,
      handoff_conversations: 34,
      handoff_conversations_seen_shared: 0,
    });

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    const gap = screen.getByText(/Réconciliation impossible/);
    expect(gap.textContent).toMatch(/34 transferts/);
    expect(gap.textContent).toMatch(/comptés en double/);
    expect(screen.queryByText(/Transferts réconciliés/)).toBeNull();
    // And the old unearned claim is gone from the dedup line itself.
    expect(screen.queryByText(/handoff = 1/)).toBeNull();
  });

  it("says reconciled when every attested journey is seen under two agents", async () => {
    const fleet = fleetFromWire({
      handoff_events: 3,
      handoff_conversations: 2,
      handoff_conversations_seen_shared: 2,
    });

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    expect(screen.getByText(/Transferts réconciliés/)).toBeTruthy();
    expect(screen.queryByText(/Réconciliation impossible/)).toBeNull();
  });

  it("stays silent when the journal attests no handoffs at all", async () => {
    const fleet = fleetFromWire({
      handoff_events: 0,
      handoff_conversations: 0,
      handoff_conversations_seen_shared: 0,
    });

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    expect(screen.queryByText(/Réconciliation impossible/)).toBeNull();
    expect(screen.queryByText(/Transferts réconciliés/)).toBeNull();
  });

  it("renders the gap sentence in every locale", async () => {
    for (const locale of ["fr", "de", "en"] as const) {
      cleanup();
      const fleet = fleetFromWire({
        handoff_events: 34,
        handoff_conversations: 34,
        handoff_conversations_seen_shared: 0,
      });
      render(await AgentBreakdown({ fleet, scope: "all", locale }));
      const pattern = {
        fr: /Réconciliation impossible/,
        de: /Abgleich nicht möglich/,
        en: /Cannot reconcile/,
      }[locale];
      expect(screen.getByText(pattern)).toBeTruthy();
    }
  });
});
