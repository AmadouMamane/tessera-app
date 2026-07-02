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

import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Final

from tessera.observability.spine.adapters.base import SpineUnavailableError

__all__ = ["ONLINE_SCORES_TABLE", "ClickHouseAdapter", "ClickHouseConfig", "online_scores_ddl"]

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

    def execute(self, query: str, *, data: bytes | None = None) -> str:
        """Run one statement over the HTTP interface and return the raw response body.

        With ``data`` the query goes in the URL and ``data`` is the POST body (the
        ``INSERT … FORMAT JSONEachRow`` shape); otherwise the query itself is the body.
        Auth uses the ClickHouse HTTP headers, so the query string never carries a secret.
        """
        if data is not None:
            url = f"{self._config.url}/?{urllib.parse.urlencode({'query': query})}"
            body = data
        else:
            url = f"{self._config.url}/"
            body = query.encode("utf-8")
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
