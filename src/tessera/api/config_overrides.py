"""Governed runtime overrides for operable config knobs (ADR 0030).

Tessera's config truth is frozen per deploy (env-derived settings, git-versioned
files). A **closed registry** of knobs may carry a durable, governed override on
top of that base: today the serving chat model, org-wide
(``llm.chat_model``) or per fleet agent (``llm.chat_model.agent.<agent_id>``).

Three invariants, all from ADR 0030:

* **Closed registry** — an unknown key or an uncatalogued model is refused at
  write time, never stored. There is no generic "override any setting" path.
* **Effective by construction** — the only consumer of this store is the turn
  path itself (``resolve_chat_model_override`` at the routing seam), so a
  stored-but-ignored override cannot exist.
* **Reads fail open to base, writes fail closed** — a turn must never be blocked
  by the override store (the frozen base is always valid), but a write that
  cannot be durably recorded is refused.

The table is materialised at startup in the active env schema (ADR 0014), same
pattern as :mod:`tessera.api.settings_store`.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from psycopg import sql
from psycopg.rows import dict_row

from tessera.retrieval.store import get_pool
from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    "CHAT_MODEL_KEY",
    "KnobError",
    "Override",
    "OverrideNotStoredError",
    "agent_of_key",
    "allowed_chat_models",
    "base_chat_model",
    "delete_override",
    "ensure_overrides_schema",
    "knob_keys",
    "list_overrides",
    "resolve_chat_model_override",
    "set_override",
]

_TABLE: Final = sql.Identifier("config_overrides")

#: The org-wide serving chat model knob.
CHAT_MODEL_KEY: Final[str] = "llm.chat_model"
#: Per-agent knobs are ``llm.chat_model.agent.<agent_id>`` for known fleet agents.
_AGENT_KEY_PREFIX: Final[str] = "llm.chat_model.agent."


class KnobError(ValueError):
    """A refused write: unknown knob, uncatalogued value, or missing reason."""


class OverrideNotStoredError(KeyError):
    """A revert of a knob that holds no override — nothing changed, said loudly.

    Raised instead of returning a bare ``bool`` (the verdict-debt freeze): the
    refusal carries the knob it is about, and "nothing changed" can never be
    mistaken for "change recorded".
    """


@dataclass(frozen=True, slots=True)
class Override:
    """One stored override with its full attribution (ADR 0024: author + reason)."""

    key: str
    value: str
    author: str
    reason: str
    updated_at: datetime


def knob_keys() -> list[str]:
    """The closed registry: every key an override may be written under.

    The org-wide chat model plus one per-agent key per registered fleet agent —
    derived from the real agent registry, never free-typed.
    """
    from tessera.agent.registry import list_agents

    return [CHAT_MODEL_KEY, *(f"{_AGENT_KEY_PREFIX}{a.id}" for a in list_agents())]


def agent_of_key(key: str) -> str | None:
    """The agent id a per-agent knob targets, or ``None`` for the org-wide knob."""
    if key.startswith(_AGENT_KEY_PREFIX):
        return key[len(_AGENT_KEY_PREFIX) :]
    return None


def allowed_chat_models() -> set[str]:
    """Every model id an override may name: catalogued chat models + OpenAI registry.

    The same real sources the catalogue page reads — a value outside this set is
    refused at write time (import deferred to keep module import light).
    """
    from tessera.observability.model_catalogue import _catalogue_models

    settings = get_settings()
    catalogued = {m.model_id for m in _catalogue_models() if m.role == "chat"}
    return catalogued | set(settings.openai.models)


def base_chat_model() -> str:
    """The frozen (env/git) chat model the active profile serves without overrides."""
    settings = get_settings()
    frontier = settings.resolved_llm_profile() is LLMProfile.FRONTIER
    return settings.vertex.chat_model if frontier else settings.ollama.chat_model


async def ensure_overrides_schema() -> None:
    """Materialise ``config_overrides`` in the active env schema at boot (ADR 0014)."""
    pool = get_pool()
    if pool.closed:
        await pool.open()
    create_table = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {table} (
            key        text        PRIMARY KEY,
            value      text        NOT NULL,
            author     text        NOT NULL,
            reason     text        NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        """
    ).format(table=_TABLE)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(create_table)
        await conn.commit()


def _row_to_override(row: dict[str, object]) -> Override:
    return Override(
        key=str(row["key"]),
        value=str(row["value"]),
        author=str(row["author"]),
        reason=str(row["reason"]),
        updated_at=row["updated_at"],  # type: ignore[arg-type]
    )


async def list_overrides() -> list[Override]:
    """Every stored override, in registry order (unknown strays sort last, kept visible)."""
    await ensure_overrides_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT key, value, author, reason, updated_at FROM {table};").format(
                table=_TABLE
            )
        )
        rows = await cur.fetchall()
    order = {key: i for i, key in enumerate(knob_keys())}
    overrides = [_row_to_override(r) for r in rows]
    overrides.sort(key=lambda o: order.get(o.key, len(order)))
    return overrides


async def set_override(key: str, value: str, *, author: str, reason: str) -> Override:
    """Validate against the closed registry and upsert one override, attributed.

    Args:
        key: A key from :func:`knob_keys` — anything else is refused.
        value: A model id from :func:`allowed_chat_models` — anything else is refused.
        author: The verified principal (``actor_of(session).principal``), never
            caller-supplied text.
        reason: The operator's declared reason — mandatory, ADR 0024.

    Returns:
        The stored override, timestamped by the database.

    Raises:
        KnobError: On an unknown key, an uncatalogued value, or a blank reason.
    """
    if key not in knob_keys():
        raise KnobError(f"unknown knob {key!r} — the registry is closed (ADR 0030)")
    if value not in allowed_chat_models():
        raise KnobError(f"model {value!r} is not in the catalogue — refused, never stored")
    if not reason.strip():
        raise KnobError("a governed override carries its reason (ADR 0024) — blank refused")
    await ensure_overrides_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL(
                """
                INSERT INTO {table} (key, value, author, reason, updated_at)
                VALUES (%s, %s, %s, %s, now())
                ON CONFLICT (key) DO UPDATE
                  SET value = EXCLUDED.value, author = EXCLUDED.author,
                      reason = EXCLUDED.reason, updated_at = now()
                RETURNING key, value, author, reason, updated_at;
                """
            ).format(table=_TABLE),
            (key, value, author, reason.strip()),
        )
        row = await cur.fetchone()
        await conn.commit()
    if row is None:  # pragma: no cover — RETURNING on an upsert always yields
        raise KnobError(f"override {key!r} was not stored")
    return _row_to_override(row)


async def delete_override(key: str) -> None:
    """Remove one override so the base serves again (revert).

    Raises:
        OverrideNotStoredError: When the knob held no override — the caller maps
            it to a 404 rather than recording a change that never happened.
    """
    await ensure_overrides_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("DELETE FROM {table} WHERE key = %s;").format(table=_TABLE),
            (key,),
        )
        deleted = cur.rowcount > 0
        await conn.commit()
    if not deleted:
        raise OverrideNotStoredError(key)


def _precedence_keys(agent_id: str | None) -> list[str]:
    """Most-specific first (ADR 0030 §3): the agent's own knob, then the org-wide one."""
    keys = [CHAT_MODEL_KEY]
    if agent_id:
        keys.insert(0, f"{_AGENT_KEY_PREFIX}{agent_id}")
    return keys


async def _winning_override(agent_id: str | None) -> tuple[str, str] | None:
    """``(key, value)`` of the most-specific stored override, or ``None`` (base).

    Shared read for the two resolvers below. **Fails open to base**: a store
    error logs loudly and returns ``None`` — a read is never blocked on this
    store.
    """
    keys = _precedence_keys(agent_id)
    try:
        await ensure_overrides_schema()
        pool = get_pool()
        async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                sql.SQL("SELECT key, value FROM {table} WHERE key = ANY(%s);").format(table=_TABLE),
                (keys,),
            )
            rows = await cur.fetchall()
    except Exception as exc:  # fail open to base — never block a turn on this store
        sys.stderr.write(f"tessera.config_overrides: read failed, serving base: {exc}\n")
        return None
    by_key = {str(r["key"]): str(r["value"]) for r in rows}
    for key in keys:
        if key in by_key:
            return key, by_key[key]
    return None


async def resolve_chat_model_override(agent_id: str | None) -> str | None:
    """The durable override for this turn's agent, or ``None`` to serve the base.

    Precedence below the per-turn picker (ADR 0030 §3): per-agent override, then
    the org-wide override, then ``None`` (the frozen base serves). Fails open to
    base (see :func:`_winning_override`).
    """
    winner = await _winning_override(agent_id)
    return winner[1] if winner else None


async def resolve_chat_model_with_provenance(
    agent_id: str | None,
) -> tuple[str, Literal["agent", "org", "base"]]:
    """The model that would serve ``agent_id`` and WHERE it comes from.

    ``(model, "agent")`` for a per-agent override, ``(model, "org")`` for the
    org-wide one, ``(base, "base")`` otherwise — the same precedence the chat
    seam applies (ADR 0030 §3), exposed so read surfaces (e.g. the agent's
    Configurations page) can display the effective model WITH its provenance
    instead of the frozen base. Fails open to ``(base, "base")``.
    """
    winner = await _winning_override(agent_id)
    if winner is None:
        return base_chat_model(), "base"
    key, value = winner
    return value, "org" if key == CHAT_MODEL_KEY else "agent"
