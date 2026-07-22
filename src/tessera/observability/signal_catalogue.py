"""Signal catalogue cockpit overview (configurer/signal-catalog).

The catalogue of the AI quality/safety **signals** Tessera actually monitors,
derived from real artifacts — never a fixture:

  * the failure-catalogue eval run (``observability.eval_data.load_eval_snapshot``)
    — every monitored category (hallucination, pii_leak, prompt_injection, …) is
    a signal whose live "quality" is its real pass rate, with real passed/total/
    failed counts, per-language distribution and run timestamp;
  * the shared guard policy (``guard.decisions.load_policy``) — the deny/PII/tool
    composition that enforces the safety signals, surfaced in the KPIs and in the
    detail of each guard-enforced signal.

Read-only by design: a signal is a derived governance fact (eval + policy), not a
UI-authored record, so there is no mutation endpoint (like Prompts). The page's
functional axis is real search / filter / sort / pagination / detail. Free-text is
localized fr/de/en (French keeps accents, German transliterates ae/oe/ue/ss, per
the sibling guardrail-catalogue convention); enum keys (status/severity/category/
source) and signal name slugs stay stable so the frontend localizes its own chrome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tessera.guard.decisions import load_policy
from tessera.observability.eval_data import load_eval_snapshot
from tessera.observability.knowledge import _LANG_IDX, _norm_lang

if TYPE_CHECKING:
    from tessera.guard.decisions import Policy
    from tessera.observability.eval_data import EvalSnapshot

__all__ = ["compute_signal_catalogue", "total_signals"]

# Eval category -> (taxonomy, severity, source, name slug, owner).
# Severity reflects business impact (not the current score); source marks whether
# the guard enforces it (Guard) or it is purely an eval-measured quality (Eval).
_TAXO: dict[str, tuple[str, str, str, str, str]] = {
    "pii_leak": ("securite", "critical", "Guard", "pii_leak_rate", "Privacy Team"),
    "prompt_injection": (
        "securite",
        "critical",
        "Guard",
        "prompt_injection_bypass",
        "Security Team",
    ),
    "hallucination": ("qualite", "high", "Eval", "hallucination_rate", "AI Quality Team"),
    "citation_fabrication": (
        "qualite",
        "high",
        "Eval",
        "citation_fabrication_rate",
        "AI Quality Team",
    ),
    "tool_misuse": ("securite", "high", "Guard", "tool_misuse_rate", "Security Team"),
    "policy_violation": ("conformite", "high", "Guard", "policy_violation_rate", "Compliance"),
    "regulatory_misstatement": (
        "conformite",
        "high",
        "Eval",
        "regulatory_error_rate",
        "Compliance",
    ),
    "overconfidence": ("qualite", "medium", "Eval", "overconfidence_rate", "AI Quality Team"),
    "language_mixing": ("qualite", "medium", "Eval", "language_routing_error", "AI Quality Team"),
    "escalation_failure": ("qualite", "medium", "Eval", "escalation_failure_rate", "Safety Team"),
}

# Per-category descriptions (fr accents / de ae-oe-ue-ss / en plain).
_DESC: dict[str, tuple[str, str, str]] = {
    "pii_leak": (
        "Fuite de données personnelles dans les sorties du modèle.",
        "Abfluss personenbezogener Daten in den Modellausgaben.",
        "Leak of personal data in the model's outputs.",
    ),
    "prompt_injection": (
        "Tentative de faire ignorer à l'agent les instructions qui le protègent.",
        "Versuch, den Agenten seine schützenden Anweisungen ignorieren zu lassen.",
        "Attempt to make the agent ignore the instructions that protect it.",
    ),
    "hallucination": (
        "Réponses qui ne sont pas appuyées par les sources retrouvées.",
        "Antworten, die nicht durch die gefundenen Quellen gestützt sind.",
        "Answers that are not supported by the sources found.",
    ),
    "citation_fabrication": (
        "Citations ou références fabriquées dans la réponse.",
        "Erfundene Zitate oder Referenzen in der Antwort.",
        "Fabricated citations or references in the answer.",
    ),
    "tool_misuse": (
        "Outil utilisé à mauvais escient ou sans autorisation.",
        "Werkzeug falsch oder ohne Berechtigung verwendet.",
        "Tool used incorrectly or without permission.",
    ),
    "policy_violation": (
        "Règle interne non respectée pendant une réponse ou une action.",
        "Interne Regel bei einer Antwort oder Aktion nicht eingehalten.",
        "Internal rule not followed during an answer or action.",
    ),
    "regulatory_misstatement": (
        "Affirmation réglementaire erronée (DORA / RGPD / BaFin).",
        "Falsche regulatorische Aussage (DORA / DSGVO / BaFin).",
        "Incorrect regulatory statement (DORA / GDPR / BaFin).",
    ),
    "overconfidence": (
        "Réponse ou action présentée comme certaine sans vérification suffisante.",
        "Antwort oder Aktion als sicher dargestellt, ohne ausreichende Prüfung.",
        "Answer or action presented as certain without enough verification.",
    ),
    "language_mixing": (
        "Mélange de langues ou mauvais routage de la langue de réponse.",
        "Sprachvermischung oder falsches Routing der Antwortsprache.",
        "Language mixing or wrong response-language routing.",
    ),
    "escalation_failure": (
        "Intervention humaine non demandée alors qu'elle était nécessaire.",
        "Menschliche Hilfe nicht angefordert, obwohl sie erforderlich war.",
        "Human help not requested when it was required.",
    ),
}

# Localized labels + fixed values (fr, de, en).
_TR: dict[str, tuple[str, str, str]] = {
    "l_source": ("Source", "Quelle", "Source"),
    "l_type": ("Type", "Typ", "Type"),
    "l_unit": ("Unité", "Einheit", "Unit"),
    "l_direction": ("Direction", "Richtung", "Direction"),
    "l_frequency": ("Fréquence", "Frequenz", "Frequency"),
    "l_environment": ("Environnement", "Umgebung", "Environment"),
    "l_pass_rate": ("Taux de réussite", "Erfolgsrate", "Pass rate"),
    "l_cases_passed": ("Cas réussis", "Bestandene Faelle", "Passed cases"),
    "l_cases_failed": ("Cas en échec", "Fehlgeschlagene Faelle", "Failed cases"),
    "l_model": ("Modèle évalué", "Geprüftes Modell", "Evaluated model"),
    "l_last_run": ("Dernière évaluation", "Letzte Prüfung", "Last evaluation"),
    "l_deny": ("Formes d'attaque bloquées", "Blockierte Angriffsformen", "Blocked attack patterns"),
    "l_pii": (
        "Types de données personnelles",
        "Arten personenbezogener Daten",
        "Personal-data types",
    ),
    "l_guarded_tools": ("Outils encadrés", "Eingeschraenkte Tools", "Guarded tools"),
    "l_policy_version": ("Version des règles", "Regelversion", "Rule version"),
    "source_guard": ("Contrôle en ligne", "Laufende Kontrolle", "Live check"),
    "source_eval": ("Évaluation", "Prüfung", "Evaluation"),
    "footer_source": (
        "Évaluation ({model}) et règles de contrôle",
        "Prüfung ({model}) und Kontrollregeln",
        "Evaluation ({model}) and control rules",
    ),
    "v_pass_rate": ("Taux de réussite", "Erfolgsrate", "Pass rate"),
    "v_higher_better": ("Plus haut est mieux", "Hoeher ist besser", "Higher is better"),
    "v_per_run": ("À chaque évaluation", "Bei jeder Prüfung", "At each evaluation"),
    "v_all_env": ("Tous (fr / de / en)", "Alle (fr / de / en)", "All (fr / de / en)"),
    "v_passed": ("Réussis", "Bestanden", "Passed"),
    "v_failed": ("Échecs", "Fehler", "Failed"),
    "sub_categories": (
        "catégories surveillées",
        "ueberwachte Kategorien",
        "monitored categories",
    ),
    "sub_share": ("{pct}% du total", "{pct}% des Gesamt", "{pct}% of total"),
    "u_cases": ("{n} cas", "{n} Faelle", "{n} cases"),
    "u_langs": ("{n} langues", "{n} Sprachen", "{n} languages"),
    "rt_now": ("à l'instant", "gerade eben", "just now"),
    "rt_days": ("il y a {n} j", "vor {n} T", "{n}d ago"),
    "rt_hours": ("il y a {n} h", "vor {n} Std", "{n}h ago"),
    "rt_min": ("il y a {n} min", "vor {n} Min", "{n}m ago"),
}

# Order signals worst-impact first, then by category for a stable catalogue.
_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_LANG_LABEL = {"fr": "FR", "de": "DE", "en": "EN"}
_MIN_CASES_ACTIVE = 8  # under-sampled categories show as "in evaluation", honestly.


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


def _desc(category: str, lang: str) -> str:
    return _DESC[category][_LANG_IDX.get(lang, 0)]


def _kpi(key: str, value: str, sub: str, series: list[int]) -> dict[str, object]:
    return {"key": key, "value": value, "sub": sub, "series": series}


def _aware(dt: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime so it can be compared to an aware now."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _relative(then: datetime | None, now: datetime, lang: str) -> str:
    """Honest localized relative-time label from a run timestamp to now."""
    then = _aware(then)
    if then is None:
        return "-"
    secs = int((now - then).total_seconds())
    if secs < 0:
        return _t("rt_now", lang)
    minutes, hours, days = secs // 60, secs // 3600, secs // 86400
    if days >= 1:
        return _t("rt_days", lang).format(n=days)
    if hours >= 1:
        return _t("rt_hours", lang).format(n=hours)
    if minutes >= 1:
        return _t("rt_min", lang).format(n=minutes)
    return _t("rt_now", lang)


def _pct(passed: int, total: int) -> int:
    return round(passed / total * 100) if total else 0


def _per_language(snapshot: EvalSnapshot, category: str) -> list[dict[str, object]]:
    """Real per-language case counts (passed/total) for one category."""
    out: list[dict[str, object]] = []
    for code, label in _LANG_LABEL.items():
        cases = [s for s in snapshot.sessions if s.category == category and s.language == code]
        if not cases:
            continue
        passed = sum(1 for s in cases if s.passed)
        out.append(
            {
                "label": label,
                "count": len(cases),
                "passed": passed,
                "color": "#34d399" if passed == len(cases) else "#fbbf24",
            }
        )
    return out


def _signal(
    snapshot: EvalSnapshot,
    policy: Policy,
    category: str,
    index: int,
    now: datetime,
    lang: str,
) -> dict[str, object]:
    taxo, severity, source, slug, owner = _TAXO[category]
    stat = snapshot.category(category)
    total = stat.total if stat else 0
    passed = stat.passed if stat else 0
    failed = total - passed
    quality = _pct(passed, total)
    status = "active" if total >= _MIN_CASES_ACTIVE else "evaluation"
    run_dt = snapshot.run_datetime()
    modified = run_dt.strftime("%d/%m/%Y") if run_dt else "-"
    per_lang = _per_language(snapshot, category)
    desc = _desc(category, lang)

    # Guard-enforced signals show the real policy composition that backs them.
    guard_rows: list[dict[str, str]] = []
    if source == "Guard":
        guard_rows = [
            {"label": _t("l_deny", lang), "value": str(len(policy.prompt_injection_deny))},
            {"label": _t("l_pii", lang), "value": str(len(policy.pii_patterns))},
            {"label": _t("l_guarded_tools", lang), "value": str(len(policy.tools))},
            {"label": _t("l_policy_version", lang), "value": f"v{policy.version}"},
        ]

    detail = {
        "id": f"SIG-{index:03d}",
        "name": slug,
        "category": taxo,
        "status": status,
        "severity": severity,
        "description": desc,
        "definition": [
            {
                "label": _t("l_source", lang),
                "value": _t("source_guard" if source == "Guard" else "source_eval", lang),
            },
            {"label": _t("l_type", lang), "value": _t("v_pass_rate", lang)},
            {"label": _t("l_unit", lang), "value": "%"},
            {"label": _t("l_direction", lang), "value": _t("v_higher_better", lang)},
            {"label": _t("l_frequency", lang), "value": _t("v_per_run", lang)},
            {"label": _t("l_environment", lang), "value": _t("v_all_env", lang)},
        ],
        "performance": [
            {"label": _t("l_pass_rate", lang), "value": f"{quality}%"},
            {"label": _t("l_cases_passed", lang), "value": f"{passed} / {total}"},
            {"label": _t("l_cases_failed", lang), "value": str(failed)},
            {"label": _t("l_model", lang), "value": snapshot.model},
            {"label": _t("l_last_run", lang), "value": modified},
        ],
        "guard": guard_rows,
        "distribution": per_lang,
        "outcome": [
            {"label": _t("v_passed", lang), "count": passed, "color": "#34d399"},
            {"label": _t("v_failed", lang), "count": failed, "color": "#f87171"},
        ],
        "tags": [taxo, severity, source.lower()],
        "usage": {
            "logged_by": _t("u_cases", lang).format(n=total),
            "monitors": _t("u_langs", lang).format(n=len(per_lang)),
        },
    }

    return {
        "id": f"SIG-{index:03d}",
        "name": slug,
        "category": taxo,
        "description": desc,
        "source": source,
        "severity": severity,
        "status": status,
        "quality": quality,
        "last_activity": _relative(run_dt, now, lang),
        "owner": owner,
        "modified": modified,
        "detail": detail,
    }


def _assemble(
    snapshot: EvalSnapshot, policy: Policy, now: datetime, lang: str
) -> dict[str, object]:
    """Pure assembler: build the catalogue payload from real eval + policy inputs."""
    lang = _norm_lang(lang)
    present = [c for c in _TAXO if snapshot.category(c) is not None]
    present.sort(key=lambda c: (_SEV_RANK[_TAXO[c][1]], _TAXO[c][0], c))
    signals = [
        _signal(snapshot, policy, category, idx, now, lang)
        for idx, category in enumerate(present, start=1)
    ]
    total = len(signals)

    by_status = {"active": 0, "evaluation": 0, "deprecated": 0, "disabled": 0}
    by_sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for s in signals:
        by_status[str(s["status"])] += 1
        by_sev[str(s["severity"])] += 1
    # A real distribution (the spread of signal quality) — not a faked time-series.
    quality_spread = sorted(
        _pct(stat.passed, stat.total) for c in present if (stat := snapshot.category(c)) is not None
    ) or [0]

    def share(n: int) -> str:
        return _t("sub_share", lang).format(pct=round(n / total * 100)) if total else "-"

    kpis = [
        _kpi("total", str(total), _t("sub_categories", lang), quality_spread),
        _kpi("active", str(by_status["active"]), share(by_status["active"]), quality_spread),
        _kpi(
            "evaluation",
            str(by_status["evaluation"]),
            share(by_status["evaluation"]),
            quality_spread,
        ),
        _kpi("deprecated", str(by_status["deprecated"]), share(by_status["deprecated"]), [0]),
        _kpi("disabled", str(by_status["disabled"]), share(by_status["disabled"]), [0]),
        _kpi("critical", str(by_sev["critical"]), share(by_sev["critical"]), quality_spread),
        _kpi("high", str(by_sev["high"]), share(by_sev["high"]), quality_spread),
        _kpi("medium", str(by_sev["medium"]), share(by_sev["medium"]), quality_spread),
        _kpi("low", str(by_sev["low"]), share(by_sev["low"]), [0]),
    ]

    sources = sorted({str(s["source"]) for s in signals})
    categories = sorted({str(s["category"]) for s in signals})
    run_dt = snapshot.run_datetime()
    return {
        "generated_at": now.isoformat(),
        "total_signals": total,
        "page_size": 10,
        "kpis": kpis,
        "signals": signals,
        "categories": categories,
        "sources": sources,
        "footer": {
            "total": total,
            "source": _t("footer_source", lang).format(model=snapshot.model),
        },
        "run_at": run_dt.strftime("%d/%m/%Y") if run_dt else "-",
    }


def compute_signal_catalogue(lang: str = "fr") -> dict[str, object]:
    """Return the full Signal catalogue overview payload from real sources.

    Args:
        lang: UI language (``fr`` / ``de`` / ``en``) for the localized free-text.

    Returns:
        A JSON-serialisable mapping with the catalogue posture KPIs, the signal
        table (one row per monitored eval category, each carrying its real detail)
        and the catalogue provenance — all derived from the live eval run and the
        shared guard policy.
    """
    snapshot = load_eval_snapshot(None)
    policy = load_policy()
    return _assemble(snapshot, policy, datetime.now(UTC), lang)


def total_signals() -> int:
    """How many signals the catalogue actually monitors — one per present eval category.

    The sidebar badge asks this rather than assembling the whole page, and asks *this*
    rather than counting on its own: the two must agree by construction. The badge used to
    read ``200`` while the catalogue held ten.
    """
    snapshot = load_eval_snapshot(None)
    return sum(1 for category in _TAXO if snapshot.category(category) is not None)
