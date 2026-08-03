"""One switch that makes a replay reproducible, honoured by every chat backend.

The eval harness has no LLM judge — its grader is a deterministic string comparison — and yet
two runs of the same catalogue against the same model do not produce the same score. The
reason is upstream of the grader: the agent samples at ``temperature=0.2`` with no seed, so
the *responses* differ between runs and the pass rate moves with them. "The eval is flaky" was
being read as a property of the harness; it is a property of the sampler.

Runs meant to be compared — a ratchet, a floor, a contribution measurement, a bisection —
export ``TESSERA_EVAL_DETERMINISTIC=1`` and get greedy decoding, plus a fixed seed on the
backend that supports one. Ordinary production traffic is untouched: the variable is read at
call time and absent everywhere else.

This is a harness switch, not a governed knob: it belongs to whoever launches the run, not to
the deployment, so it is an environment variable rather than a settings field.
"""

from __future__ import annotations

import os
from typing import Final

__all__ = [
    "DETERMINISTIC_ENV",
    "DETERMINISTIC_SEED",
    "deterministic_sampling",
    "effective_temperature",
    "sampling_seed",
]

DETERMINISTIC_ENV: Final[str] = "TESSERA_EVAL_DETERMINISTIC"

#: Fixed, arbitrary, and written down: a seed nobody can reconstruct is not reproducible.
DETERMINISTIC_SEED: Final[int] = 20260803

_TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})


def deterministic_sampling() -> bool:
    """Return whether this process was asked to sample reproducibly."""
    return os.environ.get(DETERMINISTIC_ENV, "").strip().casefold() in _TRUTHY


def effective_temperature(requested: float) -> float:
    """Return the temperature a backend must actually send.

    Args:
        requested: The temperature the caller asked for.

    Returns:
        ``0.0`` under deterministic sampling, ``requested`` otherwise.
    """
    return 0.0 if deterministic_sampling() else requested


def sampling_seed() -> int | None:
    """Return the seed to send, or ``None`` when the backend should choose its own."""
    return DETERMINISTIC_SEED if deterministic_sampling() else None
