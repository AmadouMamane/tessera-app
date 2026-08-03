"""Process-wide LLM cost / token budget tracker.

The tracker is intentionally minimal: it accumulates token counts per
``(backend, model)`` pair into thread-safe counters — cumulative AND for the
current Europe/Paris calendar day — and converts them to an indicative EUR
cost using a small in-memory price table. The day counters feed the ONE
enforcement that exists: the org-wide daily budget ceiling applied at the
chat routing seam (ADR 0034). This module used to claim "per-conversation
caps" that no caller enforced — a meter with no breaker; the claim is gone
and the breaker is real.

Prices are *indicative only* — the project's positioning makes no claim of
production-grade FinOps. The table lives at the bottom of this file and is
the place to extend when new models come on-stream.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from tessera.fsutil import atomic_write_text
from tessera.settings import get_settings

_FCNTL: ModuleType | None
try:  # POSIX only; the fall-back keeps a single-process deployment working unchanged.
    import fcntl as _fcntl_module
except ImportError:  # pragma: no cover - no supported deployment lacks fcntl
    _FCNTL = None
else:
    _FCNTL = _fcntl_module

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType

__all__ = [
    "BudgetSnapshot",
    "BudgetTracker",
    "estimate_turn_cost",
    "get_budget_tracker",
    "model_is_paid",
    "priced_models",
]

_PARIS = ZoneInfo("Europe/Paris")

_WARNED: set[str] = set()


def _warn(message: str) -> None:
    """Report a budget-layer degradation on stderr, once per process and cause."""
    if message in _WARNED:
        return
    _WARNED.add(message)
    sys.stderr.write(f"tessera.budget: {message}\n")


def _today() -> str:
    """The current Europe/Paris calendar day (the ceiling's accounting window)."""
    return datetime.now(_PARIS).date().isoformat()


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    """An immutable view of the tracker at a point in time.

    Cumulative counters since first start, plus the current Europe/Paris
    day's counters (ADR 0034 — the daily ceiling reads ``day_cost_eur``).
    """

    input_tokens: int
    output_tokens: int
    estimated_cost_eur: Decimal
    day: str = ""
    day_input_tokens: int = 0
    day_output_tokens: int = 0
    day_cost_eur: Decimal = Decimal("0")
    #: True when the persisted counters could not be read and this process restarted them at
    #: zero. A spend breaker reading zero because it lost its file is not the same fact as a
    #: breaker reading zero because nothing was spent, and the two must not look alike.
    degraded: bool = False


@dataclass(frozen=True, slots=True)
class _Price:
    """Price per million tokens, by direction."""

    eur_per_million_input: Decimal
    eur_per_million_output: Decimal


_PRICES: dict[tuple[str, str], _Price] = {
    # Vertex AI Gemini 2.0 family — indicative European pricing per million tokens.
    ("vertex-ai", "gemini-2.0-flash-001"): _Price(
        eur_per_million_input=Decimal("0.10"),
        eur_per_million_output=Decimal("0.40"),
    ),
    ("vertex-ai", "gemini-2.0-pro-001"): _Price(
        eur_per_million_input=Decimal("1.25"),
        eur_per_million_output=Decimal("5.00"),
    ),
    # On-prem inference is treated as zero marginal LLM cost — hardware
    # amortisation lives in the FinOps doc, not in per-call accounting.
    ("ollama", "llama3.3:70b"): _Price(
        eur_per_million_input=Decimal("0"),
        eur_per_million_output=Decimal("0"),
    ),
    # Declared, not merely absent. It served the whole eval catalogue and every dev turn
    # while the table had never heard of it, and an unknown model and a free one produced
    # the identical 0.00 € — so nothing could tell "local inference costs nothing" apart
    # from "we forgot to write down what this costs" (audit 2026-08-03).
    ("ollama", "llama3.2:3b"): _Price(
        eur_per_million_input=Decimal("0"),
        eur_per_million_output=Decimal("0"),
    ),
    # OpenAI frontier — indicative EUR/million tokens (estimate; adjust to the
    # real GPT-5.5 tariff). Lets the budget dashboard show real spend.
    ("openai", "gpt-5.5"): _Price(
        eur_per_million_input=Decimal("1.10"),
        eur_per_million_output=Decimal("8.80"),
    ),
    ("openai", "gpt-5.5-pro"): _Price(
        eur_per_million_input=Decimal("2.50"),
        eur_per_million_output=Decimal("20.00"),
    ),
}


def estimate_turn_cost(*, model: str, input_tokens: int, output_tokens: int) -> tuple[str, Decimal]:
    """Estimate the indicative EUR cost of a single turn for ``model``.

    Looks the model up in the price table by name (model names are unique
    across providers), without instantiating a backend. Returns the resolved
    ``(provider, cost)`` pair. Unknown models — notably the small local Ollama
    chat models used in development — resolve to the on-prem provider at zero
    marginal cost, which is the honest figure for local inference.

    Args:
        model: The chat model that actually ran the turn.
        input_tokens: Prompt tokens billed.
        output_tokens: Completion tokens billed.

    Returns:
        ``(provider, cost_eur)`` — provider is ``"ollama"`` when the model is
        not in the price table; cost is :class:`~decimal.Decimal`.
    """
    for (backend, table_model), price in _PRICES.items():
        if table_model == model:
            cost = (
                Decimal(input_tokens) * price.eur_per_million_input
                + Decimal(output_tokens) * price.eur_per_million_output
            ) / Decimal(1_000_000)
            return backend, cost
    return "ollama", Decimal(0)


def priced_models() -> frozenset[str]:
    """Every model name the price table knows, whatever its price.

    A model can be *servable* and absent from this set, and that combination is the blind
    spot: :func:`estimate_turn_cost` resolves it to on-prem at zero cost, so it is free to
    the counter and invisible to the daily ceiling — an org could burn a paid model all day
    against a breaker that never sees a euro. Zero is the right answer for local inference and
    the wrong one for a tariff nobody wrote down, and only the table can tell them apart.
    Frozen by ``tests/unit/test_every_servable_model_is_priced.py``.
    """
    return frozenset(model for _backend, model in _PRICES)


def model_is_paid(model: str) -> bool:
    """Whether ``model`` carries a nonzero indicative price (ADR 0034).

    The daily ceiling gates PAID models only: local zero-cost inference is
    never blocked by a spend breaker. Derived from the same real price table
    every other cost figure reads.
    """
    _, cost = estimate_turn_cost(model=model, input_tokens=1_000_000, output_tokens=1_000_000)
    return cost > 0


_BUDGET_FILE = Path("/tmp/tessera/budget.json")  # noqa: S108 — ephemeral local cache; the container mounts a dedicated volume here


class BudgetTracker:
    """Thread-safe accumulator of token usage and indicative cost.

    Persists totals to ``_BUDGET_FILE`` after every ``record()`` call so
    that cumulative usage survives backend restarts (important for the
    dashboard view — the user should see a growing counter, not a reset).
    """

    def __init__(self, *, persist_path: Path | None = _BUDGET_FILE) -> None:
        self._lock = threading.Lock()
        self._degraded = False
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cost_eur: Decimal = Decimal("0")
        # ADR 0034 — the current Europe/Paris day's counters, rolled on the
        # first record or read of a new day. Yesterday is gone, said plainly.
        self._day: str = _today()
        self._day_input_tokens: int = 0
        self._day_output_tokens: int = 0
        self._day_cost_eur: Decimal = Decimal("0")
        self._persist_path: Path | None = persist_path  # None → no persistence
        self._load()

    def _load(self) -> None:
        """Restore persisted totals from disk on startup (caller holds the file lock)."""
        if self._persist_path is None:
            return
        try:
            raw = self._persist_path.read_text()
        except FileNotFoundError:
            return  # first start — zero is the truth
        except OSError as exc:
            _warn(f"budget file unreadable ({exc}); this process starts its counters at zero")
            self._degraded = True
            return
        try:
            data = json.loads(raw)
            self._input_tokens = int(data.get("input_tokens", 0))
            self._output_tokens = int(data.get("output_tokens", 0))
            self._cost_eur = Decimal(str(data.get("cost_eur", "0")))
            # Restore the day counters only when the stored day is still today;
            # a stale day starts a fresh window (the roll, applied at load).
            if str(data.get("day", "")) == self._day:
                self._day_input_tokens = int(data.get("day_input_tokens", 0))
                self._day_output_tokens = int(data.get("day_output_tokens", 0))
                self._day_cost_eur = Decimal(str(data.get("day_cost_eur", "0")))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            # A cost breaker that silently resets to zero fails OPEN, which is the one
            # direction it must never fail in. It cannot refuse every call either — that
            # would take the agent down over a cache file — so it starts at zero and SAYS SO,
            # and the snapshot carries `degraded` all the way to the dashboard.
            _warn(f"budget file is not readable JSON ({exc}); counters restart at zero")
            self._degraded = True

    def _state(self) -> dict[str, object]:
        return {
            "input_tokens": self._input_tokens,
            "output_tokens": self._output_tokens,
            "cost_eur": str(self._cost_eur),
            "day": self._day,
            "day_input_tokens": self._day_input_tokens,
            "day_output_tokens": self._day_output_tokens,
            "day_cost_eur": str(self._day_cost_eur),
        }

    def _persist(self) -> None:
        """Write current totals to disk (caller holds self._lock and the file lock)."""
        if self._persist_path is None:
            return
        # Atomic: temp file, fsync, os.replace. `write_text` truncates first, so a reader on
        # another worker could see an empty budget — which reads as "nothing spent today" on
        # a spend breaker. OSError is suppressed: a read-only filesystem degrades gracefully.
        with suppress(OSError):
            atomic_write_text(self._persist_path, json.dumps(self._state()))

    def _roll_day(self) -> None:
        """Start a fresh day window when the calendar day changed (lock held)."""
        today = _today()
        if today != self._day:
            self._day = today
            self._day_input_tokens = 0
            self._day_output_tokens = 0
            self._day_cost_eur = Decimal("0")

    def record(
        self,
        *,
        backend: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Add a usage record."""
        price = _PRICES.get((backend, model))
        cost = (
            (
                Decimal(input_tokens) * price.eur_per_million_input
                + Decimal(output_tokens) * price.eur_per_million_output
            )
            / Decimal(1_000_000)
            if price is not None
            else Decimal(0)
        )
        with self._lock, self._file_lock():
            # Re-read INSIDE the lock. The counters used to live only in this process's
            # memory and `_persist` rewrote the whole file from them, so with `api.workers = N`
            # each worker accumulated its own day total and the last writer won: the real
            # ceiling was N times daily_eur, and ADR 0034 says "one org-wide daily breaker".
            self._load()
            self._roll_day()
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._cost_eur += cost
            self._day_input_tokens += input_tokens
            self._day_output_tokens += output_tokens
            self._day_cost_eur += cost
            self._persist()

    def snapshot(self) -> BudgetSnapshot:
        """Return the current totals (day counters rolled to the current day)."""
        with self._lock, self._file_lock():
            # A reader must see what every worker has spent, not what this one has.
            self._load()
            self._roll_day()
            return BudgetSnapshot(
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                estimated_cost_eur=self._cost_eur,
                day=self._day,
                day_input_tokens=self._day_input_tokens,
                day_output_tokens=self._day_output_tokens,
                day_cost_eur=self._day_cost_eur,
                degraded=self._degraded,
            )

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        """Hold an exclusive OS lock on the budget file for the duration of the block.

        ``threading.Lock`` serialises the threads of ONE process. Since ADR 0044 the agent
        runs N of them, each with its own tracker, and the daily ceiling is supposed to be
        org-wide. ``flock`` is the scope that was missing.
        """
        if _FCNTL is None or self._persist_path is None:  # pragma: no cover - POSIX everywhere
            yield
            return
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self._persist_path.with_suffix(".lock").open("a+", encoding="utf-8") as handle:
            _FCNTL.flock(handle.fileno(), _FCNTL.LOCK_EX)
            try:
                yield
            finally:
                _FCNTL.flock(handle.fileno(), _FCNTL.LOCK_UN)

    def reset(self) -> None:
        """Reset all counters; used by tests."""
        with self._lock:
            self._input_tokens = 0
            self._output_tokens = 0
            self._cost_eur = Decimal("0")
            self._day = _today()
            self._day_input_tokens = 0
            self._day_output_tokens = 0
            self._day_cost_eur = Decimal("0")
            self._persist()


@lru_cache(maxsize=1)
def get_budget_tracker() -> BudgetTracker:
    """Return the process-wide singleton tracker.

    Honours ``TESSERA_BUDGET_FILE`` for the persistence path, so a separate
    process — notably the offline eval runner — can keep its own *eval* budget
    instead of polluting the live agent's *prod* counters. Unset → the default
    file (the agent's prod budget).
    """
    env_path = os.environ.get("TESSERA_BUDGET_FILE")
    if env_path:
        return BudgetTracker(persist_path=Path(env_path))
    # Per-env path (ADR 0014, layer 3): /tmp/tessera/<env>/budget.json, so a dev
    # run never increments the prod budget counter.
    return BudgetTracker(persist_path=get_settings().state_dir / _BUDGET_FILE.name)
