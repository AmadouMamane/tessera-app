"""Client-space (Produit) datasets for the customer-facing pages.

The customer space exposes four leaves that were previously scaffolds:

* **Documents** — the customer's available banking documentation, sourced for
  real from the Crédit Aurore corpus (``tessera.corpus.data``): every unique
  ``source`` in the active-locale product corpus is one document, with its title,
  category and excerpt derived from the real chunk text. This is genuine data,
  not a fixture.
* **Mes demandes** — the customer's support requests (escalation tickets). A
  realistic, deterministic seed for the demo customer; the schema mirrors the
  :class:`tessera.agent.tools.ticket_escalate.Ticket` the agent actually opens.
* **Alertes** — account notifications. Deterministic seed plus a durable
  read-state overlay so "marquer comme lu" is a real, surviving mutation.
* **Paramètres** — the customer's preferences and GDPR rights, persisted to the
  same durable store so every toggle survives a reload.

The durable parts live in ``client_space.json`` next to the guard audit log,
mirroring :mod:`tessera.observability.console_feedback`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from importlib import resources
from typing import TYPE_CHECKING

from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "compute_alerts",
    "compute_documents",
    "compute_requests",
    "compute_settings",
    "mark_alert_read",
    "update_setting",
]

# ── document taxonomy ────────────────────────────────────────────────────────

# Map the corpus path segment to a stable category key (locale-independent).
_CATEGORY_KEYS = {
    "produits": "products",
    "produkte": "products",
    "products": "products",
    "conditions": "terms",
    "bedingungen": "terms",
    "procedures": "procedures",
    "prozeduren": "procedures",
    "programme": "services",
    "programm": "services",
    "program": "services",
    "service": "services",
    "kundenservice": "services",
    "services": "services",
}
_CATEGORY_COLOR = {
    "products": "#60a5fa",
    "terms": "#a78bfa",
    "procedures": "#34d399",
    "services": "#fbbf24",
    "other": "#f472b6",
}
# Character budget for the table excerpt before an ellipsis.
_EXCERPT_LEN = 240
# A corpus source like ``credit-aurore/produits/compte-courant`` needs at least
# this many ``/`` segments for the middle one to be a real category.
_MIN_DOC_SEGMENTS = 3


def _humanise(slug: str) -> str:
    """Turn a corpus slug (``carte-visa-premier``) into a title."""
    return slug.replace("-", " ").replace("_", " ").strip().capitalize()


def _load_corpus(locale: str) -> list[dict[str, object]]:
    name = f"credit_aurore_{locale}.json"
    package = resources.files("tessera.corpus.data")
    entry = package / name
    if not entry.is_file():
        entry = package / "credit_aurore_fr.json"
    payload = json.loads(entry.read_text(encoding="utf-8"))
    return [item for item in payload if isinstance(item, dict)]


def compute_documents(locale: str = "fr") -> dict[str, object]:
    """Return the customer documents payload from the real product corpus.

    Args:
        locale: Active UI locale (``fr`` / ``de`` / ``en``); selects the corpus
            file and therefore the customer's document language.

    Returns:
        A JSON-serialisable mapping with KPIs, a category distribution and the
        document table — every row traced to a real corpus ``source``.
    """
    locale = locale if locale in {"fr", "de", "en"} else "fr"
    docs = _load_corpus(locale)

    rows: list[dict[str, object]] = []
    for idx, doc in enumerate(sorted(docs, key=lambda d: str(d.get("source", "")))):
        source = str(doc.get("source", ""))
        text = str(doc.get("text", "")).strip()
        parts = source.split("/")
        seg = parts[1] if len(parts) >= _MIN_DOC_SEGMENTS else "other"
        category = _CATEGORY_KEYS.get(seg, "other")
        slug = parts[-1] if parts else source
        size_kb = max(1, round(len(text.encode("utf-8")) / 1024))
        rows.append(
            {
                "id": f"DOC-{idx + 1:03d}",
                "title": _humanise(slug),
                "category": category,
                "language": locale.upper(),
                "source": source,
                "excerpt": text[:_EXCERPT_LEN] + ("…" if len(text) > _EXCERPT_LEN else ""),
                "body": text,
                "size_kb": size_kb,
                "pages": max(1, round(len(text) / 1800)),
                # The corpus is generated/translated as a batch; use a stable
                # reference date so the page never "dances".
                "updated": "12/06/2026",
            }
        )

    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[str(r["category"])] = by_cat.get(str(r["category"]), 0) + 1
    total = len(rows) or 1
    distribution = [
        {
            "key": k,
            "count": v,
            "pct": round(v / total * 100),
            "color": _CATEGORY_COLOR.get(k, _CATEGORY_COLOR["other"]),
        }
        for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])
    ]

    kpis = [
        {"key": "total", "value": str(len(rows)), "sub": "documents disponibles"},
        {"key": "products", "value": str(by_cat.get("products", 0)), "sub": "fiches produit"},
        {"key": "terms", "value": str(by_cat.get("terms", 0)), "sub": "conditions & contrats"},
        {"key": "procedures", "value": str(by_cat.get("procedures", 0)), "sub": "procédures"},
    ]

    return {
        "kpis": kpis,
        "distribution": distribution,
        "documents": rows,
        "footer": {"total": len(rows), "source": "Corpus Crédit Aurore (pgvector)"},
    }


# ── durable store ────────────────────────────────────────────────────────────


def _state_path() -> Path:
    return get_settings().guard.audit_file.parent / "client_space.json"


def _load_state() -> dict[str, object]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(state: dict[str, object]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )


def _read_alert_ids(state: dict[str, object]) -> set[str]:
    """Return the set of alert ids marked read in the durable store."""
    raw = state.get("alerts_read")
    return {str(x) for x in raw} if isinstance(raw, list) else set()


def _settings_dict(state: dict[str, object]) -> dict[str, object]:
    """Return the stored settings mapping (empty if absent/malformed)."""
    raw = state.get("settings")
    return dict(raw) if isinstance(raw, dict) else {}


# ── requests (support tickets) ───────────────────────────────────────────────

_REQUESTS = [
    {
        "reference": "TS-7F3A2C9D11",
        "subject": "Opposition carte Visa Premier",
        "category": "card",
        "channel": "phone",
        "status": "resolved",
        "opened": "03/06/2026 09:12",
        "updated": "03/06/2026 09:48",
        "summary": (
            "Demande d'opposition immédiate suite à la perte de la carte Visa Premier. "
            "Carte bloquée et réémission programmée sous 5 jours ouvrés."
        ),
    },
    {
        "reference": "TS-2B9E14A7C0",
        "subject": "Simulation prêt immobilier 180 000 €",
        "category": "loan",
        "channel": "email",
        "status": "in_progress",
        "opened": "08/06/2026 14:30",
        "updated": "10/06/2026 11:05",
        "summary": (
            "Étude d'un crédit immobilier sur 20 ans. Pièces justificatives reçues, "
            "dossier transmis au conseiller pour validation du taux."
        ),
    },
    {
        "reference": "TS-55C1D8F2A3",
        "subject": "Contestation prélèvement SEPA",
        "category": "dispute",
        "channel": "branch",
        "status": "open",
        "opened": "11/06/2026 16:22",
        "updated": "11/06/2026 16:22",
        "summary": (
            "Contestation d'un prélèvement de 49,90 € non reconnu. "
            "Procédure de remboursement SEPA en cours d'ouverture."
        ),
    },
    {
        "reference": "TS-A07B33E6F4",
        "subject": "Augmentation plafond de retrait",
        "category": "account",
        "channel": "phone",
        "status": "resolved",
        "opened": "29/05/2026 10:40",
        "updated": "29/05/2026 10:55",
        "summary": (
            "Relèvement temporaire du plafond de retrait à 1 500 € / semaine "
            "accordé pour un déplacement à l'étranger."
        ),
    },
    {
        "reference": "TS-9D4C71B0E8",
        "subject": "Activation alertes SMS solde",
        "category": "account",
        "channel": "email",
        "status": "resolved",
        "opened": "21/05/2026 08:05",
        "updated": "21/05/2026 08:09",
        "summary": "Activation des alertes SMS de solde sous le seuil de 50 €.",
    },
]


def compute_requests() -> dict[str, object]:
    """Return the customer's support requests (escalation tickets)."""
    rows = list(_REQUESTS)
    counts = {"open": 0, "in_progress": 0, "resolved": 0}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    kpis = [
        {"key": "total", "value": str(len(rows)), "sub": "demandes au total"},
        {"key": "open", "value": str(counts["open"]), "sub": "en attente"},
        {"key": "in_progress", "value": str(counts["in_progress"]), "sub": "en cours"},
        {"key": "resolved", "value": str(counts["resolved"]), "sub": "résolues"},
    ]
    return {
        "kpis": kpis,
        "requests": rows,
        "footer": {"total": len(rows), "source": "File d'escalade — tickets agent"},
    }


# ── alerts ───────────────────────────────────────────────────────────────────

_ALERTS = [
    {
        "id": "AL-1001",
        "title": "Relevé de compte disponible",
        "category": "statement",
        "severity": "info",
        "date": "12/06/2026 06:00",
        "body": "Votre relevé du Compte Courant Aurore de mai 2026 est disponible "
        "dans vos documents.",
    },
    {
        "id": "AL-1002",
        "title": "Échéance de prêt à venir",
        "category": "payment",
        "severity": "warning",
        "date": "11/06/2026 09:30",
        "body": "L'échéance de votre crédit consommation (312,40 €) sera prélevée "
        "le 15/06/2026.",
    },
    {
        "id": "AL-1003",
        "title": "Nouvelle connexion détectée",
        "category": "security",
        "severity": "warning",
        "date": "10/06/2026 21:14",
        "body": "Une connexion à votre espace a été détectée depuis un nouvel "
        "appareil (Paris, FR). Si ce n'était pas vous, contactez-nous.",
    },
    {
        "id": "AL-1004",
        "title": "Plafond carte bientôt atteint",
        "category": "card",
        "severity": "info",
        "date": "09/06/2026 13:45",
        "body": "Vous avez utilisé 1 820 € sur votre plafond mensuel de 2 000 € "
        "de la carte Visa Premier.",
    },
    {
        "id": "AL-1005",
        "title": "Authentification forte activée",
        "category": "security",
        "severity": "success",
        "date": "02/06/2026 18:02",
        "body": "L'authentification forte DSP2 a été activée sur votre compte.",
    },
]


def compute_alerts() -> dict[str, object]:
    """Return account alerts with the durable read-state applied."""
    read = _read_alert_ids(_load_state())
    rows = [{**a, "read": a["id"] in read} for a in _ALERTS]
    unread = sum(1 for r in rows if not r["read"])
    kpis = [
        {"key": "total", "value": str(len(rows)), "sub": "notifications"},
        {"key": "unread", "value": str(unread), "sub": "non lues"},
        {
            "key": "security",
            "value": str(sum(1 for a in _ALERTS if a["category"] == "security")),
            "sub": "sécurité",
        },
    ]
    return {
        "kpis": kpis,
        "alerts": rows,
        "footer": {"total": len(rows), "source": "Notifications compte"},
    }


def mark_alert_read(alert_id: str, *, read: bool) -> dict[str, object]:
    """Persist the read/unread state of one alert and return the alerts payload."""
    state = _load_state()
    current = _read_alert_ids(state)
    valid = {a["id"] for a in _ALERTS}
    if alert_id in valid:
        if read:
            current.add(alert_id)
        else:
            current.discard(alert_id)
    state["alerts_read"] = sorted(current)
    _save_state(state)
    return compute_alerts()


# ── settings ─────────────────────────────────────────────────────────────────

_DEFAULT_SETTINGS: dict[str, object] = {
    "language": "fr",
    "notify_email": True,
    "notify_sms": True,
    "notify_push": False,
    "consent_marketing": False,
    "consent_cookies": True,
    "consent_data_sharing": False,
    "strong_auth": True,
}
_BOOL_KEYS = frozenset(k for k, v in _DEFAULT_SETTINGS.items() if isinstance(v, bool))


def compute_settings() -> dict[str, object]:
    """Return the customer's preferences merged over the defaults."""
    stored = _load_state().get("settings")
    merged = dict(_DEFAULT_SETTINGS)
    if isinstance(stored, dict):
        for k in merged:
            if k in stored:
                merged[k] = stored[k]
    groups = [
        {
            "key": "notifications",
            "items": ["notify_email", "notify_sms", "notify_push"],
        },
        {
            "key": "privacy",
            "items": ["consent_marketing", "consent_cookies", "consent_data_sharing"],
        },
        {"key": "security", "items": ["strong_auth"]},
    ]
    return {
        "values": merged,
        "groups": groups,
        "languages": ["fr", "de", "en"],
        "updated_at": _load_state().get("settings_updated_at", "—"),
        "footer": {"source": "Préférences client (RGPD)"},
    }


def update_setting(key: str, value: object) -> dict[str, object]:
    """Persist one preference and return the full settings payload.

    Boolean keys accept any truthy/falsy value; ``language`` accepts a locale
    code. Unknown keys are ignored so the endpoint can't be used to write
    arbitrary state.
    """
    if key not in _DEFAULT_SETTINGS:
        return compute_settings()
    state = _load_state()
    settings = _settings_dict(state)
    if key in _BOOL_KEYS:
        settings[key] = bool(value)
    elif key == "language" and value in {"fr", "de", "en"}:
        settings[key] = str(value)
    state["settings"] = settings
    state["settings_updated_at"] = datetime.now(UTC).strftime("%d/%m/%Y %H:%M")
    _save_state(state)
    return compute_settings()
