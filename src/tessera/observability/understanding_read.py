"""Read the layer-1 understanding telemetry for the métier view (ADR 0053).

One question, answered in COUNTS: over the recent classified turns, how often did
the model and the word lists agree, how often did the model fail (each failure
named), how fast was it, and when did it last speak. The understanding ruler
never shares a denominator with the business signals (ADR 0017 §A5.3), so this
block carries no rate a reader could confuse with them — counts, a window, and a
timestamp. ``None`` means the agent has no classified turns at all: an absent
plane, not an empty score.
"""

from __future__ import annotations

from tessera.observability.business_events import business_event_rows

__all__ = ["UNDERSTANDING_WINDOW", "understanding_summary"]

#: How many recent comparison rows the summary reads. A window, said in the payload,
#: so the card can name its population instead of implying all history.
UNDERSTANDING_WINDOW = 200


def _payload(row: dict[str, object]) -> dict[str, object]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else {}


def understanding_summary(agent_id: str) -> dict[str, object] | None:
    """Aggregate the agent's recent ``shadow_understanding`` rows, or ``None``.

    Args:
        agent_id: The agent whose understanding plane is read.

    Returns:
        Counts over the last :data:`UNDERSTANDING_WINDOW` comparison rows —
        verdicts, agreement, failures by kind, p50 latency, the latest row's
        mode/model/timestamp — or ``None`` when the ledger holds no comparison
        row for this agent (no understanding plane to report).
    """
    rows = business_event_rows(agent_id=agent_id, event_name="intent.routed")
    shadow = sorted(
        (row for row in rows if row.get("node_name") == "shadow_understanding"),
        key=lambda row: str(row.get("timestamp") or ""),
    )
    if not shadow:
        return None
    recent = shadow[-UNDERSTANDING_WINDOW:]
    verdicts = [row for row in recent if _payload(row).get("llm_status") == "verdict"]
    failures: dict[str, int] = {}
    for row in recent:
        status = str(_payload(row).get("llm_status"))
        if status != "verdict":
            failures[status] = failures.get(status, 0) + 1
    latencies = sorted(
        float(latency)
        for row in verdicts
        if isinstance(latency := _payload(row).get("llm_latency_ms"), int | float)
    )
    latest = recent[-1]
    return {
        "observed": len(recent),
        "window": UNDERSTANDING_WINDOW,
        "total_rows": len(shadow),
        "verdicts": len(verdicts),
        "agree": sum(1 for row in verdicts if _payload(row).get("agree") is True),
        "disagree": sum(1 for row in verdicts if _payload(row).get("agree") is False),
        "failures": failures,
        "latency_ms_p50": (round(latencies[len(latencies) // 2], 1) if latencies else None),
        "latest_at": latest.get("timestamp"),
        "latest_mode": _payload(latest).get("mode"),
        "latest_model": latest.get("model"),
    }
