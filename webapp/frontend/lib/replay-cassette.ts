// XT-01 (registre des rails) — build the C3 execution tree of a captured
// cassette from its persisted S2 record. Pure projection: every span is a node
// the turn really timed (`latency_ms`), positioned only when the real start
// offsets were captured (`node_starts`); every child is a tool call the worker
// itself recorded with its parent node. Nothing is fabricated — a bundle
// captured before the S2 fields existed renders unpositioned or empty, and an
// unpositioned trace has no total (summing durations would misstate overlap).

import type { ReplayBundle } from "@/lib/api/schemas";

export type CassetteTool = { name: string; succeeded: boolean; duration_ms: number };

export type CassetteSpan = {
  key: string;
  /** Real measured start offset in ms, or null when the capture predates offsets. */
  start_ms: number | null;
  duration_ms: number;
  /** Real children: tool calls this node recorded at invocation time. */
  tools: CassetteTool[];
};

export type CassetteTrace = {
  spans: CassetteSpan[];
  /** Real wall-clock end (max start+duration, + streamed reporter), or null unpositioned. */
  total_ms: number | null;
  /** True when the bundle captured real start offsets (post-S2 capture). */
  positioned: boolean;
  /** Tool calls whose recorded node was not among the timed spans ("" = unattributed). */
  orphan_tools: CassetteTool[];
};

function toolRows(bundle: ReplayBundle): { node: string; tool: CassetteTool }[] {
  return (bundle.tool_calls ?? []).map((call) => ({
    node: call.node,
    tool: { name: call.name, succeeded: call.succeeded, duration_ms: call.duration_ms },
  }));
}

/** The C3 trace of a cassette, or null when the bundle recorded no execution shape. */
export function buildCassetteTrace(bundle: ReplayBundle): CassetteTrace | null {
  const timings = bundle.latency_ms ?? null;
  const tools = toolRows(bundle);
  if ((timings === null || Object.keys(timings).length === 0) && tools.length === 0) {
    return null;
  }

  const starts = bundle.node_starts ?? null;
  const positioned = starts !== null && Object.keys(starts ?? {}).length > 0;
  const byNode = new Map<string, CassetteTool[]>();
  for (const { node, tool } of tools) {
    const bucket = byNode.get(node) ?? [];
    bucket.push(tool);
    byNode.set(node, bucket);
  }

  const spans: CassetteSpan[] = Object.entries(timings ?? {}).map(([key, duration]) => ({
    key,
    start_ms: positioned ? (starts?.[key] ?? 0) : null,
    duration_ms: duration,
    tools: byNode.get(key) ?? [],
  }));
  if (positioned) {
    spans.sort((a, b) => (a.start_ms ?? 0) - (b.start_ms ?? 0) || a.key.localeCompare(b.key));
  }

  let total: number | null = positioned
    ? spans.reduce((acc, s) => Math.max(acc, (s.start_ms ?? 0) + s.duration_ms), 0)
    : null;

  // The reporter streams after the timed graph phase (mirror of the backend
  // trace builder): append its measured wall time as the final span, starting
  // where the timed phase ends when the trace is positioned.
  const reporterMs = bundle.reporter_ms ?? null;
  if (reporterMs !== null && reporterMs > 0 && !(timings && "reporter" in timings)) {
    spans.push({
      key: "reporter",
      start_ms: positioned ? total : null,
      duration_ms: reporterMs,
      tools: byNode.get("reporter") ?? [],
    });
    if (total !== null) total += reporterMs;
  }

  const claimed = new Set(spans.map((s) => s.key));
  const orphans = tools.filter(({ node }) => !claimed.has(node)).map(({ tool }) => tool);

  return { spans, total_ms: total, positioned, orphan_tools: orphans };
}
