"""Firewall efficacy as a security metric (ADR 0010, idea #13).

The guard is only worth its latency if it actually catches attacks without
blocking legitimate traffic. This module turns that into numbers: it replays the
prompt-injection cases from the failure corpus (positives) and a small bundled
set of benign banking questions (negatives) through ``check_user_input`` — no
LLM needed — and reports the confusion matrix plus precision / recall / F1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tessera.guard.adapter import check_user_input
from tessera.guard.decisions import load_policy

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["EfficacyReport", "compute_efficacy", "load_benign", "load_injection_prompts"]

# src/tessera/observability/firewall_efficacy.py → parents[3] is the repo root.
_REPO = Path(__file__).resolve().parents[3]
_FAILURES_DIR = _REPO / "eval" / "failures"
_BENIGN_PATH = _REPO / "eval" / "calibration" / "benign_inputs.json"


@dataclass(frozen=True, slots=True)
class EfficacyReport:
    """Confusion matrix + derived metrics for the firewall."""

    n_positive: int
    n_negative: int
    true_positive: int
    false_negative: int
    false_positive: int
    true_negative: int
    precision: float
    recall: float
    f1: float


def load_injection_prompts() -> list[str]:
    """Load every prompt from the ``prompt_injection`` failure cases."""
    prompts: list[str] = []
    for path in _FAILURES_DIR.glob("[0-9]*_*.json"):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case.get("category") != "prompt_injection":
            continue
        for lang_prompt in case.get("prompts", {}).values():
            user = lang_prompt.get("user")
            if user:
                prompts.append(user)
    return prompts


def load_benign() -> list[str]:
    """Load the bundled benign-input set (legitimate traffic)."""
    data: list[str] = json.loads(_BENIGN_PATH.read_text(encoding="utf-8"))
    return data


def compute_efficacy(
    *,
    injections: Sequence[str] | None = None,
    benign: Sequence[str] | None = None,
) -> EfficacyReport:
    """Run the guard over positives + negatives and score detection efficacy."""
    positives = list(injections) if injections is not None else load_injection_prompts()
    negatives = list(benign) if benign is not None else load_benign()
    policy = load_policy()

    tp = sum(1 for text in positives if not check_user_input(text, policy=policy).allowed)
    fn = len(positives) - tp
    fp = sum(1 for text in negatives if not check_user_input(text, policy=policy).allowed)
    tn = len(negatives) - fp

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return EfficacyReport(
        n_positive=len(positives),
        n_negative=len(negatives),
        true_positive=tp,
        false_negative=fn,
        false_positive=fp,
        true_negative=tn,
        precision=precision,
        recall=recall,
        f1=f1,
    )
