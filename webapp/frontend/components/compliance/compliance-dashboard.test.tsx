// @vitest-environment jsdom
//
// Found live with ClickHouse refusing auth: the compliance POSTURE was honestly
// "indisponible", and its early return swallowed the `agentScope` slot — the whole page
// collapsed to one sentence while the per-agent facts (a different store, healthy) were
// sitting right there. A proven table must not hide behind an unrelated outage: the
// unavailable state renders the per-agent context AND the posture's own unavailability.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/fr.json";

const fetchCompliance = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  fetchCompliance,
}));

import { ComplianceDashboard } from "@/components/compliance/compliance-dashboard";

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      <QueryClientProvider client={client}>{node}</QueryClientProvider>
    </NextIntlClientProvider>
  );
}

afterEach(() => {
  // No `globals: true` in the vitest config: without explicit cleanup the previous test's
  // DOM stays mounted and the next assertion can pass against leftovers.
  cleanup();
  vi.clearAllMocks();
});

describe("the unavailable posture does not swallow the per-agent context", () => {
  it("renders the agentScope slot AND the posture's own unavailability", async () => {
    // Exactly what /observability/compliance returns when its compute raised (except-arm).
    fetchCompliance.mockResolvedValue({ available: false });

    render(
      wrap(
        <ComplianceDashboard
          agentScope={<div data-testid="agent-scope-slot">Vue par agent</div>}
        />,
      ),
    );

    // The posture says what IT knows: the read failed, and the card states it.
    expect(await screen.findByText(messages.compliance.unavailable)).toBeTruthy();
    // And the per-agent context is still there — it never depended on that read.
    expect(screen.getByTestId("agent-scope-slot")).toBeTruthy();
  });
});
