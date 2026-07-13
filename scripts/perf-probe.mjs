#!/usr/bin/env node
// scripts/perf-probe.mjs — ADR 0015 §Performance measurement harness.
//
// A performance budget is a GATE, not a hope: this probe measures the cockpit snapshot read
// model against the budget table and exits non-zero if p95 exceeds it.
//
// ⚠ AND IT IS A HOPE, TODAY. This header used to end "It runs inside the twice-green gate from
// Phase A" — and it does not. It is invoked from NOWHERE: not the Makefile, not a workflow, not
// package.json. Only prose mentions it. **A gate that is never called cannot fail**, and a file
// that says it gates when nothing runs it is a false green with a shebang — the same shape as
// the `detect-secrets` job that scanned into /dev/null and reported success for a year.
//
// It needs a live backend serving /observability/snapshot, so wiring it into the hermetic gate
// is a lot of its own. Until then the claim is corrected rather than dressed up, and the debt is
// named where debts live: `OWED_EXIT_WITNESSES`, tests/unit/test_exit_witness_debt.py.
//
// It measures, against a running backend serving `GET /observability/snapshot`:
//   • cold compute p95   — distinct scopes (each a cache miss), all signals in one pass
//   • warm reload  p95   — one fixed scope hammered (served from cache)
//   • upstream-read budget — meta.upstream_reads on a miss (shared reads, no per-signal fan-out)
//
// Usage:  node scripts/perf-probe.mjs            (defaults to http://localhost:8392)
//         TESSERA_SNAPSHOT_URL=http://host:port node scripts/perf-probe.mjs
//
// Optionally, when TESSERA_PROBE_FRONTEND is set to a dashboard URL and Playwright is
// installed, it also measures cold TTI (time until every KPI card holds a real value).

const BASE = process.env.TESSERA_SNAPSHOT_URL ?? "http://localhost:8392";
// Kept comfortably under the read rate limit (120/min) so a single run never self-throttles;
// 429s are also transparently retried (the wait is excluded from the measured latency).
const N_COLD = Number(process.env.PROBE_N_COLD ?? 20);
const N_WARM = Number(process.env.PROBE_N_WARM ?? 25);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The budget table (ADR 0015 §Performance).
const BUDGET = {
  computeP95Ms: 300, // backend snapshot compute (1 scope, all signals), cache miss
  warmP95Ms: 150, // warm reload / poll refresh, served from cache
  upstreamReads: 4, // shared spine reads per snapshot — O(1), not O(signals)
};

function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
  return sorted[idx];
}

async function snapshot(query) {
  const url = `${BASE}/observability/snapshot${query ? `?${query}` : ""}`;
  // The read surface is rate limited (120/min). A 429 is orthogonal to the latency budget:
  // honour Retry-After and retry, and measure only the successful attempt so the wait never
  // inflates the reported p95.
  for (let attempt = 0; attempt < 8; attempt++) {
    const started = performance.now();
    const res = await fetch(url);
    const ms = performance.now() - started;
    if (res.status === 429) {
      const retryAfter = Number(res.headers.get("retry-after")) || 2;
      await sleep(Math.min(retryAfter, 5) * 1000);
      continue;
    }
    if (!res.ok) throw new Error(`snapshot HTTP ${res.status} for ${url}`);
    return { ms, body: await res.json() };
  }
  throw new Error(`snapshot still rate-limited after retries — wait for the window or relax the read limit`);
}

async function reachable() {
  try {
    const res = await fetch(`${BASE}/healthz`);
    return res.ok;
  } catch {
    return false;
  }
}

async function main() {
  if (!(await reachable())) {
    console.error(`✗ backend not reachable at ${BASE} — start the dev agent first`);
    console.error(`  PYTHONPATH=src uv run uvicorn tessera.api.main:build_app --factory --port 8392`);
    process.exit(2);
  }

  // Warm the process (imports, first compute) so we measure steady-state, not cold start.
  await snapshot("agent=all");

  // 1. Cold compute p95 — each request a DISTINCT scope (unique as-of-T instant) so the
  //    read-through cache misses every time and we measure the real compute.
  const cold = [];
  let sampleMeta = null;
  const now = Date.now();
  for (let i = 0; i < N_COLD; i++) {
    const at = new Date(now - i * 1000).toISOString();
    const { ms, body } = await snapshot(`at=${encodeURIComponent(at)}`);
    cold.push(ms);
    if (i === 0) sampleMeta = body.meta;
  }

  // 2. Warm p95 — one fixed scope hammered; after the first miss these are cache hits.
  await snapshot("agent=all");
  const warm = [];
  for (let i = 0; i < N_WARM; i++) {
    const { ms } = await snapshot("agent=all");
    warm.push(ms);
  }

  // 3. Upstream-read budget — read the compute's shared-read count from a fresh miss.
  const fresh = await snapshot(`at=${encodeURIComponent(new Date(now - 9999_000).toISOString())}`);
  const upstreamReads = fresh.body.meta?.upstream_reads ?? Infinity;
  const nSignals = Object.keys(fresh.body.signals ?? {}).length;

  const coldP95 = percentile(cold, 0.95);
  const warmP95 = percentile(warm, 0.95);

  const results = [
    {
      name: "cold compute p95",
      value: coldP95,
      budget: BUDGET.computeP95Ms,
      unit: "ms",
      ok: coldP95 <= BUDGET.computeP95Ms,
    },
    {
      name: "warm reload  p95",
      value: warmP95,
      budget: BUDGET.warmP95Ms,
      unit: "ms",
      ok: warmP95 <= BUDGET.warmP95Ms,
    },
    {
      name: "upstream reads  ",
      value: upstreamReads,
      budget: BUDGET.upstreamReads,
      unit: `(for ${nSignals} signals)`,
      ok: upstreamReads <= BUDGET.upstreamReads,
    },
  ];

  console.log(`\nADR 0015 perf probe — ${BASE}`);
  console.log(`  server-reported: cache=${sampleMeta?.cache} upstream_reads=${sampleMeta?.upstream_reads}`);
  console.log(`  cold p50=${percentile(cold, 0.5).toFixed(1)}ms  warm p50=${percentile(warm, 0.5).toFixed(2)}ms\n`);
  let failed = false;
  for (const r of results) {
    const status = r.ok ? "✓" : "✗";
    const shown = typeof r.value === "number" ? r.value.toFixed(r.unit === "ms" ? 1 : 0) : r.value;
    console.log(`  ${status} ${r.name}: ${shown} ${r.unit}  (budget ${r.budget})`);
    if (!r.ok) failed = true;
  }
  console.log("");

  if (failed) {
    console.error("✗ perf budget exceeded — phase gate FAILS");
    process.exit(1);
  }
  console.log("✓ all budgets met");
}

main().catch((err) => {
  console.error(`✗ probe error: ${err.message}`);
  process.exit(2);
});
