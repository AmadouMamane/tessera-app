"""The cockpit chrome's numbers — each one a measured fact with a page behind it.

A number in the chrome is a promise. A sidebar badge says "this page holds that many
things"; the bell says "that many things want you". Until now both lied by construction:
five badges (24 / 8 / 52 / 11 / 6) and the bell's 7 were literals typed into TSX, and no
count anywhere in the product could ever have made them true.

The rule this module exists to enforce: **a displayed number is a real count of the same
source the page it points at reads, or there is no number at all.** Honest-empty means the
badge disappears — never a decorative ``0``, which reads as "checked, nothing there" when
the truth is "never looked".

Two consequences worth stating.

*Single source of truth, not a second opinion.* Every count here comes from the very
function the destination page uses (``load_items``, ``decision_counts``, the incidents
core). A badge computed from a parallel query would drift from its page the day one of
them changed, and the drift would be silent.

*Tones are derived, never assigned.* The queue's own SLA rule (``OperatorItem.overdue`` /
``sla_tone``, hours declared in the domain) decides whether À traiter is red; the incident
core's own severity decides whether Incidents is. Nothing in the chrome invents a
threshold, which is why there is no threshold constant below that a page does not already
honour.

**Qualité IA carries no badge.** Its page exposes no count of outstanding things — the 52
it used to show was not a rounded, stale or approximate number, it was a decoration. It is
absent here rather than replaced, and that absence is the point.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Literal

from tessera.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG = get_logger("tessera.observability.chrome")

#: "argument not supplied" — distinct from a supplied ``None`` (a precomputed read that
#: FAILED). ``compute_chrome`` reads the shared operator-items halves ONCE and passes them
#: (or ``None`` on failure) to both queue helpers; a standalone caller passes nothing and the
#: helper reads them itself, unchanged.
_UNSET: Final = object()

#: Tone vocabulary shared by badges and notifications. ``danger`` means an SLA or an
#: integrity guarantee is already broken; ``warning`` means it is about to be.
Tone = Literal["danger", "warning", "neutral"]

#: Single-flight + short-TTL memo for the whole chrome result (ADR 0044 follow-up). The bell
#: hangs on ALL 32 cockpit pages and is IDENTICAL for every viewer at a given moment, yet every
#: page load fired its own six-read fan-out — and each fan-out spawns a 6-thread pool, so under
#: the page's own ~14 concurrent requests (times N operators, times N workers) the chrome threads
#: thrash the worker's GIL and postgres. Browser-measured end-to-end this was the #1 settle-variance
#: driver (1.6 s typical, 7.6 s under contention through the tunnel). The memo collapses a burst
#: of chrome requests — rapid navigation between pages, the 15 s client poll, several operators —
#: to ONE compute per worker per window. The TTL is short: the counts (incidents, pending
#: validations, curation) stay fresh well inside the client's own 15 s poll interval, and the SLA
#: tones can lag at most this long — imperceptible for a header bell.
_CHROME_TTL_S: Final = 3.0
_chrome_lock = threading.Lock()
_chrome_cache: dict[str, tuple[float, dict[str, object]]] = {}

__all__ = ["compute_chrome", "reset_chrome_cache"]


def reset_chrome_cache() -> None:
    """Drop the memoised chrome result (tests, and any caller that must force a recompute)."""
    with _chrome_lock:
        _chrome_cache.clear()


def _t(key: str, lang: str) -> str:
    fr, de, en = _STRINGS[key]
    return {"fr": fr, "de": de, "en": en}.get(lang, fr)


_STRINGS: dict[str, tuple[str, str, str]] = {
    "canary_red": (
        "Canary en échec : {agent}",
        "Canary fehlgeschlagen: {agent}",
        "Canary failing: {agent}",
    ),
    "integrity_broken": (
        "Intégrité du registre d'audit non vérifiée",
        "Integritaet des Audit-Registers nicht verifiziert",
        "Audit ledger integrity unverified",
    ),
    "seal_degraded": (
        "Sceau d'opposabilité dégradé ({state})",
        "Opposabilitaetssiegel beeintraechtigt ({state})",
        "Opposability seal degraded ({state})",
    ),
}

_COUNT_STRINGS: dict[str, tuple[tuple[str, str], tuple[str, str], tuple[str, str]]] = {
    "n_pending": (
        ("Une validation attend votre décision", "{n} validations attendent votre décision"),
        (
            "Eine Freigabe wartet auf Ihre Entscheidung",
            "{n} Freigaben warten auf Ihre Entscheidung",
        ),
        (
            "One approval is waiting for your decision",
            "{n} approvals are waiting for your decision",
        ),
    ),
    "n_overdue": (
        ("Une validation a dépassé son délai", "{n} validations ont dépassé leur délai"),
        ("Eine Freigabe ist überfällig", "{n} Freigaben sind überfällig"),
        ("One approval is past its deadline", "{n} approvals are past their deadline"),
    ),
    "n_pending_eval": (
        ("Une évaluation doit être revue", "{n} évaluations doivent être revues"),
        ("Eine Evaluierung muss geprüft werden", "{n} Evaluierungen müssen geprüft werden"),
        ("One evaluation needs review", "{n} evaluations need review"),
    ),
    "n_overdue_eval": (
        ("Une évaluation a dépassé son délai", "{n} évaluations ont dépassé leur délai"),
        ("Eine Evaluierung ist überfällig", "{n} Evaluierungen sind überfällig"),
        ("One evaluation is past its deadline", "{n} evaluations are past their deadline"),
    ),
}


def _counted_t(key: str, n: int, lang: str) -> str:
    """Return human singular/plural chrome copy without ``item(s)`` placeholders."""
    fr, de, en = _COUNT_STRINGS[key]
    singular, plural = {"fr": fr, "de": de, "en": en}.get(lang, fr)
    return (singular if n == 1 else plural).format(n=n)


#: A seal that was never configured is the shipped default (``NoOpSealProvider``), not a
#: degradation — alerting on it would teach the operator to ignore the bell. These three
#: states each mean a seal exists and no longer backs the ledger it claims to.
_DEGRADED_SEAL_STATES = frozenset({"stale", "divergent", "unverifiable"})


def _queue_halves() -> dict[str, list[Any]]:
    """The queue behind À traiter and À faire — read once, partitioned by nature.

    ADR 0038: the two pages serve disjoint halves of the backlog, so every
    chrome number derived from it must count ONE half — the one its page lists.
    """
    from tessera.observability.operator_items import load_items, partition_items

    return partition_items(load_items())


def _half_tone(items: Sequence[Any], now: datetime) -> Tone:
    """One half's SLA verdict: red past due, amber inside the warning window."""
    open_items = [item for item in items if item.status != "done"]
    if any(item.overdue(now) for item in open_items):
        return "danger"
    if any(item.sla_tone(now) == "warn" for item in open_items):
        return "warning"
    return "neutral"


def _queue_badges(now: datetime, halves: Any = _UNSET) -> dict[str, dict[str, object]]:
    """À traiter and À faire, each counted from the half its page lists (ADR 0038).

    ``a_traiter`` mirrors the inbox page's ``total_items`` (its business items);
    ``a_faire`` mirrors its own page's open eval items. The tone is each half's
    own SLA verdict, not a number-size heuristic: red once one of ITS open items
    is past its declared due time, amber while one is inside the warning window
    the domain itself defines.

    ``halves`` may be supplied precomputed (``compute_chrome`` reads it once for both queue
    surfaces); ``None`` means that shared read failed → no badges. Omitted → read it here.
    """
    from tessera.observability.operator_items import NATURE_A_FAIRE, NATURE_A_TRAITER

    if halves is _UNSET:
        try:
            halves = _queue_halves()
        except Exception:  # a cockpit chrome never crashes the page it decorates
            LOG.warning("chrome.operator_items_unreadable")
            return {}
    if halves is None:  # a precomputed read that failed
        return {}

    badges: dict[str, dict[str, object]] = {}
    a_traiter = halves[NATURE_A_TRAITER]
    if a_traiter:
        badges["a_traiter"] = {"count": len(a_traiter), "tone": _half_tone(a_traiter, now)}
    a_faire_open = [item for item in halves[NATURE_A_FAIRE] if item.status != "done"]
    if a_faire_open:
        badges["a_faire"] = {"count": len(a_faire_open), "tone": _half_tone(a_faire_open, now)}
    return badges


def _incidents_badge() -> dict[str, object] | None:
    """Open incidents, from the same core the incidents page renders."""
    try:
        from tessera.observability.incidents import open_incidents

        count, critical = open_incidents()
    except Exception:
        LOG.warning("chrome.incidents_unreadable")
        return None
    if not count:
        return None
    return {"count": count, "tone": "danger" if critical else "warning"}


def _curation_badge() -> dict[str, object] | None:
    """Eval-set candidates still awaiting a decision — the page's own ``pending`` KPI."""
    try:
        from tessera.observability.curation_store import decision_counts

        pending = decision_counts().get("pending", 0)
    except Exception:
        LOG.warning("chrome.curation_unreadable")
        return None
    if not pending:
        return None
    return {"count": pending, "tone": "warning"}


def _signal_catalog_badge() -> dict[str, object] | None:
    """How many signals the catalogue monitors — a fact, not a round number.

    This badge read ``200`` while `total_signals()` returned ten. It was not stale: no
    version of the product ever monitored two hundred signals. Neutral tone: a catalogue
    with entries in it is not a problem, it is the platform working.
    """
    try:
        from tessera.observability.signal_catalogue import total_signals

        total = total_signals()
    except Exception:
        LOG.warning("chrome.signal_catalogue_unreadable")
        return None
    if not total:
        return None
    return {"count": total, "tone": "neutral"}


def _canary_notifications(lang: str) -> list[dict[str, object]]:
    """One notification per agent whose latest canary invocation came back red.

    The canary already writes a durable S1 verdict per run; nothing new is stored here.
    A green canary, or an agent that never ran one, produces nothing.

    ONE query for the whole fleet. This bell hangs in the header of all 32 cockpit pages, and it
    used to ask the question once per agent — each ask loading all 29 600 ledger entries into
    memory. The header alone was six full ledger reads, on every page load.
    """
    notifications: list[dict[str, object]] = []
    try:
        from tessera.agent.registry import list_agents
        from tessera.observability.quality_nets import latest_canary_verdicts

        verdicts = latest_canary_verdicts()
    except Exception:  # an unreadable ledger must not silence the bell (0015)
        LOG.warning("chrome.canary_unreadable")
        return notifications

    for agent in list_agents():
        if verdicts.get(agent.id) == "red":
            notifications.append(
                {
                    "id": f"canary:{agent.id}",
                    "label": _t("canary_red", lang).format(agent=agent.name),
                    "count": 1,
                    "href": "/surveiller/observabilite",
                    "tone": "danger",
                }
            )
    return notifications


def _ledger_notifications(lang: str) -> list[dict[str, object]]:
    """Ledger integrity and seal posture — the two facts État à date already proves.

    Two cheap reads, not one expensive one. The bell hangs in the header of all 32 cockpit pages
    and it used to call ``active_ledger_opposability`` — the FULL opposability verdict, 29 600
    rows re-hashed in Python, on every page load — to ask two yes/no questions. It now asks the
    incremental verdict for the chain and the typed seal facet for the posture. Neither
    materialises the chain, and neither claims more than the bell needs.
    """
    notifications: list[dict[str, object]] = []
    try:
        from tessera.guard.ledger_checkpoint import active_ledger_verdict
        from tessera.guard.seal import active_ledger_seal_status

        content_integrity = active_ledger_verdict().tree.content_integrity
        seal_state = active_ledger_seal_status().state
    except Exception:
        LOG.warning("chrome.opposability_unreadable")
        return notifications

    if not content_integrity:
        notifications.append(
            {
                "id": "ledger:integrity",
                "label": _t("integrity_broken", lang),
                "count": 1,
                "href": "/prouver/etat-a-date",
                "tone": "danger",
            }
        )
    if seal_state in _DEGRADED_SEAL_STATES:
        notifications.append(
            {
                "id": "ledger:seal",
                "label": _t("seal_degraded", lang).format(state=seal_state),
                "count": 1,
                "href": "/prouver/etat-a-date",
                "tone": "warning",
            }
        )
    return notifications


def _queue_notifications(lang: str, now: datetime, halves: Any = _UNSET) -> list[dict[str, object]]:
    """Work waiting on a human — each row counted from the page it links to.

    ADR 0038: the pending/overdue rows that deep-link to ``/a-traiter`` count
    the business half only; the eval half gets its own rows towards ``/a-faire``.
    A row counting the union while linking to one page would be a number whose
    page cannot make it true — the exact lie this module exists to prevent.

    ``halves`` shares ``compute_chrome``'s single operator-items read (``None`` = that read
    failed → no rows); omitted → read it here.
    """
    from tessera.observability.operator_items import NATURE_A_FAIRE, NATURE_A_TRAITER

    if halves is _UNSET:
        try:
            halves = _queue_halves()
        except Exception:
            return []
    if halves is None:  # a precomputed read that failed
        return []

    notifications: list[dict[str, object]] = []
    for nature, href, pending_key, overdue_key in (
        (NATURE_A_TRAITER, "/a-traiter", "n_pending", "n_overdue"),
        (NATURE_A_FAIRE, "/a-faire", "n_pending_eval", "n_overdue_eval"),
    ):
        open_items = [item for item in halves[nature] if item.status != "done"]
        if not open_items:
            continue
        notifications.append(
            {
                "id": f"queue:pending:{nature}",
                "label": _counted_t(pending_key, len(open_items), lang),
                "count": len(open_items),
                "href": href,
                "tone": "warning",
            }
        )
        overdue = [item for item in open_items if item.overdue(now)]
        if overdue:
            notifications.append(
                {
                    "id": f"queue:overdue:{nature}",
                    "label": _counted_t(overdue_key, len(overdue), lang),
                    "count": len(overdue),
                    "href": href,
                    "tone": "danger",
                }
            )
    return notifications


def compute_chrome(lang: str = "fr") -> dict[str, object]:
    """Badges and notifications for the cockpit chrome, memoised per language (single-flight).

    Delegates to :func:`_compute_chrome_uncached`, but serves a result computed within the last
    ``_CHROME_TTL_S`` seconds instead of recomputing. A cache hit is lock-free (an immutable
    tuple read under the GIL); a miss takes ``_chrome_lock`` so a burst of concurrent callers
    for the same language yields exactly ONE fan-out (the rest wait, then read the fresh value)
    rather than N six-thread fan-outs contending on the worker's GIL. See ``_chrome_cache``.

    Args:
        lang: Locale for the notification sentences. Badge counts are language-free.

    Returns:
        ``badges``: id → ``{count, tone}``, present only where a real count exists.
        ``notifications``: ``{count, items}``, each item deep-linking to where the act is
        performed. A ``count`` of zero means the bell shows no dot.
    """
    cached = _chrome_cache.get(lang)
    if cached is not None and time.monotonic() - cached[0] < _CHROME_TTL_S:
        return cached[1]
    with _chrome_lock:
        # Double-check under the lock: a caller that raced us here may have just refreshed it.
        cached = _chrome_cache.get(lang)
        if cached is not None and time.monotonic() - cached[0] < _CHROME_TTL_S:
            return cached[1]
        result = _compute_chrome_uncached(lang)
        _chrome_cache[lang] = (time.monotonic(), result)
        return result


def _compute_chrome_uncached(lang: str = "fr") -> dict[str, object]:
    """Compose the chrome from existing reads, with no caching (the cold path of the memo).

    No new store, no new fact: every number below is produced by the function that also
    produces the page it deep-links to. An unreadable source contributes nothing rather
    than a zero — the chrome then shows less, never something false.
    """
    now = datetime.now(UTC)

    # This bell hangs on all 32 cockpit pages, and its reads are INDEPENDENT — the incident
    # core alone is ~440 ms. They share no mutable state (each opens its own connection), so
    # run them concurrently and assemble the result in the SAME order: byte-identical output,
    # bounded by the slowest read instead of their sum. The operator-items read feeds BOTH the
    # queue badges and the queue notifications, so it happens ONCE here, not twice.
    def _safe_halves() -> Any:
        try:
            return _queue_halves()
        except Exception:  # a cockpit chrome never crashes the page it decorates
            LOG.warning("chrome.operator_items_unreadable")
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        f_halves = pool.submit(_safe_halves)
        f_incidents = pool.submit(_incidents_badge)
        f_curation = pool.submit(_curation_badge)
        f_signal = pool.submit(_signal_catalog_badge)
        f_canary = pool.submit(_canary_notifications, lang)
        f_ledger = pool.submit(_ledger_notifications, lang)

        halves = f_halves.result()
        badges = _queue_badges(now, halves)
        if incidents := f_incidents.result():
            badges["incidents"] = incidents
        if curation := f_curation.result():
            badges["curation"] = curation
        if signal_catalog := f_signal.result():
            badges["signal_catalog"] = signal_catalog

        items = [
            *_queue_notifications(lang, now, halves),
            *f_canary.result(),
            *f_ledger.result(),
        ]
    return {
        "badges": badges,
        "notifications": {"count": len(items), "items": items},
    }
