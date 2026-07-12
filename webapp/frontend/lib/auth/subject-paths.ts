/**
 * Which backend paths return SUBJECT-SCOPED data (audit 2026-07-12, P1 F-4).
 *
 * The EDGE's copy of a rule whose authority lives in the agent: `routes/observability/pii.py`
 * mounts these behind `require_subject_reader`, and re-checks the signed operator assertion
 * on every call. A predicate in the browser's own BFF can only ever be the friendly refusal —
 * the same division of labour as `canMutateCockpit` / `MUTATION_ROLES`.
 *
 * Why the edge needs to know at all: the BFF proxy attaches the service bearer on the
 * caller's behalf, and for GETs it attaches *nothing else*. So without this list a logged-in
 * admin's request would reach the agent with no assertion and be refused — the cockpit would
 * break for the very operators the fix protects. The BFF must authenticate the human, mint
 * the assertion, and only then proxy.
 *
 * Drift between this list and the agent's is fail-safe in both directions and never silent:
 * a path gated in the agent but missing here arrives without an assertion and gets a loud
 * 401; a path listed here but public in the agent merely asks for a login it did not need.
 * Neither leaks. The agent is the one that decides.
 */

/**
 * Backend paths (no `/api` prefix, no query string) whose responses can identify a person:
 * a conversation transcript, a session's turn-by-turn detail, the memory inventory, a
 * subject's erasure footprint, a captured turn's question and answer.
 *
 * Three of these are not obvious and were found by the agent's canary ratchet, not by
 * review: `handoffs` and `context-overflow` hand each turn's question to an analyzer that
 * echoes it back as a row label, and `agent-historique` is a synthetic dashboard with one
 * real `live_conversations` block bolted on.
 */
const SUBJECT_SCOPED_PREFIXES: readonly string[] = [
  "observability/conversations",
  "observability/conversation-messages",
  "observability/session-detail",
  "observability/agent-console/feedback",
  "observability/replays",
  "observability/trace-snapshot",
  "observability/trajectory",
  "observability/provenance",
  "observability/erasure/",
  "observability/memory-inventory",
  "observability/handoffs",
  "observability/context-overflow",
  "observability/agent-historique",
  "memory/",
];

/**
 * Does this proxied path return personal data?
 *
 * Matched on the joined path so a segmented route (`observability/trajectory/<id>`) is caught
 * by its prefix. `observability/erasure/` keeps its trailing slash deliberately: the sibling
 * `observability/erasure-coverage` returns three integers and stays public — a prefix without
 * the slash would lock it and break the public cockpit.
 */
export function isSubjectScopedPath(segments: string[]): boolean {
  const path = segments.join("/");
  return SUBJECT_SCOPED_PREFIXES.some(
    (prefix) => path === prefix || path.startsWith(prefix.endsWith("/") ? prefix : `${prefix}/`),
  );
}
