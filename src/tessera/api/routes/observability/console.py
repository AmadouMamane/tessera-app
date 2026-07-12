"""Observability routes — console surface. AGGREGATES ONLY.

The subject-scoped reads that used to live here — the transcript, the conversations
directory, the session detail, the replay bundles, the trajectory, the provenance, the
trace-snapshot drifts, the console feedback — moved to :mod:`.pii`, behind
``require_subject_reader`` (audit 2026-07-12, **P1 F-4**). What is left returns counts,
rates, shapes and config: the public cockpit surface ADR 0009 declares, and it stays public.

Two routes here still *read* subject records on their way to a number — ``tail-sampling``
(retention statistics over replay bundles) and ``replay-shadow`` (which projects only
``bundle_id[:12]``, agent, model and timestamps). They are public deliberately, and the read
ratchet holds them there by name: an aggregate that starts carrying a question or an answer
must move next door.
"""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.api.routes.observability._common import (
    _read_audit_entries,
    _scores_for,
)
from tessera.observability import (
    agent_console as agent_console_mod,
    assistant as assistant_mod,
    langfuse_obs as langfuse_obs_mod,
    replay as replay_mod,
    replay_shadow as replay_shadow_mod,
    span_propagation as span_propagation_mod,
    tail_sampling as tail_sampling_mod,
)
from tessera.observability._asof import occurred_before
from tessera.observability.spine.runtime import get_runtime_provider

router = APIRouter()

_propagation_cache: dict[str, object] | None = None


@router.get("/observability/timeline")
async def observability_timeline(at: str | None = None) -> dict[str, object]:
    """Temporal control backbone — dated lineage events for the cockpit time rail.

    Every cockpit view reads at an instant T and compares to a baseline; this is
    the event scrubber behind that control. Events are *derived from real
    signals*, never fabricated: quality points (online-eval scores), judge-model
    changes, agent-model changes and guard denials (the tamper-evident audit
    log). With ``?at=`` the window ends at T (as-of-T read, ADR 0011): only
    events with timestamp ≤ T are returned.
    """
    from datetime import UTC, datetime

    events: list[dict[str, object]] = []

    # Quality points + judge-model change detection (scores oldest→newest, ≤ T).
    ordered = sorted(_scores_for(at), key=lambda s: str(s.get("scored_at", "")))
    prev_judge: str | None = None
    for s in ordered:
        ts = str(s.get("scored_at", ""))
        if not ts:
            continue
        score = float(s.get("score", 0.0))  # type: ignore[arg-type]
        good, fair = 0.8, 0.5
        tone = "success" if score >= good else "warning" if score >= fair else "danger"
        events.append(
            {
                "at": ts,
                "kind": "score",
                "label": f"Score {score:.2f}",
                "detail": f"{s.get('metric', '')} · {str(s.get('language', '')).upper()}",
                "tone": tone,
            }
        )
        judge = s.get("judge_model")
        if isinstance(judge, str) and judge and judge != prev_judge:
            if prev_judge is not None:
                events.append(
                    {
                        "at": ts,
                        "kind": "judge_change",
                        "label": "Juge mis à jour",
                        "detail": f"{prev_judge} → {judge} — re-calibration κ requise",
                        "tone": "gold",
                    }
                )
            prev_judge = judge

    # Guard denials + agent-model changes from the tamper-evident audit log,
    # filtered to occurrences ≤ T. Denials are clustered by hour so a busy log
    # becomes a few legible scrubber markers rather than hundreds of dots.
    prev_model: str | None = None
    denials: dict[str, dict[str, object]] = {}
    for entry in _read_audit_entries():
        ts = str(entry.get("occurred_at", ""))
        if not ts:
            continue
        if not occurred_before(ts, at):
            continue
        outcome = str(entry.get("outcome", ""))
        if outcome not in ("allowed", "allow"):
            bucket = ts[:13]  # YYYY-MM-DDTHH
            agg = denials.setdefault(
                bucket, {"at": ts, "count": 0, "target": entry.get("target", "")}
            )
            count = agg["count"]
            agg["count"] = (count if isinstance(count, int) else 0) + 1
            agg["at"] = ts  # latest occurrence in the hour
        model = entry.get("model")
        if isinstance(model, str) and model and model != prev_model:
            if prev_model is not None:
                events.append(
                    {
                        "at": ts,
                        "kind": "model_change",
                        "label": "Modèle déployé",
                        "detail": f"{prev_model} → {model}",
                        "tone": "info",
                    }
                )
            prev_model = model

    for agg in denials.values():
        events.append(
            {
                "at": str(agg["at"]),
                "kind": "guard_denial",
                "label": f"Garde — {agg['count']} refus",
                "detail": str(agg["target"]),
                "tone": "danger",
            }
        )

    events.sort(key=lambda e: str(e["at"]))
    window_end = at or datetime.now(UTC).isoformat()
    window_start = str(events[0]["at"]) if events else window_end
    return {
        "window_start": window_start,
        "window_end": window_end,
        "baseline_at": window_start,
        "n_events": len(events),
        "events": events[-60:],
        "as_of": at,
    }


@router.get("/observability/span-propagation")
async def observability_span_propagation() -> dict[str, object]:
    """Async/parallel span-propagation health from a live isolated probe (#85), cached."""
    global _propagation_cache
    if _propagation_cache is None:
        _propagation_cache = asdict(await span_propagation_mod.probe_propagation())
    return _propagation_cache


@router.get("/observability/tail-sampling")
async def observability_tail_sampling() -> dict[str, object]:
    """Tail-sampling retention: 100% of slow/low-score traces, sampled head."""
    return asdict(tail_sampling_mod.analyze_sampling(replay_mod.recent_bundles()))


@router.get("/observability/agent-console")
async def observability_agent_console(
    lang: str = "fr", agent: str = DEFAULT_AGENT_ID
) -> dict[str, object]:
    """Agent Console (Debug) surface (reference image agent-console-normative).

    ADR 0019 §I2 — agent-scoped and *generated* from the agent's declared
    ``invocation.binding``. An ``in_process_chat`` agent returns the full interactive
    payload (context strip, tools / guardrails / eval panels, the tabbed inspector); a
    publish-only agent (``binding: none``) returns a slim honest-empty descriptor
    (``invocation.invocable: false`` + an ``empty`` copy) so the console never renders a
    chat it cannot drive. Real config (guard policy, eval scores), never a fixture;
    degrades to ``available: false`` (e.g. an unknown ``agent``).
    """
    try:
        return {"available": True, **agent_console_mod.compute_agent_console(lang, agent)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.agent_console: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/assistant")
async def observability_assistant(lang: str = "fr") -> dict[str, object]:
    """Assistant overview (Chat and Console sub-tabs).

    Composes the session header, the grounded conversation, the session context,
    the cited sources, the tools called, the guardrails triggered, the response
    quality scores, the execution trace, the follow-up suggestions and the
    console rail KPIs into one payload. ``lang`` localizes the grounded
    conversation. Degrades to ``available: false``.
    """
    try:
        return {"available": True, **assistant_mod.compute_assistant_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.assistant: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/traces-obs")
async def observability_traces_obs(at: str | None = None) -> dict[str, object]:
    """Real trace observability read from the running Langfuse stack (best tool).

    The OTel instrumentation fans every span to Langfuse; this reads the REAL trace
    volume + latency back through its public API and hands the operator deep-links to
    each tool for the job it is best at (Langfuse = trace explorer, Grafana =
    dashboards, Phoenix = retrieval). Honours as-of-T via Langfuse ``toTimestamp`` so
    it projects like the rest of the page; degrades to ``available: false`` when the
    stack is unreachable — never a fabricated number.
    """
    import asyncio

    try:
        # The Langfuse read is a blocking HTTP call — run it off the event loop.
        result = await asyncio.to_thread(langfuse_obs_mod.compute_traces_observability, at)
        return asdict(result)
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.traces_obs: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/replay-shadow")
async def observability_replay_shadow(lang: str = "fr") -> dict[str, object]:
    """Replay & shadow overview (page #11).

    Composes the replay posture, traffic and deviation series, recent / top
    sessions, baseline comparisons, per-service/model distributions, replayed
    evals and the live activity feed. Degrades to ``available: false``.
    """
    try:
        return {"available": True, **replay_shadow_mod.compute_replay_shadow_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.replay_shadow: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/graph-topology")
async def observability_graph_topology() -> dict[str, object]:
    """Topology fingerprint of the live agent graph vs the golden pin (#87).

    ADR 0017 §1: the fingerprint is computed by the agent runtime (which imports
    langgraph) and read through the spine port — the cockpit never builds the graph.
    """
    return get_runtime_provider().graph_topology()
