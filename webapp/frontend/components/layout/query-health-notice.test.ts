import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { activeErrorQueryCount } from "./query-health-notice";

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
});
