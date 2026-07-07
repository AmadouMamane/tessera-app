"""ClickHouse adapter — the owned home of ONLINE monitoring scores (ADR 0015 §Correction 2b).

The Nature-2 online eval scores (the sampled per-turn monitoring telemetry emitted by
``evaluate_turn``) live in an **owned** ClickHouse table ``tessera.eval_online_scores``,
written by **direct insert** — never via Langfuse's public Scores ingestion (proven fragile
2026-07-02: the POST returns 201 yet never materialises). ClickHouse already runs in the
stack (under Langfuse) and this is natively its workload: ``MergeTree`` gives monthly
``PARTITION BY`` + ``TTL`` retention with no hand-rolled maintenance job, so the
§Amendment 2 partition/retention machinery disappears.

The governing split (§Amendment 3): ClickHouse is **never** a home for a fact that gates or
proves — the gating scores and the audit/S1 ledger stay in owned Postgres; this table holds
only the sampled monitoring firehose. Langfuse/Phoenix keep the *trace* for drill-down (via
``trace_id``); the score value + dimensions are owned here.

Dimension columns are plain ``String``s: an unattributed dimension is stored as ``""`` and
mapped back to ``None`` at read, mirroring the jsonl rows' ``null`` — never a fabricated
value. Credentials default to the self-hosted stack (``docker-compose.obs.claude.yml``) and
resolve from Secret Manager in the deployed profile. An unreachable ClickHouse raises
:class:`SpineUnavailableError` → honest-empty reads / best-effort-skipped writes, never a
fabricated zero.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tessera.observability.spine.adapters.base import SpineUnavailableError

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope

__all__ = [
    "BUSINESS_EVENTS_TABLE",
    "ONLINE_SCORES_TABLE",
    "ClickHouseAdapter",
    "ClickHouseConfig",
    "business_events_ddl",
    "online_scores_ddl",
]

# Mirrors the live ring buffer's bound (``eval.scores._RECENT`` maxlen) so the live read
# has the same semantics as the jsonl reader it must hold parity with.
_LIVE_LIMIT: Final = 200

# The business-event live cut mirrors ``InMemoryBusinessEventStore``'s deque bound (maxlen
# 500), so the flipped ClickHouse read holds parity with the in-process store it replaces.
_BUSINESS_EVENTS_LIVE_LIMIT: Final = 500
# A TOTAL order for reproducible as-of-T business-event reads (same (scope, T) ⇒ same rows,
# same order — SR-01). The DESC twin keeps the live newest-cut deterministic at the boundary.
_BE_TOTAL_ORDER: Final = "occurred_at, event_name, conversation_id, turn_id, artifact_id"
_BE_TOTAL_ORDER_DESC: Final = (
    "occurred_at DESC, event_name DESC, conversation_id DESC, turn_id DESC, artifact_id DESC"
)

# A TOTAL order, not just time: rows sharing a millisecond would otherwise come back in
# whatever part-merge order ClickHouse happens to hold, and an as-of-T read must be
# REPRODUCIBLE — same (scope, T) ⇒ same rows in the same order (SR-01 "Vue figée au T").
# The DESC twin keeps the live newest-200 cut deterministic at the boundary too; the
# python `reversed()` of that cut yields exactly the ascending total order.
_TOTAL_ORDER: Final = "scored_at, metric, trace_id, conversation_id"
_TOTAL_ORDER_DESC: Final = "scored_at DESC, metric DESC, trace_id DESC, conversation_id DESC"

ONLINE_SCORES_TABLE: Final = "eval_online_scores"
# The owned durable home of business events (ADR 0017 §5). Dimensional, traffic-driven
# monitoring telemetry — direct insert, MergeTree + monthly partitions + 6-month TTL,
# aligned with ``eval_online_scores``. The opposable facet stays in the Postgres ledger.
BUSINESS_EVENTS_TABLE: Final = "business_events"

# Database / identifier names are interpolated into DDL, so they must stay plain
# identifiers even though they come from trusted env config — defence in depth.
_IDENTIFIER: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ClickHouseConfig:
    """Self-hosted ClickHouse connection (fixed local creds; Secret Manager in prod)."""

    url: str
    user: str
    password: str
    database: str

    def __post_init__(self) -> None:
        if not _IDENTIFIER.match(self.database):
            msg = f"clickhouse database must be a plain identifier; got {self.database!r}"
            raise ValueError(msg)

    @classmethod
    def from_env(cls) -> ClickHouseConfig:
        """Resolve from the environment, defaulting to the local obs stack's HTTP port.

        In the deployed profile (ADR 0014) the same names resolve from Secret Manager,
        never the repo — the backend reads them from the environment either way.
        """
        return cls(
            url=os.environ.get("TESSERA_CLICKHOUSE_URL", "http://localhost:18123").rstrip("/"),
            user=os.environ.get("TESSERA_CLICKHOUSE_USER", "clickhouse"),
            password=os.environ.get("TESSERA_CLICKHOUSE_PASSWORD", "clickhouse"),
            database=os.environ.get("TESSERA_CLICKHOUSE_DATABASE", "tessera"),
        )


def online_scores_ddl(database: str) -> str:
    """The §Correction 2b DDL — MergeTree + native monthly partitions + TTL retention.

    ``ORDER BY (agent_id, metric, scored_at)`` serves the per-agent/metric and as-of-T
    window reads; ``PARTITION BY toYYYYMM(scored_at)`` + ``TTL`` are the two volume levers
    the amendment requires **natively** (no scheduled DROP job to hand-roll).
    """
    return f"""
CREATE TABLE IF NOT EXISTS {database}.{ONLINE_SCORES_TABLE} (
    scored_at        DateTime64(3),
    agent_id         LowCardinality(String),
    language         LowCardinality(String),
    model            LowCardinality(String),
    metric           LowCardinality(String),
    score            Float64,
    conversation_id  String,
    trace_id         String,
    sampled          UInt8,
    judge_model      String
) ENGINE = MergeTree
ORDER BY (agent_id, metric, scored_at)
PARTITION BY toYYYYMM(scored_at)
TTL toDateTime(scored_at) + INTERVAL 6 MONTH
""".strip()


def business_events_ddl(database: str) -> str:
    """The ADR 0017 §5 DDL — the owned business-event read model.

    ``ORDER BY (agent_id, workflow_id, event_name, occurred_at)`` serves the per-agent /
    per-workflow / as-of-T run reads; ``PARTITION BY toYYYYMM(occurred_at)`` + a 6-month
    ``TTL`` (aligned with ``eval_online_scores``) are the native volume levers. ``payload``
    is the strict-schema-validated JSON kept PII-free by construction (§2), so erasure by
    ``conversation_id`` stays cheap and complete. ``node_name`` is carried (beyond the §5
    column list) so the flipped read holds run-timeline parity with the in-process store.
    """
    return f"""
CREATE TABLE IF NOT EXISTS {database}.{BUSINESS_EVENTS_TABLE} (
    occurred_at      DateTime64(3),
    agent_id         LowCardinality(String),
    workflow_id      LowCardinality(String),
    capability_id    LowCardinality(String),
    event_name       LowCardinality(String),
    node_name        LowCardinality(String),
    conversation_id  String,
    turn_id          String,
    case_id          String,
    artifact_id      String,
    artifact_type    LowCardinality(String),
    artifact_status  LowCardinality(String),
    decision         LowCardinality(String),
    reason_codes     Array(LowCardinality(String)),
    actor            LowCardinality(String),
    surface          LowCardinality(String),
    language         LowCardinality(String),
    model            LowCardinality(String),
    environment      LowCardinality(String),
    schema_version   LowCardinality(String),
    event_version    UInt16,
    grammar_version  LowCardinality(String),
    payload          String
) ENGINE = MergeTree
ORDER BY (agent_id, workflow_id, event_name, occurred_at)
PARTITION BY toYYYYMM(occurred_at)
TTL toDateTime(occurred_at) + INTERVAL 6 MONTH
""".strip()


class ClickHouseAdapter:
    """Query/DDL client for the owned ClickHouse online-score store (§Correction 2b)."""

    def __init__(self, config: ClickHouseConfig | None = None, *, timeout_s: float = 3.0) -> None:
        self._config = config if config is not None else ClickHouseConfig.from_env()
        self._timeout_s = timeout_s

    @property
    def config(self) -> ClickHouseConfig:
        """The resolved ClickHouse connection config."""
        return self._config

    @property
    def table(self) -> str:
        """The fully-qualified owned online-scores table (``<database>.<table>``)."""
        return f"{self._config.database}.{ONLINE_SCORES_TABLE}"

    @property
    def business_events_table(self) -> str:
        """The fully-qualified owned business-events table (ADR 0017 §5)."""
        return f"{self._config.database}.{BUSINESS_EVENTS_TABLE}"

    def execute(
        self, query: str, *, data: bytes | None = None, params: dict[str, str] | None = None
    ) -> str:
        """Run one statement over the HTTP interface and return the raw response body.

        With ``data`` the query goes in the URL and ``data`` is the POST body (the
        ``INSERT … FORMAT JSONEachRow`` shape); otherwise the query itself is the body.
        ``params`` bind ``{name:Type}`` placeholders server-side (``param_<name>``) — values
        never enter the SQL text, so a scoped read is injection-safe by construction.
        Auth uses the ClickHouse HTTP headers, so the query string never carries a secret.
        """
        url_params: dict[str, str] = {f"param_{k}": v for k, v in (params or {}).items()}
        if data is not None:
            url_params["query"] = query
            body = data
        else:
            body = query.encode("utf-8")
        url = f"{self._config.url}/"
        if url_params:
            url = f"{url}?{urllib.parse.urlencode(url_params)}"
        request = urllib.request.Request(  # noqa: S310 — self-hosted spine
            url,
            data=body,
            method="POST",
            headers={
                "X-ClickHouse-User": self._config.user,
                "X-ClickHouse-Key": self._config.password,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:  # noqa: S310
                payload: bytes = response.read()
                return payload.decode("utf-8")
        except urllib.error.HTTPError as exc:
            # ClickHouse returns its error text in the body — surface it, bounded.
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            msg = f"clickhouse error at {self._config.url}: {exc.code} {detail}"
            raise SpineUnavailableError(msg) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            msg = f"clickhouse unreachable at {self._config.url}: {exc}"
            raise SpineUnavailableError(msg) from exc

    def ensure_schema(self) -> None:
        """Create the owned database + online-scores table idempotently (§Correction 2b).

        Mirrors the repo's ``ensure_*_schema`` bootstrap discipline (no Alembic): both
        statements are ``IF NOT EXISTS`` so re-running is free, and the DDL is the single
        source of the table shape.
        """
        self.execute(f"CREATE DATABASE IF NOT EXISTS {self._config.database}")
        self.execute(online_scores_ddl(self._config.database))

    def ensure_business_events_schema(self) -> None:
        """Create the owned database + business-events table idempotently (ADR 0017 §5).

        A sibling of :meth:`ensure_schema` (kept separate so the scores write path never
        materialises the business-event table, and vice versa); both ``IF NOT EXISTS``, so
        re-running is free and the DDL stays the single source of the table shape.
        """
        self.execute(f"CREATE DATABASE IF NOT EXISTS {self._config.database}")
        self.execute(business_events_ddl(self._config.database))

    def business_events(
        self,
        *,
        at: str | None = None,
        agent_id: str | None = None,
        workflow_id: str | None = None,
        conversation_id: str | None = None,
        turn_id: str | None = None,
        case_id: str | None = None,
        event_name: str | None = None,
        artifact_type: str | None = None,
        decision: str | None = None,
    ) -> list[dict[str, object]]:
        """Business-event rows for the filters, shaped exactly like ``BusinessEvent.to_row``.

        Mirrors :meth:`online_scores` semantics so the flipped read holds parity with the
        in-process store: **as-of-T** (``at``) reads every row at/before T ascending;
        **live** (no ``at``) returns the newest ``500`` (the deque bound) then ascending.
        Dimension filters push into SQL as bound ``{name:String}`` params (injection-safe);
        an unparsable ``at`` falls back to no time bound, exactly like the jsonl reader.
        """
        table = self.business_events_table
        conditions: list[str] = []
        params: dict[str, str] = {}
        if at:
            cutoff = _ch_datetime(at)
            if cutoff is not None:
                conditions.append("occurred_at <= {at:DateTime64(3)}")
                params["at"] = cutoff
        for column, value in (
            ("agent_id", agent_id),
            ("workflow_id", workflow_id),
            ("conversation_id", conversation_id),
            ("turn_id", turn_id),
            ("case_id", case_id),
            ("event_name", event_name),
            ("artifact_type", artifact_type),
            ("decision", decision),
        ):
            if value is not None:
                conditions.append(f"{column} = {{{column}:String}}")
                params[column] = value
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        if at:
            raw = self.execute(
                f"SELECT * FROM {table}{where} ORDER BY {_BE_TOTAL_ORDER} FORMAT JSONEachRow",  # noqa: S608 — identifiers validated, values bound server-side
                params=params,
            )
            return [_business_row_from_ch(r) for r in _jsonl_lines(raw)]
        raw = self.execute(
            f"SELECT * FROM {table}{where} ORDER BY {_BE_TOTAL_ORDER_DESC} "  # noqa: S608 — identifiers validated, values bound server-side
            f"LIMIT {_BUSINESS_EVENTS_LIVE_LIMIT} FORMAT JSONEachRow",
            params=params,
        )
        return [_business_row_from_ch(r) for r in reversed(_jsonl_lines(raw))]

    def delete_business_events(self, conversation_id: str) -> int:
        """Erase a conversation's business-event rows (GDPR Art. 17 — the owned-store leg).

        Count-then-``DELETE``, both value-bound — the same primitive as
        :meth:`delete_conversation` for the score store. Returns the number of rows covered;
        0 for an unknown conversation (no pointless mutation).
        """
        if not conversation_id:
            return 0
        table = self.business_events_table
        params = {"conv": conversation_id}
        count = self.execute(
            f"SELECT count() FROM {table} WHERE conversation_id = {{conv:String}}",  # noqa: S608 — fixed identifiers, value bound server-side
            params=params,
        ).strip()
        deleted = int(count) if count.isdigit() else 0
        if deleted:
            self.execute(
                f"DELETE FROM {table} WHERE conversation_id = {{conv:String}}",  # noqa: S608 — fixed identifiers, value bound server-side
                params=params,
            )
        return deleted

    def online_scores(self, scope: Scope) -> list[dict[str, object]]:
        """Online score rows for ``scope``, shaped exactly like the jsonl store's rows.

        The G4 parity gate compares this read against the jsonl reader count-for-count,
        so the semantics mirror it deliberately: **as-of-T** (``scope.at``) reads every
        row at/before T with the dimension filters pushed into SQL; **live** (no ``at``)
        mirrors the in-process ring — the last ``200`` rows org-wide by ``scored_at``,
        dimension filters applied *after* the cut, exactly like ``recent_scores``. An
        unparsable ``at`` falls back to no time bound (the jsonl reader ignores a bad
        cutoff rather than dropping data).
        """
        table = self.table
        if scope.at:
            cutoff = _ch_datetime(scope.at)
            conditions: list[str] = []
            params: dict[str, str] = {}
            if cutoff is not None:
                conditions.append("scored_at <= {at:DateTime64(3)}")
                params["at"] = cutoff
            if scope.agent_id is not None:
                conditions.append("agent_id = {agent:String}")
                params["agent"] = scope.agent_id
            if scope.language is not None:
                conditions.append("language = {language:String}")
                params["language"] = scope.language
            if scope.model is not None:
                conditions.append("model = {model:String}")
                params["model"] = scope.model
            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            raw = self.execute(
                f"SELECT * FROM {table}{where} ORDER BY {_TOTAL_ORDER} FORMAT JSONEachRow",  # noqa: S608 — identifiers validated, values bound server-side
                params=params,
            )
            return [_row_from_ch(r) for r in _jsonl_lines(raw)]
        raw = self.execute(
            f"SELECT * FROM {table} ORDER BY {_TOTAL_ORDER_DESC} LIMIT {_LIVE_LIMIT} "  # noqa: S608 — identifiers validated, constant limit
            "FORMAT JSONEachRow"
        )
        rows = [_row_from_ch(r) for r in reversed(list(_jsonl_lines(raw)))]
        if scope.agent_id is not None:
            rows = [r for r in rows if r.get("agent_id") == scope.agent_id]
        if scope.language is not None:
            rows = [r for r in rows if r.get("language") == scope.language]
        if scope.model is not None:
            rows = [r for r in rows if r.get("model") == scope.model]
        return rows

    def delete_conversation(self, conversation_id: str) -> int:
        """Erase a conversation's online score rows (GDPR Art. 17 — the owned-store leg).

        Counts first, then issues a lightweight ``DELETE`` (rows are masked from reads
        immediately and physically removed by the mutation) — both value-bound. Returns
        the number of rows the deletion covers; 0 for an unknown conversation.
        """
        if not conversation_id:
            return 0
        params = {"conv": conversation_id}
        count = self.execute(
            f"SELECT count() FROM {self.table} WHERE conversation_id = {{conv:String}}",  # noqa: S608 — fixed identifiers, value bound server-side
            params=params,
        ).strip()
        deleted = int(count) if count.isdigit() else 0
        if deleted:
            self.execute(
                f"DELETE FROM {self.table} WHERE conversation_id = {{conv:String}}",  # noqa: S608 — fixed identifiers, value bound server-side
                params=params,
            )
        return deleted


def _ch_datetime(value: str) -> str | None:
    """An ISO instant as a ClickHouse ``DateTime64(3)`` literal (UTC), or ``None``."""
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    utc = stamp.astimezone(UTC)
    return utc.strftime("%Y-%m-%d %H:%M:%S.") + f"{utc.microsecond // 1000:03d}"


def _jsonl_lines(raw: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _opt(value: object) -> str | None:
    """The table's ``""`` "unattributed" marker mapped back to ``None`` (never invented)."""
    return value if isinstance(value, str) and value else None


def _business_row_from_ch(row: dict[str, object]) -> dict[str, object]:
    """One ClickHouse business-event row → the ``BusinessEvent.to_row`` shape.

    So ``business_events._row_to_event`` rebuilds it unchanged (classification is
    re-derived there from event_name/decision/payload — it is not stored). ``occurred_at``
    is reconstructed as ISO-8601 UTC (millisecond precision; sub-ms digits are gone —
    truncated, never padded). The ``""`` unattributed markers map back to ``None``.
    """
    occurred = row.get("occurred_at")
    reason_codes = row.get("reason_codes")
    payload_raw = row.get("payload")
    payload: dict[str, object] = {}
    if isinstance(payload_raw, str) and payload_raw:
        try:
            loaded = json.loads(payload_raw)
        except ValueError:
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded
    event_version = row.get("event_version")
    actor = row.get("actor")
    return {
        "event_name": _opt(row.get("event_name")),
        "timestamp": (f"{occurred.replace(' ', 'T')}+00:00" if isinstance(occurred, str) else None),
        "agent_id": _opt(row.get("agent_id")),
        "conversation_id": _opt(row.get("conversation_id")),
        "turn_id": _opt(row.get("turn_id")),
        "workflow_id": _opt(row.get("workflow_id")),
        "capability_id": _opt(row.get("capability_id")),
        "surface": _opt(row.get("surface")),
        "language": _opt(row.get("language")),
        "model": _opt(row.get("model")),
        "environment": _opt(row.get("environment")),
        "case_id": _opt(row.get("case_id")),
        "node_name": _opt(row.get("node_name")),
        "artifact_id": _opt(row.get("artifact_id")),
        "artifact_type": _opt(row.get("artifact_type")),
        "artifact_status": _opt(row.get("artifact_status")),
        "decision": _opt(row.get("decision")),
        "reason_codes": [str(code) for code in reason_codes]
        if isinstance(reason_codes, list)
        else [],
        "payload": payload,
        "actor": actor if isinstance(actor, str) and actor else "system",
        "schema_version": _opt(row.get("schema_version")) or "business_event.v1",
        "event_version": event_version if isinstance(event_version, int) else 1,
        "grammar_version": _opt(row.get("grammar_version")),
    }


def _row_from_ch(row: dict[str, object]) -> dict[str, object]:
    """One ClickHouse row → the jsonl row shape every score consumer already reads.

    ``scored_at`` is reconstructed as ISO-8601 UTC; ClickHouse stores millisecond
    precision, so the sub-millisecond digits of the original jsonl stamp are gone —
    truncated, never padded with invented digits.
    """
    scored_at = row.get("scored_at")
    return {
        "scored_at": (
            f"{scored_at.replace(' ', 'T')}+00:00" if isinstance(scored_at, str) else None
        ),
        "metric": _opt(row.get("metric")),
        "score": row.get("score"),
        "language": _opt(row.get("language")),
        "judge_model": _opt(row.get("judge_model")),
        "conversation_id": _opt(row.get("conversation_id")),
        "trace_id": _opt(row.get("trace_id")),
        "sampled": bool(row.get("sampled")),
        "agent_id": _opt(row.get("agent_id")),
        "model": _opt(row.get("model")),
    }
