"""CONFIGURER model catalogue (configurer/modeles) — the real LLM model layer.

A first-class catalogue block, like Sources & memoire for knowledge: the LLM
models the agent layer can bind, read from the *real* configuration and price
table, never invented. Each model carries its provider, role (chat/embedding),
the active-profile status, indicative pricing (``tessera.llm.budget``), limits
and dimension, plus the agents that consume it (``catalogue_consumers``) and the
re-gate blast radius of changing it (define -> consumers -> re-validate).

Real sources:
  * ``Settings`` (vertex / ollama / openai) — the configured models + the active
    profile (which model actually serves now);
  * ``tessera.llm.budget._PRICES`` — the indicative EUR/million-token tariff;
  * ``tessera.llm.budget.get_budget_tracker`` — real cumulative tokens + cost;
  * ``catalogue_consumers("model")`` — the consuming agents + their gate verdict.

Free-text is localized (fr/de/en); enum keys (provider/role/status) stay stable.
"""

from __future__ import annotations

from decimal import Decimal

from tessera.llm.budget import _PRICES, get_budget_tracker
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.settings import LLMProfile, get_settings

__all__ = ["available_model_ids", "build_model_catalogue"]

_LANG = _LANG_IDX

_TR: dict[str, tuple[str, str, str]] = {
    "subtitle": (
        "Les modèles LLM que les agents peuvent lier (config + tarif réels).",
        "Die LLM-Modelle, die Agenten binden koennen (reale Konfig + Tarif).",
        "The LLM models agents can bind (real config + tariff).",
    ),
    "kpi_models": ("Modèles au catalogue", "Modelle im Katalog", "Catalogued models"),
    "kpi_chat": ("Modèle chat actif", "Aktives Chat-Modell", "Active chat model"),
    "kpi_embed": ("Modèle d'embedding actif", "Aktives Embedding-Modell", "Active embedding model"),
    "kpi_profile": ("Profil actif", "Aktives Profil", "Active profile"),
    "kpi_tokens": ("Tokens cumulés", "Kumulierte Tokens", "Cumulative tokens"),
    "kpi_cost": ("Coût cumulé", "Kumulierte Kosten", "Cumulative cost"),
    "col_model": ("Modèle", "Modell", "Model"),
    "col_provider": ("Fournisseur", "Anbieter", "Provider"),
    "col_role": ("Rôle", "Rolle", "Role"),
    "col_status": ("Statut", "Status", "Status"),
    "col_price": ("Tarif (entrée/sortie)", "Tarif (Ein/Aus)", "Tariff (in/out)"),
    "col_usedby": ("Utilisé par", "Verwendet von", "Used by"),
    "role_chat": ("Chat", "Chat", "Chat"),
    "role_embedding": ("Embedding", "Embedding", "Embedding"),
    "st_active": ("Actif", "Aktiv", "Active"),
    "st_available": ("Disponible", "Verfuegbar", "Available"),
    "free": ("On-prem (0 EUR)", "On-prem (0 EUR)", "On-prem (EUR 0)"),
    "per_m": ("/M tokens", "/M Tokens", "/M tokens"),
    "sec_overview": ("Définition", "Definition", "Definition"),
    "sec_pricing": ("Tarification", "Preisgestaltung", "Pricing"),
    "sec_usage": ("Usage", "Nutzung", "Usage"),
    "l_provider": ("Fournisseur", "Anbieter", "Provider"),
    "l_role": ("Rôle", "Rolle", "Role"),
    "l_status": ("Statut", "Status", "Status"),
    "l_version": ("Version (tag du modèle)", "Version (Modell-Tag)", "Version (model tag)"),
    "l_dim": ("Dimension d'embedding", "Embedding-Dimension", "Embedding dimension"),
    "l_maxout": ("Sortie max (tokens)", "Max. Ausgabe (Tokens)", "Max output (tokens)"),
    "l_source": ("Source de config", "Konfigurationsquelle", "Config source"),
    "l_price_in": ("Entrée", "Eingabe", "Input"),
    "l_price_out": ("Sortie", "Ausgabe", "Output"),
    "l_tokens": ("Tokens cumulés (process)", "Kumulierte Tokens (Prozess)", "Cumulative tokens"),
    "l_cost": ("Coût cumulé (process)", "Kumulierte Kosten (Prozess)", "Cumulative cost"),
    "ub_title": ("Utilisé par", "Verwendet von", "Used by"),
    "ub_none": ("Aucun agent", "Kein Agent", "No agent"),
    "ub_regate": ("{n} à re-valider", "{n} neu zu validieren", "{n} to re-validate"),
    "ub_revalidate": (
        "Re-valider les consommateurs",
        "Konsumenten neu validieren",
        "Re-validate consumers",
    ),
    "ub_note": (
        "Changer le modèle d'un agent re-gate ce produit (define -> consommateurs -> "
        "re-valider). La pastille = verdict eval-gate actuel.",
        "Das Modell eines Agenten zu aendern re-gated dieses Produkt. Der Punkt = "
        "aktuelles Eval-Gate-Verdikt.",
        "Changing an agent's model re-gates that product (define -> consumers -> "
        "re-validate). The dot = current eval-gate verdict.",
    ),
    "note": (
        "Catalogue dérivé de la configuration active et du tarif indicatif "
        "(tessera.llm.budget). Aucun chiffre inventé.",
        "Katalog aus aktiver Konfiguration + indikativem Tarif (tessera.llm.budget). "
        "Keine erfundenen Zahlen.",
        "Catalogue derived from the active config + indicative tariff "
        "(tessera.llm.budget). No invented figures.",
    ),
    "src_settings": (
        "Settings (env / Secret Manager)",
        "Settings (env / Secret Manager)",
        "Settings (env / Secret Manager)",
    ),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG.get(lang, 0)]


def _fmt_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _fmt_eur(value: Decimal) -> str:
    return f"EUR {value:.4f}" if value else "EUR 0"


def _provider_label(provider: str) -> str:
    return {"vertex-ai": "Vertex AI", "ollama": "Ollama", "openai": "OpenAI"}.get(
        provider, provider
    )


def available_model_ids() -> set[str]:
    """Known model ids in the catalogue (for endpoint validation)."""
    settings = get_settings()
    ids = {m for _, m in _PRICES}
    ids.add(settings.ollama.chat_model)
    ids.add(settings.ollama.embedding_model)
    ids.add(settings.vertex.embedding_model)
    ids.update(settings.openai.models)
    return ids


class _Model:
    """One catalogue model definition assembled from real config + price table."""

    __slots__ = ("dim", "max_out", "model_id", "price", "provider", "role")

    def __init__(
        self,
        model_id: str,
        provider: str,
        role: str,
        *,
        price: object = None,
        dim: int | None = None,
        max_out: int | None = None,
    ) -> None:
        self.model_id = model_id
        self.provider = provider
        self.role = role
        self.price = price
        self.dim = dim
        self.max_out = max_out


def _catalogue_models() -> list[_Model]:
    """The real model set: priced models (budget table) + the configured models."""
    settings = get_settings()
    models: dict[str, _Model] = {}

    # 1. Every priced model (chat) from the indicative tariff table.
    for (provider, model_id), price in _PRICES.items():
        models[model_id] = _Model(model_id, provider, "chat", price=price)

    # 2. The configured chat models (may be unpriced on-prem dev models).
    models.setdefault(
        settings.ollama.chat_model, _Model(settings.ollama.chat_model, "ollama", "chat")
    )
    models.setdefault(
        settings.vertex.chat_model, _Model(settings.vertex.chat_model, "vertex-ai", "chat")
    )
    for openai_model in settings.openai.models:
        models.setdefault(openai_model, _Model(openai_model, "openai", "chat"))
    # vertex max output is a real configured limit on its chat model.
    if settings.vertex.chat_model in models:
        models[settings.vertex.chat_model].max_out = settings.vertex.max_output_tokens

    # 3. The two embedding models (real dimension).
    models[settings.ollama.embedding_model] = _Model(
        settings.ollama.embedding_model,
        "ollama",
        "embedding",
        dim=settings.ollama.embedding_dimension,
    )
    models[settings.vertex.embedding_model] = _Model(
        settings.vertex.embedding_model,
        "vertex-ai",
        "embedding",
        dim=settings.vertex.embedding_dimension,
    )
    return sorted(models.values(), key=lambda m: (m.role, m.provider, m.model_id))


def _active_ids() -> tuple[str, str]:
    """The (chat, embedding) model ids that actually serve under the active profile."""
    settings = get_settings()
    frontier = settings.resolved_llm_profile() is LLMProfile.FRONTIER
    chat = settings.vertex.chat_model if frontier else settings.ollama.chat_model
    embed = settings.vertex.embedding_model if frontier else settings.ollama.embedding_model
    return chat, embed


def build_model_catalogue(lang: str = "fr", *, agent_scope: str = "all") -> dict[str, object]:
    """Assemble the model-catalogue payload from the real config + price table."""
    lang = _norm_lang(lang)
    settings = get_settings()
    snap = get_budget_tracker().snapshot()
    consumers = _consumers_index(agent_scope)
    active_chat, active_embed = _active_ids()
    profile = settings.resolved_llm_profile().value

    models = _catalogue_models()
    rows: list[dict[str, object]] = []
    for m in models:
        active = (m.role == "chat" and m.model_id == active_chat) or (
            m.role == "embedding" and m.model_id == active_embed
        )
        cons = consumers.get(m.model_id, [])
        rows.append(_model_row(m, active=active, consumers=cons, lang=lang))

    return {
        "subtitle": _t("subtitle", lang),
        "kpis": _kpis(rows, active_chat, active_embed, profile, snap, lang),
        "columns": [
            _t("col_model", lang),
            _t("col_provider", lang),
            _t("col_role", lang),
            _t("col_status", lang),
            _t("col_price", lang),
            _t("col_usedby", lang),
        ],
        "models": rows,
        "note": _t("note", lang),
    }


def _consumers_index(agent_scope: str) -> dict[str, list[dict[str, object]]]:
    """Per-model consuming agents (with gate verdict), from catalogue_consumers."""
    try:
        from tessera.observability.catalogue_consumers import catalogue_consumers

        data = catalogue_consumers("model", agent_scope=agent_scope)
    except Exception:  # registry/release unavailable - degrade to empty
        return {}
    index: dict[str, list[dict[str, object]]] = {}
    items = data.get("items")
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        cons: list[dict[str, object]] = []
        raw_consumers = item.get("consumers")
        for con in raw_consumers if isinstance(raw_consumers, list) else []:
            if not isinstance(con, dict):
                continue
            rel_raw = con.get("release")
            rel = rel_raw if isinstance(rel_raw, dict) else {}
            cons.append(
                {
                    "agent_id": str(con.get("agent_id", "")),
                    "name": str(con.get("name", con.get("agent_id", ""))),
                    "tone": str(rel.get("verdict_tone", "muted")),
                    "label": str(rel.get("verdict_label", "")),
                    "passed": bool(rel.get("passed", False)),
                }
            )
        index[str(item.get("item", ""))] = cons
    return index


def _price_str(m: _Model, lang: str) -> str:
    price = m.price
    if price is None:
        return _t("free", lang) if m.provider == "ollama" else "-"
    pin = getattr(price, "eur_per_million_input", None)
    pout = getattr(price, "eur_per_million_output", None)
    if pin == 0 and pout == 0:
        return _t("free", lang)
    return f"EUR {pin} / EUR {pout} {_t('per_m', lang)}"


def _model_row(
    m: _Model, *, active: bool, consumers: list[dict[str, object]], lang: str
) -> dict[str, object]:
    regate = sum(1 for c in consumers if not c.get("passed", False))
    return {
        "id": m.model_id,
        "name": m.model_id,
        "provider": m.provider,
        "provider_label": _provider_label(m.provider),
        "role": m.role,
        "role_label": _t("role_chat" if m.role == "chat" else "role_embedding", lang),
        "status": "active" if active else "available",
        "status_label": _t("st_active" if active else "st_available", lang),
        "price": _price_str(m, lang),
        "used_by": str(len(consumers)),
        "used_by_count": len(consumers),
        "consumer_ids": [str(c["agent_id"]) for c in consumers],
        "detail": _model_detail(m, active=active, consumers=consumers, regate=regate, lang=lang),
    }


def _model_detail(
    m: _Model, *, active: bool, consumers: list[dict[str, object]], regate: int, lang: str
) -> dict[str, object]:
    snap = get_budget_tracker().snapshot()
    price = m.price
    pin = getattr(price, "eur_per_million_input", None) if price is not None else None
    pout = getattr(price, "eur_per_million_output", None) if price is not None else None
    overview = [
        {"label": _t("l_provider", lang), "value": _provider_label(m.provider)},
        {
            "label": _t("l_role", lang),
            "value": _t("role_chat" if m.role == "chat" else "role_embedding", lang),
        },
        {"label": _t("l_version", lang), "value": m.model_id},
        {
            "label": _t("l_status", lang),
            "value": _t("st_active" if active else "st_available", lang),
        },
        {"label": _t("l_source", lang), "value": _t("src_settings", lang)},
    ]
    if m.dim is not None:
        overview.append({"label": _t("l_dim", lang), "value": str(m.dim)})
    if m.max_out is not None:
        overview.append({"label": _t("l_maxout", lang), "value": _fmt_int(m.max_out)})
    pricing = [
        {
            "label": _t("l_price_in", lang),
            "value": f"EUR {pin} {_t('per_m', lang)}" if pin is not None else _t("free", lang),
        },
        {
            "label": _t("l_price_out", lang),
            "value": f"EUR {pout} {_t('per_m', lang)}" if pout is not None else _t("free", lang),
        },
    ]
    usage = [
        {
            "label": _t("l_tokens", lang),
            "value": _fmt_int(snap.input_tokens + snap.output_tokens)
            if active and m.role == "chat"
            else "-",
        },
        {
            "label": _t("l_cost", lang),
            "value": _fmt_eur(snap.estimated_cost_eur) if active and m.role == "chat" else "-",
        },
    ]
    return {
        "id": m.model_id,
        "name": m.model_id,
        "status": "active" if active else "available",
        "sections": [
            {"key": "overview", "title": _t("sec_overview", lang), "rows": overview},
            {"key": "pricing", "title": _t("sec_pricing", lang), "rows": pricing},
            {"key": "usage", "title": _t("sec_usage", lang), "rows": usage},
        ],
        "consumers": {
            "title": _t("ub_title", lang),
            "count": len(consumers),
            "regate_count": regate,
            "regate_label": _t("ub_regate", lang).format(n=regate) if regate else "",
            "revalidate_label": _t("ub_revalidate", lang),
            "empty": _t("ub_none", lang),
            "note": _t("ub_note", lang),
            "items": consumers,
        },
    }


def _kpi(key: str, label: str, value: str) -> dict[str, object]:
    return {"key": key, "label": label, "value": value}


def _kpis(
    rows: list[dict[str, object]],
    active_chat: str,
    active_embed: str,
    profile: str,
    snap: object,
    lang: str,
) -> list[dict[str, object]]:
    tokens = getattr(snap, "input_tokens", 0) + getattr(snap, "output_tokens", 0)
    cost = getattr(snap, "estimated_cost_eur", Decimal(0))
    return [
        _kpi("models", _t("kpi_models", lang), str(len(rows))),
        _kpi("chat", _t("kpi_chat", lang), active_chat),
        _kpi("embed", _t("kpi_embed", lang), active_embed),
        _kpi("profile", _t("kpi_profile", lang), profile),
        _kpi("tokens", _t("kpi_tokens", lang), _fmt_int(tokens)),
        _kpi(
            "cost",
            _t("kpi_cost", lang),
            _fmt_eur(cost if isinstance(cost, Decimal) else Decimal(0)),
        ),
    ]
