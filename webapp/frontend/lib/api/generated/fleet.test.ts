// The generated schemas, checked against the two things the hand-written ones got wrong.
//
// This is the front half of the P1.4 pilot. The backend now declares the fleet domain's contract
// (`response_model`), and `scripts/generate_zod.py` emits this module from its OpenAPI — so the
// front stops re-deriving that contract by hand. The two failures being fixed are both real and
// both were found by running the REAL backend output through the REAL hand-written schemas:
//
//   1. `AccessOverviewSchema` **rejected** `{available:false}` — the backend's own honest-empty
//      degrade. `request()` throws on a rejected schema, so `/observability/access` broke the
//      page on the exact response that exists so the page would not break.
//   2. Three schemas silently **stripped** fields the backend sends, `agent-historique.synthetic`
//      among them — the ADR 0019 §4 canary marker. Dropped, with no error, so the surface could
//      not tell a synthetic row from a real one.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import {
  AccessResponseSchema,
  AgentEvaluationsResponseSchema,
  ChromeResponseSchema,
  FleetResponseSchema,
  RbacMatrixResponseSchema,
  SandboxConfigResponseSchema,
} from "@/lib/api/generated/fleet";

const REAL = JSON.parse(
  readFileSync(
    new URL("../../../../../tests/unit/fixtures/fleet_real_responses.json", import.meta.url),
    "utf-8",
  ),
) as Record<string, unknown[]>;

const PILOT = [
  ["sandbox-config", SandboxConfigResponseSchema],
  ["chrome", ChromeResponseSchema],
  ["rbac-matrix", RbacMatrixResponseSchema],
  ["fleet", FleetResponseSchema],
  ["access", AccessResponseSchema],
  ["agent-evaluations", AgentEvaluationsResponseSchema],
] as const;

/** Every field path, index-agnostic — so a stripped key is visible wherever it hides. */
function paths(node: unknown, prefix = "$"): Set<string> {
  const out = new Set<string>();
  if (node && typeof node === "object" && !Array.isArray(node)) {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
      out.add(`${prefix}.${k}`);
      for (const p of paths(v, `${prefix}.${k}`)) out.add(p);
    }
  } else if (Array.isArray(node) && node.length > 0) {
    for (const p of paths(node[0], `${prefix}[]`)) out.add(p);
  }
  return out;
}

describe("the generated schemas accept what the backend really sends", () => {
  for (const [route, schema] of PILOT) {
    it(`${route}: parses every captured live response, stripping nothing`, () => {
      const samples = REAL[route];
      expect(samples?.length ?? 0).toBeGreaterThan(0);
      for (const sample of samples ?? []) {
        const parsed = schema.safeParse(sample);
        expect(parsed.success, `${route}: ${JSON.stringify(parsed.error?.issues?.[0])}`).toBe(true);
        // The silent failure: zod drops unknown keys. A generated schema must not.
        expect(paths(parsed.data)).toEqual(paths(sample));
      }
    });
  }
});

describe("the generated schemas accept the honest-empty degrade", () => {
  for (const [route, schema] of PILOT) {
    it(`${route}: {available:false} parses`, () => {
      // The regression that matters. Pre-generation, AccessOverviewSchema REJECTED this and
      // `request()` threw — breaking the page on the response designed to keep it alive.
      const parsed = schema.safeParse({ available: false });

      expect(parsed.success).toBe(true);
      expect(parsed.data).toEqual({ available: false });
    });
  }
});

describe("the union is discriminated, so `available: true` GUARANTEES the payload", () => {
  it("rejects a payload that claims available:true and omits its fields", () => {
    // What the hand-written schemas cannot do: 13 of the 14 model the union as
    // "everything optional", so a backend that dropped `agents` entirely would sail through.
    const parsed = FleetResponseSchema.safeParse({ available: true });

    expect(parsed.success).toBe(false);
  });
});
