"""Governed eval-gate waivers — an S1, hash-chained, append-only event store.

A waiver (dérogation) is a **first-class governed object**, not a "non-blocking"
flag (eval-gate policy §5). Each grant/revoke is an append-only, hash-chained
event carrying the full governance envelope: justification, requester, approver
(separation of duties), scope, compensating controls, incident reference, and an
**expiry**. The store is the S1 substrate behind "État à date / opposable".

Effectiveness is **computed dynamically at render, never stored** (like the
opposability badge):

* A grant is *effective* only for its bound ``(case_id, language,
  candidate_version)`` — it **never carries over** to the next candidate run
  (``candidate_version`` is the evaluated run's stamp).
* **Auto-expiry → auto re-block**: past ``expires_at`` the waiver lapses and the
  case re-blocks, with no further action.
* A later ``revoke`` for the same target cancels the grant.
* A waiver on a **Tier 0** (non-dérogeable) case is **never effective** — it is
  surfaced as "sans effet (cœur non-dérogeable)", encoding ``T0 ∩ dérog = ∅``.

The store is intentionally model-agnostic and pure I/O so it can be unit-tested
and seeded without a database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from tessera.observability.eval_tiers import Tier, load_tier_map
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

__all__ = [
    "EffectiveWaiver",
    "WaiverEvent",
    "effective_waivers",
    "load_waiver_events",
    "record_waiver",
    "seed_demo_waivers",
    "verify_waiver_chain",
    "waivers_path",
]

_GENESIS_HASH = "0" * 64
_ALL_LANGS = "*"


def waivers_path() -> Path:
    """The durable JSONL store, next to the guard audit log (same S1 family)."""
    return get_settings().guard.audit_file.parent / "eval_waivers.jsonl"


@dataclass(frozen=True, slots=True)
class WaiverEvent:
    """One append-only governance event (a grant or a revoke)."""

    event_id: str
    action: str  # "grant" | "revoke"
    case_id: str
    language: str  # "fr" | "de" | "en" | "*"
    agent_id: str
    candidate_version: str
    justification: str
    requester: str
    requester_role: str
    approver: str
    approver_role: str
    scope: str
    compensating_controls: tuple[str, ...]
    incident_ref: str
    valid_from: str
    expires_at: str
    recorded_at: str
    prev_hash: str
    hash: str

    def targets(self, case_id: str, language: str, candidate_version: str) -> bool:
        """Whether this event governs a given ``(case, language, candidate)``."""
        if self.case_id != case_id or self.candidate_version != candidate_version:
            return False
        return self.language in (_ALL_LANGS, language)


@dataclass(frozen=True, slots=True)
class EffectiveWaiver:
    """A grant resolved against the current run + clock (status is derived)."""

    event: WaiverEvent
    tier: Tier
    status: str  # "active" | "expirée" | "révoquée" | "sans_effet_socle" | "autre_candidat"
    status_label: str
    active: bool


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash_core(core: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()


def _last_hash(events: list[WaiverEvent]) -> str:
    return events[-1].hash if events else _GENESIS_HASH


def _coerce_event(obj: Mapping[str, Any]) -> WaiverEvent | None:
    try:
        controls = obj.get("compensating_controls")
        return WaiverEvent(
            event_id=str(obj["event_id"]),
            action=str(obj["action"]),
            case_id=str(obj["case_id"]),
            language=str(obj.get("language", _ALL_LANGS)),
            agent_id=str(obj.get("agent_id", "")),
            candidate_version=str(obj.get("candidate_version", "")),
            justification=str(obj.get("justification", "")),
            requester=str(obj.get("requester", "")),
            requester_role=str(obj.get("requester_role", "")),
            approver=str(obj.get("approver", "")),
            approver_role=str(obj.get("approver_role", "")),
            scope=str(obj.get("scope", "")),
            compensating_controls=tuple(str(c) for c in controls)
            if isinstance(controls, list)
            else (),
            incident_ref=str(obj.get("incident_ref", "")),
            valid_from=str(obj.get("valid_from", "")),
            expires_at=str(obj.get("expires_at", "")),
            recorded_at=str(obj.get("recorded_at", "")),
            prev_hash=str(obj.get("prev_hash", _GENESIS_HASH)),
            hash=str(obj.get("hash", "")),
        )
    except (KeyError, TypeError):
        return None


def load_waiver_events() -> list[WaiverEvent]:
    """Read every waiver event in chain order (oldest first)."""
    path = waivers_path()
    if not path.exists():
        return []
    events: list[WaiverEvent] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            event = _coerce_event(obj)
            if event is not None:
                events.append(event)
    return events


def verify_waiver_chain() -> bool:
    """Recompute the hash chain end to end; any tamper breaks it."""
    prev = _GENESIS_HASH
    for event in load_waiver_events():
        core = _event_core(event, prev)
        if event.prev_hash != prev or event.hash != _hash_core(core):
            return False
        prev = event.hash
    return True


def _event_core(event: WaiverEvent, prev_hash: str) -> dict[str, Any]:
    """The hashed body of an event (everything except its own ``hash``)."""
    return {
        "type": "tessera.eval.waiver",
        "version": 1,
        "event_id": event.event_id,
        "action": event.action,
        "case_id": event.case_id,
        "language": event.language,
        "agent_id": event.agent_id,
        "candidate_version": event.candidate_version,
        "justification": event.justification,
        "requester": event.requester,
        "requester_role": event.requester_role,
        "approver": event.approver,
        "approver_role": event.approver_role,
        "scope": event.scope,
        "compensating_controls": list(event.compensating_controls),
        "incident_ref": event.incident_ref,
        "valid_from": event.valid_from,
        "expires_at": event.expires_at,
        "recorded_at": event.recorded_at,
        "prev_hash": prev_hash,
    }


def record_waiver(
    *,
    action: str,
    case_id: str,
    language: str,
    agent_id: str,
    candidate_version: str,
    justification: str,
    requester: str,
    requester_role: str,
    approver: str,
    approver_role: str,
    scope: str,
    compensating_controls: Iterable[str],
    incident_ref: str,
    expires_at: str,
    valid_from: str | None = None,
) -> WaiverEvent:
    """Append a governed waiver event, hash-chained onto the prior tail.

    Separation of duties is enforced structurally: the requester (eval owner)
    must differ from the approver. Returns the persisted event.

    Raises:
        ValueError: if requester == approver (no self-approval).
    """
    if requester and requester == approver:
        msg = "séparation des tâches : le demandeur ne peut pas être l'approbateur"
        raise ValueError(msg)
    events = load_waiver_events()
    prev = _last_hash(events)
    now = datetime.now(UTC).isoformat()
    stub = WaiverEvent(
        event_id=f"WV-{len(events) + 1:03d}",
        action=action,
        case_id=case_id,
        language=language,
        agent_id=agent_id,
        candidate_version=candidate_version,
        justification=justification,
        requester=requester,
        requester_role=requester_role,
        approver=approver,
        approver_role=approver_role,
        scope=scope,
        compensating_controls=tuple(compensating_controls),
        incident_ref=incident_ref,
        valid_from=valid_from or now,
        expires_at=expires_at,
        recorded_at=now,
        prev_hash=prev,
        hash="",
    )
    digest = _hash_core(_event_core(stub, prev))
    event = replace(stub, hash=digest)
    path = waivers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({**_event_core(event, prev), "hash": digest}, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")
    return event


def _parse_dt(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None


_STATUS_LABEL: dict[str, str] = {
    "active": "Dérogation active",
    "expirée": "Expirée — re-blocage auto",
    "révoquée": "Révoquée",
    "sans_effet_socle": "Sans effet (cœur non-dérogeable)",
    "autre_candidat": "Liée à un autre candidat",
}


def effective_waivers(
    candidate_version: str, *, now: datetime | None = None
) -> list[EffectiveWaiver]:
    """Resolve every grant against the current candidate + clock.

    A grant becomes a single :class:`EffectiveWaiver` with a *derived* status.
    Revokes cancel an earlier grant on the same ``(case, language, candidate)``.
    The Tier 0 rule is enforced here: a socle case is never ``active``.
    """
    clock = now or datetime.now(UTC)
    tiers = load_tier_map()
    events = load_waiver_events()
    revoked: set[tuple[str, str, str]] = {
        (e.case_id, e.language, e.candidate_version) for e in events if e.action == "revoke"
    }
    resolved: list[EffectiveWaiver] = []
    for event in events:
        if event.action != "grant":
            continue
        tier = tiers.tier_of(event.case_id)
        key = (event.case_id, event.language, event.candidate_version)
        if not tiers.waivable(tier):
            status = "sans_effet_socle"
        elif key in revoked:
            status = "révoquée"
        elif event.candidate_version != candidate_version:
            status = "autre_candidat"
        else:
            expiry = _parse_dt(event.expires_at)
            status = "expirée" if (expiry is not None and clock >= expiry) else "active"
        resolved.append(
            EffectiveWaiver(
                event=event,
                tier=tier,
                status=status,
                status_label=_STATUS_LABEL[status],
                active=status == "active",
            )
        )
    return resolved


def seed_demo_waivers(
    *,
    candidate_version: str,
    agent_id: str,
    failing_t1: list[tuple[str, str]],
    failing_t0: list[tuple[str, str]],
) -> int:
    """Seed realistic governed waivers idempotently; return the number written.

    ``failing_t1`` / ``failing_t0`` are the ``(case_id, language)`` failures in
    the current run, by tier. We grant two **active** T1 waivers (future expiry,
    compliance double-control), one **expired** T1 waiver (auto re-block demo),
    and one **Tier 0 attempt** that the store renders as "sans effet" — the
    ``T0 ∩ dérog = ∅`` invariant demonstrated with a real event, not prose.
    """
    existing = {
        (e.case_id, e.language, e.candidate_version, e.action) for e in load_waiver_events()
    }
    written = 0

    def grant(case_id: str, language: str, **kw: Any) -> None:
        nonlocal written
        if (case_id, language, candidate_version, "grant") in existing:
            return
        record_waiver(
            action="grant",
            case_id=case_id,
            language=language,
            agent_id=agent_id,
            candidate_version=candidate_version,
            **kw,
        )
        written += 1

    now = datetime.now(UTC).replace(microsecond=0)
    in_30d = (now + timedelta(days=30)).isoformat()
    in_14d = (now + timedelta(days=14)).isoformat()
    past_2d = (now - timedelta(days=2)).isoformat()
    short = candidate_version[:13]

    # 1. Active governed waiver on the first failing T1 case (future expiry).
    if failing_t1:
        case_id, language = failing_t1[0]
        grant(
            case_id,
            language,
            justification=(
                "Risque résiduel accepté pour la fenêtre de release : le correctif de "
                "garde-fou est planifié au prochain sprint ; l'exposition est contenue par "
                "les contrôles compensatoires ci-dessous."
            ),
            requester="M. Diallo",
            requester_role="ML Engineer (propriétaire éval)",
            approver="Mme Keita",
            approver_role="Compliance Officer (double-contrôle DORA/CNIL)",
            scope=f"{case_id} · {language} · candidat {short}",
            compensating_controls=[
                "Garde-fou runtime mcp-firewall en mode blocage sur ce motif",
                "Revue humaine obligatoire de toute action irréversible (HITL)",
                "Alerte temps-réel + plafond d'exposition journalier",
            ],
            incident_ref="RISK-2026-0142",
            expires_at=in_30d,
        )
    # 2. A second active waiver on a distinct T1 failure (shorter window).
    if len(failing_t1) > 1:
        case_id, language = failing_t1[1]
        grant(
            case_id,
            language,
            justification=(
                "Dérogation temporaire encadrée le temps d'enrichir le jeu d'évaluation ; "
                "cas reproduit en préprod uniquement, jamais observé en production."
            ),
            requester="M. Diallo",
            requester_role="ML Engineer (propriétaire éval)",
            approver="Mme Keita",
            approver_role="Compliance Officer (double-contrôle)",
            scope=f"{case_id} · {language} · candidat {short}",
            compensating_controls=[
                "Désactivation de l'outil concerné en production",
                "Journalisation renforcée + revue hebdomadaire",
            ],
            incident_ref="RISK-2026-0148",
            expires_at=in_14d,
        )
    # 3. An EXPIRED T1 waiver → auto re-block (status derived from the clock).
    _expired_slot = 2
    if len(failing_t1) > _expired_slot:
        case_id, language = failing_t1[_expired_slot]
        grant(
            case_id,
            language,
            justification=(
                "Dérogation arrivée à échéance : la fenêtre d'acceptation du risque est "
                "close ; le cas redevient bloquant automatiquement (re-blocage auto)."
            ),
            requester="M. Diallo",
            requester_role="ML Engineer (propriétaire éval)",
            approver="Mme Keita",
            approver_role="Compliance Officer",
            scope=f"{case_id} · {language} · candidat {short}",
            compensating_controls=["Contrôle compensatoire expiré avec la dérogation"],
            incident_ref="RISK-2026-0131",
            valid_from=(now - timedelta(days=16)).isoformat(),
            expires_at=past_2d,
        )
    # 4. Tier 0 attempt → "sans effet (cœur non-dérogeable)". Demonstrates the
    #    invariant: a waiver on the socle is recorded but never effective.
    if failing_t0:
        case_id, language = failing_t0[0]
        grant(
            case_id,
            language,
            justification=(
                "Demande de dérogation REFUSÉE par construction : cas du socle "
                "(Tier 0, PII / hard-stop). Aucune dérogation possible — conservé pour "
                "trace d'audit de la tentative."
            ),
            requester="M. Diallo",
            requester_role="ML Engineer (propriétaire éval)",
            approver="Mme Keita",
            approver_role="Compliance Officer",
            scope=f"{case_id} · {language} · candidat {short}",
            compensating_controls=[],
            incident_ref="RISK-2026-0150",
            expires_at=in_30d,
        )
    return written
