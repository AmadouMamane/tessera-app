import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";

import { activeErrorQueries, activeErrorQueryCount, queryFailureKind } from "./query-health-notice";

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
          href: "/surveiller/qualite-ia?tab=runs",
        },
      },
    });
    const unsubscribe = observer.subscribe(() => undefined);
    await observer.refetch();

    expect(activeErrorQueries(client)).toEqual([
      expect.objectContaining({
        source: "Embedding skew",
        label: "Compatibilité des embeddings",
        href: "/surveiller/qualite-ia?tab=runs",
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
