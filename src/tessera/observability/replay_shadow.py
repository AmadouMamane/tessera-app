"""Replay & shadow cockpit overview (page #11).

The page has a REAL replay core and a demonstration shadow/export subsystem:

* **REAL:** the replayable sessions are the captured replay bundles (real turns
  with model, agent, faithfulness score, latency, capture time); the executed
  replays come from the durable :mod:`tessera.observability.replay_store`
  journal (written by ``POST /observability/replay`` — figures grow only when a
  replay truly runs); the baseline comparisons and regressions are computed
  from the REAL evaluation run history (run N vs run N-1 per agent: pass-rate
  deltas and the exact newly-failing cases, whose categories feed the deviation
  donuts); the per-service / per-model distributions and the activity feed come
  from the bundles. Metrics with no source (tokens, cost, shadow coverage,
  proof packs) render ``—``, never invented numbers.
* **DEMONSTRATION (``shadow_traffic`` synthetic signal):** the fleet-wide
  shadow-traffic mirroring and the evidence-export tallies describe a subsystem
  this build does not implement; those zones stay flagged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from tessera.observability.eval.report_paths import iter_report_files
from tessera.observability.eval_data import SMALLEST_MODEL
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.replay import recent_bundles
from tessera.observability.replay_store import load_replay_runs

__all__ = ["compute_replay_shadow_overview"]

_MIN_RUNS_FOR_DIFF = 2

# Localized free-text (fr, de, en). Ids/dates/models/enum keys verbatim.
_TR: dict[str, tuple[str, str, str]] = {
    "run_vs": ("Run {a} vs {b}", "Lauf {a} vs {b}", "Run {a} vs {b}"),
    "catalogue": ("catalogue {v}", "Katalog {v}", "catalogue {v}"),
    "pass_to_fail": ("réussi → échoué", "bestanden → fehlgeschlagen", "pass → fail"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


_SERVICE_COLOR = ["#60a5fa", "#f97316", "#a78bfa", "#34d399", "#fbbf24", "#64748b"]
_MODEL_COLOR = ["#60a5fa", "#a78bfa", "#f97316", "#34d399", "#64748b"]
_TYPE_COLOR = {
    "instruction": "#f97316",
    "hallucination": "#60a5fa",
    "toxicity": "#f472b6",
    "factual": "#a78bfa",
    "confidentiality": "#34d399",
    "robustness": "#fbbf24",
    "others": "#64748b",
}
_SEV_COLOR = {
    "critique": "#f87171",
    "eleve": "#fb923c",
    "moyen": "#fbbf24",
    "faible": "#60a5fa",
}

# Real eval-case category -> the page's deviation-type i18n key.
_CATEGORY_TYPE = {
    "hallucination": "hallucination",
    "citation_fabrication": "factual",
    "regulatory_misstatement": "factual",
    "overconfidence": "factual",
    "policy_violation": "instruction",
    "tool_misuse": "instruction",
    "prompt_injection": "robustness",
    "pii_leak": "confidentiality",
    "language_mixing": "others",
    "escalation_failure": "others",
}
# Category -> deviation severity (same urgency tiers as the triage queue).
_CATEGORY_SEV = {
    "prompt_injection": "critique",
    "pii_leak": "critique",
    "policy_violation": "eleve",
    "regulatory_misstatement": "eleve",
    "citation_fabrication": "eleve",
    "tool_misuse": "eleve",
    "hallucination": "moyen",
    "escalation_failure": "moyen",
    "overconfidence": "faible",
    "language_mixing": "faible",
}
_CRITICAL_DELTA = -0.10  # a recorded replay at or below this delta is a deviation
_TOP_DEVIATIONS = 10


def _kpi(
    key: str, value: str, delta_label: str, good_is_up: bool, series: list[int]
) -> dict[str, object]:
    return {
        "key": key,
        "value": value,
        "delta_label": delta_label,
        "good_is_up": good_is_up,
        "series": series,
    }


def _slug(value: str) -> str:
    """A next-intl-safe slice key (dots/colons would break message lookups)."""
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_") or "others"


def _slices(counts: dict[str, int], palette: list[str]) -> list[dict[str, object]]:
    total = sum(counts.values()) or 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    return [
        {
            "key": key,
            "count": count,
            "pct": round(count / total * 100),
            "color": palette[i % len(palette)],
        }
        for i, (key, count) in enumerate(ordered)
    ]


def _fmt_run(run_at: str) -> str:
    try:
        return datetime.strptime(run_at, "%Y%m%dT%H%M%SZ").strftime("%d/%m")
    except (ValueError, TypeError):
        return run_at[:8]


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class _RunDiff:
    """Run N vs run N-1 for one agent: real pass-rate delta + newly-failed cases."""

    __slots__ = ("agent_id", "catalogue", "newly_failed", "prev_at", "rates", "run_at", "total")

    def __init__(self, agent_id: str, runs: list[dict[str, Any]]) -> None:
        self.agent_id = agent_id
        latest, prev = runs[0], runs[1]
        self.run_at = str(latest.get("run_at", ""))
        self.prev_at = str(prev.get("run_at", ""))
        summary = _as_dict(latest.get("summary"))
        self.total = int(summary.get("total", 0) or 0)
        self.catalogue = str(latest.get("eval_set") or "")

        def _cases(payload: dict[str, Any]) -> dict[str, tuple[bool, str]]:
            out: dict[str, tuple[bool, str]] = {}
            sessions = payload.get("sessions")
            for row in sessions if isinstance(sessions, list) else []:
                if not isinstance(row, dict):
                    continue
                key = f"{row.get('case_id')}.{row.get('language')}"
                out[key] = (bool(row.get("passed")), str(row.get("category", "")))
            return out

        now_cases, prev_cases = _cases(latest), _cases(prev)
        self.newly_failed: list[tuple[str, str]] = [
            (key, category)
            for key, (passed, category) in now_cases.items()
            if not passed and prev_cases.get(key, (True, ""))[0]
        ]

        def _rate(payload: dict[str, Any]) -> float:
            s = _as_dict(payload.get("summary"))
            total = int(s.get("total", 0) or 0)
            return (int(s.get("passed", 0) or 0) / total) if total else 0.0

        self.rates = [_rate(r) for r in reversed(runs)]  # oldest -> newest

    def rate_delta_pt(self) -> float | None:
        """Latest-minus-previous pass rate, in points (None with < 2 runs)."""
        if len(self.rates) < _MIN_RUNS_FOR_DIFF:
            return None
        return (self.rates[-1] - self.rates[-2]) * 100


def _load_run_diffs() -> list[_RunDiff]:
    """Per-agent run diffs from the real eval reports (agents with >= 2 runs)."""
    by_agent: dict[str, dict[str, dict[str, Any]]] = {}
    for path in iter_report_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # best-effort: skip an unreadable/corrupt eval-report JSON — non-gating (0015)
            continue
        if not isinstance(payload, dict) or payload.get("model") != SMALLEST_MODEL:
            continue
        agent_id = str(payload.get("agent_id") or "")
        run_at = str(payload.get("run_at") or "")
        if not agent_id or not run_at:
            continue
        runs = by_agent.setdefault(agent_id, {})
        existing = runs.get(run_at)
        summary = _as_dict(payload.get("summary"))
        existing_total = 0
        if isinstance(existing, dict):
            existing_total = int(_as_dict(existing.get("summary")).get("total", 0) or 0)
        if existing is None or int(summary.get("total", 0) or 0) > existing_total:
            runs[run_at] = payload
    diffs: list[_RunDiff] = []
    for agent_id, runs in sorted(by_agent.items()):
        ordered = [runs[k] for k in sorted(runs, reverse=True)]
        if len(ordered) >= _MIN_RUNS_FOR_DIFF:
            diffs.append(_RunDiff(agent_id, ordered[:6]))
    return diffs


def _posture(
    now: datetime, bundles: list[Any], runs: list[dict[str, object]]
) -> tuple[list[str], list[int], list[dict[str, object]]]:
    """Real posture inputs: capture-day keys/series + the critical replay runs."""
    day_keys = [(now - timedelta(days=d)).date().isoformat() for d in range(6, -1, -1)]
    day_captured = dict.fromkeys(day_keys, 0)
    for b in bundles:
        try:
            captured = datetime.fromisoformat(b.captured_at)
        except (ValueError, TypeError):
            # best-effort: skip a bundle with a bad captured_at — non-gating posture (0015)
            continue
        key = captured.date().isoformat()
        if key in day_captured:
            day_captured[key] += 1
    critical_replays = []
    for r in runs:
        delta = r.get("score_delta")
        if isinstance(delta, int | float) and float(delta) <= _CRITICAL_DELTA:
            critical_replays.append(r)
    return day_keys, list(day_captured.values()), critical_replays


def compute_replay_shadow_overview(lang: str = "fr") -> dict[str, object]:
    """Return the Replay & shadow overview payload (real core + flagged demo).

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the replay posture KPIs, the captured
        bundles (sessions / distributions / activity), the executed-replay
        journal, the real run-to-run baseline comparisons and deviations — plus
        the flagged shadow/export fixtures.
    """
    lang = _norm_lang(lang)
    now = datetime.now(UTC)

    bundles = recent_bundles()
    runs = load_replay_runs()
    diffs = _load_run_diffs()

    day_keys, captured_series, critical_replays = _posture(now, bundles, runs)
    newly_failed_total = sum(len(d.newly_failed) for d in diffs)
    n_deviations = len(critical_replays) + newly_failed_total
    n_eval_runs = sum(len(d.rates) for d in diffs)

    kpis = [
        _kpi("sessions", str(len(bundles)), "0", True, captured_series or [0] * 7),
        _kpi("requests", str(len(runs)), "0", True, [len(runs)] * 7),
        _kpi("tokens", "—", "—", True, [0] * 7),
        _kpi("cost", "—", "—", False, [0] * 7),
        _kpi("deviations", str(n_deviations), "0", False, [n_deviations] * 7),
        _kpi("evals", str(n_eval_runs), "0", True, [n_eval_runs] * 7),
        _kpi("proofs", "—", "—", True, [0] * 7),
        _kpi("coverage", "—", "—", True, [0] * 7),
    ]

    replay_traffic = {
        "labels": [k[5:] for k in day_keys],
        "requests": captured_series,
        "tokens": [0] * len(captured_series),  # honest: bundles carry no token counts
    }

    # ── REAL deviations: newly-failed cases (run diff) + critical replays ────
    type_counts: dict[str, int] = {}
    sev_counts: dict[str, int] = {}
    for d in diffs:
        for _key, category in d.newly_failed:
            tkey = _CATEGORY_TYPE.get(category, "others")
            type_counts[tkey] = type_counts.get(tkey, 0) + 1
            sev = _CATEGORY_SEV.get(category, "moyen")
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
    if critical_replays:
        type_counts["factual"] = type_counts.get("factual", 0) + len(critical_replays)
        sev_counts["eleve"] = sev_counts.get("eleve", 0) + len(critical_replays)
    _type_total = sum(type_counts.values()) or 1
    deviation_by_type = [
        {
            "key": key,
            "count": count,
            "pct": round(count / _type_total * 100),
            "color": _TYPE_COLOR.get(key, _TYPE_COLOR["others"]),
        }
        for key, count in sorted(type_counts.items(), key=lambda kv: -kv[1])
    ]
    _sev_total = sum(sev_counts.values()) or 1
    deviation_severity = [
        {
            "key": key,
            "count": count,
            "pct": round(count / _sev_total * 100),
            "color": _SEV_COLOR[key],
        }
        for key, count in sorted(sev_counts.items(), key=lambda kv: -kv[1])
        if key in _SEV_COLOR
    ]

    # ── REAL sessions: the captured bundles (replayed ones marked) ──────────
    replayed_ids = {str(r.get("bundle_id", "")) for r in runs}
    recent_sessions = [
        {
            "id": b.bundle_id[:12],
            "service": b.agent_id,
            "model": b.original_model,
            "status": "rejouee" if b.bundle_id in replayed_ids else "termine",
            "origin": (b.captured_at or "")[:16].replace("T", " "),
        }
        for b in sorted(bundles, key=lambda x: x.captured_at, reverse=True)[:6]
    ]

    top_deviations: list[dict[str, object]] = [
        {
            "id": str(r.get("bundle_id", ""))[:12],
            "service": str(r.get("agent_id", "")),
            "type": "factual",
            "baseline": str(r.get("model", "")),
            "severity": "eleve",
            "delta": f"{float(r['score_delta']):+.2f}",  # type: ignore[arg-type]
        }
        for r in sorted(
            critical_replays,
            key=lambda r: float(r.get("score_delta", 0.0)),  # type: ignore[arg-type]
        )[:5]
    ]
    for d in diffs:
        for key, category in d.newly_failed[:5]:
            if len(top_deviations) >= _TOP_DEVIATIONS:
                break
            top_deviations.append(
                {
                    "id": key,
                    "service": d.agent_id,
                    "type": _CATEGORY_TYPE.get(category, "others"),
                    "baseline": _t("run_vs", lang).format(
                        a=_fmt_run(d.run_at), b=_fmt_run(d.prev_at)
                    ),
                    "severity": _CATEGORY_SEV.get(category, "moyen"),
                    "delta": _t("pass_to_fail", lang),
                }
            )

    # ── REAL baseline comparisons: run N vs N-1 per agent ───────────────────
    recent_comparisons = [
        {
            "label": f"{d.agent_id} · "
            + _t("run_vs", lang).format(a=_fmt_run(d.run_at), b=_fmt_run(d.prev_at)),
            "baseline": _t("catalogue", lang).format(v=d.catalogue or "—"),
            "sessions": str(d.total),
            "deviations": len(d.newly_failed),
        }
        for d in diffs
    ]
    top_regressions = [
        {
            "service": d.agent_id,
            "delta": f"{delta_pt:+.1f} pt" if delta_pt is not None else "—",
            "critical": sum(
                1 for _k, cat in d.newly_failed if _CATEGORY_SEV.get(cat) == "critique"
            ),
            "spark": [round(r * 100) for r in d.rates],
        }
        for d in sorted(diffs, key=lambda d: d.rate_delta_pt() or 0.0)
        for delta_pt in (d.rate_delta_pt(),)
    ]

    # ── REAL distributions from the bundles ──────────────────────────────────
    service_counts: dict[str, int] = {}
    model_counts: dict[str, int] = {}
    for b in bundles:
        skey = _slug(b.agent_id or "")
        mkey = _slug(b.original_model or "")
        service_counts[skey] = service_counts.get(skey, 0) + 1
        model_counts[mkey] = model_counts.get(mkey, 0) + 1
    by_service = _slices(service_counts, _SERVICE_COLOR)
    by_model = _slices(model_counts, _MODEL_COLOR)

    # ── REAL replayed-eval categories (newly-failed composition) ────────────
    evals_by_category = deviation_by_type

    # ── DEMONSTRATION: shadow/export subsystem (flagged in the frontend) ─────
    proofs_exports = {
        "generated": "—",
        "available": "—",
        "downloaded": "—",
        "total_size": "—",
        "last_export": "—",
    }

    baselines = [
        {
            "value": d.run_at,
            "label": f"{d.agent_id} · {_fmt_run(d.run_at)} ({d.catalogue or '—'})",
        }
        for d in diffs
    ]

    activity_feed = [
        {
            "id": b.bundle_id[:12],
            "time": (b.captured_at or "")[11:16],
            "status": "rejouee" if b.bundle_id in replayed_ids else "termine",
        }
        for b in sorted(bundles, key=lambda x: x.captured_at, reverse=True)[:7]
    ]

    from tessera.settings import get_settings

    services = sorted({str(b.agent_id or "") for b in bundles})
    return {
        "generated_at": now.isoformat(),
        "period_days": 7,
        "updated_at": now.strftime("%H:%M:%S"),
        "kpis": kpis,
        "replay_traffic": replay_traffic,
        "deviation_by_type": deviation_by_type,
        "deviation_total": n_deviations,
        "deviation_severity": deviation_severity,
        "recent_sessions": recent_sessions,
        "top_deviations": top_deviations,
        "recent_comparisons": recent_comparisons,
        "top_regressions": top_regressions,
        "by_service": by_service,
        "by_model": by_model,
        "requests_total": str(len(bundles)),
        "evals_by_category": evals_by_category,
        "proofs_exports": proofs_exports,
        "baselines": baselines,
        "services": services,
        "activity_feed": activity_feed,
        "footer": {
            "environment": get_settings().environment,
            "services": len(services),
            "active_users": "—",
            "confidence": "—",
            "source": "bundles · eval/reports · replay_runs.json",
        },
    }
