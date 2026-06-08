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

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "AssuranceLevel",
    "DeploymentMode",
    "Environment",
    "LanguageCode",
    "LLMProfile",
    "MemorySettings",
    "ObservabilityProfile",
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


class AssuranceLevel(StrEnum):
    """Target evidence maturity for the active observability profile."""

    L0_OBSERVED = "L0"
    L1_CORRELATED = "L1"
    L2_AUDITABLE = "L2"
    L3_VERIFIABLE = "L3"
    L4_REPLAYABLE = "L4"
    L5_CERTIFIABLE = "L5"


class ObservabilityProfile(StrEnum):
    """Deployment-aware observability assurance profile."""

    LOCAL_DEV = "local_dev"
    DEMO_PREMIUM = "demo_premium"
    CLOUD_GCP_STANDARD = "cloud_gcp_standard"
    CLOUD_GCP_REGULATED = "cloud_gcp_regulated"
    ON_PREM_STANDARD = "on_prem_standard"
    ON_PREM_AIRGAPPED = "on_prem_airgapped"


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
    pool_min_size: int = 1
    pool_max_size: int = 10
    statement_timeout_ms: int = 5_000
    vector_table: str = "documents"


class GuardSettings(BaseSettings):
    """Runtime guardrail configuration — wraps mcp-firewall."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_GUARD_", extra="ignore")

    policy_path: Path = Path("src/tessera/guard/policy.yaml")
    audit_sink: Literal["stdout", "file", "cloud_logging", "postgres"] = "file"
    audit_file: Path = Path("/tmp/tessera/audit.log")  # noqa: S108  default local audit sink
    fail_closed: bool = True
    escalation_confidence_threshold: float = 0.6

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
    profile: ObservabilityProfile | None = None
    assurance_level: AssuranceLevel | None = None
    collector_required: bool | None = None
    langfuse_enabled: bool = False
    langfuse_host: str | None = None
    grafana_url: str | None = None
    jaeger_url: str | None = None
    prometheus_url: str | None = None
    raw_prompts_export: bool = False
    pii_export: bool = False
    evidence_enabled: bool = True
    evidence_dir: Path = Path("/tmp/tessera/evidence")  # noqa: S108  local evidence store
    evidence_signing_enabled: bool | None = None
    prompt_family: str = "banking_support"
    prompt_version: str = "local"
    dataset_id: str | None = None
    experiment_id: str | None = None
    experiment_variant: str | None = None


class APISettings(BaseSettings):
    """HTTP layer configuration."""

    model_config = SettingsConfigDict(env_prefix="TESSERA_API_", extra="ignore")

    host: str = "0.0.0.0"  # noqa: S104  Cloud Run requires bind-all
    port: int = 8080
    cors_origins: list[str] = Field(default_factory=list)
    request_timeout_seconds: float = 60.0
    streaming_enabled: bool = True
    bearer_token: SecretStr | None = None

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

    @field_validator("history_window", "long_term_top_k", "token_budget")
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
