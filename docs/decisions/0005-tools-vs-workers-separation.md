# 5. Separation of tools and workers in the agent layer

Date: 2026-05-27

## Status

Accepted

## Context

The Tessera agent is built on LangGraph. Its execution is described as a state graph in which nodes consume and produce a shared state, and edges are conditional transitions between nodes. The agent also exposes a set of callable functions to the underlying language model via the model's native function-calling or tool-use interface — these are the means by which the LLM requests concrete actions like fetching an account balance, searching the transaction history, or blocking a card.

Both concepts are colloquially called "tools" in the agent literature, and both are sometimes called "agents" or "workers" in the multi-agent literature. The terminology collapses two distinct objects into one bucket, and this collapse leads to a recurring class of design mistake: writing a function that is simultaneously a LangGraph node *and* an LLM-callable tool. The function ends up entangling orchestration concerns (state transition, retry, error handling, escalation routing) with action concerns (input validation against an LLM-provided schema, side effect on an external system, structured output back to the model). The result is hard to test in isolation, hard to reuse across graph topologies, and hard to swap out when the orchestrator changes.

The two objects deserve different names, different locations in the codebase, and different testing strategies. A *worker* in Tessera is a LangGraph node — a Python callable whose input and output are the agent state, whose responsibility is orchestration, and whose only LLM interaction is to send prompts and receive completions or tool-call requests. A *tool* in Tessera is an LLM-callable function — a Python callable whose input is a typed argument structure declared via Pydantic, whose responsibility is to perform one concrete action on the world (read or write), and whose output is a typed response that the LLM consumes via the tool-use protocol.

A worker may call zero or more tools during its node execution; a worker may exist that calls no tools at all (for example, a pure-classification router worker). A tool exists independently of any particular worker and can be invoked by multiple workers. Tools never know about agent state directly; they receive only their declared arguments. Workers never know about tool-call wire formats; they delegate to the tool registry.

## Decision

The agent code is split along this distinction. LangGraph nodes live under `src/tessera/agent/workers/` and are named by their role in the graph (`router.py` at the agent root, `planner.py` likewise, and `workers/{product_lookup,regulation_lookup,account_lookup,simulator,escalation}.py` for the per-domain workers). LLM-callable tools live under `src/tessera/agent/tools/` and are named by the action they perform (`account_balance.py`, `card_block.py`, `transaction_search.py`, `loan_simulate.py`, `ticket_escalate.py`).

Workers import tools from the tool registry; tools never import workers. Tools never read or write the LangGraph state object; they receive only their declared Pydantic arguments and return only typed responses. The tool registry is assembled at agent startup and exposed to the LLM via LangGraph's tool-binding mechanism.

Unit tests target tools and workers separately. Tool tests exercise the action in isolation against a fake of the external system. Worker tests exercise the node logic against a fake LLM that returns deterministic tool-call sequences. Integration tests exercise the assembled graph end to end.

## Consequences

Tools are reusable across worker topologies; if the orchestrator changes (LangGraph to a hypothetical successor, or a vendor-specific orchestrator on a partner deployment), tools port unchanged. Workers are testable without spinning up the real LLM. The separation makes the agent legible to a reader who has never seen Tessera before: they can read `tools/` to understand what the agent *can do*, and `workers/` to understand *how it decides what to do next*.

The cost is one additional directory and one mental distinction to maintain. Pull requests that conflate the two are rejected with a pointer to this ADR. New contributors who do not yet have the distinction internalized are guided by the file layout itself — placing a function under `workers/` when it should be a tool, or vice versa, surfaces in review the moment the file path is read.

## Amendment 1 (2026-08-03) — the binding was never wired

The decision above stands. Its justification, in one sentence, did not.

"The tool registry is assembled at agent startup and exposed to the LLM via LangGraph's
tool-binding mechanism" describes something that has never existed in this repository. There
is no `bind_tools`, no `tool_choice`, no `ToolNode` and no `tools=` anywhere in `src/`; the
audit of 2026-08-03 looked for all four and found only this ADR, three docstrings and
`CLAUDE.md` repeating the claim to one another. What the code actually does is this: a worker
decides, in Python, that a tool is needed, builds its arguments in Python, and calls it
through `guarded_invoke`. The model never emits a tool call and never sees a tool schema.

Two honest ways out were available.

**Wire the function-calling.** The five Pydantic input schemas are already stable contracts,
`guarded_invoke` applies unchanged, and LangGraph supports it directly. It was not taken, and
the reason is not effort: letting the model choose the tool changes what the agent *does*, so
every number measured against the current agent — the null floor, the discrimination
classification, the 63-case catalogue's pass rates — would describe a different system. That
is a deliberate product change with its own evaluation campaign, not a correction.

**Say what is true.** Taken. A Tessera *tool* is a **typed action target invoked by a worker**:
a Python callable with a Pydantic-validated input schema, a frozen output type, no access to
`AgentState`, and no knowledge of any wire format. A *worker* is a LangGraph node that decides
which action to take and calls it.

Every reason the separation was adopted survives the correction intact, because none of them
depended on the model doing the choosing:

* tools port unchanged if the orchestrator is replaced — still true, and *more* true when the
  caller is ordinary Python;
* workers are testable without a real LLM — still true;
* a reader learns what the agent *can do* from `tools/` and *how it decides* from `workers/` —
  still true;
* the guard sits at exactly one chokepoint — still true, and it is the load-bearing one.

What changes is the sentence in §Decision about tool-binding, and the "fake LLM that returns
deterministic tool-call sequences" in §Decision's testing paragraph: worker tests drive the
node directly, because there is no tool-call sequence to fake.

If the function-calling is wired later, this amendment is the record of what it would cost:
a fresh null floor, a fresh discrimination measurement, and a catalogue re-run — not a
refactor.
