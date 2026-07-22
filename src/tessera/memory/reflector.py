"""Post-turn memory formation — the cold-path write of Tier 2 (ADR 0007).

After a turn completes (and only after the guard and reviewer have passed), the
reflector asks a cheap model to extract durable facts about the customer,
screens each candidate through :mod:`tessera.memory.governance` (consent,
anti-poisoning, PII minimisation), and upserts the survivors into the long-term
store. It runs as a background task, never on the user's hot path, and swallows
its own failures.

The same flow powers the nightly consolidation job, which simply calls
:func:`form_memories` over the previous day's turns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tessera.authz import Actor
from tessera.guard.redaction import mask_pan
from tessera.memory import governance
from tessera.memory.entities import extract_entities
from tessera.memory.persistent import upsert_memory

if TYPE_CHECKING:
    from tessera.memory.protocol import MemoryScope, TurnRecord

__all__ = ["form_memories"]

# Hard cap on facts persisted per turn — bounds cost and prevents a single
# adversarial turn from flooding the store.
_MAX_FACTS_PER_TURN: Final[int] = 5

#: The reflector is the agent forming its own memories after a turn — a cold-path write no
#: human asked for. Named, so a `memory.write` the SYSTEM performed can never be mistaken in
#: the trail for a rectification an operator performed (Art. 16), which is a human act and
#: carries a human's name.
_REFLECTOR_ACTOR: Final = Actor.system("memory-reflector")

_DEFAULT_EXTRACT_INSTRUCTION: Final[str] = (
    "From the exchange below, extract at most five durable facts worth "
    "remembering about this customer for future conversations (preferences, "
    "products held, stable circumstances). One short fact per line, no "
    "numbering. Do not invent anything. If there is nothing durable, reply with "
    "exactly NONE."
)


async def _extract_facts(turn: TurnRecord) -> list[str]:
    """Ask the cheap model for durable customer facts; return a clean list."""
    from tessera.agent.reporter import load_prompts
    from tessera.llm.router import ChatMessage, get_summary_backend

    prompts = load_prompts(turn.language)
    instruction = prompts.get("memory_extract", _DEFAULT_EXTRACT_INSTRUCTION)
    # Input-leg PAN mask (pii-input-redaction, cold-path model call): the
    # fact-extraction model never sees a clear card number; governance still
    # screens/minimises every resulting candidate downstream.
    exchange = mask_pan(f"Customer: {turn.user_input}\nAgent: {turn.final_response}").text
    response = await get_summary_backend().chat(
        [
            ChatMessage(role="system", content=instruction),
            ChatMessage(role="user", content=exchange),
        ],
        temperature=0.0,
    )
    facts: list[str] = []
    for raw in response.content.splitlines():
        line = raw.strip().lstrip("-•* ").strip()
        if not line or line.upper() == "NONE":
            continue
        facts.append(line)
        if len(facts) >= _MAX_FACTS_PER_TURN:
            break
    return facts


async def form_memories(scope: MemoryScope, turn: TurnRecord) -> None:
    """Extract, screen, and upsert durable memories for a finished turn."""
    if not await governance.consent_allows(scope.subject_id):
        governance.audit_memory(
            action="memory.write",
            subject_id=scope.subject_id,
            decision="deny",
            rationale="no long-term retention consent for subject",
            actor=_REFLECTOR_ACTOR,
        )
        return

    facts = await _extract_facts(turn)
    written = 0
    for fact in facts:
        screened = governance.screen_memory(fact, actor=_REFLECTOR_ACTOR)
        if not screened.allowed:
            governance.audit_memory(
                action="memory.write",
                subject_id=scope.subject_id,
                decision="deny",
                rationale="candidate rejected by screen (poisoning/PII)",
                actor=_REFLECTOR_ACTOR,
            )
            continue
        await upsert_memory(
            subject_id=scope.subject_id,
            kind="semantic",
            text=screened.text,
            entities=extract_entities(screened.text),
        )
        written += 1

    governance.audit_memory(
        action="memory.write",
        subject_id=scope.subject_id,
        decision="allow" if written else "transform",
        rationale=f"persisted {written}/{len(facts)} candidate fact(s)",
        actor=_REFLECTOR_ACTOR,
    )
