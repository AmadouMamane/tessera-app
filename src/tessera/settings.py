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

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    """Where Tessera is deployed (ADR 0008).

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


class GuardSettings(BaseSettings):
    """Runtime guardrail configuration — wraps mcp-firewall."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_GUARD_", extra="ignore")

    policy_path: Path = _PACKAGE_ROOT / "guard" / "policy.yaml"
    audit_sink: Literal["stdout", "file", "cloud_logging", "postgres"] = "file"
    audit_file: Path = Path("/tmp/tessera/audit.log")  # noqa: S108  default local audit sink
    fail_closed: bool = True
    escalation_confidence_threshold: float = 0.6

    # Hica external opposability seal (ADR 0015 §Amendment 3 pt3 + §Correction 3c pt4;
    # docs/decisions/0015-hica-seal-design-note.md). Enrichment, never the store. The default
    # ``none`` is the honesty invariant: with no provider configured the badge can NEVER read
    # "Scellé" (the NoOp provider cannot mint a token). A verified but non-eIDAS-qualified TSA
    # renders "Scellé (non qualifié)"; only a qualified one earns "Scellé · opposable".
    seal_provider: Literal["none", "rfc3161"] = "none"
    seal_tsa_url: str | None = None  # required iff seal_provider="rfc3161"
    seal_tsa_cert: Path | None = None  # pinned CA/verify cert — the offline trust root
    seal_tsa_qualified: bool = False  # eIDAS-qualified TSA? → "opposable" vs "non qualifié"
    seal_interval_s: int = 3600  # τ — the guaranteed upper bound on undetected-anomaly time
    seal_staleness_budget_s: int = 7200  # 2τ — beyond this a seal is "stale" → Intégrité partielle

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

    @field_validator("online_eval_sample_rate")
    @classmethod
    def _sample_rate_is_a_fraction(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"online_eval_sample_rate must be in [0.0, 1.0]; got {value!r}")
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

    # -- Security hardening (ADR 0008) ---------------------------------------
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
    """Deployment-aware secret resolution (ADR 0008).

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
        cannot be silently disabled there (ADR 0008, control x mode matrix).
        """
        return self.api.rate_limit_enabled or self.is_on_prem()

    @property
    def hsts_enabled(self) -> bool:
        """Send HSTS only when TLS is actually terminated for this deployment."""
        return self.api.tls_terminated


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
