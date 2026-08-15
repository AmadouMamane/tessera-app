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

// ComplianceDashboard renders SignalCommandBar (added with the shared temporal rail in
// c2f297c0) and calls useUrlBackedView; both reach router hooks that throw "invariant
// expected app router to be mounted" without a router context in jsdom. The hooks come
// from TWO modules: signal-command-bar reads usePathname/useRouter/useSearchParams from
// next/navigation, while use-url-backed-view reads usePathname/useRouter from the
// locale-aware @/i18n/navigation wrapper (and useSearchParams from next/navigation). Mock
// both, and stub the i18n Link as a plain anchor. Test-only: the assertions below
// (unavailable message + agentScope slot) are unchanged.
// Inlined (not a shared const): vi.mock factories are hoisted above the module body, so
// referencing a top-level const here would hit its temporal dead zone (the repo uses
// vi.hoisted for the same reason with fetchCompliance).
vi.mock("next/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/navigation")>()),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/surveiller/conformite",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
}));
vi.mock("@/i18n/navigation", () => ({
  usePathname: () => "/surveiller/conformite",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
  redirect: vi.fn(),
  getPathname: () => "/surveiller/conformite",
  Link: ({ href, children, ...rest }: { href: unknown; children: ReactNode }) => (
    <a href={String(href)} {...rest}>
      {children}
    </a>
  ),
}));

import { ComplianceDashboard } from "@/components/compliance/compliance-dashboard";
import { TooltipProvider } from "@/components/ui/tooltip";

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      {/* The FULLY drawn page mounts ⓘ tooltips; the "unavailable" case above returns before
          reaching any of them, which is why this provider was not needed until a test rendered
          the healthy layout. Supplied by the app shell in production. */}
      <TooltipProvider>
        <QueryClientProvider client={client}>{node}</QueryClientProvider>
      </TooltipProvider>
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

describe("a counter the backend could not compute is not a clean bill of health", () => {
  /**
   * The static ratchet (`lib/unread-is-not-zero.test.ts`) proves no call site coalesces an
   * absent reading into a threshold. This proves what the OPERATOR sees when it happens — the
   * half a source grep structurally cannot reach.
   *
   * The posture answers `available: true`, so none of the page's unavailability branches fire:
   * the read SUCCEEDED and simply could not compute these two figures. That is the case the old
   * code got wrong, and the one that looks most like health — a fully drawn page, every panel
   * present, and a green **0 non-conformities** underneath.
   */
  it("renders an em dash and a muted tone, never a green zero", async () => {
    fetchCompliance.mockResolvedValue({
      available: true,
      score: 82,
      n_controls: 40,
      n_conformant: 30,
      n_partial: 10,
      n_non_conformant: null,
      n_critical_deadlines: null,
      n_residual_risk: 0,
    });

    render(wrap(<ComplianceDashboard agentScope={<div />} />));

    const label = await screen.findByText(messages.compliance.kpi.nonConformant);
    const tile = label.closest("div")?.parentElement;
    expect(tile, "the non-conformant KPI tile").toBeTruthy();
    const text = tile?.textContent ?? "";
    // The figure: an absence, not a zero.
    expect(text).toContain("—");
    expect(text).not.toMatch(/\b0\b/);
    // The colour: never the green that says "conformant".
    expect(tile?.innerHTML ?? "").not.toContain("text-emerald-600");
    // A neighbouring tile whose value WAS computed still reads normally — this test must fail
    // on a fabricated zero, not on the page having gone blank.
    expect(screen.getByText("82")).toBeTruthy();
  });
});
