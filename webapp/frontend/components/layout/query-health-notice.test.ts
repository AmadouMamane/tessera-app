import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";

import { activeErrorQueries, activeErrorQueryCount, queryFailureKind } from "./query-health-notice";

/**
 * The destination the embedding-skew read declares when it fails.
 *
 * This used to be a made-up literal, and being made up it survived the tab moving: the notice
 * kept promising `?tab=runs`, a dashboard tab that no longer exists, and this test stayed green
 * because it was comparing its own invention with itself. The value is now the app's, asserted
 * below to still be the app's — a health notice whose "go and look" lands on the wrong screen is
 * worse than no notice, because the operator concludes there is nothing to see.
 */
const SKEW_HREF = "/surveiller/qualite-ia?vue=evaluations&tab=archive";

it("uses the href the application actually declares, not one invented here", async () => {
  const { readFileSync } = await import("node:fs");
  const source = readFileSync("components/eval/eval-dashboard.tsx", "utf8");
  expect(source).toContain(`href: "${SKEW_HREF}"`);
});

describe("activeErrorQueryCount", () => {
  it("counts only failed queries observed by the current screen", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const observer = new QueryObserver(client, {
      queryKey: ["visible-failure"],
      queryFn: async () => {
        throw new Error("offline");
      },
    });
    const unsubscribe = observer.subscribe(() => undefined);

    await observer.refetch();
    expect(activeErrorQueryCount(client)).toBe(1);

    unsubscribe();
    expect(activeErrorQueryCount(client)).toBe(0);
  });

  it("does not count a failed query once its only observer is disabled", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const observer = new QueryObserver(client, {
      queryKey: ["hidden-tab-source"],
      queryFn: async () => {
        throw new Error("offline");
      },
    });
    const unsubscribe = observer.subscribe(() => undefined);
    await observer.refetch();

    observer.setOptions({
      queryKey: ["hidden-tab-source"],
      queryFn: async () => {
        throw new Error("offline");
      },
      enabled: false,
    });

    expect(activeErrorQueryCount(client)).toBe(0);
    unsubscribe();
  });

  it("carries the operator-facing source name and destination", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const observer = new QueryObserver(client, {
      queryKey: ["embedding-skew"],
      queryFn: async () => {
        throw new ApiError("schema mismatch", 200, {});
      },
      meta: {
        health: {
          label: "Compatibilité des embeddings",
          href: SKEW_HREF,
        },
      },
    });
    const unsubscribe = observer.subscribe(() => undefined);
    await observer.refetch();

    expect(activeErrorQueries(client)).toEqual([
      expect.objectContaining({
        source: "Embedding skew",
        label: "Compatibilité des embeddings",
        href: SKEW_HREF,
        kind: "contract",
      }),
    ]);
    unsubscribe();
  });

  it("distinguishes contract, access and service failures", () => {
    expect(queryFailureKind(new ApiError("schema", 200, {}))).toBe("contract");
    expect(queryFailureKind(new ApiError("denied", 403, {}))).toBe("access");
    expect(queryFailureKind(new ApiError("down", 503, {}))).toBe("service");
    expect(queryFailureKind(new TypeError("offline"))).toBe("network");
  });
});
