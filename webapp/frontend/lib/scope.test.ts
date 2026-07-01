import { describe, expect, it } from "vitest";

import { isScopedToAgent, parseScope, scopeAgentParam, scopeKey, withScope } from "./scope";

describe("parseScope", () => {
  it("maps agent=all / empty to the org view", () => {
    expect(parseScope(new URLSearchParams("agent=all")).agent).toBeUndefined();
    expect(parseScope(new URLSearchParams("")).agent).toBeUndefined();
    expect(parseScope(new URLSearchParams("agent=%20")).agent).toBeUndefined();
  });

  it("reads a concrete agent and instant", () => {
    const scope = parseScope(new URLSearchParams("agent=support&at=2026-06-12T10:00:00Z"));
    expect(scope.agent).toBe("support");
    expect(scope.at).toBe("2026-06-12T10:00:00Z");
  });

  it("reads from a server searchParams record", () => {
    const scope = parseScope({ agent: "recouvrement", language: "fr", at: undefined });
    expect(scope.agent).toBe("recouvrement");
    expect(scope.language).toBe("fr");
    expect(scope.at).toBeUndefined();
  });

  it("takes the first value of an array param", () => {
    expect(parseScope({ agent: ["support", "other"] }).agent).toBe("support");
  });
});

describe("withScope", () => {
  it("omits the org view and unset dimensions", () => {
    expect(withScope("/observability/slo", {})).toBe("/observability/slo");
    expect(withScope("/observability/slo", { agent: "all" })).toBe("/observability/slo");
  });

  it("writes set dimensions", () => {
    expect(withScope("/observability/slo", { agent: "support", at: "2026-06-12T10:00:00Z" })).toBe(
      "/observability/slo?at=2026-06-12T10%3A00%3A00Z&agent=support",
    );
  });

  it("carries language + model (Phase F dimensions)", () => {
    expect(withScope("/x", { language: "de", model: "llama3.2:3b" })).toBe(
      "/x?language=de&model=llama3.2%3A3b",
    );
  });
});

describe("scopeKey", () => {
  it("is stable and distinguishes scopes", () => {
    expect(scopeKey({ agent: "support" })).toBe(scopeKey({ agent: "support" }));
    expect(scopeKey({ agent: "support" })).not.toBe(scopeKey({ agent: "recouvrement" }));
    expect(scopeKey({})).not.toBe(scopeKey({ at: "2026-06-12T10:00:00Z" }));
  });
});

describe("helpers", () => {
  it("scopeAgentParam round-trips the org view to 'all'", () => {
    expect(scopeAgentParam({})).toBe("all");
    expect(scopeAgentParam({ agent: "support" })).toBe("support");
  });

  it("isScopedToAgent reflects a concrete agent", () => {
    expect(isScopedToAgent({})).toBe(false);
    expect(isScopedToAgent({ agent: "all" })).toBe(false);
    expect(isScopedToAgent({ agent: "support" })).toBe(true);
  });
});
