"""External memory-engine adapters behind the :class:`MemoryBackend` Protocol.

Each adapter maps Tessera's memory contract onto a third-party engine
(LangMem, Mem0, Zep). They are optional: the native ``window``/``summary``/
``persistent`` tiers need none of them. An adapter lazily imports its engine and
raises :class:`MissingMemoryExtraError` with an install hint when the matching
optional extra is not present, so the default install stays lean (ADR 0007).
"""

from __future__ import annotations

import os

__all__ = ["MissingMemoryExtraError", "UnconfiguredMemoryBackendError", "required_env"]


class MissingMemoryExtraError(RuntimeError):
    """Raised when an external memory backend is selected without its extra."""

    def __init__(self, *, backend: str, package: str, extra: str) -> None:
        """Build a message pointing at the exact extra to install.

        Args:
            backend: The configured ``MEMORY_BACKEND`` value.
            package: The importable package that is missing.
            extra: The pip extra that provides it.
        """
        super().__init__(
            f"memory backend {backend!r} requires the {package!r} package; "
            f"install it with: pip install 'tessera[{extra}]'"
        )


class UnconfiguredMemoryBackendError(RuntimeError):
    """Raised when an external memory backend is selected without what it needs to work.

    Installing the extra is not the same as configuring the engine, and the difference had been
    swallowed. `ZepBackend` built its client with a literal ``api_key=""`` under a comment saying
    the client "reads them itself" — an explicit empty string *overrides* whatever the
    environment holds, so it authenticated as nobody. `LangMemBackend` hard-coded
    ``openai:gpt-4o-mini``: a paid model outside the LLM router, outside the model policy and
    outside the org-wide budget breaker (ADR 0034), chosen by a string literal.

    Neither raised. Both produced an object that answered every call, recalled nothing, and
    reported no error — the shape of failure this repository refuses everywhere else.
    """

    def __init__(self, *, backend: str, missing: str, why: str) -> None:
        """Name what is missing, and what happens if it is left missing.

        Args:
            backend: The configured ``MEMORY_BACKEND`` value.
            missing: The environment variable that is unset.
            why: What the value is for, in one sentence.
        """
        super().__init__(
            f"memory backend {backend!r} is installed but not configured: {missing} is unset. "
            f"{why} Set it, or select a native backend (`window`, `summary`, `persistent`), "
            f"which needs no external service."
        )


def required_env(name: str, *, backend: str, why: str) -> str:
    """Read a mandatory environment variable, or refuse by name.

    A default here would be a credential, an endpoint or a paid model chosen by nobody — the
    same class of bug as a default password (F-9). There is deliberately no fallback.

    Args:
        name: The variable to read.
        backend: The backend requesting it, for the message.
        why: What it is for, in one sentence.

    Returns:
        The value.

    Raises:
        UnconfiguredMemoryBackendError: When it is unset or empty.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise UnconfiguredMemoryBackendError(backend=backend, missing=name, why=why)
    return value
