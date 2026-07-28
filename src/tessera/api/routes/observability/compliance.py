"""Observability routes — compliance surface."""

from __future__ import annotations

import sys
from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from tessera.api.routes.observability._common import (
    _CITATION_SENTENCE,
    _corpus_sources,
    _read_audit_entries,
)
from tessera.observability import (
    ai_act as ai_act_mod,
    citation_resolver as citation_resolver_mod,
    citation_validity as citation_validity_mod,
    compliance as compliance_mod,
    connectors as connectors_mod,
    corpus_freshness as corpus_freshness_mod,
    corpus_injection as corpus_injection_mod,
    disclosure as disclosure_mod,
    governance_feed as governance_feed_mod,
    integrations as integrations_mod,
    locale_format as locale_format_mod,
    localization as localization_mod,
    parameters as parameters_mod,
    proofs as proofs_mod,
    replay as replay_mod,
    sources as sources_mod,
    system_profile as system_profile_mod,
)
from tessera.observability._asof import occurred_before

router = APIRouter()


@router.get("/observability/compliance")
def observability_compliance(lang: str = "fr") -> dict[str, object]:
    """Regulatory compliance posture derived from the real runtime signals (#07).

    Maps the live AI-Act, conformance, citation, disclosure, PII, refusal,
    erasure and firewall signals onto per-framework controls (RGPD, EU AI Act,
    DORA, ISO 27001, SOC 2, internal policies). ``lang`` localizes the labels and
    the per-tab catalogues. Degrades to ``available: false`` if assembly fails so
    the dashboard never errors.
    """
    try:
        return {"available": True, **asdict(compliance_mod.compute_compliance(lang))}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.compliance: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/catalogue-consumers")
def observability_catalogue_consumers(
    kind: str, agent: str = "all", lang: str = "fr"
) -> dict[str, object]:
    """CONFIGURER "used-by": which agents consume each catalogue item of ``kind``.

    The inverse of the AGENT instance binding — each shared definition shows its
    consumer agents + their release verdict, so a change's re-gate blast radius is
    explicit. Global, filterable by agent. ``lang`` localizes the verdict label.
    Degrades to ``available: false``.
    """
    from tessera.observability import catalogue_consumers as cc_mod

    try:
        return {
            "available": True,
            **cc_mod.catalogue_consumers(kind, agent_scope=agent, lang=lang),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.catalogue_consumers: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/governance")
def observability_governance(
    at: str | None = None, limit: int = 8, agent: str = "all"
) -> dict[str, object]:
    """Governed-activity feed — real S1 governance events + lineage deploys (≤ T).

    Surfaces genuine governance actions (agent routing/hand-overs/proposals/release
    decisions from the hash-chained S1 journal, and model/prompt/policy version
    deploys from the bundle lineage), newest-first. Honours as-of-T (``?at=``) so it
    stays consistent with the rail's provenance contract; ``?agent=`` scopes the S1
    events. Only real events are returned — sparse categories simply do not appear
    (honest empty state). Degrades to ``available: false`` on failure.
    """
    try:
        bounded = max(1, min(limit, 30))
        feed = governance_feed_mod.compute_governance_feed(at, limit=bounded, agent=agent)
        return {"available": True, **asdict(feed)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.governance: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/parameters")
async def observability_parameters(lang: str = "fr", asof: str | None = None) -> dict[str, object]:
    """Settings / parameters overview (page #21), live or governed-overrides as-of T.

    Composes the active config version, posture KPIs, quick-config categories,
    recent parameters, configuration-state distribution and compliance checks.
    With ``asof`` the governed overrides are FOLDED from the hash-chained ledger
    at T (OT-01 — "mes paramètres d'il y a 3 h") and the POLICY socle is
    reconstructed from git history at T when a repository is present
    (``socle_policy_asof`` says which claim holds); the runtime posture stays
    live and the UI scopes the claim accordingly.
    Degrades to ``available: false`` on failure.
    """
    try:
        # As-of T: the overrides in force at T, refolded from the governed
        # journal — never today's store rows under a T label. A malformed
        # hand-edited instant reads live (État à date's tolerance): the
        # frontend chip derives from the same URL and falls back identically.
        folded: list[parameters_mod.OverrideRow] | None = None
        policy_at: parameters_mod.PolicySocleAtT | None = None
        if asof:
            try:
                folded = parameters_mod.override_rows_as_of(asof)
            except ValueError:
                folded = None
            if folded is not None:
                # The provable slice of the socle: policy.yaml at T from git.
                # None = CANNOT SAY (no repo, no commit at T) — the flag below
                # keeps the UI's claim exact, never silently live-under-T.
                policy_at = parameters_mod.policy_socle_as_of(asof)
        if folded is not None:
            override_rows = folded
        else:
            # ADR 0030 — the stored governed overrides are the only parameters
            # with a real per-row author; the store read is async so it happens
            # here, and the sync composer receives plain rows. Fail open to base:
            # an unreadable store must not blank the whole page.
            try:
                from tessera.api.config_overrides import list_overrides

                override_rows = [
                    parameters_mod.OverrideRow(
                        key=o.key,
                        value=o.value,
                        author=o.author,
                        reason=o.reason,
                        updated_at=o.updated_at,
                    )
                    for o in await list_overrides()
                ]
            except Exception as exc:
                sys.stderr.write(
                    f"tessera.observability.parameters: overrides read failed: {exc}\n"
                )
                override_rows = []
        return {
            "available": True,
            # Which as-of claim holds for the socle: true = policy socle read
            # from git at T; false = overrides only (repo absent / no commit).
            # Live reads carry false — there is no as-of claim to scope.
            "socle_policy_asof": policy_at is not None,
            **parameters_mod.compute_parameters_overview(
                lang, override_rows=override_rows, policy_at=policy_at
            ),
        }
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.parameters: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/system-profile")
def observability_system_profile(lang: str = "fr") -> dict[str, object]:
    """System profile overview (page #20).

    Composes the operational posture, architecture, topology, resource
    distribution, OS info, health checks, resource series and services table.
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **system_profile_mod.compute_system_profile(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.system_profile: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/integrations")
def observability_integrations(lang: str = "fr") -> dict[str, object]:
    """Integrations overview (page #19).

    Composes the integration posture, the catalogue table, the
    selected-integration detail and the distributions. Degrades to
    ``available: false`` on failure.
    """
    try:
        return {"available": True, **integrations_mod.compute_integrations_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.integrations: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/sources")
async def observability_sources(lang: str = "fr") -> dict[str, object]:
    """Sources & memory overview (page #17).

    Composes the catalogue posture (corpus + memory), the source table, the
    selected-source detail and the type / volume / language distributions, read
    live from pgvector and the memory tables. Degrades to ``available: false``
    on failure.
    """
    try:
        return {"available": True, **await sources_mod.build_sources_overview(lang)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.sources: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/evidence-packs/{pack_id}/manifest")
def observability_evidence_pack_manifest(pack_id: str) -> dict[str, object]:
    """One stored evidence-pack manifest, verbatim (the downloadable artifact).

    404 on an id nobody created — never an empty manifest that looks real.
    """
    from fastapi import HTTPException

    from tessera.observability import evidence_pack_store

    try:
        return evidence_pack_store.get_pack(pack_id)
    except evidence_pack_store.PackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown evidence pack {pack_id!r}") from exc


@router.get("/observability/evidence-packs/{pack_id}/verify")
def observability_evidence_pack_verify(pack_id: str) -> dict[str, object]:
    """Re-derive the pack digest + re-verify the live chain — a real verdict.

    Two independent facts (manifest_ok, chain_verified_now), never folded into
    one green. 404 on an unknown id.
    """
    from fastapi import HTTPException

    from tessera.observability import evidence_pack_store

    try:
        return evidence_pack_store.verify_pack(pack_id)
    except evidence_pack_store.PackNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"unknown evidence pack {pack_id!r}") from exc


@router.get("/observability/proofs")
def observability_proofs(lang: str = "fr", asof: str | None = None) -> dict[str, object]:
    """Proofs & exporter overview (page #15), live or as-of ``asof``.

    Composes the proof posture, assembly pipeline, current evidence pack,
    recent packs, artifact distribution, exporters & destinations, cryptographic
    verification, control-case proofs, retention obligations and export journal.
    With ``asof`` every real count is bounded at T (SR-01 "État au T" is real).
    Degrades to ``available: false`` on failure.
    """
    try:
        return {"available": True, **proofs_mod.compute_proofs_overview(lang, asof=asof)}
    except Exception as exc:  # never break the dashboard
        sys.stderr.write(f"tessera.observability.proofs: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/corpus-freshness")
def observability_corpus_freshness() -> dict[str, object]:
    """Staleness of the ingested regulatory corpora vs their review horizon (#50)."""
    from importlib import resources
    from pathlib import Path

    data_dir = Path(str(resources.files("tessera.corpus.data")))
    return asdict(corpus_freshness_mod.load_corpus_freshness(data_dir))


@router.get("/observability/citation-links")
def observability_citation_links() -> dict[str, object]:
    """Resolve answer citations to verifiable corpus sources (clickable, #132)."""
    sources = _corpus_sources()
    citations: list[str] = []
    for bundle in replay_mod.recent_bundles():
        citations.extend(
            m.group(0).strip() for m in _CITATION_SENTENCE.finditer(bundle.original_answer)
        )
    return asdict(citation_resolver_mod.resolve_citations(citations, sources))


@router.get("/observability/disclosure")
def observability_disclosure() -> dict[str, object]:
    """AI-interaction disclosure status and per-locale text (Art. 50, #134)."""
    return asdict(disclosure_mod.disclosure_status())


@router.get("/observability/ai-act")
def observability_ai_act(at: str | None = None) -> dict[str, object]:
    """EU AI Act compliance posture: transparency, oversight, traceability (#76).

    Turn and oversight counts honour T; the audit-chain integrity check is a
    structural property of the whole log, so it stays live.
    """
    from tessera.guard.ledger_store import ledger_available, verify_active_ledger

    entries = _read_audit_entries()
    oversight = sum(
        1
        for e in entries
        if e.get("target") == "ticket_escalate" and occurred_before(e.get("occurred_at"), at)
    )
    chain = verify_active_ledger()
    signals = ai_act_mod.AIActSignals(
        disclosure_enabled=True,  # disclosure shipped on the chat UI (#134)
        n_turns=len(replay_mod.recent_bundles(at)),
        oversight_events=oversight,
        escalation_available=True,
        audit_present=ledger_available(),
        audit_chain_verified=chain.verified,
        data_governance_enabled=True,
    )
    return asdict(ai_act_mod.assess_compliance(signals))


@router.get("/observability/localization")
def observability_localization() -> dict[str, object]:
    """Per-locale message completeness vs the default locale (#77)."""
    import json
    from pathlib import Path

    messages_dir = Path(__file__).resolve().parents[5] / "webapp" / "frontend" / "messages"
    catalogues: dict[str, dict[str, object]] = {}
    for locale in ("en", "fr", "de"):
        path = messages_dir / f"{locale}.json"
        try:
            catalogues[locale] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            catalogues[locale] = {}
    return asdict(localization_mod.assess_localization(catalogues))


@router.get("/observability/citations")
def observability_citations() -> dict[str, object]:
    """Regulatory citation validity: cited articles absent from the grounding."""
    turns = [(b.original_answer, b.context) for b in replay_mod.recent_bundles()]
    return asdict(citation_validity_mod.aggregate_citations(turns))


@router.get("/observability/locale-format")
def observability_locale_format() -> dict[str, object]:
    """Locale-formatting correctness: amounts whose style mismatches the locale."""
    turns = [(b.original_answer, b.language) for b in replay_mod.recent_bundles()]
    return asdict(locale_format_mod.aggregate_formatting(turns))


@router.get("/observability/corpus-scan/{bundle_id}")
def observability_corpus_scan(bundle_id: str) -> dict[str, object]:
    """Screen a captured turn's retrieved chunks for indirect injection."""
    bundle = replay_mod.get_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="replay bundle not found")
    chunks = [c for c in bundle.context.split("\n\n") if c.strip()]
    return asdict(corpus_injection_mod.scan_chunks(chunks))


@router.get("/observability/connectors")
def observability_connectors(lang: str = "fr") -> dict[str, object]:
    """Connectors overview for the real Tessera stack (configurer/connecteurs)."""
    try:
        return {"available": True, **connectors_mod.compute_connectors(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.connectors: failed: {exc}\n")
        return {"available": False}
