"use client";

/**
 * Report / evidence-pack export, scoped to the cockpit's current temporal context
 * `(period, asOf)` — ADR 0011 §3/§5. Extracted from the header so the SURVEILLER
 * SignalCommandBar and the header (non-SURVEILLER pages) snapshot signals the same
 * way: in history mode the pack reflects the state as of T, not just "now". Audit
 * integrity and the disclosure text are structural/static, so they stay live.
 */

import {
  fetchAIAct,
  fetchAuditIntegrity,
  fetchCost,
  fetchDisclosure,
  fetchPiiLeak,
  fetchSLO,
  fetchToxicity,
} from "@/lib/api/client";
import { getTemporalContext } from "@/lib/temporal-context";

function downloadJson(name: string, obj: unknown): void {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

/** Snapshot the cockpit signals and download them as a report / evidence pack. */
export async function exportSnapshot(kind: "export" | "evidence"): Promise<void> {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const { asOf, period } = getTemporalContext();
  const at = asOf ?? undefined;
  const scope = { generated_at: new Date().toISOString(), as_of: asOf, period };
  const settle = async <T>(p: Promise<T>) => p.catch(() => null);
  if (kind === "evidence") {
    const [audit, aiAct, disclosure, pii] = await Promise.all([
      settle(fetchAuditIntegrity()),
      settle(fetchAIAct(undefined, at)),
      settle(fetchDisclosure()),
      settle(fetchPiiLeak(undefined, at)),
    ]);
    downloadJson(`tessera-evidence-pack-${stamp}.json`, {
      ...scope,
      kind: "evidence_pack",
      audit_integrity: audit, // structural hash-chain check — always live
      ai_act: aiAct,
      disclosure,
      pii_leak: pii,
    });
    return;
  }
  const [slo, cost, toxicity] = await Promise.all([
    settle(fetchSLO(undefined, at)),
    settle(fetchCost(undefined, at)),
    settle(fetchToxicity(undefined, at)),
  ]);
  downloadJson(`tessera-report-${stamp}.json`, {
    ...scope,
    kind: "overview_report",
    slo,
    cost,
    toxicity,
  });
}
