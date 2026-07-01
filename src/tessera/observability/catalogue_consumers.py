"""CONFIGURER "used-by" — which agents consume each catalogue building block.

This is the **inverse** of the AGENT instance binding. An agent (`agents.yaml`)
BINDS reusable blocks from the CONFIGURER catalogue (model, guardrails, knowledge,
prompts, tools, eval set); here we invert that mapping so each catalogue item shows
**which agents consume it**. Changing a shared definition therefore has a known
blast radius: the consuming agents must be **re-validated** (re-gated), so we attach
each consumer's current release verdict (define → consumers → re-validate).

All data is real: derived from the governed registry bindings + each agent's
policy-correct eval-gate verdict (:mod:`agent_release`). Nothing is fabricated.
"""

from __future__ import annotations

from tessera.observability.agent_release import agent_release_state

__all__ = ["KINDS", "catalogue_consumers"]

# Catalogue kinds we can invert from the registry bindings, with the CONFIGURER
# route slug each maps to (so the UI can deep-link "Voir la définition").
KINDS: dict[str, str] = {
    "model": "modeles",
    "guardrails": "garde-fous",
    "knowledge": "sources-memoire",
    "prompts": "parametres",
    "tools": "integrations",
    "eval_set": "parametres",
}


def _agents() -> list[object]:
    try:
        from tessera.agent.registry import list_agents

        return list(list_agents())
    except (OSError, ValueError):
        return []


def _items_for(agent: object, kind: str) -> list[str]:
    """Return the catalogue item(s) of ``kind`` bound by ``agent`` (str or tuple)."""
    value = getattr(agent, kind, None)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, tuple | list):
        return [str(v) for v in value]
    return []


def catalogue_consumers(
    kind: str, *, agent_scope: str = "all", lang: str = "fr"
) -> dict[str, object]:
    """Return, for one catalogue ``kind``, each item and its consumer agents.

    Args:
        kind: a key of :data:`KINDS` (model, guardrails, knowledge, …).
        agent_scope: when set to a concrete agent id, only items consumed by that
            agent are returned (the global filter ?agent=); ``"all"`` returns every
            item used across the fleet.
        lang: UI language (fr / de / en) for each consumer's release verdict label.

    Returns:
        ``{"kind", "route", "items": [{item, consumers: [{agent_id, name, verdict…}]}]}``.
    """
    if kind not in KINDS:
        msg = f"unknown catalogue kind: {kind!r}"
        raise ValueError(msg)

    agents = _agents()
    by_item: dict[str, list[object]] = {}
    for agent in agents:
        for item in _items_for(agent, kind):
            by_item.setdefault(item, []).append(agent)

    # Cache the (expensive) gate verdict per agent across all items.
    verdicts: dict[str, dict[str, object]] = {}

    def verdict_of(agent_id: str) -> dict[str, object]:
        if agent_id not in verdicts:
            verdicts[agent_id] = agent_release_state(agent_id, lang).as_dict()
        return verdicts[agent_id]

    items: list[dict[str, object]] = []
    for item in sorted(by_item):
        consumers = [
            {
                "agent_id": str(getattr(a, "id", "")),
                "name": str(getattr(a, "name", getattr(a, "id", ""))),
                "release": verdict_of(str(getattr(a, "id", ""))),
            }
            for a in by_item[item]
        ]
        if agent_scope != "all":
            consumers = [c for c in consumers if c["agent_id"] == agent_scope]
            if not consumers:
                continue
        items.append(
            {
                "item": item,
                "consumer_count": len(consumers),
                # A change re-gates every consumer not currently passing-clean.
                "regate_count": sum(1 for c in consumers if not _passing(c["release"])),
                "consumers": consumers,
            }
        )

    return {"kind": kind, "route": KINDS[kind], "items": items}


def _passing(release: object) -> bool:
    if not isinstance(release, dict):
        return False
    return bool(release.get("available")) and bool(release.get("passed"))
