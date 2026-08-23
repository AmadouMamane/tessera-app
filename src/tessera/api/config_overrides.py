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
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Final, Literal

from psycopg import sql
from psycopg.rows import dict_row

from tessera.retrieval.store import get_pool
from tessera.settings import LLMProfile, get_settings

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    "BUDGET_OVERRUN_BEHAVIOURS",
    "BUDGET_OVERRUN_KEY",
    "CHAT_MODEL_KEY",
    "DAILY_BUDGET_KEY",
    "UNDERSTANDING_MODES",
    "UNDERSTANDING_MODE_KEY",
    "UNDERSTANDING_THRESHOLD_KEY",
    "UNDERSTANDING_TIMEOUT_KEY",
    "BudgetPolicy",
    "KnobError",
    "Override",
    "OverrideNotStoredError",
    "UnderstandingConfig",
    "agent_of_key",
    "allowed_chat_models",
    "base_chat_model",
    "delete_override",
    "ensure_overrides_schema",
    "knob_keys",
    "list_overrides",
    "resolve_budget_policy",
    "resolve_chat_model_override",
    "resolve_understanding_config",
    "set_override",
]

_TABLE: Final = sql.Identifier("config_overrides")

#: The org-wide serving chat model knob.
CHAT_MODEL_KEY: Final[str] = "llm.chat_model"
#: Per-agent knobs are ``llm.chat_model.agent.<agent_id>`` for known fleet agents.
_AGENT_KEY_PREFIX: Final[str] = "llm.chat_model.agent."
#: ADR 0034 — the org-wide daily LLM budget ceiling (EUR, positive decimal).
DAILY_BUDGET_KEY: Final[str] = "llm.budget.daily_eur"
#: ADR 0034 — the declared behaviour at overrun.
BUDGET_OVERRUN_KEY: Final[str] = "llm.budget.overrun"
BUDGET_OVERRUN_BEHAVIOURS: Final[tuple[str, ...]] = ("block", "local_fallback")
#: ADR 0053 §5 — recouvrement layer-1 deployment mode. The regex→LLM switch is a
#: journalled governed act with a named author and reason, never a code edit.
UNDERSTANDING_MODE_KEY: Final[str] = "recouvrement.understanding.mode"
UNDERSTANDING_MODES: Final[tuple[str, ...]] = ("shadow", "active")
#: ADR 0053 §6 — the calibrated confidence floor below which layer 1 falls back to the
#: regex ladder. The RULE is engraved; the NUMBER comes from a bench run (store it with
#: the run in the reason). ``active`` cannot be stored without it.
UNDERSTANDING_THRESHOLD_KEY: Final[str] = "recouvrement.understanding.confidence_threshold"
#: ADR 0053 — the per-call bound on the layer-1 model, seconds (measured, then governed).
UNDERSTANDING_TIMEOUT_KEY: Final[str] = "recouvrement.understanding.timeout_s"


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
    derived from the real agent registry, never free-typed — plus the two
    org-wide budget knobs (ADR 0034).
    """
    from tessera.agent.registry import list_agents

    return [
        CHAT_MODEL_KEY,
        *(f"{_AGENT_KEY_PREFIX}{a.id}" for a in list_agents()),
        DAILY_BUDGET_KEY,
        BUDGET_OVERRUN_KEY,
        UNDERSTANDING_MODE_KEY,
        UNDERSTANDING_THRESHOLD_KEY,
        UNDERSTANDING_TIMEOUT_KEY,
    ]


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


def _validated_value(key: str, value: str) -> str:
    """Validate ``value`` against ITS knob family's value space (ADR 0034).

    Each family owns its value space — chat-model knobs take a catalogued
    model id, the daily ceiling takes a positive decimal (normalised), the
    overrun knob takes one of the declared behaviours. Anything else is
    refused, never stored.
    """
    if key == DAILY_BUDGET_KEY:
        try:
            ceiling = Decimal(value)
        except InvalidOperation as exc:
            raise KnobError(f"{value!r} is not a decimal EUR amount — refused") from exc
        if not ceiling.is_finite() or ceiling <= 0:
            raise KnobError(f"the daily ceiling must be a positive EUR amount; got {value!r}")
        return str(ceiling)
    if key == BUDGET_OVERRUN_KEY:
        if value not in BUDGET_OVERRUN_BEHAVIOURS:
            raise KnobError(
                f"overrun behaviour {value!r} is not one of {BUDGET_OVERRUN_BEHAVIOURS} — refused"
            )
        return value
    understood = _validated_understanding_value(key, value)
    if understood is not None:
        return understood
    if value not in allowed_chat_models():
        raise KnobError(f"model {value!r} is not in the catalogue — refused, never stored")
    return value


def _validated_understanding_value(key: str, value: str) -> str | None:
    """Validate an ADR 0053 understanding-knob value, or ``None`` for other families."""
    if key == UNDERSTANDING_MODE_KEY:
        if value not in UNDERSTANDING_MODES:
            raise KnobError(
                f"understanding mode {value!r} is not one of {UNDERSTANDING_MODES} — refused"
            )
        return value
    if key == UNDERSTANDING_THRESHOLD_KEY:
        try:
            threshold = Decimal(value)
        except InvalidOperation as exc:
            raise KnobError(f"{value!r} is not a decimal confidence threshold — refused") from exc
        if not threshold.is_finite() or not Decimal(0) <= threshold <= Decimal(1):
            raise KnobError(f"the confidence threshold lives in [0, 1]; got {value!r}")
        return str(threshold)
    if key == UNDERSTANDING_TIMEOUT_KEY:
        try:
            timeout_s = Decimal(value)
        except InvalidOperation as exc:
            raise KnobError(f"{value!r} is not a decimal timeout in seconds — refused") from exc
        if not timeout_s.is_finite() or not Decimal(0) < timeout_s <= Decimal(60):
            raise KnobError(f"the understanding timeout lives in (0, 60] seconds; got {value!r}")
        return str(timeout_s)
    return None


def _forget_cached_ceiling() -> None:
    """Drop the ceiling cache after any override write (ADR 0034).

    Placed in the STORE, not in the two route handlers: a third writer added later would
    otherwise leave an operator's new ceiling unenforced for a TTL without anyone noticing.
    Invalidating on a model-knob write too is deliberate — one wasted read within 30 s is
    cheaper than a rule about which keys matter, which is the kind of rule that goes stale.
    Imported lazily: :mod:`tessera.llm.ceiling` reads this module back.
    """
    from tessera.llm.ceiling import invalidate_policy_cache

    invalidate_policy_cache()
    _forget_cached_understanding()


async def set_override(key: str, value: str, *, author: str, reason: str) -> Override:
    """Validate against the closed registry and upsert one override, attributed.

    Args:
        key: A key from :func:`knob_keys` — anything else is refused.
        value: A value from the KEY's own value space (catalogued model id,
            positive decimal ceiling, declared overrun behaviour) — anything
            else is refused.
        author: The verified principal (``actor_of(session).principal``), never
            caller-supplied text.
        reason: The operator's declared reason — mandatory, ADR 0024.

    Returns:
        The stored override, timestamped by the database.

    Raises:
        KnobError: On an unknown key, a value outside its family's space, or a
            blank reason.
    """
    if key not in knob_keys():
        raise KnobError(f"unknown knob {key!r} — the registry is closed (ADR 0030)")
    value = _validated_value(key, value)
    if not reason.strip():
        raise KnobError("a governed override carries its reason (ADR 0024) — blank refused")
    # ADR 0053 §6: the rule is engraved, the number is measured — an active layer 1
    # with no calibrated threshold is an illegal state, made unrepresentable in the
    # store rather than patched over at read time.
    if (
        key == UNDERSTANDING_MODE_KEY
        and value == "active"
        and await _stored_value(UNDERSTANDING_THRESHOLD_KEY) is None
    ):
        raise KnobError(
            "active understanding requires a stored confidence threshold first — "
            "calibrate on the bench (eval.intent_bench threshold sweep), store "
            f"{UNDERSTANDING_THRESHOLD_KEY!r} citing the run, then flip (ADR 0053 §6)"
        )
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
    _forget_cached_ceiling()
    return _row_to_override(row)


async def delete_override(key: str) -> None:
    """Remove one override so the base serves again (revert).

    Raises:
        OverrideNotStoredError: When the knob held no override — the caller maps
            it to a 404 rather than recording a change that never happened.
        KnobError: When removing this override would leave the store in an
            illegal state (the calibrated threshold under an active layer 1).
    """
    # The write guard's mirror: deleting the threshold under an ACTIVE layer 1 would
    # recreate the illegal state sideways. Flip the mode back to shadow first.
    if (
        key == UNDERSTANDING_THRESHOLD_KEY
        and await _stored_value(UNDERSTANDING_MODE_KEY) == "active"
    ):
        raise KnobError(
            "the confidence threshold cannot be removed while understanding mode is "
            "'active' — set the mode back to 'shadow' first (ADR 0053 §6)"
        )
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
    _forget_cached_ceiling()


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


@dataclass(frozen=True, slots=True)
class BudgetPolicy:
    """The org's daily LLM budget ceiling and its declared overrun behaviour (ADR 0034)."""

    daily_eur: Decimal
    overrun: Literal["block", "local_fallback"]


async def resolve_budget_policy() -> BudgetPolicy | None:
    """The stored budget ceiling, or ``None`` when no ceiling is set (ADR 0034).

    ``None`` is the historical truth — no breaker. **Fails open to no ceiling**
    with a loud log: the frozen deploy without this feature is the known-good
    state, and a turn is never blocked because the override store is down. An
    unset or invalid overrun value resolves to ``block`` — a ceiling someone
    set means *stop spending*.
    """
    try:
        await ensure_overrides_schema()
        pool = get_pool()
        async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                sql.SQL("SELECT key, value FROM {table} WHERE key = ANY(%s);").format(table=_TABLE),
                ([DAILY_BUDGET_KEY, BUDGET_OVERRUN_KEY],),
            )
            rows = await cur.fetchall()
    except Exception as exc:  # fail open to "no ceiling" — never block a turn on this store
        sys.stderr.write(f"tessera.config_overrides: budget read failed, no ceiling: {exc}\n")
        return None
    by_key = {str(r["key"]): str(r["value"]) for r in rows}
    raw_ceiling = by_key.get(DAILY_BUDGET_KEY)
    if raw_ceiling is None:
        return None
    try:
        ceiling = Decimal(raw_ceiling)
    except InvalidOperation:
        sys.stderr.write(
            f"tessera.config_overrides: stored ceiling {raw_ceiling!r} is not a decimal — ignored\n"
        )
        return None
    overrun_raw = by_key.get(BUDGET_OVERRUN_KEY)
    overrun: Literal["block", "local_fallback"] = (
        "local_fallback" if overrun_raw == "local_fallback" else "block"
    )
    return BudgetPolicy(daily_eur=ceiling, overrun=overrun)


async def _stored_value(key: str) -> str | None:
    """The stored override value for ``key``, or ``None`` when none is stored.

    Used by the understanding write/delete guards. Unlike the read resolvers it
    does NOT fail open: a guard that cannot see must refuse rather than allow
    (ADR 0026), so a store error propagates and the governed write is refused.
    """
    await ensure_overrides_schema()
    pool = get_pool()
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT value FROM {table} WHERE key = %s;").format(table=_TABLE),
            (key,),
        )
        row = await cur.fetchone()
    return str(row["value"]) if row else None


@dataclass(frozen=True, slots=True)
class UnderstandingConfig:
    """The governed layer-1 deployment state recouvrement serves under (ADR 0053)."""

    mode: Literal["shadow", "active"]
    threshold: float | None
    timeout_s: float


#: How long a read of the understanding knobs stays good (the ADR 0034 ceiling pattern:
#: an operator's flip takes effect within a page refresh, and the hot path does not pay
#: a Postgres read per turn for a knob that changes a few times a year).
_UNDERSTANDING_TTL_SECONDS: Final[float] = 30.0
_understanding_cache: tuple[float, UnderstandingConfig] | None = None


def _forget_cached_understanding() -> None:
    """Drop the understanding-config cache; called from the same write path as the ceiling's."""
    global _understanding_cache
    _understanding_cache = None


async def resolve_understanding_config() -> UnderstandingConfig:
    """The layer-1 mode / threshold / timeout this turn serves under (ADR 0053 §5-§6).

    Cached for :data:`_UNDERSTANDING_TTL_SECONDS`; every override write or delete
    drops the cache (same seam as the ceiling's). Fails open to SHADOW, loudly:
    shadow is the known-good state and a turn is never blocked on this store.
    ``active`` with no stored threshold cannot be written (the write guard) nor
    left behind by a delete (its mirror); if a legacy or hand-edited store
    presents it anyway, the resolver serves shadow and says so on stderr — a
    degradation, never a silent one.
    """
    global _understanding_cache
    now = time.monotonic()
    if _understanding_cache is not None and now - _understanding_cache[0] < (
        _UNDERSTANDING_TTL_SECONDS
    ):
        return _understanding_cache[1]
    config = await _read_understanding_config()
    _understanding_cache = (now, config)
    return config


async def _read_understanding_config() -> UnderstandingConfig:
    """One uncached read of the three understanding knobs (see the resolver's contract)."""
    from tessera.recouvrement.understanding import DEFAULT_TIMEOUT_S

    keys = [UNDERSTANDING_MODE_KEY, UNDERSTANDING_THRESHOLD_KEY, UNDERSTANDING_TIMEOUT_KEY]
    try:
        await ensure_overrides_schema()
        pool = get_pool()
        async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                sql.SQL("SELECT key, value FROM {table} WHERE key = ANY(%s);").format(table=_TABLE),
                (keys,),
            )
            rows = await cur.fetchall()
    except Exception as exc:  # fail open to shadow — never block a turn on this store
        sys.stderr.write(
            f"tessera.config_overrides: understanding read failed, serving shadow: {exc}\n"
        )
        return UnderstandingConfig(mode="shadow", threshold=None, timeout_s=DEFAULT_TIMEOUT_S)
    by_key = {str(r["key"]): str(r["value"]) for r in rows}
    return _interpret_understanding_rows(by_key, default_timeout_s=DEFAULT_TIMEOUT_S)


def _interpret_understanding_rows(
    by_key: dict[str, str], *, default_timeout_s: float
) -> UnderstandingConfig:
    """Turn stored knob rows into the served config — degradations spoken, never silent."""
    threshold = (
        float(by_key[UNDERSTANDING_THRESHOLD_KEY])
        if UNDERSTANDING_THRESHOLD_KEY in by_key
        else None
    )
    timeout_s = float(by_key.get(UNDERSTANDING_TIMEOUT_KEY, default_timeout_s))
    mode = by_key.get(UNDERSTANDING_MODE_KEY, "shadow")
    if mode == "active" and threshold is None:
        sys.stderr.write(
            "tessera.config_overrides: understanding mode 'active' with no stored threshold "
            "— an illegal store state; serving shadow (ADR 0053 §6)\n"
        )
        mode = "shadow"
    resolved_mode: Literal["shadow", "active"] = "active" if mode == "active" else "shadow"
    return UnderstandingConfig(mode=resolved_mode, threshold=threshold, timeout_s=timeout_s)
