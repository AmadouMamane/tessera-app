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

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from tessera.observability.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG = get_logger("tessera.observability.chrome")

#: Tone vocabulary shared by badges and notifications. ``danger`` means an SLA or an
#: integrity guarantee is already broken; ``warning`` means it is about to be.
Tone = Literal["danger", "warning", "neutral"]

__all__ = ["compute_chrome"]


def _t(key: str, lang: str) -> str:
    fr, de, en = _STRINGS[key]
    return {"fr": fr, "de": de, "en": en}.get(lang, fr)


_STRINGS: dict[str, tuple[str, str, str]] = {
    "n_pending": (
        "{n} élément(s) en attente de validation",
        "{n} Element(e) warten auf Freigabe",
        "{n} item(s) awaiting validation",
    ),
    "n_overdue": (
        "{n} élément(s) hors délai",
        "{n} Element(e) über der Frist",
        "{n} item(s) past their deadline",
    ),
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

#: A seal that was never configured is the shipped default (``NoOpSealProvider``), not a
#: degradation — alerting on it would teach the operator to ignore the bell. These three
#: states each mean a seal exists and no longer backs the ledger it claims to.
_DEGRADED_SEAL_STATES = frozenset({"stale", "divergent", "unverifiable"})


def _operator_items() -> Sequence[Any]:
    """The queue behind both À traiter and À faire — read once, counted twice."""
    from tessera.observability.operator_items import load_items

    return load_items()


def _queue_badges(now: datetime) -> dict[str, dict[str, object]]:
    """À traiter and À faire, counted from the queue their pages list.

    ``a_traiter`` mirrors the inbox page's ``total_items`` (every item); ``a_faire``
    mirrors its own page's open items. The tone is the queue's SLA verdict, not a
    number-size heuristic: red once an open item is past its declared due time, amber
    while one is inside the warning window the domain itself defines.
    """
    try:
        items = _operator_items()
    except Exception:  # a cockpit chrome never crashes the page it decorates
        LOG.warning("chrome.operator_items_unreadable")
        return {}

    open_items = [item for item in items if item.status != "done"]
    overdue = [item for item in open_items if item.overdue(now)]
    warning = [item for item in open_items if item.sla_tone(now) == "warn"]

    tone: Tone = "danger" if overdue else ("warning" if warning else "neutral")
    badges: dict[str, dict[str, object]] = {}
    if items:
        badges["a_traiter"] = {"count": len(items), "tone": tone}
    if open_items:
        badges["a_faire"] = {"count": len(open_items), "tone": tone}
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
                "href": "/prouver/etat-a-date",
                "tone": "danger",
            }
        )
    if seal_state in _DEGRADED_SEAL_STATES:
        notifications.append(
            {
                "id": "ledger:seal",
                "label": _t("seal_degraded", lang).format(state=seal_state),
                "href": "/prouver/etat-a-date",
                "tone": "warning",
            }
        )
    return notifications


def _queue_notifications(lang: str, now: datetime) -> list[dict[str, object]]:
    """Work waiting on a human: what is open, and what has already blown its SLA."""
    try:
        items = _operator_items()
    except Exception:
        return []
    open_items = [item for item in items if item.status != "done"]
    if not open_items:
        return []

    notifications: list[dict[str, object]] = [
        {
            "id": "queue:pending",
            "label": _t("n_pending", lang).format(n=len(open_items)),
            "href": "/a-traiter",
            "tone": "warning",
        }
    ]
    overdue = [item for item in open_items if item.overdue(now)]
    if overdue:
        notifications.append(
            {
                "id": "queue:overdue",
                "label": _t("n_overdue", lang).format(n=len(overdue)),
                "href": "/a-traiter",
                "tone": "danger",
            }
        )
    return notifications


def compute_chrome(lang: str = "fr") -> dict[str, object]:
    """Badges and notifications for the cockpit chrome, composed from existing reads.

    No new store, no new fact: every number below is produced by the function that also
    produces the page it deep-links to. An unreadable source contributes nothing rather
    than a zero — the chrome then shows less, never something false.

    Args:
        lang: Locale for the notification sentences. Badge counts are language-free.

    Returns:
        ``badges``: id → ``{count, tone}``, present only where a real count exists.
        ``notifications``: ``{count, items}``, each item deep-linking to where the act is
        performed. A ``count`` of zero means the bell shows no dot.
    """
    now = datetime.now(UTC)

    badges = _queue_badges(now)
    if incidents := _incidents_badge():
        badges["incidents"] = incidents
    if curation := _curation_badge():
        badges["curation"] = curation
    if signal_catalog := _signal_catalog_badge():
        badges["signal_catalog"] = signal_catalog

    items = [
        *_queue_notifications(lang, now),
        *_canary_notifications(lang),
        *_ledger_notifications(lang),
    ]
    return {
        "badges": badges,
        "notifications": {"count": len(items), "items": items},
    }
