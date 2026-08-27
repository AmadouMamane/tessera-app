"""Centralised, typed configuration for Tessera.

Settings flow in three layers, in decreasing precedence:

1. Explicit constructor arguments (used by tests and scripts).
2. Process environment variables, prefixed with ``TESSERA_``.
3. A local development override file at ``.env.local`` (gitignored).

In production on Cloud Run, secrets are mounted from GCP Secret Manager into
the environment by the container start-up wrapper — callers therefore see them
as plain env vars and never have to know about Secret Manager directly.

The settings object is cached behind :func:`get_settings`; tests can clear the
cache with ``get_settings.cache_clear()`` after mutating the environment.

This module is intentionally dependency-light (only pydantic-settings) so it
can be imported from any layer — agent, retrieval, guard, API — without
triggering heavy LLM client initialisation.
"""

from __future__ import annotations

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from tessera.sql import safe_identifier

if TYPE_CHECKING:
    from collections.abc import Mapping

# Resolve bundled defaults relative to the installed package, not the process
# working directory: the backend may be launched from anywhere (uvicorn, tests,
# Cloud Run) and must still find the policy shipped at src/tessera/guard/.
_PACKAGE_ROOT = Path(__file__).resolve().parent

# The historical, environment-agnostic local-state root. When `guard.audit_file`
# is still this default, the Settings validator relocates it under the per-env
# state dir (ADR 0014, layer 3) so audit/lineage/agent-config isolate by path.
_DEFAULT_AUDIT_FILE = Path("/tmp/tessera/audit.log")  # noqa: S108  default local sink

__all__ = [
    "DeploymentMode",
    "Environment",
    "LanguageCode",
    "LLMProfile",
    "MemorySettings",
    "SecretsSettings",
    "Settings",
    "dotenv_files",
    "dotenv_values",
    "env_setting",
    "get_settings",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Environment(StrEnum):
    """Deployment environment the process believes it is running in."""

    LOCAL = "local"
    CI = "ci"
    STAGING = "staging"
    PRODUCTION = "production"


class LLMProfile(StrEnum):
    """Which LLM backend the router should prefer.

    ``frontier`` routes through Vertex AI; ``on_prem`` routes through a local
    Ollama serving Llama 3.3 70B; ``auto`` selects ``frontier`` when Vertex AI
    credentials are present and falls back to ``on_prem`` otherwise.
    """

    FRONTIER = "frontier"
    ON_PREM = "on_prem"
    AUTO = "auto"


class LanguageCode(StrEnum):
    """Supported user-input languages — frozen project convention."""

    FR = "fr"
    DE = "de"
    EN = "en"


class DeploymentMode(StrEnum):
    """Where Tessera is deployed (ADR 0020).

    Load-bearing for security: ``on_prem`` has no managed load balancer, secret
    manager, or platform rate limiter underneath, so app-level controls that are
    *defence in depth* on Cloud Run become the *primary* line of defence there.
    """

    CLOUD_RUN = "cloud_run"
    ON_PREM = "on_prem"


# ---------------------------------------------------------------------------
# Nested setting blocks
# ---------------------------------------------------------------------------


class VertexAISettings(BaseSettings):
    """Vertex AI (frontier path) configuration."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_VERTEX_", extra="ignore")

    project_id: str | None = None
    location: str = "europe-west1"
    chat_model: str = "gemini-2.0-flash-001"
    embedding_model: str = "text-multilingual-embedding-002"
    embedding_dimension: int = 768
    timeout_seconds: float = 30.0
    max_output_tokens: int = 2048


class OllamaSettings(BaseSettings):
    """Ollama (on-prem path) configuration."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_OLLAMA_", extra="ignore")

    host: HttpUrl = Field(default=HttpUrl("http://localhost:11434"))
    chat_model: str = "llama3.2:3b"  # fastest by default; override per env/UI
    embedding_model: str = "bge-m3"
    embedding_dimension: int = 1024
    timeout_seconds: float = 120.0
    keep_alive_seconds: int = 600


class OpenAISettings(BaseSettings):
    """OpenAI (frontier path) configuration.

    The API key is read by the SDK directly from ``OPENAI_API_KEY``; it is never
    stored in this object so it cannot leak into logs or the audit trail.
    """

    model_config = SettingsConfigDict(env_prefix="TESSERA_OPENAI_", extra="ignore")

    chat_model: str = "gpt-5.5"
    base_url: str | None = None
    timeout_seconds: float = 120.0
    # Explicit registry: the models the picker routes to the OpenAI backend
    # (declared, not guessed by name). Anything not listed falls back to the
    # profile backend (Ollama on-prem / Vertex frontier).
    models: list[str] = Field(default_factory=lambda: ["gpt-5.5", "gpt-5.5-pro"])


class PostgresSettings(BaseSettings):
    """Postgres + pgvector configuration."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_POSTGRES_", extra="ignore")

    dsn: PostgresDsn = Field(
        default=PostgresDsn("postgresql://tessera:tessera@localhost:5432/tessera"),
    )
    # Connection-pool bounds (retrieval.store.get_pool). Conservative for a single local
    # process. Per-environment guidance (audit P1.3):
    #   dev / on-prem single instance : 1 / 10 — one process, few concurrent turns.
    #   e2e (Playwright, prod build)  : many pages hit one backend; max 10 STARVES under load
    #     (the proven e2e famine). Keep the suite at low worker count (playwright.config
    #     workers=1 already does) OR raise pool_max_size (~20) for parallel runs.
    #   CI / staging / production     : size to the Cloud SQL max_connections budget —
    #     pool_max_size * instance_count must stay under it; 10-20/instance is a sane start.
    pool_min_size: int = 1
    pool_max_size: int = 10
    statement_timeout_ms: int = 5_000
    vector_table: str = "documents"

    @field_validator("vector_table")
    @classmethod
    def _validate_vector_table(cls, value: str) -> str:
        """Refuse a table name that could not be a table name (audit P0.3 `sql-fstring`).

        This name is a **SQL identifier**, and an identifier cannot be bound as a parameter —
        it is spliced into the query text (`retrieval/store.py`, `observability/knowledge.py`,
        `observability/etat_a_date.py`). It is also settable from the environment
        (`TESSERA_POSTGRES__VECTOR_TABLE`), which makes it the widest door in the class.

        Validating here means an unsafe value cannot exist in the process at all — the
        deployment fails to start rather than building a query around it. The interpolation
        sites validate again, independently; see `tessera.sql`.
        """
        return safe_identifier(value)


class GuardSettings(BaseSettings):
    """Runtime guardrail configuration for the first-party guard (ADR 0028)."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_GUARD_", extra="ignore")

    policy_path: Path = _PACKAGE_ROOT / "guard" / "policy.yaml"
    audit_sink: Literal["stdout", "file", "cloud_logging", "postgres"] = "file"
    audit_file: Path = Path("/tmp/tessera/audit.log")  # noqa: S108  default local audit sink
    fail_closed: bool = True
    escalation_confidence_threshold: float = 0.6

    # Hica external opposability seal (ADR 0015 §Amendment 3 pt3 + §Correction 3c pt4;
    # docs/decisions/0022-hica-seal-design-note.md). Enrichment, never the store. The default
    # ``none`` is the honesty invariant: with no provider configured the badge can NEVER read
    # "Scellé" (the NoOp provider cannot mint a token). A verified but non-eIDAS-qualified TSA
    # renders "Scellé (non qualifié)"; only a qualified one earns "Scellé · opposable".
    seal_provider: Literal["none", "rfc3161"] = "none"
    seal_tsa_url: str | None = None  # required iff seal_provider="rfc3161"
    seal_tsa_cert: Path | None = None  # pinned CA/verify cert — the offline trust root
    seal_tsa_qualified: bool = False  # eIDAS-qualified TSA? → "opposable" vs "non qualifié"
    seal_interval_s: int = 3600  # τ — the guaranteed upper bound on undetected-anomaly time
    seal_staleness_budget_s: int = 7200  # 2τ — beyond this a seal is "stale" → Intégrité partielle
    # How often the WHOLE chain is re-walked and re-hashed (boot, then off-chrono). The badge
    # verifies incrementally against a checkpoint on the request path; this is the walk that
    # earns that checkpoint, and the badge publishes how long ago it last ran. 0 disables the
    # loop — and the badge then says so, rather than quietly resting on an old proof.
    ledger_verify_interval_s: int = 900

    @field_validator("escalation_confidence_threshold")
    @classmethod
    def _threshold_is_a_probability(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                "escalation_confidence_threshold must be in [0.0, 1.0]; " f"got {value!r}"
            )
        return value


class ObservabilitySettings(BaseSettings):
    """Logging, tracing, and metrics configuration."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_OBS_", extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    otel_endpoint: str | None = None
    otel_service_name: str = "tessera-agent"
    cloud_logging_project: str | None = None
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # -- Frontier observability (ADR 0010) -----------------------------------
    # Which observability backend stack this process targets. Independent of
    # ``deployment_mode``: an on-prem app may still ship traces to GCP, or a
    # Cloud Run app may export to a self-hosted Phoenix. ``on_prem`` → OTLP to
    # the local OpenTelemetry Collector (fanning out to Phoenix / Langfuse);
    # ``gcp`` → Cloud Trace plus managed backends.
    profile: Literal["on_prem", "gcp"] = "on_prem"
    # OTLP/HTTP endpoint of the OpenTelemetry Collector, preferred over
    # ``otel_endpoint``. The Claude-Powered local stack exposes it on
    # ``http://localhost:4418`` (see docker-compose.obs.claude.yml).
    otel_collector_endpoint: str | None = None
    # Opt-in capture of prompt/completion *content* as span events (OTel GenAI
    # convention). Off by default — content is sensitive in banking, so it is
    # screened before it is ever attached (ADR 0010, idea #4).
    content_capture: bool = False
    # Data-residency tag attached to every span as a resource attribute and used
    # by the Collector to route EU-only (ADR 0010, idea #3).
    data_residency: str = "eu"
    # LLM-as-judge model for online evaluation; None → the cheap summary backend
    # (the sovereign local Llama on the on-prem path). (ADR 0010, Phase 4.)
    judge_model: str | None = None
    # Fraction of un-flagged turns scored online; flagged turns are always scored
    # (tiered, cost-aware online eval — idea #6).
    online_eval_sample_rate: float = 0.1
    # ADR 0019 §I4 — the scheduled-canary master switch (the operator's activation). OFF by
    # default: even with a manifest cadence declared, no synthetic turn fires until the operator
    # opts in (synthetic traffic hits the real agent + LLM — a deliberate act, never implicit).
    # The scheduler is always WIRED (it idles under this flag), so flipping it is go-and-observe,
    # never a latent provisioned-but-silent trap (the Hica-seal off-chrono lesson).
    canary_scheduler_enabled: bool = False
    # ADR 0052 §Amendment 1 — the stack-probe cadence, in seconds; 0 disables. ON by default,
    # unlike the canary: probing twelve local sockets is passive observation with no LLM cost
    # and no synthetic traffic, and without it the component history only covers the minutes a
    # cockpit happened to be open (1.3 % of the day it shipped). Runs on the ADR 0044 leader
    # only, so N workers never multiply it — and unit tests, which have no Postgres to elect a
    # leader with, never start it at all.
    probe_interval_s: int = 60
    # ADR 0055 — where a state-transition alert is pushed OUT of the cockpit (Slack-compatible
    # webhook, `{"text": ...}`). None = no push: conditions are still evaluated and journalled
    # on the leader beat, only the egress is skipped — and the cockpit card says "no channel"
    # out loud instead of looking armed. Arming it is a deliberate operator act (an env var),
    # like the canary switch above.
    alert_webhook_url: str | None = None

    @field_validator("alert_webhook_url")
    @classmethod
    def _alert_webhook_is_http(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError(f"alert_webhook_url must be an http(s) URL; got {value!r}")
        return value

    @field_validator("online_eval_sample_rate")
    @classmethod
    def _sample_rate_is_a_fraction(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"online_eval_sample_rate must be in [0.0, 1.0]; got {value!r}")
        return value

    @field_validator("probe_interval_s")
    @classmethod
    def _probe_interval_is_not_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"probe_interval_s must be >= 0 (0 disables); got {value!r}")
        return value


class APISettings(BaseSettings):
    """HTTP layer configuration."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_API_", extra="ignore")

    host: str = "0.0.0.0"  # noqa: S104  Cloud Run requires bind-all
    port: int = 8080
    cors_origins: list[str] = Field(default_factory=list)
    request_timeout_seconds: float = 60.0
    streaming_enabled: bool = True
    bearer_token: SecretStr | None = None

    # Size of the threadpool Starlette runs synchronous (``def``) endpoints in. The
    # observability READ handlers are synchronous so their blocking DB reads run OFF the
    # event loop — a dashboard fires ~25 reads at once and they must run in parallel, not
    # serialize behind one loop. This caps concurrent in-flight blocking reads (and thus
    # transient DB connections); the anyio default is 40. Tune per env / DB max_connections.
    read_threads: int = 40

    # Number of uvicorn worker PROCESSES (ADR 0044). The threadpool above parallelises the
    # *I/O wait* of the synchronous reads, but a single process shares ONE GIL, so the Python
    # CPU work of concurrent cockpit reads still serialises. N workers give N independent GILs
    # — true CPU parallelism for the dashboard's fan-out. The default 1 is byte-identical to the
    # single-process serving model (no multiproc metrics dir, no leader election needed). Raise
    # it on the on-prem agent (~4) where the fan-out is the bottleneck. Constraints when >1:
    #   * pool_max_size * workers must stay under Postgres max_connections (4 * 10 = 40 < 100);
    #   * Prometheus switches to multiprocess aggregation (only the leader binds metrics_port);
    #   * the lifespan background loops (seal/canary/purge/verify) run on ONE advisory-lock
    #     leader, never N times over — see tessera.api.leader.
    workers: int = 1

    # HMAC key for the signed customer-session cookie (ADR 0008/0009). Resolved
    # from the environment — in production from GCP Secret Manager, mounted as
    # TESSERA_API_SESSION_SIGNING_KEY — and NEVER committed. When unset (local
    # dev / CI) the session layer falls back to a process-ephemeral key.
    session_signing_key: SecretStr | None = None

    # HMAC key for the signed OPERATOR assertion (ADR 0010 Phase B). The Next BFF
    # mints the assertion after verifying a next-auth operator session; the agent
    # verifies it here to derive AuthState.OPERATOR. Because mint (front) and
    # verify (agent) live in *different* processes, both MUST share this exact
    # value via env / GCP Secret Manager (TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY)
    # — there is no ephemeral fallback (a per-process key could never match across
    # the trust boundary). Required in production (fail-closed); when unset in
    # dev/CI the operator path is simply inert (no assertion ever verifies).
    operator_assertion_signing_key: SecretStr | None = None

    # -- Security hardening (ADR 0020) ---------------------------------------
    # TLS is terminated by Cloud Run; an on-prem reverse proxy may not, in which
    # case HSTS must stay off. Drives the security-headers middleware.
    tls_terminated: bool = True
    security_headers_enabled: bool = True

    # Interactive API docs (/docs) and the OpenAPI schema (/openapi.json). On by
    # default for local dev, always forced off in production. Set False to also
    # close them on a non-prod agent that is nonetheless reachable from the
    # internet (e.g. exposed via a tunnel) — they leak the full route surface.
    expose_docs: bool = True

    # Rate limiting (the `limits` lib). Defaults are conservative; tune per env.
    rate_limit_enabled: bool = True
    # Per-session limit on POST /chat (keyed by the X-Session-Id cookie the front
    # forwards). "20/hour" embodies the "20 per session" budget for a public,
    # login-less demo; raise it for trusted environments.
    rate_limit_chat: str = "20/hour"
    # Hard global ceiling on POST /chat across ALL sessions — bounds total LLM
    # cost even if sessions are farmed. Checked in addition to the per-session limit.
    rate_limit_chat_global: str = "200/hour"
    rate_limit_read: str = "120/minute"
    # Optional shared store (e.g. "redis://host:6379") for correct limits across
    # multiple Cloud Run instances; in-memory (per-instance) when unset.
    rate_limit_storage_uri: str | None = None
    # When True, derive the rate-limit identity from forwarded headers
    # (X-Forwarded-For / CF-Connecting-IP) instead of the immediate peer. Enable
    # only behind a trusted proxy (Next, nginx, cloudflared) that sets them.
    trust_forwarded_headers: bool = False

    # POST /agents/{id}/invoke — the declared invocation seam (ADR 0019). Bounded PER
    # AGENT (binding) and PER ROLE (the operator surface), so an operator cannot hammer
    # an agent's test endpoint. A purpose-built limit, tighter than the generic read one.
    rate_limit_invoke: str = "12/minute"
    # Max concurrent in-flight invocations of one agent per role — protects a foreign
    # runtime from a thundering herd of operator test turns. In-process (per instance;
    # a shared rate_limit_storage_uri only backs the rate window, not this counter).
    invoke_max_concurrent: int = 4

    # Global request-body ceiling, in addition to per-field Pydantic caps.
    max_request_bytes: int = 256_000


class SecretsSettings(BaseSettings):
    """Deployment-aware secret resolution (ADR 0020).

    ``provider`` selects where secrets come from. ``env`` (default) covers the
    Cloud Run managed path, where GCP Secret Manager — the premium cloud choice —
    is mounted as env vars. On-prem, the **recommended premium** path is
    ``vault`` (HashiCorp Vault / OpenBao: dynamic secrets, leases, rotation);
    ``sops`` (SOPS+age file) is the lighter, server-less standard option.
    """

    model_config = SettingsConfigDict(env_prefix="TESSERA_SECRETS_", extra="ignore")

    provider: Literal["env", "gcp", "sops", "vault"] = "env"
    # gcp
    gcp_project_id: str | None = None
    # sops (on-prem standard)
    sops_file: str | None = None
    # vault / openbao (on-prem premium)
    vault_url: str | None = None
    vault_token: SecretStr | None = None
    vault_mount: str = "secret"
    vault_path: str = "tessera"


class MemorySettings(BaseSettings):
    """Agent memory configuration — see ADR 0007.

    ``backend`` selects the :class:`~tessera.memory.protocol.MemoryBackend`
    implementation; everything else is shared knob territory the active backend
    is free to read or ignore. The default (``window``) is lossless and free,
    matching the short-conversation common case of retail banking support.
    """

    model_config = SettingsConfigDict(env_prefix="TESSERA_MEMORY_", extra="ignore")

    backend: Literal[
        "window",  # Tier 0 — sliding window (default)
        "summary",  # Tier 1 — summary buffer + entity ledger
        "persistent",  # Tier 2 — cross-session, pgvector Store
        "langmem",  # external adapter (extra: memory-langmem)
        "mem0",  # external adapter (extra: memory-mem0)
        "zep",  # external adapter (extra: memory-zep)
    ] = "window"

    # Recency window: number of prior (user/assistant) messages kept verbatim.
    history_window: int = 6
    # Token budget above which Tier 1 compacts older turns into a summary.
    token_budget: int = 2_000
    # Whether long-term (Tier 2) writes are allowed absent an explicit consent
    # flag. Conservative default: no long-term retention without consent.
    consent_default: bool = False
    # Number of long-term items retrieved and injected per turn (Tier 2).
    long_term_top_k: int = 5
    # Cadence of the retention purge that physically deletes memories past their
    # TTL (``ttl_for``). Before this existed, `purge_expired` had no caller at all:
    # the TTL filtered at *read* time while the rows lived on in Postgres forever —
    # retention on paper only. 0 disables the purge (and says so at boot).
    purge_interval_s: int = 3_600

    @field_validator("history_window", "long_term_top_k", "token_budget", "purge_interval_s")
    @classmethod
    def _non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"memory size knobs must be >= 0; got {value!r}")
        return value


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Top-level Tessera configuration.

    All fields are populated from environment variables prefixed with
    ``TESSERA_`` (with nested fields using a double-underscore delimiter, e.g.
    ``TESSERA_VERTEX__PROJECT_ID``). For local development, values can be
    placed in ``.env.local`` next to the repository root.

    Attributes:
        environment: The deployment context (local, ci, staging, production).
        llm_profile: Which LLM backend to prefer.
        default_language: Fallback language when detection is unavailable.
        vertex: Vertex AI settings.
        ollama: Ollama settings.
        postgres: Postgres + pgvector settings.
        guard: Runtime guardrail settings.
        observability: Logging, tracing, and metrics settings.
        api: HTTP layer settings.
        memory: Agent memory settings (ADR 0007).
    """

    # ── Env-var naming, and its trap (audit P1.3) ───────────────────────────────
    # Nested blocks resolve TWO ways, easy to confuse:
    #   1. CANONICAL — the `__` delimiter below, keyed on the FIELD NAME:
    #        TESSERA_POSTGRES__DSN, TESSERA_OBSERVABILITY__LOG_FORMAT, TESSERA_API__PORT.
    #   2. LEGACY — each nested block also carries its own single-`_` env_prefix:
    #        TESSERA_POSTGRES_DSN, TESSERA_OBS_LOG_FORMAT  (note: OBS, not OBSERVABILITY).
    # The trap is the abbreviated block prefix: `observability` is TESSERA_OBSERVABILITY__X
    # (form 1) or TESSERA_OBS_X (form 2) — but TESSERA_OBS__X (abbreviation + double
    # underscore) matches NEITHER and is SILENTLY IGNORED. Prefer form 1 everywhere. Full
    # generated inventory: docs/configuration.md (scripts/config_inventory.py).
    model_config = SettingsConfigDict(
        env_prefix="TESSERA_",
        env_nested_delimiter="__",
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    environment: Environment = Environment.LOCAL
    deployment_mode: DeploymentMode = DeploymentMode.CLOUD_RUN
    llm_profile: LLMProfile = LLMProfile.AUTO
    default_language: LanguageCode = LanguageCode.FR

    vertex: VertexAISettings = Field(default_factory=VertexAISettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    secrets: SecretsSettings = Field(default_factory=SecretsSettings)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    guard: GuardSettings = Field(default_factory=GuardSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    api: APISettings = Field(default_factory=APISettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)

    def resolved_llm_profile(self) -> LLMProfile:
        """Materialise ``LLMProfile.AUTO`` into a concrete profile.

        ``frontier`` requires a Vertex AI project id to be set; otherwise we
        fall back to the on-prem Ollama path. This is the only place that
        knows the resolution rule — callers should always go through it.
        """
        if self.llm_profile is not LLMProfile.AUTO:
            return self.llm_profile
        if self.vertex.project_id is not None:
            return LLMProfile.FRONTIER
        return LLMProfile.ON_PREM

    def is_production(self) -> bool:
        """Return True when running with production-grade safety expectations."""
        return self.environment is Environment.PRODUCTION

    @property
    def pg_schema(self) -> str:
        """Postgres schema that isolates this environment's durable state (ADR 0014).

        Production keeps the historical ``public`` schema so the deployed stack is
        never migrated; every other environment gets its own ``tessera_<env>``
        schema. This is the *spatial* sibling of the temporal ``as-of T``
        dimension (ADR 0011): a local dev process and a deployed-style process can
        then run against one Postgres without touching each other's transcript,
        eval, or memory state. Read once here so the pool and any migration share
        a single definition.
        """
        if self.environment is Environment.PRODUCTION:
            return "public"
        return f"tessera_{self.environment.value}"

    @property
    def state_dir(self) -> Path:
        """Per-env root for file-based local state (ADR 0014, layer 3).

        Isolates the audit log, ingestion lineage, agent-config store and budget
        cache by *path*, the way :attr:`pg_schema` isolates Postgres by schema —
        ``/tmp/tessera/<env>/`` — so two environments never share an audit chain
        or a budget counter. File-based state is cross-env precisely because it
        is not under the connection ``search_path``; isolating by path is the
        same doctrine, not an ``environment`` column.
        """
        return Path("/tmp/tessera") / self.environment.value  # noqa: S108

    @model_validator(mode="after")
    def _scope_state_paths_to_env(self) -> Settings:
        """Relocate still-default file-state paths to their per-env location.

        Only the untouched default is moved; an explicitly-set
        ``TESSERA_GUARD__AUDIT_FILE`` is respected as-is. Ingestion lineage and
        the agent-config store derive from ``guard.audit_file.parent``, so
        rewriting the audit file relocates them together.
        """
        if self.guard.audit_file == _DEFAULT_AUDIT_FILE:
            self.guard.audit_file = self.state_dir / _DEFAULT_AUDIT_FILE.name
        return self

    def is_on_prem(self) -> bool:
        """True on the self-hosted path (no managed platform underneath)."""
        return self.deployment_mode is DeploymentMode.ON_PREM

    @property
    def rate_limit_required(self) -> bool:
        """Rate limiting is mandatory on-prem; recommended (default-on) on cloud.

        On-prem has no upstream load balancer to absorb abuse, so the control
        cannot be silently disabled there (ADR 0020, control x mode matrix).
        """
        return self.api.rate_limit_enabled or self.is_on_prem()

    @property
    def hsts_enabled(self) -> bool:
        """Send HSTS only when TLS is actually terminated for this deployment."""
        return self.api.tls_terminated


# ---------------------------------------------------------------------------
# Unbound overrides — making `extra="ignore"` audible
# ---------------------------------------------------------------------------


def unbound_env_overrides(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return ``TESSERA_<section>__<name>`` variables that bind to no settings field.

    Every model here is ``extra="ignore"``, and that is deliberate rather than sloppy: the
    nested sections are addressed with a DOUBLE underscore (``TESSERA_GUARD__AUDIT_SINK``)
    while each sub-model also declares a single-underscore ``env_prefix``, so ``forbid`` would
    reject the very names the deployment sets. What ``ignore`` costs is the typo:
    ``TESSERA_GUARD__FAILCLOSED`` is accepted, dropped, and the breaker quietly keeps its
    default while the operator believes they changed it. A setting that can be *asked for* and
    silently not applied is the same defect as a knob that is not effective by construction
    (ADR 0030).

    Only the ``TESSERA_<section>__…`` form is inspected, because there the section name is
    already proof of intent: the caller meant a settings field of that section. Bare
    ``TESSERA_*`` names are left alone — many of them belong to compose, the Makefile or the
    scripts and were never addressed to this module.

    Args:
        environ: Environment to inspect; defaults to the process environment.

    Returns:
        The offending variable names, sorted. Empty when every override binds.
    """
    env = os.environ if environ is None else environ
    sections: dict[str, frozenset[str]] = {}
    for field_name, field in Settings.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseSettings):
            sections[field_name.upper()] = frozenset(n.upper() for n in annotation.model_fields)

    unbound: list[str] = []
    for name in env:
        upper = name.upper()
        if not upper.startswith("TESSERA_") or "__" not in upper:
            continue
        section, _, rest = upper[len("TESSERA_") :].partition("__")
        known = sections.get(section)
        if known is not None and rest not in known:
            unbound.append(name)
    return tuple(sorted(unbound))


# ---------------------------------------------------------------------------
# Cached accessor
# ---------------------------------------------------------------------------

Cached = Annotated[Settings, "process-wide cached settings instance"]


@lru_cache(maxsize=1)
def get_settings() -> Cached:
    """Return the cached process-wide :class:`Settings` instance.

    Tests should call ``get_settings.cache_clear()`` whenever they mutate the
    environment to ensure subsequent reads reflect the change.
    """
    return Settings()


# ---------------------------------------------------------------------------
# The dotenv seam, for settings that do NOT live on `Settings`
# ---------------------------------------------------------------------------
#
# A handful of addresses and credentials are read by the name their own tool
# publishes — ``LANGFUSE_HOST``, ``TESSERA_CLICKHOUSE_URL`` — rather than as a
# ``Settings`` field, because that is the name the vendor's SDK and the compose
# file already use. Those readers used to call ``os.environ.get`` alone, which
# made them the only settings in the project blind to ``.env.local`` — the file
# CLAUDE.md tells an operator to configure. Configuring it changed nothing, and
# the literal default that took over looked plausible enough to hide the hole
# for a day (ClickHouse, 2026-08-05, commit ``e7184679``).
#
# ClickHouse learned this first and kept the fix private; Langfuse repeated the
# bug three files away. So the resolver lives HERE, once, next to the
# declaration it defers to.


def dotenv_files() -> tuple[str, ...]:
    """The dotenv files :class:`Settings` is CURRENTLY configured to read, in precedence order.

    Asked of the live config rather than restated. The subtle half of that choice would
    otherwise have been a real regression: the test suite's ``conftest`` sets ``env_file`` to
    ``None`` on purpose, so a run never picks up a developer's ``.env.local``. A private copy
    of the path list quietly re-opens that hole; deferring inherits the guard for free.
    """
    declared = Settings.model_config.get("env_file")
    if declared is None:
        return ()
    if isinstance(declared, str | Path):
        return (str(declared),)
    return tuple(str(item) for item in declared)


# A quoted dotenv value is at least the pair of quotes itself; a lone `"` is a one-character
# value, not an empty quoted one, and stripping it would invent a credential nobody wrote.
_QUOTED_MIN_LEN = 2


def dotenv_values() -> dict[str, str]:
    """``KEY=value`` pairs from the project's dotenv files, best effort.

    Deliberately NOT cached: the cost is two small file reads on paths that already perform an
    HTTP round-trip, and a cache here would both leak state between tests and go stale the
    moment an operator edits the file they were told to edit.

    Parsing is intentionally minimal — ``KEY=value``, ``#`` comments, optional surrounding
    quotes. A value this cannot parse is skipped rather than guessed: a credential read wrong
    produces a 403 that looks exactly like a missing store, and that confusion is what this
    whole seam exists to end.
    """
    values: dict[str, str] = {}
    for name in dotenv_files():
        path = Path(name)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.removeprefix("export ").strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= _QUOTED_MIN_LEN and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            values[key] = value
    return values


def env_setting(name: str, default: str) -> str:
    """Resolve one non-``Settings`` name: process environment, then dotenv, then the default.

    The same precedence ``Settings`` itself applies, so the two can never disagree about where
    a value came from. An empty value is treated as absent — an env var set to ``""`` in a
    compose file is a placeholder somebody forgot to fill, not a deliberate empty address.

    Args:
        name: The variable to resolve, spelled as its own tool spells it.
        default: What to use when neither source carries it.

    Returns:
        The resolved value, or ``default``.
    """
    from_env = os.environ.get(name, "").strip()
    if from_env:
        return from_env
    from_file = dotenv_values().get(name, "").strip()
    return from_file or default
