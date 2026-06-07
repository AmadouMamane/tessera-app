"""Process-wide LLM cost / token budget tracker.

The tracker is intentionally minimal: it accumulates token counts per
``(backend, model)`` pair into thread-safe counters and converts them to an
indicative EUR cost using a small in-memory price table. The API layer
queries it once per request to enforce per-conversation caps.

Prices are *indicative only* — the project's positioning makes no claim of
production-grade FinOps. The table lives at the bottom of this file and is
the place to extend when new models come on-stream.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

__all__ = ["BudgetSnapshot", "BudgetTracker", "get_budget_tracker"]


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    """An immutable view of the tracker at a point in time."""

    input_tokens: int
    output_tokens: int
    estimated_cost_eur: Decimal


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


_BUDGET_FILE = Path("/tmp/tessera/budget.json")  # noqa: S108 — ephemeral local cache; the container mounts a dedicated volume here


class BudgetTracker:
    """Thread-safe accumulator of token usage and indicative cost.

    Persists totals to ``_BUDGET_FILE`` after every ``record()`` call so
    that cumulative usage survives backend restarts (important for the
    dashboard view — the user should see a growing counter, not a reset).
    """

    def __init__(self, *, persist_path: Path | None = _BUDGET_FILE) -> None:
        self._lock = threading.Lock()
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._cost_eur: Decimal = Decimal("0")
        self._persist_path: Path | None = persist_path  # None → no persistence
        self._load()

    def _load(self) -> None:
        """Restore persisted totals from disk on startup."""
        if self._persist_path is None:
            return
        try:
            data = json.loads(self._persist_path.read_text())
            self._input_tokens = int(data.get("input_tokens", 0))
            self._output_tokens = int(data.get("output_tokens", 0))
            self._cost_eur = Decimal(str(data.get("cost_eur", "0")))
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            pass  # first start or corrupt file — start at zero

    def _persist(self) -> None:
        """Write current totals to disk (caller holds self._lock)."""
        if self._persist_path is None:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._persist_path.write_text(
                json.dumps(
                    {
                        "input_tokens": self._input_tokens,
                        "output_tokens": self._output_tokens,
                        "cost_eur": str(self._cost_eur),
                    }
                )
            )
        except OSError:
            pass  # read-only filesystem — degrade gracefully

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
        with self._lock:
            self._input_tokens += input_tokens
            self._output_tokens += output_tokens
            self._cost_eur += cost
            self._persist()
        from tessera.observability.metrics import BUDGET_GAUGE, LLM_COST_EUR_TOTAL, LLM_TOKENS_TOTAL

        LLM_TOKENS_TOTAL.labels(backend=backend, model=model, direction="input").inc(input_tokens)
        LLM_TOKENS_TOTAL.labels(backend=backend, model=model, direction="output").inc(output_tokens)
        LLM_COST_EUR_TOTAL.labels(backend=backend, model=model).inc(float(cost))
        BUDGET_GAUGE.set(float(self.snapshot().estimated_cost_eur))

    def snapshot(self) -> BudgetSnapshot:
        """Return the current totals."""
        with self._lock:
            return BudgetSnapshot(
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                estimated_cost_eur=self._cost_eur,
            )

    def reset(self) -> None:
        """Reset all counters; used by tests."""
        with self._lock:
            self._input_tokens = 0
            self._output_tokens = 0
            self._cost_eur = Decimal("0")
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
    return BudgetTracker(persist_path=Path(env_path) if env_path else _BUDGET_FILE)
