"""Agent Console (Debug) payload (reference image agent-console-normative).

The endpoint exposes the operator-facing debug context for the live chat
console. Static-looking labels are still derived from source-of-truth files:
runtime settings, guard policy, prompt/corpus files, and durable eval/replay
telemetry. The chat itself streams through the same `/chat` route as the client
product console; debug details for each turn are attached to the SSE final
envelope by `tessera.api.routes.chat`.

ADR 0019 §I2 — the Console is a *generated* surface: its shape is derived from the
agent's declared ``invocation.binding``, never a per-agent assumption. An agent whose
binding is ``in_process_chat`` gets today's interactive console (parity, no behaviour
change); a publish-only agent (``binding: none``) gets an honest-empty descriptor —
*"this agent exposes no test invocation — observe it through its runs and evals"* —
never a broken chat over fabricated config panels. The binding is read through the
boundary-allowed registry seam (ADR 0017 §1: ``tessera.agent.registry`` is a permitted
manifest import, the runtime graph is not).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tessera.agent.identity import DEFAULT_AGENT_ID
from tessera.agent.registry import Agent, InvocationBinding, get_agent, load_input_schema
from tessera.guard.decisions import load_policy
from tessera.observability.knowledge import _LANG_IDX, _norm_lang
from tessera.observability.spine.adapters import read_scores
from tessera.settings import LLMProfile, get_settings

__all__ = ["capability_forms", "compute_agent_console"]

# Localized free-text (fr, de, en). Proper nouns (Tessera, Prompt/Sources labels
# that double as tab keys are localized below) handled explicitly.
_TR: dict[str, tuple[str, str, str]] = {
    "ep_title": ("Évaluation automatique", "Automatische Bewertung", "Automatic evaluation"),
    "ep_note": (
        "Dernier run d'évaluation — la console ne ré-évalue pas chaque tour.",
        "Letzter Bewertungslauf - die Konsole bewertet nicht jeden Tour neu.",
        "Latest evaluation run - the console does not re-evaluate each turn.",
    ),
    "ep_cta": ("Voir les évaluations", "Bewertungen ansehen", "View evaluations"),
    "m_faith": ("Fidélité", "Treue", "Faithfulness"),
    "m_ground": ("Ancrage", "Verankerung", "Grounding"),
    "m_hallu": ("Hallucination", "Halluzination", "Hallucination"),
    "tool_allowed": ("Autorisé", "Erlaubt", "Allowed"),
    "tools_title": (
        "Outils disponibles ({n})",
        "Verfuegbare Tools ({n})",
        "Available tools ({n})",
    ),
    "gd_deny_detail": (
        "Patterns deny chargés depuis la policy runtime.",
        "Deny-Patterns aus der Laufzeit-Policy geladen.",
        "Deny patterns loaded from the runtime policy.",
    ),
    "gd_pii_detail": (
        "Patterns PII chargés depuis la policy runtime.",
        "PII-Patterns aus der Laufzeit-Policy geladen.",
        "PII patterns loaded from the runtime policy.",
    ),
    "gd_title": (
        "Garde-fous chargés ({n})",
        "Geladene Guardrails ({n})",
        "Loaded guardrails ({n})",
    ),
    "lbl_guard": ("Garde-fous", "Guardrails", "Guardrails"),
    "tab_tools": ("Outils", "Tools", "Tools"),
    "tab_eval": ("Évaluation", "Bewertung", "Evaluation"),
    "footer_started": (
        "Session ouverte à {t}",
        "Sitzung geoeffnet um {t}",
        "Session opened at {t}",
    ),
    "lang_name": ("Français", "Deutsch", "English"),
    "placeholder": (
        "Posez votre question à l'assistant...",
        "Stellen Sie Ihre Frage an den Assistenten...",
        "Ask the assistant your question...",
    ),
    "fb_useful": ("Utile", "Nuetzlich", "Useful"),
    "fb_notuseful": ("Pas utile", "Nicht nuetzlich", "Not useful"),
    "fa_replay": ("Rejouer cette session", "Diese Sitzung wiederholen", "Replay this session"),
    "fa_compare": (
        "Comparer à la version actuelle",
        "Mit aktueller Version vergleichen",
        "Compare to current version",
    ),
    "fa_export": ("Exporter la session", "Sitzung exportieren", "Export session"),
    "fa_close": ("Clôturer la session", "Sitzung schliessen", "Close session"),
    "timeline_incidents": ("Timeline incidents", "Vorfall-Timeline", "Incident timeline"),
    "new_session": ("Nouvelle session", "Neue Sitzung", "New session"),
    "replay": ("Relire à T", "Bei T abspielen", "Replay at T"),
    "title": ("Conversation de test", "Testkonversation", "Test conversation"),
    "subtitle": (
        "Interagissez avec l'assistant et observez en détail les traces, "
        "sources, outils et garde-fous.",
        "Interagieren Sie mit dem Assistenten und beobachten Sie Traces, Quellen, "
        "Tools und Guardrails im Detail.",
        "Interact with the assistant and observe traces, sources, tools and "
        "guardrails in detail.",
    ),
    # ADR 0019 §I2 — the honest-empty state for a publish-only agent (binding: none):
    # there is nothing to test-invoke, so the console points to the observe-only surfaces
    # (runs / evals) instead of rendering a broken chat over config it does not have.
    "empty_title": (
        "Aucune invocation de test",
        "Keine Testinvokation",
        "No test invocation",
    ),
    "empty_detail": (
        "Cet agent n'expose aucune invocation de test — observez-le via ses "
        "exécutions et ses évaluations.",
        "Dieser Agent stellt keine Testinvokation bereit — beobachten Sie ihn über "
        "seine Ausführungen und Bewertungen.",
        "This agent exposes no test invocation — observe it through its runs and evaluations.",
    ),
    # ADR 0019 §I3 — the http console: a request/response test bench over the endpoint the
    # agent declares. Distinct from the in-process SSE console (no sandbox / debug tabs —
    # those are in-process concepts); the foreign runtime owns its own guard and telemetry.
    "http_title": (
        "Invocation de test (HTTP)",
        "Testinvokation (HTTP)",
        "Test invocation (HTTP)",
    ),
    "http_subtitle": (
        "Envoyez un tour à l'endpoint déclaré par l'agent et observez le TurnResult. "
        "Requête/réponse, sous assertion opérateur ; chaque invocation est auditée.",
        "Senden Sie einen Turn an den vom Agenten deklarierten Endpoint und beobachten Sie "
        "das TurnResult. Request/Response, unter Operator-Assertion; jede Invokation "
        "wird auditiert.",
        "Send a turn to the endpoint the agent declares and observe the TurnResult. "
        "Request/response, under an operator assertion; every invocation is audited.",
    ),
    "http_placeholder": (
        "Message de test à envoyer à l'agent...",
        "Testnachricht an den Agenten...",
        "Test message to send to the agent...",
    ),
    "http_send": ("Envoyer le tour", "Turn senden", "Send turn"),
    "http_reply": ("Réponse", "Antwort", "Reply"),
    "http_result": ("TurnResult (brut)", "TurnResult (roh)", "TurnResult (raw)"),
    "http_ok": ("Conforme", "Konform", "Conformant"),
    "http_failed": ("Échec", "Fehlgeschlagen", "Failed"),
    # ADR 0019 §A1.2 (c) — the generated capability form. Generic by construction: these labels
    # frame ANY declared input_schema, and no agent is named in any of them.
    "cap_free_text": ("Message libre", "Freier Text", "Free message"),
    "cap_section": (
        "Capacités déclarées",
        "Deklarierte Fähigkeiten",
        "Declared capabilities",
    ),
    "cap_hint": (
        "Formulaire généré depuis le schéma que l'agent déclare — aucun champ écrit à la main.",
        "Formular aus dem deklarierten Schema erzeugt — kein Feld ist handgeschrieben.",
        "Form generated from the schema the agent declares — no field is hand-written.",
    ),
    "cap_submit": ("Envoyer la capacité", "Fähigkeit senden", "Send capability"),
    "cap_required": ("Requis", "Erforderlich", "Required"),
}


def _t(key: str, lang: str) -> str:
    return _TR[key][_LANG_IDX.get(lang, 0)]


_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _ROOT / "src" / "tessera" / "agent" / "prompts"
_CORPUS_DIR = _ROOT / "src" / "tessera" / "corpus" / "data"
_PARIS = ZoneInfo("Europe/Paris")


def _mtime(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=_PARIS)
    except FileNotFoundError:
        return datetime.now(_PARIS)


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")


def _version(path: Path, *, prefix: str = "v") -> str:
    digest = hashlib.sha256(path.read_bytes() if path.exists() else str(path).encode()).hexdigest()
    stamp = _mtime(path)
    return f"{prefix}{stamp.month}.{stamp.day}.{int(digest[:2], 16) % 10}"


def _active_model() -> tuple[str, str]:
    settings = get_settings()
    profile = settings.resolved_llm_profile()
    if profile is LLMProfile.ON_PREM:
        return settings.ollama.chat_model, "Ollama"
    return settings.vertex.chat_model, "Vertex AI"


def _score_rows(metric: str) -> list[float]:
    rows = read_scores()
    values: list[float] = []
    for row in rows:
        if row.get("metric") != metric:
            continue
        raw = row.get("score")
        if isinstance(raw, int | float):
            values.append(float(raw))
    return values


def _latest_score(metric: str) -> float | None:
    values = _score_rows(metric)
    return values[-1] if values else None


def _evaluation_panel(lang: str) -> dict[str, object]:
    """Latest *real* automated-eval metrics for this agent (honest, not per-turn).

    The console does not re-run the evaluation harness on each turn, so this
    block surfaces the metrics from the latest durable eval run (the same source
    that feeds the Évaluations page), each labelled distinctly. When a metric has
    no recorded score it renders an honest empty value (``None``) rather than a
    fabricated number.
    """
    metrics = (
        (_t("m_faith", lang), "faithfulness"),
        (_t("m_ground", lang), "grounding"),
        (_t("m_hallu", lang), "hallucination"),
    )
    rows: list[dict[str, object]] = []
    for label, key in metrics:
        value = _latest_score(key)
        rows.append({"label": label, "value": None if value is None else f"{value:.2f}"})
    return {
        "title": _t("ep_title", lang),
        "note": _t("ep_note", lang),
        "cta": _t("ep_cta", lang),
        "available": any(row["value"] is not None for row in rows),
        "rows": rows,
    }


def _tools_panel(lang: str) -> dict[str, object]:
    policy = load_policy(get_settings().guard.policy_path)
    rows = [
        {"name": name, "status": _t("tool_allowed", lang), "tone": "good", "latency": "policy"}
        for name, rule in policy.tools.items()
        if rule.allow
    ][:3]
    return {"title": _t("tools_title", lang).format(n=len(rows)), "rows": rows}


def _guardrails_panel(lang: str) -> dict[str, object]:
    policy = load_policy(get_settings().guard.policy_path)
    rows = [
        {
            "name": "Prompt Injection Deny",
            "status": str(len(policy.prompt_injection_deny)),
            "tone": "warn",
            "detail": _t("gd_deny_detail", lang),
        },
        {
            "name": "PII Output Guard",
            "status": str(len(policy.pii_patterns)),
            "tone": "warn",
            "detail": _t("gd_pii_detail", lang),
        },
    ]
    return {"title": _t("gd_title", lang).format(n=len(rows)), "rows": rows}


def _honest_empty_payload(lang: str, binding: InvocationBinding) -> dict[str, object]:
    """The slim honest-empty console for a non-invocable agent (ADR 0019 §I2).

    A publish-only agent (``binding: none``) exposes no test invocation, so the payload
    carries only the honest-empty descriptor and the binding — never fabricated tools /
    guardrails / eval panels, which belong to an agent that actually runs the tessera
    guard. The frontend renders it as an observe-only state pointing at runs / evals.
    """
    return {
        "invocation": {"binding": binding.value, "invocable": False},
        "title": _t("title", lang),
        "subtitle": _t("subtitle", lang),
        "empty": {"title": _t("empty_title", lang), "detail": _t("empty_detail", lang)},
    }


def capability_forms(agent: Agent) -> list[dict[str, object]]:
    """The generated-form descriptors for the agent's capabilities (ADR 0019 §A1.2 c).

    One entry per capability that declares an ``input_schema``; a capability without one has no
    parameters, so there is nothing to render and it is honestly absent rather than shown as an
    empty form. The ``label_key`` travels unresolved: the frontend owns the locale catalogue, and
    passing the key (not a string) is what keeps this projection agent-agnostic.

    A declared schema that cannot be loaded is a manifest error, not a degraded console — it
    raises, and the route surfaces it, rather than rendering a form the agent never promised.
    """
    spec = agent.observability
    if spec is None:
        return []
    return [
        {
            "id": capability.id,
            "label_key": capability.label_key,
            "schema": load_input_schema(capability.input_schema),
        }
        for capability in spec.capabilities
        if capability.input_schema
    ]


def _http_console_payload(lang: str, agent: Agent) -> dict[str, object]:
    """The request/response test bench for an ``http``-binding agent (ADR 0019 §I3).

    A foreign runtime invoked over the declared endpoint — so the payload carries the http
    console descriptor and the endpoint, but NONE of the in-process panels (sandbox / debug /
    guardrails): those are in-process concepts, and the remote agent owns its own guard and
    telemetry. The frontend renders a send-a-turn / show-the-TurnResult panel driven by the
    ``POST /agents/{id}/invoke`` seam (each turn audited, under an operator assertion).

    Since §A1.2 the bench also carries the agent's declared capability forms. Free text remains:
    a capability is a typed entry point, not a replacement for probing the agent in its own words.
    """
    return {
        "invocation": {
            "binding": InvocationBinding.HTTP.value,
            "invocable": True,
            "mode": "request_response",
            "endpoint": agent.invocation.endpoint,
        },
        "capabilities": capability_forms(agent),
        "title": _t("http_title", lang),
        "subtitle": _t("http_subtitle", lang),
        "http_console": {
            "placeholder": _t("http_placeholder", lang),
            "send_label": _t("http_send", lang),
            "reply_label": _t("http_reply", lang),
            "result_label": _t("http_result", lang),
            "verdict_ok": _t("http_ok", lang),
            "verdict_failed": _t("http_failed", lang),
        },
        # Generic chrome for the generated capability forms (ADR 0019 §A1.2 c). Agent-agnostic
        # by construction: these labels frame ANY declared input_schema, no agent is named.
        "capability_console": {
            "free_text_label": _t("cap_free_text", lang),
            "section_label": _t("cap_section", lang),
            "hint": _t("cap_hint", lang),
            "submit_label": _t("cap_submit", lang),
            "required_label": _t("cap_required", lang),
        },
    }


def compute_agent_console(lang: str = "fr", agent_id: str = DEFAULT_AGENT_ID) -> dict[str, object]:
    """Return the Console (Debug) payload for ``agent_id`` from live settings and files.

    ADR 0019 §I2/§I3 — the payload is *generated* from the agent's declared
    ``invocation.binding``: ``in_process_chat`` gets the full interactive payload (parity, no
    behaviour change); ``http`` gets a request/response test bench (ADR 0019 §I3); a
    publish-only ``none`` agent gets a slim honest-empty descriptor with NO fabricated config
    panels. Raises ``KeyError`` for an unknown ``agent_id`` (the route degrades to
    ``available: false``).
    """
    lang = _norm_lang(lang)
    agent = get_agent(agent_id)
    binding = agent.invocation.binding
    if binding is InvocationBinding.HTTP:
        return _http_console_payload(lang, agent)
    if binding is not InvocationBinding.IN_PROCESS_CHAT:
        # ``none``: nothing the console can drive, so render honest-empty rather than a chat
        # over config it does not own.
        return _honest_empty_payload(lang, binding)
    settings = get_settings()
    model, provider = _active_model()
    prompt_path = _PROMPTS_DIR / f"{settings.default_language.value}.yaml"
    policy_path = settings.guard.policy_path
    newest_corpus = max(
        (_mtime(path) for path in _CORPUS_DIR.glob("*.json")),
        default=_mtime(_CORPUS_DIR),
    )
    prompt_version = _version(prompt_path)
    sources_version = f"snapshot {len(list(_CORPUS_DIR.glob('*.json')))}.{newest_corpus.month}"
    guard_version = _version(policy_path)
    session_seed = f"{model}:{prompt_version}:{sources_version}:{guard_version}"
    session_id = f"sess_{hashlib.sha256(session_seed.encode()).hexdigest()[:8]}"
    now = datetime.now(_PARIS)

    return {
        # ADR 0019 §I2 — the declared cockpit→agent binding this console drives. Present on
        # every payload so the frontend generates its shape from the declaration, never an
        # assumption; ``in_process_chat`` is the only invocable binding until the I3 invoker.
        "invocation": {"binding": binding.value, "invocable": True},
        # Provenance strip atop the central "Résumé de la réponse" column
        # (normative 05): the lineage versions the answer was produced with —
        # prompt bundle, corpus snapshot, guard policy. The environment ("Sandbox")
        # and the model are deliberately NOT echoed here: the top sandbox bar owns
        # the live model selection and the Debug tab echoes the effective config,
        # so repeating a *static* model here was both redundant and stale.
        "context": {
            "session_id": session_id,
            "fields": [
                {"label": "Prompt", "value": prompt_version},
                {"label": "Sources", "value": sources_version},
                {"label": _t("lbl_guard", lang), "value": guard_version},
            ],
        },
        # Stable keys: the frontend gates panel content on these exact strings and
        # maps them to localized labels for display. Do NOT localize here.
        "tabs": ["Sources", "Outils", "Garde-fous", "Évaluation"],
        # Response-specific panels (quality / sources used / trace) are NOT seeded:
        # before a turn there is no response to summarise, so the frontend renders
        # an honest awaiting state. Only the configuration panels below are real
        # pre-turn (loaded tools / guardrails from the policy) + the latest eval run.
        "tools": _tools_panel(lang),
        "guardrails": _guardrails_panel(lang),
        "evaluation": _evaluation_panel(lang),
        "footer": {
            "started": _t("footer_started", lang).format(t=_fmt_time(now)),
            "live": True,
            "context": "Plateforme Tessera",
            "language": _t("lang_name", lang),
            "session_id": session_id,
        },
        "actions": {
            "input_placeholder": _t("placeholder", lang),
            "feedback": [_t("fb_useful", lang), _t("fb_notuseful", lang)],
            "footer_actions": [
                {"key": "replay", "label": _t("fa_replay", lang)},
                {"key": "compare", "label": _t("fa_compare", lang)},
                {"key": "export", "label": _t("fa_export", lang)},
                {"key": "close", "label": _t("fa_close", lang)},
            ],
            "timeline_incidents": _t("timeline_incidents", lang),
            "new_session": _t("new_session", lang),
            "replay": _t("replay", lang),
        },
        "title": _t("title", lang),
        "subtitle": _t("subtitle", lang),
        "provider": provider,
    }
