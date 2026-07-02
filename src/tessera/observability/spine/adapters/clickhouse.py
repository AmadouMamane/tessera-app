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

__all__ = ["ONLINE_SCORES_TABLE", "ClickHouseAdapter", "ClickHouseConfig", "online_scores_ddl"]

# Mirrors the live ring buffer's bound (``eval.scores._RECENT`` maxlen) so the live read
# has the same semantics as the jsonl reader it must hold parity with.
_LIVE_LIMIT: Final = 200

ONLINE_SCORES_TABLE: Final = "eval_online_scores"

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
                f"SELECT * FROM {table}{where} ORDER BY scored_at FORMAT JSONEachRow",  # noqa: S608 — identifiers validated, values bound server-side
                params=params,
            )
            return [_row_from_ch(r) for r in _jsonl_lines(raw)]
        raw = self.execute(
            f"SELECT * FROM {table} ORDER BY scored_at DESC LIMIT {_LIVE_LIMIT} "  # noqa: S608 — identifiers validated, constant limit
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
