import { describe, expect, it } from "vitest";

import { ReleaseControlAgentSchema } from "@/lib/api/schemas";
import { asBlockCause, levelShortfalls, summarizeRelease } from "@/lib/release-verdict";

import type { AgentDecision } from "@/lib/release-verdict";

const agent = (over: Partial<AgentDecision> & { agentId: string }): AgentDecision => ({
  name: over.agentId,
  allowed: false,
  hasRun: true,
  blockedBy: null,
  observabilityLevel: "L0",
  requiredLevel: null,
  floorRegressions: [],
  ...over,
});

describe("the payload contract", () => {
  it("declares `decision`, so the fields naming the block are not stripped", () => {
    // The backend gained these on 2026-08-07 and zod would have dropped every one of them in
    // silence — the same failure this whole screen was fixed for, one endpoint over.
    const parsed = ReleaseControlAgentSchema.parse({
      agent_id: "recouvrement",
      name: "Recouvrement",
      owner: "ops",
      state: "En service",
      state_tone: "good",
      last_phase: "live",
      flow: ["proposed", "live"],
      history: [],
      release: {
        agent_id: "recouvrement",
        available: true,
        passed: true,
        verdict_label: "PRÊT",
        verdict_tone: "good",
        candidate_version: "v1",
        eval_set: "recouvrement",
        executions: 174,
        socle_ok: true,
        blocking_socle: 0,
        blocking_t1: 0,
        waived_active: 0,
      },
      decision: {
        allowed: false,
        reason: "level below requirement",
        has_run: true,
        gate_passed: true,
        failed_critical: [],
        run_at: "20260806T101500Z",
        observability_level: "L2",
        required_level: "L3",
        blocked_by: "observability_level",
        floor_graded: true,
        floor_regressions: [],
      },
    });

    expect(parsed.decision?.blocked_by).toBe("observability_level");
    expect(parsed.decision?.required_level).toBe("L3");
    expect(parsed.decision?.observability_level).toBe("L2");
  });
});

describe("asBlockCause", () => {
  it("does not attribute an unrecognised cause to the eval gate", () => {
    // The failure mode this guards: a new backend reason arriving at an older cockpit. Reading
    // it as `eval_gate` would send the operator to fix a passing test.
    expect(asBlockCause("quota_exhausted")).toBe("unknown");
    expect(asBlockCause(null)).toBe("unknown");
    expect(asBlockCause("null_floor")).toBe("null_floor");
  });
});

describe("summarizeRelease", () => {
  it("never counts an unevaluated agent as blocked — silence is not a failure", () => {
    const v = summarizeRelease([
      agent({ agentId: "a", allowed: true }),
      agent({ agentId: "b", hasRun: false }),
    ]);

    expect(v.releasable).toBe(1);
    expect(v.notEvaluated.map((a) => a.agentId)).toEqual(["b"]);
    expect(v.blocked).toEqual([]);
    expect(v.worst).toBeNull();
    // Not `ok`: painting "all clear" over an agent nobody ran describes our own silence.
    expect(v.severity).toBe("info");
  });

  it("says ok only when every agent was judged and cleared", () => {
    const v = summarizeRelease([
      agent({ agentId: "a", allowed: true }),
      agent({ agentId: "b", allowed: true }),
    ]);
    expect(v.severity).toBe("ok");
    expect(v.worst).toBeNull();
  });

  it("ranks 'worse than no model at all' above every other block", () => {
    const v = summarizeRelease([
      agent({ agentId: "lvl", blockedBy: "observability_level" }),
      agent({ agentId: "gate", blockedBy: "eval_gate" }),
      agent({ agentId: "floor", blockedBy: "null_floor" }),
    ]);

    expect(v.worst).toBe("null_floor");
    expect(v.blocked.map((b) => b.cause)).toEqual([
      "null_floor",
      "eval_gate",
      "observability_level",
    ]);
    expect(v.severity).toBe("critical");
  });

  it("keeps a BLIND level apart from a measured one — different fact, different fix", () => {
    const v = summarizeRelease([
      agent({ agentId: "blind", blockedBy: "observability_level_unreadable" }),
    ]);

    expect(v.hasBlindSpot).toBe(true);
    expect(v.worst).toBe("observability_level_unreadable");
    // It refuses the release, but it is not shouted like a certified regression: it is a hole
    // in our instruments, not a fault proven in the agent (ADR 0026).
    expect(v.severity).toBe("warning");
  });

  it("groups agents under their own cause, and counts them", () => {
    const v = summarizeRelease([
      agent({ agentId: "a", name: "Alpha", blockedBy: "eval_gate" }),
      agent({ agentId: "b", name: "Beta", blockedBy: "eval_gate" }),
      agent({ agentId: "c", allowed: true }),
    ]);

    expect(v.blocked).toHaveLength(1);
    expect(v.blocked[0]?.agents.map((a) => a.name)).toEqual(["Alpha", "Beta"]);
    expect(v.releasable).toBe(1);
    expect(v.total).toBe(3);
  });
});

describe("levelShortfalls", () => {
  it("reports a gap only when a level is actually REQUIRED", () => {
    // An agent at L0 with no requirement is not short of anything — /observability/fleet shows
    // the reached level with nothing to compare it to, and that is how L0 came to look like a
    // failing grade.
    const none = levelShortfalls([agent({ agentId: "a", observabilityLevel: "L0" })]);
    expect(none).toEqual([]);

    const short = levelShortfalls([
      agent({ agentId: "b", name: "Beta", observabilityLevel: "L2", requiredLevel: "L3" }),
      agent({ agentId: "c", observabilityLevel: "L3", requiredLevel: "L3" }),
    ]);
    expect(short).toEqual([{ agentId: "b", name: "Beta", reached: "L2", required: "L3" }]);
  });
});
