// @vitest-environment jsdom
//
// The other half of the `access` degrade fix: the schema now ACCEPTS `{available:false}`, but a
// schema that parses an empty answer into a component that reads `data.roles` would just move the
// crash one line down. This renders the real component against the real degraded response and
// asserts the page stands up and says so.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "@/messages/fr.json";

const fetchAccessOverview = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api/client", () => ({ fetchAccessOverview }));

import { AccessOverview } from "@/components/access/access-overview";

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      <QueryClientProvider client={client}>{node}</QueryClientProvider>
    </NextIntlClientProvider>
  );
}

afterEach(() => {
  // No `globals: true` in the vitest config, so testing-library's auto-cleanup never runs and the
  // previous test's DOM would still be mounted — the healthy case would find the degraded card
  // left over from the degraded case and "pass" for the wrong reason.
  cleanup();
  vi.clearAllMocks();
});

describe("the roles page survives the backend's honest-empty degrade", () => {
  it("renders the unavailable state instead of throwing", async () => {
    // Exactly what `/observability/access` returns when the roles store is unreachable.
    fetchAccessOverview.mockResolvedValue({ available: false });

    render(wrap(<AccessOverview />));

    // The page stands up, and it SAYS the roles are unavailable — it does not spin forever
    // (which would claim it is on its way) and it does not fabricate an empty catalogue (which
    // would be an outage rendered as "there are no roles").
    expect(await screen.findByTestId("access-unavailable")).toBeTruthy();
    expect(screen.getByText(messages.roles.unavailableTitle)).toBeTruthy();
  });

  it("renders the real catalogue when the backend is healthy", async () => {
    fetchAccessOverview.mockResolvedValue({
      available: true,
      generated_at: "2026-07-12T10:00:00Z",
      total_roles: 1,
      page_size: 10,
      kpis: [],
      roles: [
        {
          id: "admin",
          name: "Administrateur",
          type: "systeme",
          description: "",
          users: 1,
          permissions: 2,
          scope: "org",
          environment: "prod",
          modified: "-",
          status: "active",
          caps: [],
          owner: "",
          created: "-",
          members: [],
          permission_dist: [],
          access_scope: [],
        },
      ],
      selected: {
        id: "admin",
        name: "Administrateur",
        type: "systeme",
        scope: "org",
        description: "",
        owner: "",
        created: "-",
        modified: "-",
        status: "active",
        environment: "prod",
        members: [],
        permission_dist: [],
        access_scope: [],
        caps: [],
      },
      top_roles: [],
      access_by_resource: [],
      pending_requests: [],
      sod_violations: [],
      inactive_accounts: [],
      footer: { total: 1, source: "registry" },
    });

    render(wrap(<AccessOverview />));

    expect(await screen.findByText("Administrateur")).toBeTruthy();
    expect(screen.queryByTestId("access-unavailable")).toBeNull();
  });
});
