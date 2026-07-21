"""Per-tab payloads for the Conformite command bar (reference images, tab set).

The Conformite overview (``compliance.py``) is derived live from the real runtime
signals. The remaining command-bar tabs -- Cartographie reglementaire, Obligations
& controles, Evaluations, Incidents & exceptions, Purge & retention, Preuves &
attestations, Registre des traitements -- are *governance catalogues*: regulatory
mappings, treatment registers, retention rules, evidence inventories. Exactly like
the security case identifiers, this metadata is fixed, deterministic fixture data
so the page is stable on every refetch.

The payload uses the shared, render-friendly ``CatalogTab`` shape (see
``catalog_tabs``): a KPI strip, a main table with a sticky detail panel, and a
band of bottom sections. The frontend renders each tab from this shape, so adding
or tuning a tab is a pure-data change here.

Display labels are kept in French inside the data (owners, framework names, column
headers and section titles are all part of the regulatory content), matching how
every other catalogue page in Tessera carries its domain text.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import cast

from tessera.observability.catalog_tabs import (
    CatalogTab,
    DetailField,
    DetailList,
    SectionItem,
    TabColumn,
    TabDetail,
    TabExplain,
    TabKpi,
    TabRow,
    TabSection,
    badge as _badge,
    bar as _bar,
    delta as _delta,
    owner as _owner,
)

__all__ = ["build_tabs"]


# Recurring owners across the regulatory catalogue.
_CLAIRE = _owner("Claire Martin", "AI Governance Lead")
_DAMIEN = _owner("Damien Leroy", "DPO")
_SOPHIE = _owner("Sophie Bernard", "Risk Manager")
_YACINE = _owner("Yacine Sekri", "AI Management")
_NADIA = _owner("Nadia El Idrissi", "CISO")
_THOMAS = _owner("Thomas Klein", "Audit Manager")


# --- Grounded explain text for the Conformite command-bar tabs (info popovers).
# FR is authored here as the source of truth; the DE / EN pairs live in _EX_TR
# near the bottom and are merged into _TR, so _localize renders each info popover
# in all three languages. Every distinct string is defined exactly once, which
# removes any risk of an FR literal drifting from its _TR key; metrics that recur
# across tabs (evidence readiness, recent activity, linked controls, available
# evidence) share a single constant.
# EXPLAIN_CONSTS_ANCHOR (do not remove) -- per-tab constants inserted below.
_EX_REGISTERED_PROCESSINGS = TabExplain(
    "Nombre de traitements de donnees inscrits au registre RGPD Art. 30.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_DOCUMENTED_PURPOSES = TabExplain(
    "Traitements dont la finalite est formellement documentee.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_VALID_LEGAL_BASES = TabExplain(
    "Traitements disposant d'une base legale valide au sens du RGPD Art. 6.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_COMPLIANT_RETENTION = TabExplain(
    "Traitements dont la duree de conservation respecte la politique de retention.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_REGISTRY_GAPS = TabExplain(
    "Traitements dont la fiche de registre est incomplete ou a mettre a jour.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_REGISTRY_TABLE = TabExplain(
    "Registre des traitements : finalite, base legale, categories de donnees, duree de "
    "retention, controles, owner et statut.",
    "Une ligne par traitement inscrit au registre RGPD Art. 30.",
    "Registre des traitements (RGPD Art. 30).",
)
_EX_REGISTRY_DETAIL = TabExplain(
    "Fiche du traitement selectionne : categorie de donnees, finalite, base legale, transferts, "
    "sous-traitants, duree et controles lies.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_REGISTRY_TODO = TabExplain(
    "Fiches de registre incompletes : AIPD, base legale, sous-traitant ou duree a documenter.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_SCHEDULED_REVIEWS = TabExplain(
    "Revues periodiques planifiees des fiches de traitement.",
    "Traitements avec revue a venir, triee par date.",
    "Registre des traitements (RGPD Art. 30).",
)
_EX_LINKED_EXCEPTIONS = TabExplain(
    "Exceptions et derogations rattachees aux traitements du registre.",
    source="Registre des traitements (RGPD Art. 30).",
)
_EX_VALID_ATTESTATIONS = TabExplain(
    "Attestations signees et horodatees encore valides (non expirees).",
    source="Inventaire des preuves.",
)
_EX_EXPIRING_EVIDENCE = TabExplain(
    "Preuves dont la validite arrive a echeance et qui devront etre renouvelees.",
    source="Inventaire des preuves.",
)
_EX_MISSING_CORRUPT = TabExplain(
    "Preuves attendues absentes ou dont l'integrite est compromise.",
    source="Inventaire des preuves.",
)
_EX_EVIDENCE_COVERAGE = TabExplain(
    "Part des obligations disposant d'au moins une preuve valide.",
    "Obligations avec preuve valide divisees par les obligations applicables.",
    "Inventaire des preuves.",
)
_EX_EVIDENCE_PACK_STATE = TabExplain(
    "Etat de preparation de l'evidence pack : l'ensemble des preuves requises est-il pret a "
    "etre assemble et exporte.",
    source="Inventaire des preuves.",
)
_EX_EVIDENCE_TABLE = TabExplain(
    "Inventaire des preuves : cadre, controle, type, owner, date, validite et statut.",
    "Une ligne par preuve ; la validite indique la duree restante avant expiration.",
    "Inventaire des preuves.",
)
_EX_EVIDENCE_DETAIL = TabExplain(
    "Fiche de la preuve selectionnee : cadre, controle, type, date de generation, validite, "
    "empreinte cryptographique, obligations liees et signature.",
    source="Inventaire des preuves.",
)
_EX_EVIDENCE_RENEW = TabExplain(
    "Preuves proches de l'expiration a renouveler pour maintenir la couverture.",
    "Preuves triees par proximite d'expiration.",
    "Inventaire des preuves.",
)
_EX_LATEST_ATTESTATIONS = TabExplain(
    "Dernieres attestations generees, signees ou horodatees, du plus recent au plus ancien.",
    source="Inventaire des preuves.",
)
_EX_COVERAGE_BY_FRAMEWORK = TabExplain(
    "Part des obligations couvertes par une preuve valide, par cadre reglementaire.",
    "Preuves valides sur obligations attendues, par cadre ; l'anneau montre la couverture "
    "globale.",
    "Inventaire des preuves.",
)
_EX_RESOURCES_RETAINED = TabExplain(
    "Categories de donnees soumises a une regle de retention et de purge dans Tessera.",
    source="Politique de retention et de purge.",
)
_EX_PURGE_ON_TIME = TabExplain(
    "Nombre de purges executees dans le delai cible sur la periode.",
    source="Politique de retention et de purge.",
)
_EX_PURGE_JOBS = TabExplain(
    "Nombre de taches de purge programmees, automatiques ou manuelles.",
    source="Politique de retention et de purge.",
)
_EX_LEGAL_HOLDS = TabExplain(
    "Ressources gelees par une obligation de conservation legale, exemptees de purge.",
    source="Politique de retention et de purge.",
)
_EX_RETENTION_GAPS = TabExplain(
    "Ressources dont la purge est en retard ou dont la duree de conservation n'est pas conforme.",
    source="Politique de retention et de purge.",
)
_EX_RETENTION_TABLE = TabExplain(
    "Regles de retention par ressource : base legale, duree cible, mode de purge, signal, owner "
    "et statut.",
    "Une ligne par categorie de donnees ; le mode indique une purge automatique ou manuelle.",
    "Politique de retention et de purge.",
)
_EX_RETENTION_DETAIL = TabExplain(
    "Fiche de la regle selectionnee : stockage, strategie et methode de purge, legal hold, "
    "prochaine purge et controles lies.",
    source="Politique de retention et de purge.",
)
_EX_UPCOMING_PURGES = TabExplain(
    "Purges programmees dans les sept prochains jours, automatiques ou manuelles.",
    "Taches de purge triees par date d'execution.",
    "Politique de retention et de purge.",
)
_EX_RETENTION_EXCEPTIONS = TabExplain(
    "Ressources dont la purge est bloquee ou en retard : legal hold, purge manuelle a corriger.",
    source="Politique de retention et de purge.",
)
_EX_COVERAGE_BY_SYSTEM = TabExplain(
    "Part des ressources correctement soumises a retention par systeme de stockage.",
    "Ressources conformes par systeme, normalisees sur le plus couvert.",
    "Politique de retention et de purge.",
)
_EX_OPEN_INCIDENTS = TabExplain(
    "Incidents de conformite actuellement ouverts (controle depasse, obligation non tenue).",
    source="Registre des incidents et exceptions.",
)
_EX_APPROVED_EXCEPTIONS = TabExplain(
    "Derogations formellement approuvees, assorties d'une mesure compensatoire et d'une "
    "echeance.",
    source="Registre des incidents et exceptions.",
)
_EX_OVERDUE_EXCEPTIONS = TabExplain(
    "Exceptions dont l'echeance est passee sans regularisation ; risque de non-conformite.",
    source="Registre des incidents et exceptions.",
)
_EX_MISSING_EVIDENCE = TabExplain(
    "Preuves attendues pour un incident ou une exception et non encore fournies.",
    source="Registre des incidents et exceptions.",
)
_EX_INCIDENTS_TABLE = TabExplain(
    "Liste des incidents et exceptions avec type, cadre, controle depasse, signal, owner, "
    "echeance et statut.",
    "Une ligne par incident ou exception ; le signal indique la gravite.",
    "Registre des incidents et exceptions.",
)
_EX_INCIDENTS_DETAIL = TabExplain(
    "Fiche de l'exception selectionnee : cause mere, obligation et controle lies, preuve, "
    "echeance, risque residuel, mesure compensatoire et chaine d'approbation.",
    source="Registre des incidents et exceptions.",
)
_EX_EXCEPTIONS_DUE = TabExplain(
    "Exceptions dont l'echeance approche et qui doivent etre regularisees ou renouvelees.",
    "Exceptions triees par proximite d'echeance.",
    "Registre des incidents et exceptions.",
)
_EX_GAP_TRENDS = TabExplain(
    "Evolution du nombre d'incidents, d'exceptions et de resolutions sur les cinq dernieres "
    "periodes.",
    "Compte par periode, une courbe par serie (incidents, exceptions, resolutions).",
    "Registre des incidents et exceptions.",
)
_EX_OWNERS_LOAD = TabExplain(
    "Charge relative des responsables : part des incidents et exceptions ouverts qui leur sont "
    "attribues.",
    "Incidents et exceptions ouverts par owner, normalises sur le plus sollicite.",
    "Registre des incidents et exceptions.",
)
_EX_EVAL_CAMPAIGNS = TabExplain(
    "Nombre de campagnes d'evaluation de conformite executees sur les cadres reglementaires.",
    source="Campagnes d'evaluation de conformite.",
)
_EX_CONFORMITY_SCORE = TabExplain(
    "Part des controles evalues qui passent, ponderee par gravite ; mesure globale de "
    "conformite du perimetre.",
    "Controles passes ponderes divises par les controles evalues, sur la derniere campagne.",
    "Campagnes d'evaluation de conformite.",
)
_EX_CONTROLS_PASSED = TabExplain(
    "Nombre de controles ayant reussi leur derniere evaluation.",
    source="Campagnes d'evaluation de conformite.",
)
_EX_OPEN_GAPS = TabExplain(
    "Ecarts de conformite detectes par les evaluations et non encore remedies.",
    source="Campagnes d'evaluation de conformite.",
)
_EX_EVIDENCE_REPLAYED = TabExplain(
    "Nombre de preuves re-executees pour confirmer qu'un controle passe toujours.",
    source="Campagnes d'evaluation de conformite.",
)
_EX_EVAL_TABLE = TabExplain(
    "Vue par campagne : couverture, score, obligations, controles, signaux, preuves, owner et "
    "statut.",
    "Une ligne par cadre evalue ; le score pondere les controles passes par gravite.",
    "Campagnes d'evaluation de conformite.",
)
_EX_EVAL_DETAIL = TabExplain(
    "Fiche de la campagne selectionnee : score, controles passes, echecs critiques, preuves "
    "rejouees et derniere execution.",
    source="Campagnes d'evaluation de conformite.",
)
_EX_REMEDIATION_PLAN = TabExplain(
    "Repartition des ecarts ouverts par gravite (critique, eleve, moyen, faible), a resorber "
    "dans le plan de remediation.",
    "Ecarts ouverts comptes par niveau de gravite ; le total correspond aux ecarts ouverts.",
    "Campagnes d'evaluation de conformite.",
)
_EX_SCORE_TRENDS = TabExplain(
    "Evolution du score de conformite par cadre sur les cinq dernieres campagnes.",
    "Score pondere par campagne, une courbe par cadre.",
    "Campagnes d'evaluation de conformite.",
)
_EX_DECLINING_FRAMEWORKS = TabExplain(
    "Cadres dont le score de conformite recule d'une campagne a l'autre.",
    "Cadres avec une variation de score negative, triee par ampleur.",
    "Campagnes d'evaluation de conformite.",
)
_EX_OBLIGATIONS_ACTIVE = TabExplain(
    "Obligations reglementaires actuellement applicables au perimetre et suivies dans le "
    "registre.",
    source="Cartographie reglementaire (obligations-controles).",
)
_EX_COVERAGE_OBLIGATIONS = TabExplain(
    "Part des obligations du perimetre couvertes par un controle actif et une preuve valide.",
    "Obligations couvertes (controle et preuve) divisees par les obligations applicables.",
    "Cartographie reglementaire (obligations-controles).",
)
_EX_SIGNALS_PER_EVIDENCE = TabExplain(
    "Nombre moyen de signaux d'execution (traces, tests, journaux) rattaches a chaque preuve.",
    "Total des signaux lies divise par le nombre de preuves du perimetre.",
    "Inventaire des preuves.",
)
_EX_DEGRADED_CONTROLS = TabExplain(
    "Controles dont le dernier resultat est partiel ou en echec et qui exigent une remediation.",
    "Controles au statut degrade sur l'ensemble des obligations suivies.",
    "Cartographie reglementaire (statut des controles).",
)
_EX_OBLIGATIONS_TABLE = TabExplain(
    "Liste des obligations avec leur cadre, le controle principal, les signaux, les preuves, "
    "l'owner, le statut et la couverture.",
    "Une ligne par obligation suivie ; la barre indique les preuves disponibles sur attendues, "
    "la jauge la couverture de controle.",
    "Cartographie reglementaire (obligations-controles).",
)
_EX_OBLIGATIONS_DETAIL = TabExplain(
    "Fiche de l'obligation selectionnee : cadre, controle principal, signaux et preuves "
    "rattaches, risque residuel, prochaine revue et controles mappes.",
    source="Cartographie reglementaire (fiche obligation).",
)
_EX_CONTROLS_REVIEW = TabExplain(
    "Controles au statut partiel ou moyen dont le resultat doit etre re-verifie.",
    source="Cartographie reglementaire (statut des controles).",
)
_EX_COVERAGE_GAPS = TabExplain(
    "Obligations depourvues de controle ou de preuve suffisante ; ecart de conformite a combler.",
    source="Cartographie reglementaire (obligations-controles).",
)
_EX_REMEDIATION_DEADLINES = TabExplain(
    "Plans de remediation avec leur date butoir pour les controles ou obligations en ecart.",
    "Actions de remediation triees par proximite d'echeance.",
    "Cartographie reglementaire (echeances).",
)
_EX_EVIDENCE_READINESS = TabExplain(
    "Part des preuves requises par le referentiel qui sont disponibles, valides et non "
    "expirees, donc pretes a etre assemblees en evidence pack a la demande d'un auditeur.",
    "Preuves valides rattachees aux obligations du perimetre divisees par les preuves "
    "attendues ; une preuve expiree ou manquante fait baisser le ratio.",
    "Inventaire des preuves.",
)
_EX_RECENT_ACTIVITY = TabExplain(
    "Journal chronologique des dernieres actions de gouvernance sur ce perimetre : preuves "
    "ajoutees, controles mis a jour, exceptions, revues.",
    source="Catalogue de gouvernance Conformite (donnees de reference).",
)
_EX_LINKED_CONTROLS = TabExplain(
    "Nombre de controles internes rattaches a une obligation de ce perimetre.",
    "Liens obligation-controle uniques, agreges sur le perimetre affiche.",
    "Cartographie reglementaire (obligations-controles).",
)
_EX_AVAILABLE_EVIDENCE = TabExplain(
    "Nombre de preuves et d'attestations disponibles et exploitables comme evidence pour ce "
    "perimetre.",
    source="Inventaire des preuves.",
)
_EX_FRAMEWORKS_ACTIVE = TabExplain(
    "Nombre de referentiels reglementaires actuellement suivis et cartographies dans Tessera "
    "(EU AI Act, RGPD, DORA, ISO, SOC 2, politiques internes).",
    "Cadres au statut actif dans la cartographie ; un cadre en simple veille n'est pas compte.",
    "Cartographie reglementaire (referentiel des cadres).",
)
_EX_OBLIGATIONS_MAPPED = TabExplain(
    "Nombre d'obligations reglementaires rattachees a au moins un controle interne.",
    "Somme des obligations mappees sur l'ensemble des cadres actifs.",
    "Cartographie reglementaire (obligations-controles).",
)
_EX_OBLIGATIONS_AT_RISK = TabExplain(
    "Obligations dont la couverture de controle ou de preuve est insuffisante, ou dont une "
    "echeance approche.",
    "Obligations au statut partiel ou non conforme, ou a echeance proche, comptees une fois.",
    "Cartographie reglementaire (statut des obligations).",
)
_EX_MAPPING_TABLE = TabExplain(
    "Vue par cadre reglementaire : obligations, controles, signaux et preuves rattaches, avec "
    "l'owner et le statut de conformite.",
    "Une ligne par referentiel actif ; les compteurs agregent les obligations et controles "
    "mappes, la barre indique les preuves disponibles sur attendues.",
    "Cartographie reglementaire (referentiel obligations-controles).",
)
_EX_MAPPING_DETAIL = TabExplain(
    "Fiche du cadre selectionne : articles applicables, obligations et controles mappes, "
    "preuves disponibles, risque residuel et prochaine revue.",
    source="Cartographie reglementaire (fiche cadre).",
)
_EX_FRAMEWORKS_WATCH = TabExplain(
    "Referentiels emergents ou a venir a integrer prochainement a la cartographie (NIS2, Data "
    "Act, directive responsabilite IA).",
    "Cadres en veille avec leur trimestre d'applicabilite estime.",
    "Veille reglementaire.",
)
_EX_REG_DEADLINES = TabExplain(
    "Prochaines echeances imposees par les cadres : rapports annuels, tests de resilience, "
    "mises a jour de registre.",
    "Obligations a date butoir triees par proximite d'echeance.",
    "Cartographie reglementaire (echeances).",
)


def _generer() -> list[str]:
    return ["Voir le detail", "Ouvrir les preuves", "Generer evidence pack"]


# --- Cartographie reglementaire ------------------------------------------


def _tab_mapping() -> CatalogTab:
    kpis = [
        TabKpi("Cadres actifs", "7", tone="good", explain=_EX_FRAMEWORKS_ACTIVE),
        TabKpi(
            "Obligations mappees",
            "512",
            delta="+8.2%",
            delta_good=True,
            tone="good",
            explain=_EX_OBLIGATIONS_MAPPED,
        ),
        TabKpi(
            "Controles lies", "1 284", delta="+5.1%", delta_good=True, explain=_EX_LINKED_CONTROLS
        ),
        TabKpi(
            "Preuves disponibles",
            "1 105",
            delta="+3.4%",
            delta_good=True,
            explain=_EX_AVAILABLE_EVIDENCE,
        ),
        TabKpi(
            "Obligations a risque",
            "28",
            delta="-4.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_OBLIGATIONS_AT_RISK,
        ),
        TabKpi(
            "Evidence pack readiness", "86", unit="%", tone="good", explain=_EX_EVIDENCE_READINESS
        ),
    ]
    columns = [
        TabColumn("framework", "Cadre", "text"),
        TabColumn("article", "Article / Domaine", "text"),
        TabColumn("obligations", "Obligations", "delta", "right"),
        TabColumn("controls", "Controles", "delta", "right"),
        TabColumn("signals", "Signaux", "delta", "right"),
        TabColumn("evidence", "Preuves", "bar", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "ai_act",
            {
                "framework": "EU AI Act",
                "article": "Ch. I-VI, Art. 1-85",
                "obligations": _delta("96", "+6%", True),
                "controls": _delta("248", "+5%", True),
                "signals": _delta("312", "+5%", True),
                "evidence": _bar(276, 350),
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "rgpd",
            {
                "framework": "RGPD (UE)",
                "article": "Art. 5, 6, 12-22, 32-49",
                "obligations": _delta("124", "+5%", True),
                "controls": _delta("312", "+4%", True),
                "signals": _delta("428", "+6%", True),
                "evidence": _bar(362, 420),
                "owner": _DAMIEN,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "dora",
            {
                "framework": "DORA",
                "article": "Art. 5, 15, 23-28, 30-44",
                "obligations": _delta("84", "+5%", True),
                "controls": _delta("198", "+5%", True),
                "signals": _delta("221", "+4%", True),
                "evidence": _bar(174, 240),
                "owner": _SOPHIE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "iso42001",
            {
                "framework": "ISO/IEC 42001",
                "article": "4-10 (SMIA)",
                "obligations": _delta("52", "+2%", True),
                "controls": _delta("168", "+3%", True),
                "signals": _delta("190", "+3%", True),
                "evidence": _bar(162, 190),
                "owner": _YACINE,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "iso27001",
            {
                "framework": "ISO 27001",
                "article": "A.5-A.18",
                "obligations": _delta("112", "+3%", True),
                "controls": _delta("246", "+5%", True),
                "signals": _delta("318", "+4%", True),
                "evidence": _bar(312, 360),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "soc2",
            {
                "framework": "SOC 2 — matrice de contrôles",
                "article": "CC1-CC9",
                "obligations": _delta("18", "+0%", True),
                "controls": _delta("96", "+4%", True),
                "signals": _delta("54", "+5%", True),
                "evidence": _bar(41, 55),
                "owner": _THOMAS,
                "status": _badge("Préparation partielle", "warning"),
            },
        ),
        TabRow(
            "internal",
            {
                "framework": "Politiques internes",
                "article": "Pol. AI-01 a AI-12",
                "obligations": _delta("46", "+3%", True),
                "controls": _delta("128", "+2%", True),
                "signals": _delta("96", "+3%", True),
                "evidence": _bar(88, 110),
                "owner": _CLAIRE,
                "status": _badge("Conforme", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Cadre",
        title="EU AI Act",
        status_label="Partiel",
        status_tone="warning",
        summary="Systemes d'IA a haut risque, GPAI, transparence et surveillance humaine.",
        explain=_EX_MAPPING_DETAIL,
        fields=[
            DetailField("Articles applicables", "Art. 5, 9, 13, 14, 50"),
            DetailField("Obligations mappees", "96 / 96"),
            DetailField("Controles mappes", "248"),
            DetailField("Signaux lies", "312"),
            DetailField("Preuves disponibles", "276 / 350"),
            DetailField("Niveau de risque residuel", "Moyen", "warning"),
            DetailField("Prochaine revue", "30 jun 2026"),
        ],
        lists=[
            DetailList(
                "Dernieres preuves",
                [
                    {"label": "EV-2026-06-0321"},
                    {"label": "EV-2026-06-0312"},
                    {"label": "EV-2026-06-0290"},
                ],
            ),
            DetailList(
                "Owner",
                [{"label": "Claire Martin", "sub": "AI Governance Lead"}],
            ),
        ],
        actions=["Voir toutes les preuves", *_generer()],
    )
    sections = [
        TabSection(
            "Cadres a surveiller",
            "list",
            explain=_EX_FRAMEWORKS_WATCH,
            items=[
                SectionItem(
                    "NIS2 Directive",
                    "Applicable des classification",
                    "T3 2026",
                    "Nouveau",
                    "info",
                ),
                SectionItem(
                    "Data Act",
                    "Applicable partielle",
                    "T4 2026",
                    "Veille",
                    "neutral",
                ),
                SectionItem(
                    "AI Liability Directive",
                    "Proposition en cours",
                    "T1 2027",
                    "Veille",
                    "neutral",
                ),
            ],
            cta="Voir tous les cadres a surveiller",
        ),
        TabSection(
            "Echeances reglementaires",
            "list",
            explain=_EX_REG_DEADLINES,
            items=[
                SectionItem(
                    "EU AI Act - Art. 15 (rapport annuel)",
                    "dans 15 jours",
                    "30 jun 2026",
                    badge_tone="warning",
                ),
                SectionItem(
                    "DORA - Art. 28 (test de resilience)",
                    "dans 45 jours",
                    "15 jul 2026",
                    badge_tone="neutral",
                ),
                SectionItem(
                    "RGPD - Article 30 (registre)",
                    "dans 60 jours",
                    "31 jul 2026",
                    badge_tone="neutral",
                ),
            ],
            cta="Voir toutes les echeances",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("Preuve EV-2026-06-0321 ajoutee a EU AI Act", "il y a 2 h"),
                SectionItem("Controle CTRL-09 mis a jour (RGPD)", "il y a 5 h"),
                SectionItem("Obligation OBL-1123 marquee conforme (RGPD)", "il y a 8 h"),
                SectionItem("Evaluation ISO 27001 terminee", "hier"),
                SectionItem("Exception EXC-2026-004 creee (DORA)", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Actions rapides",
            "actions",
            actions=[
                "Lancer une evaluation",
                "Mapper une obligation",
                "Ouvrir les preuves",
                "Generer evidence pack",
            ],
        ),
    ]
    return CatalogTab(
        "Cartographie reglementaire",
        table_explain=_EX_MAPPING_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Obligations & controles ---------------------------------------------


def _tab_obligations() -> CatalogTab:
    kpis = [
        TabKpi("Obligations actives", "18", tone="good", explain=_EX_OBLIGATIONS_ACTIVE),
        TabKpi(
            "Controles lies", "284", delta="+6.0%", delta_good=True, explain=_EX_LINKED_CONTROLS
        ),
        TabKpi(
            "Couverture",
            "89",
            unit="%",
            delta="+7.2 pp",
            delta_good=True,
            tone="good",
            explain=_EX_COVERAGE_OBLIGATIONS,
        ),
        TabKpi("Signaux par preuve", "3.2", sub="moyenne", explain=_EX_SIGNALS_PER_EVIDENCE),
        TabKpi(
            "Controles degrades",
            "17",
            delta="-3.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_DEGRADED_CONTROLS,
        ),
        TabKpi(
            "Evidence pack readiness", "84", unit="%", tone="good", explain=_EX_EVIDENCE_READINESS
        ),
    ]
    columns = [
        TabColumn("obligation", "Obligation", "text"),
        TabColumn("framework", "Cadre", "text"),
        TabColumn("control", "Controle principal", "text"),
        TabColumn("signals", "Signaux", "num", "right"),
        TabColumn("evidence", "Preuves", "bar", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
        TabColumn("coverage", "Couverture", "pct", "right"),
    ]
    rows = [
        TabRow(
            "art9",
            {
                "obligation": "Art. 9 - Systeme a haut risque",
                "framework": "EU AI Act",
                "control": "C-15.1 - Gestion du risque",
                "signals": "12",
                "evidence": _bar(28, 30),
                "owner": _CLAIRE,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 92},
            },
        ),
        TabRow(
            "art10",
            {
                "obligation": "Art. 10 - Qualite des donnees",
                "framework": "EU AI Act",
                "control": "C-13.2 - Gouvernance des donnees",
                "signals": "9",
                "evidence": _bar(18, 26),
                "owner": _DAMIEN,
                "status": _badge("Partiel", "warning"),
                "coverage": {"pct": 78},
            },
        ),
        TabRow(
            "art13",
            {
                "obligation": "Art. 13 - Transparence & info",
                "framework": "EU AI Act",
                "control": "C-05.2 - Transparence utilisateur",
                "signals": "7",
                "evidence": _bar(14, 22),
                "owner": _SOPHIE,
                "status": _badge("Partiel", "warning"),
                "coverage": {"pct": 71},
            },
        ),
        TabRow(
            "art5",
            {
                "obligation": "Art. 5 - Principes (a-f)",
                "framework": "RGPD",
                "control": "C-08.2 - Minimisation",
                "signals": "14",
                "evidence": _bar(31, 33),
                "owner": _YACINE,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 95},
            },
        ),
        TabRow(
            "art30",
            {
                "obligation": "Art. 30 - Registre des activites",
                "framework": "RGPD",
                "control": "C-30.1 - Tenue du registre",
                "signals": "6",
                "evidence": _bar(24, 26),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 93},
            },
        ),
        TabRow(
            "dora28",
            {
                "obligation": "DORA - Art. 28 (sous-traitance TIC)",
                "framework": "DORA",
                "control": "C-DORA.1 - Risques TIC",
                "signals": "8",
                "evidence": _bar(12, 20),
                "owner": _THOMAS,
                "status": _badge("Partiel", "warning"),
                "coverage": {"pct": 64},
            },
        ),
        TabRow(
            "isoA6",
            {
                "obligation": "ISO 27001 - A.6.1.3",
                "framework": "ISO 27001",
                "control": "C-06.1 - Roles & responsabilites",
                "signals": "5",
                "evidence": _bar(21, 24),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
                "coverage": {"pct": 88},
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Obligation",
        title="Art. 9 - Systeme a haut risque",
        status_label="Conforme",
        status_tone="success",
        summary="Maintenir un systeme de gestion des risques pour l'IA a haut risque.",
        explain=_EX_OBLIGATIONS_DETAIL,
        fields=[
            DetailField("Cadre", "EU AI Act"),
            DetailField("Controle principal", "C-15.1 - Gestion du risque"),
            DetailField("Signaux lies", "12"),
            DetailField("Preuves disponibles", "28 / 30"),
            DetailField("Risque residuel", "Faible", "success"),
            DetailField("Prochaine revue", "30 jun 2026"),
            DetailField("Owner", "Claire Martin"),
        ],
        lists=[
            DetailList(
                "Controles mappes (4)",
                [
                    {"label": "C-15.1 - Gestion du risque", "badge": "Conforme", "tone": "success"},
                    {
                        "label": "C-15.2 - Mesures d'attenuation",
                        "badge": "Conforme",
                        "tone": "success",
                    },
                    {"label": "C-09.1 - Surveillance", "badge": "Partiel", "tone": "warning"},
                    {"label": "C-04.1 - Tests adverses", "badge": "Conforme", "tone": "success"},
                ],
            ),
        ],
        actions=_generer(),
    )
    sections = [
        TabSection(
            "Controles a revoir",
            "list",
            explain=_EX_CONTROLS_REVIEW,
            items=[
                SectionItem(
                    "C-13.2 - Gouvernance des donnees", badge="Partiel", badge_tone="warning"
                ),
                SectionItem("C-12.2 - Disponibilite", badge="Moyen", badge_tone="warning"),
                SectionItem("C-08.1 - Pseudonymisation", badge="Partiel", badge_tone="warning"),
                SectionItem("C-05.2 - Transparence", badge="Partiel", badge_tone="warning"),
                SectionItem("C-DORA.1 - Risques TIC", badge="Moyen", badge_tone="warning"),
            ],
            cta="Voir tous les controles a revoir",
        ),
        TabSection(
            "Gaps de couverture",
            "list",
            explain=_EX_COVERAGE_GAPS,
            items=[
                SectionItem(
                    "C-13.2 - Donnees", "EU AI Act - Art. 10", badge="Gap", badge_tone="danger"
                ),
                SectionItem(
                    "DORA - Art. 28", "Sous-traitance TIC", badge="Gap", badge_tone="danger"
                ),
                SectionItem("RGPD - Art. 35", "AIPD a finaliser", badge="Gap", badge_tone="danger"),
            ],
            cta="Voir les gaps",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("Preuve EV-2026-06-0318 liee a C-15.1", "il y a 1 h"),
                SectionItem("Controle CTRL-13 repasse conforme", "il y a 4 h"),
                SectionItem("Obligation Art. 13 marquee partielle", "il y a 7 h"),
                SectionItem("Revue C-30.1 planifiee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Echeances de remediation",
            "list",
            explain=_EX_REMEDIATION_DEADLINES,
            items=[
                SectionItem(
                    "C-13.2 - Plan de remediation",
                    "dans 12 jours",
                    "27 jun 2026",
                    badge_tone="warning",
                ),
                SectionItem(
                    "C-DORA.1 - Test resilience",
                    "dans 30 jours",
                    "15 jul 2026",
                    badge_tone="neutral",
                ),
                SectionItem(
                    "C-05.2 - Transparence UX", "dans 22 jours", "07 jul 2026", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les echeances",
        ),
    ]
    return CatalogTab(
        "Obligations & controles",
        table_explain=_EX_OBLIGATIONS_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Evaluations ----------------------------------------------------------


def _tab_evaluations() -> CatalogTab:
    kpis = [
        TabKpi("Campagnes d'evaluation", "7", tone="good", explain=_EX_EVAL_CAMPAIGNS),
        TabKpi(
            "Score de conformite",
            "76",
            unit="%",
            delta="+3.0 pp",
            delta_good=True,
            tone="warn",
            explain=_EX_CONFORMITY_SCORE,
        ),
        TabKpi(
            "Controles passes", "512", delta="+4.0%", delta_good=True, explain=_EX_CONTROLS_PASSED
        ),
        TabKpi(
            "Ecarts ouverts",
            "28",
            delta="-6.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_OPEN_GAPS,
        ),
        TabKpi(
            "Preuves rejouees", "105", delta="+5.0%", delta_good=True, explain=_EX_EVIDENCE_REPLAYED
        ),
        TabKpi(
            "Evidence pack readiness", "86", unit="%", tone="good", explain=_EX_EVIDENCE_READINESS
        ),
    ]
    columns = [
        TabColumn("campaign", "Campagne / domaine", "text"),
        TabColumn("coverage", "Couverture", "pct", "right"),
        TabColumn("score", "Score", "pct", "right"),
        TabColumn("obligations", "Obligations", "num", "right"),
        TabColumn("controls", "Controles", "num", "right"),
        TabColumn("signals", "Signaux", "num", "right"),
        TabColumn("evidence", "Preuves", "bar", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "ai_act",
            {
                "campaign": "EU AI Act",
                "coverage": {"pct": 92},
                "score": {"pct": 82},
                "obligations": "96",
                "controls": "248",
                "signals": "312",
                "evidence": _bar(276, 350),
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "rgpd",
            {
                "campaign": "RGPD",
                "coverage": {"pct": 95},
                "score": {"pct": 91},
                "obligations": "124",
                "controls": "312",
                "signals": "428",
                "evidence": _bar(362, 420),
                "owner": _DAMIEN,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "dora",
            {
                "campaign": "DORA",
                "coverage": {"pct": 78},
                "score": {"pct": 69},
                "obligations": "84",
                "controls": "198",
                "signals": "221",
                "evidence": _bar(174, 240),
                "owner": _SOPHIE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "iso42001",
            {
                "campaign": "ISO/IEC 42001",
                "coverage": {"pct": 88},
                "score": {"pct": 85},
                "obligations": "52",
                "controls": "168",
                "signals": "190",
                "evidence": _bar(162, 190),
                "owner": _YACINE,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "iso27001",
            {
                "campaign": "ISO 27001",
                "coverage": {"pct": 90},
                "score": {"pct": 87},
                "obligations": "112",
                "controls": "246",
                "signals": "318",
                "evidence": _bar(312, 360),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "internal",
            {
                "campaign": "Politiques internes",
                "coverage": {"pct": 83},
                "score": {"pct": 80},
                "obligations": "46",
                "controls": "128",
                "signals": "96",
                "evidence": _bar(88, 110),
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Campagne",
        title="EU AI Act",
        status_label="Partiel",
        status_tone="warning",
        summary="Score de conformite 82 % - 11 echecs critiques, 248 controles evalues.",
        explain=_EX_EVAL_DETAIL,
        fields=[
            DetailField("Score de conformite", "82 %", "warning"),
            DetailField("Controles passes", "230 / 248"),
            DetailField("Echecs critiques", "11", "danger"),
            DetailField("Preuves rejouees", "276"),
            DetailField("Derniere campagne", "11 jun 2026"),
            DetailField("Owner", "Claire Martin"),
        ],
        lists=[
            DetailList(
                "Echecs critiques",
                [
                    {
                        "label": "Art. 10 - Gouvernance des donnees",
                        "badge": "Echec",
                        "tone": "danger",
                    },
                    {"label": "Art. 13 - Transparence", "badge": "Echec", "tone": "danger"},
                    {
                        "label": "Art. 9 - Monitoring post-marche",
                        "badge": "Echec",
                        "tone": "danger",
                    },
                ],
            ),
            DetailList(
                "Preuves liees",
                [
                    {"label": "EV-2026-06-0321"},
                    {"label": "EV-2026-06-0309"},
                ],
            ),
        ],
        actions=["Voir les ecarts", "Ouvrir les preuves", "Generer evidence pack"],
    )
    sections = [
        TabSection(
            "Plan de remediation",
            "donut",
            explain=_EX_REMEDIATION_PLAN,
            donut_value=0.0,
            donut_label="28 total",
            items=[
                SectionItem("Critique", value="6", badge_tone="danger"),
                SectionItem("Eleve", value="9", badge_tone="warning"),
                SectionItem("Moyen", value="8", badge_tone="info"),
                SectionItem("Faible", value="5", badge_tone="neutral"),
            ],
            cta="Voir tous les ecarts",
        ),
        TabSection(
            "Tendances des scores",
            "chart",
            explain=_EX_SCORE_TRENDS,
            series=[
                {
                    "label": "EU AI Act",
                    "color": "#3b82f6",
                    "points": [0.74, 0.76, 0.79, 0.80, 0.82],
                },
                {"label": "RGPD", "color": "#10b981", "points": [0.86, 0.88, 0.90, 0.90, 0.91]},
                {"label": "DORA", "color": "#f59e0b", "points": [0.72, 0.71, 0.70, 0.69, 0.69]},
                {
                    "label": "ISO 27001",
                    "color": "#a78bfa",
                    "points": [0.83, 0.84, 0.86, 0.86, 0.87],
                },
            ],
            cta="Voir toutes les tendances",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("Evaluation EU AI Act terminee", "il y a 3 h"),
                SectionItem("Campagne RGPD relancee", "il y a 6 h"),
                SectionItem("Ecart EXC-2026-007 ouvert (DORA)", "hier"),
                SectionItem("Evaluation ISO 27001 completee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Cadres en baisse",
            "list",
            explain=_EX_DECLINING_FRAMEWORKS,
            items=[
                SectionItem("DORA", "score en baisse", "-4 pp", badge_tone="danger"),
                SectionItem(
                    "Code de conduite IA", "score en baisse", "-3 pp", badge_tone="warning"
                ),
                SectionItem("EU AI Act", "score en baisse", "-2 pp", badge_tone="warning"),
            ],
            cta="Voir tous les cadres",
        ),
    ]
    return CatalogTab(
        "Evaluations",
        table_explain=_EX_EVAL_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Incidents & exceptions ----------------------------------------------


def _tab_incidents() -> CatalogTab:
    kpis = [
        TabKpi(
            "Incidents ouverts",
            "42",
            delta="-5.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_OPEN_INCIDENTS,
        ),
        TabKpi(
            "Controles degrades",
            "27",
            delta="-3.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_DEGRADED_CONTROLS,
        ),
        TabKpi("Exceptions approuvees", "14", tone="good", explain=_EX_APPROVED_EXCEPTIONS),
        TabKpi(
            "Exceptions depassees",
            "7",
            delta="+2.0%",
            delta_good=False,
            tone="bad",
            explain=_EX_OVERDUE_EXCEPTIONS,
        ),
        TabKpi(
            "Preuves manquantes",
            "38",
            delta="-4.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_MISSING_EVIDENCE,
        ),
        TabKpi(
            "Evidence pack readiness", "72", unit="%", tone="warn", explain=_EX_EVIDENCE_READINESS
        ),
    ]
    columns = [
        TabColumn("id", "ID", "mono"),
        TabColumn("type", "Type", "badge"),
        TabColumn("scope", "Cadre / obligation", "text"),
        TabColumn("control", "Controle depasse", "text"),
        TabColumn("signal", "Signal", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("due", "Echeance", "text", "right"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "EXC-2026-007",
            {
                "id": "EXC-2026-007",
                "type": _badge("Exception", "info"),
                "scope": "RGPD - Art. 6 (3)",
                "control": "C-08.2 - Minimisation",
                "signal": _badge("Critique", "danger"),
                "owner": _DAMIEN,
                "due": "30 jun 2026",
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "INC-2026-003",
            {
                "id": "INC-2026-003",
                "type": _badge("Incident", "danger"),
                "scope": "EU AI Act - Art. 13",
                "control": "C-05.2 - Transparence",
                "signal": _badge("Eleve", "warning"),
                "owner": _CLAIRE,
                "due": "22 jun 2026",
                "status": _badge("Ouvert", "danger"),
            },
        ),
        TabRow(
            "INC-2026-002",
            {
                "id": "INC-2026-002",
                "type": _badge("Incident", "danger"),
                "scope": "DORA - Art. 17",
                "control": "C-DORA.1 - Risques TIC",
                "signal": _badge("Eleve", "warning"),
                "owner": _SOPHIE,
                "due": "19 jun 2026",
                "status": _badge("En cours", "warning"),
            },
        ),
        TabRow(
            "EXC-2026-009",
            {
                "id": "EXC-2026-009",
                "type": _badge("Exception", "info"),
                "scope": "RGPD - Art. 30",
                "control": "C-30.1 - Registre",
                "signal": _badge("Moyen", "info"),
                "owner": _NADIA,
                "due": "07 jul 2026",
                "status": _badge("Approuvee", "success"),
            },
        ),
        TabRow(
            "EXC-2026-011",
            {
                "id": "EXC-2026-011",
                "type": _badge("Exception", "info"),
                "scope": "ISO 27001 - A.12.4",
                "control": "C-12.4 - Journalisation",
                "signal": _badge("Moyen", "info"),
                "owner": _THOMAS,
                "due": "12 jul 2026",
                "status": _badge("Approuvee", "success"),
            },
        ),
        TabRow(
            "INC-2026-001",
            {
                "id": "INC-2026-001",
                "type": _badge("Incident", "danger"),
                "scope": "EU AI Act - Art. 10",
                "control": "C-13.2 - Donnees",
                "signal": _badge("Critique", "danger"),
                "owner": _CLAIRE,
                "due": "18 jun 2026",
                "status": _badge("Depassee", "danger"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Exception",
        title="EXC-2026-014",
        status_label="Approuvee",
        status_tone="success",
        summary="Derogation temporaire RGPD - Art. 6 (3) en attente de mesure compensatoire.",
        explain=_EX_INCIDENTS_DETAIL,
        fields=[
            DetailField("Cause mere", "Base legale a reconfirmer"),
            DetailField("Obligation liee", "RGPD - Art. 6 (3)"),
            DetailField("Controle", "C-08.2 - Minimisation"),
            DetailField("Preuve liee", "EV-2026-06-0204"),
            DetailField("Echeance", "30 jun 2026", "warning"),
            DetailField("Risque residuel", "Eleve", "danger"),
            DetailField("Owner", "Damien Leroy"),
        ],
        lists=[
            DetailList(
                "Mesure compensatoire",
                [
                    {"label": "Pseudonymisation renforcee"},
                    {"label": "Revue trimestrielle dediee"},
                ],
            ),
            DetailList(
                "Chaine d'approbation",
                [
                    {"label": "Nadia El Idrissi", "badge": "Validee", "tone": "success"},
                    {"label": "Sophie Bernard", "badge": "Validee", "tone": "success"},
                    {"label": "Comite Conformite", "badge": "En attente", "tone": "warning"},
                ],
            ),
        ],
        actions=[
            "Nouvelle exception",
            "Ouvrir la preuve",
            "Ajouter une preuve",
            "Generer evidence pack",
        ],
    )
    sections = [
        TabSection(
            "Exceptions a echeance proche",
            "list",
            explain=_EX_EXCEPTIONS_DUE,
            items=[
                SectionItem("EXC-2026-007", "RGPD - Art. 6", "30 jun 2026", badge_tone="warning"),
                SectionItem("EXC-2026-005", "DORA - Art. 28", "02 jul 2026", badge_tone="neutral"),
                SectionItem(
                    "EXC-2026-002", "EU AI Act - Art. 13", "05 jul 2026", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les exceptions",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("INC-2026-003 escalade a Sophie Bernard", "il y a 1 h"),
                SectionItem("EXC-2026-009 approuvee", "il y a 4 h"),
                SectionItem("Preuve EV-2026-06-0204 ajoutee", "il y a 6 h"),
                SectionItem("INC-2026-001 marquee depassee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Tendances d'ecarts",
            "chart",
            explain=_EX_GAP_TRENDS,
            series=[
                {"label": "Incidents", "color": "#ef4444", "points": [38, 41, 44, 43, 42]},
                {"label": "Exceptions", "color": "#3b82f6", "points": [9, 11, 12, 13, 14]},
                {"label": "Resolution", "color": "#10b981", "points": [22, 24, 28, 31, 34]},
            ],
            cta="Voir toutes les tendances",
        ),
        TabSection(
            "Owners sollicites",
            "bars",
            explain=_EX_OWNERS_LOAD,
            bars=[
                {"label": "Claire Martin", "value": 0.9, "tone": "danger"},
                {"label": "Damien Leroy", "value": 0.7, "tone": "warning"},
                {"label": "Sophie Bernard", "value": 0.55, "tone": "warning"},
                {"label": "Yacine Sekri", "value": 0.4, "tone": "info"},
            ],
        ),
    ]
    return CatalogTab(
        "Incidents & exceptions",
        table_explain=_EX_INCIDENTS_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Purge & retention ----------------------------------------------------


def _tab_retention() -> CatalogTab:
    kpis = [
        TabKpi("Ressources sous retention", "38", tone="good", explain=_EX_RESOURCES_RETAINED),
        TabKpi(
            "Delais de purge respectes",
            "112",
            delta="+2.0%",
            delta_good=True,
            explain=_EX_PURGE_ON_TIME,
        ),
        TabKpi(
            "Jobs de purge planifies",
            "246",
            delta="+4.0%",
            delta_good=True,
            explain=_EX_PURGE_JOBS,
        ),
        TabKpi("Legal holds actifs", "8", sub="dossiers", explain=_EX_LEGAL_HOLDS),
        TabKpi(
            "Ecarts de retention",
            "8",
            delta="-3.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_RETENTION_GAPS,
        ),
        TabKpi(
            "Evidence pack readiness", "86", unit="%", tone="good", explain=_EX_EVIDENCE_READINESS
        ),
    ]
    columns = [
        TabColumn("resource", "Ressource", "text"),
        TabColumn("basis", "Base legale / cadre", "text"),
        TabColumn("target", "Duree cible", "text", "right"),
        TabColumn("mode", "Controle de purge", "badge"),
        TabColumn("signal", "Signal", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "logs",
            {
                "resource": "Logs d'agent",
                "basis": "Interet legitime - RGPD Art. 6",
                "target": "90 jours",
                "mode": _badge("Automatique", "success"),
                "signal": _badge("OK", "success"),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "transcripts",
            {
                "resource": "Transcriptions",
                "basis": "Consentement - RGPD Art. 6",
                "target": "180 jours",
                "mode": _badge("Automatique", "success"),
                "signal": _badge("Retard", "warning"),
                "owner": _DAMIEN,
                "status": _badge("En retard", "warning"),
            },
        ),
        TabRow(
            "tickets",
            {
                "resource": "Tickets support",
                "basis": "Obligation legale - LPF",
                "target": "3 ans",
                "mode": _badge("Manuel", "warning"),
                "signal": _badge("Moyen", "info"),
                "owner": _SOPHIE,
                "status": _badge("A corriger", "warning"),
            },
        ),
        TabRow(
            "exports",
            {
                "resource": "Exports SIEM",
                "basis": "Securite - ISO 27001",
                "target": "1 an",
                "mode": _badge("Automatique", "success"),
                "signal": _badge("OK", "success"),
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "embeddings",
            {
                "resource": "Embeddings",
                "basis": "Interet legitime - RGPD Art. 6",
                "target": "180 jours",
                "mode": _badge("Manuel", "warning"),
                "signal": _badge("Critique", "danger"),
                "owner": _YACINE,
                "status": _badge("Bloque", "danger"),
            },
        ),
        TabRow(
            "evals",
            {
                "resource": "Jeux d'evaluation",
                "basis": "Interet legitime - RGPD Art. 6",
                "target": "2 ans",
                "mode": _badge("Manuel", "warning"),
                "signal": _badge("OK", "success"),
                "owner": _THOMAS,
                "status": _badge("Bloque", "danger"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Regle de retention",
        title="Logs d'agent",
        status_label="Conforme",
        status_tone="success",
        summary="Retention 90 jours sur interet legitime, purge automatique nocturne.",
        explain=_EX_RETENTION_DETAIL,
        fields=[
            DetailField("Stockage", "Cloud SQL - Postgres"),
            DetailField("Strategie de suppression", "Purge automatique"),
            DetailField("Methode de purge", "DELETE + VACUUM nocturne"),
            DetailField("Legal hold", "Aucun", "neutral"),
            DetailField("Proprietaire", "Nadia El Idrissi"),
            DetailField("Prochaine purge", "20 jun 2026"),
            DetailField("Dernier artefact de purge", "PRG-2026-06-118"),
        ],
        lists=[
            DetailList(
                "Controles lies (3)",
                [
                    {"label": "C-10.1 - Securite", "badge": "Conforme", "tone": "success"},
                    {"label": "C-06.6 - Retention", "badge": "Conforme", "tone": "success"},
                    {"label": "C-17.1 - Effacement", "badge": "Conforme", "tone": "success"},
                ],
            ),
        ],
        actions=["Forcer revue", "Ouvrir les preuves", "Generer evidence pack"],
    )
    sections = [
        TabSection(
            "Purges a venir (7 jours)",
            "list",
            explain=_EX_UPCOMING_PURGES,
            items=[
                SectionItem("Embeddings", "purge manuelle", "18 jun 2026", badge_tone="danger"),
                SectionItem("Transcriptions", "purge auto", "19 jun 2026", badge_tone="warning"),
                SectionItem("Logs d'agent", "purge auto", "20 jun 2026", badge_tone="neutral"),
                SectionItem(
                    "Tickets support", "purge manuelle", "22 jun 2026", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les purges",
        ),
        TabSection(
            "Exceptions actives",
            "list",
            explain=_EX_RETENTION_EXCEPTIONS,
            items=[
                SectionItem(
                    "Jeux d'evaluation", "legal hold actif", badge="Bloque", badge_tone="danger"
                ),
                SectionItem(
                    "Embeddings", "purge manuelle en retard", badge="Critique", badge_tone="danger"
                ),
                SectionItem(
                    "Tickets support", "purge manuelle", badge="A corriger", badge_tone="warning"
                ),
            ],
            cta="Voir toutes les exceptions",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("Purge auto Logs d'agent executee", "il y a 2 h"),
                SectionItem("Legal hold ajoute sur Jeux d'evaluation", "il y a 5 h"),
                SectionItem("Transcriptions purge en retard signalee", "il y a 9 h"),
                SectionItem("Regle Exports SIEM mise a jour", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Couverture par systeme",
            "bars",
            explain=_EX_COVERAGE_BY_SYSTEM,
            bars=[
                {"label": "Postgres", "value": 0.95, "tone": "success"},
                {"label": "Object store", "value": 0.72, "tone": "warning"},
                {"label": "Vertex", "value": 0.6, "tone": "warning"},
                {"label": "Helpdesk", "value": 0.81, "tone": "info"},
                {"label": "SIEM", "value": 0.9, "tone": "success"},
            ],
        ),
    ]
    return CatalogTab(
        "Purge & retention",
        table_explain=_EX_RETENTION_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Preuves & attestations ----------------------------------------------


def _tab_evidence() -> CatalogTab:
    kpis = [
        TabKpi(
            "Preuves disponibles",
            "8 246",
            delta="+2.0%",
            delta_good=True,
            tone="good",
            explain=_EX_AVAILABLE_EVIDENCE,
        ),
        TabKpi(
            "Attestations valides",
            "7 112",
            delta="+1.0%",
            delta_good=True,
            explain=_EX_VALID_ATTESTATIONS,
        ),
        TabKpi(
            "Preuves expirantes",
            "312",
            delta="+4.0%",
            delta_good=False,
            tone="warn",
            explain=_EX_EXPIRING_EVIDENCE,
        ),
        TabKpi(
            "Manquant / corrompu",
            "28",
            delta="-2.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_MISSING_CORRUPT,
        ),
        TabKpi("Couverture preuve", "86", unit="%", tone="good", explain=_EX_EVIDENCE_COVERAGE),
        TabKpi("Evidence pack", "Prete", tone="good", explain=_EX_EVIDENCE_PACK_STATE),
    ]
    columns = [
        TabColumn("id", "Preuve", "mono"),
        TabColumn("scope", "Cadre / obligation", "text"),
        TabColumn("control", "Controle", "text"),
        TabColumn("kind", "Type", "badge"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("date", "Date", "text", "right"),
        TabColumn("validity", "Validite", "text", "right"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "PRV-2026-06-0123",
            {
                "id": "PRV-2026-06-0123",
                "scope": "EU AI Act - Art. 9",
                "control": "C-15.1 - Gestion du risque",
                "kind": _badge("Rapport", "info"),
                "owner": _CLAIRE,
                "date": "11 jun 2026",
                "validity": "12 mois",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PRV-2026-06-0118",
            {
                "id": "PRV-2026-06-0118",
                "scope": "RGPD - Art. 30",
                "control": "C-30.1 - Registre",
                "kind": _badge("Export", "neutral"),
                "owner": _DAMIEN,
                "date": "10 jun 2026",
                "validity": "6 mois",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PRV-2026-05-0091",
            {
                "id": "PRV-2026-05-0091",
                "scope": "DORA - Art. 28",
                "control": "C-DORA.1 - Risques TIC",
                "kind": _badge("Attestation", "info"),
                "owner": _SOPHIE,
                "date": "28 mai 2026",
                "validity": "30 jours",
                "status": _badge("Expirante", "warning"),
            },
        ),
        TabRow(
            "PRV-2026-06-0102",
            {
                "id": "PRV-2026-06-0102",
                "scope": "ISO 27001 - A.12",
                "control": "C-12.4 - Journalisation",
                "kind": _badge("Log signe", "neutral"),
                "owner": _NADIA,
                "date": "09 jun 2026",
                "validity": "12 mois",
                "status": _badge("Valide", "success"),
            },
        ),
        TabRow(
            "PRV-2026-04-0044",
            {
                "id": "PRV-2026-04-0044",
                "scope": "EU AI Act - Art. 13",
                "control": "C-05.2 - Transparence",
                "kind": _badge("Capture", "neutral"),
                "owner": _CLAIRE,
                "date": "14 avr 2026",
                "validity": "expiree",
                "status": _badge("Manquante", "danger"),
            },
        ),
        TabRow(
            "PRV-2026-06-0130",
            {
                "id": "PRV-2026-06-0130",
                "scope": "SOC 2 - CC7",
                "control": "C-12.2 - Disponibilite",
                "kind": _badge("Dossier de contrôle", "info"),
                "owner": _THOMAS,
                "date": "12 jun 2026",
                "validity": "12 mois",
                "status": _badge("Valide", "success"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Preuve",
        title="PRV-2026-06-0123",
        status_label="Valide",
        status_tone="success",
        summary="Rapport de gestion du risque EU AI Act - Art. 9, signe et horodate.",
        explain=_EX_EVIDENCE_DETAIL,
        fields=[
            DetailField("Cadre", "EU AI Act - Art. 9"),
            DetailField("Controle", "C-15.1 - Gestion du risque"),
            DetailField("Type", "Rapport"),
            DetailField("Genere le", "11 jun 2026"),
            DetailField("Validite", "12 mois"),
            DetailField("Empreinte", "sha256:9f3a...c021"),
            DetailField("Proprietaire", "Claire Martin"),
        ],
        lists=[
            DetailList(
                "Obligations liees (3)",
                [
                    {"label": "Art. 9 - Gestion du risque"},
                    {"label": "Art. 15 - Exactitude"},
                    {"label": "Art. 17 - SMQ"},
                ],
            ),
            DetailList(
                "Proprietaire & signature",
                [
                    {"label": "Claire Martin", "badge": "Signee", "tone": "success"},
                ],
            ),
        ],
        actions=["Voir evidence pack", "Telecharger preuve", "Combiner evidence pack"],
    )
    sections = [
        TabSection(
            "Preuves a renouveler (312)",
            "list",
            explain=_EX_EVIDENCE_RENEW,
            items=[
                SectionItem(
                    "PRV-2026-05-0091", "DORA - Art. 28", "dans 6 jours", badge_tone="warning"
                ),
                SectionItem(
                    "PRV-2026-05-0073", "RGPD - Art. 32", "dans 11 jours", badge_tone="warning"
                ),
                SectionItem(
                    "PRV-2026-05-0061", "ISO 27001 - A.9", "dans 18 jours", badge_tone="neutral"
                ),
            ],
            cta="Voir toutes les preuves a renouveler",
        ),
        TabSection(
            "Dernieres attestations",
            "activity",
            explain=_EX_LATEST_ATTESTATIONS,
            items=[
                SectionItem("PRV-2026-06-0130 generee (SOC 2)", "il y a 1 h"),
                SectionItem("PRV-2026-06-0123 signee (EU AI Act)", "il y a 3 h"),
                SectionItem("PRV-2026-06-0118 exportee (RGPD)", "il y a 6 h"),
                SectionItem("PRV-2026-06-0102 horodatee (ISO)", "hier"),
            ],
            cta="Voir toutes les attestations",
        ),
        TabSection(
            "Couverture par cadre",
            "donut",
            explain=_EX_COVERAGE_BY_FRAMEWORK,
            donut_value=0.865,
            donut_label="Couverture",
            items=[
                SectionItem("EU AI Act", value="82 %", badge_tone="warning"),
                SectionItem("RGPD", value="91 %", badge_tone="success"),
                SectionItem("DORA", value="73 %", badge_tone="warning"),
                SectionItem("ISO 27001", value="88 %", badge_tone="success"),
            ],
            cta="Voir le detail par cadre",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("Evidence pack EU AI Act genere", "il y a 2 h"),
                SectionItem("Preuve PRV-2026-04-0044 marquee manquante", "il y a 7 h"),
                SectionItem("Attestation DORA renouvelee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
    ]
    return CatalogTab(
        "Inventaire des preuves & attestations",
        table_explain=_EX_EVIDENCE_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


# --- Registre des traitements --------------------------------------------


def _tab_registry() -> CatalogTab:
    kpis = [
        TabKpi("Traitements enregistres", "36", tone="good", explain=_EX_REGISTERED_PROCESSINGS),
        TabKpi(
            "Finalites documentees",
            "36",
            delta="+5.0%",
            delta_good=True,
            explain=_EX_DOCUMENTED_PURPOSES,
        ),
        TabKpi("Bases legales valides", "36", tone="good", explain=_EX_VALID_LEGAL_BASES),
        TabKpi(
            "Durees de retention conformes",
            "33",
            delta="+2.0%",
            delta_good=True,
            explain=_EX_COMPLIANT_RETENTION,
        ),
        TabKpi(
            "Ecarts de registre",
            "4",
            delta="-3.0%",
            delta_good=True,
            tone="warn",
            explain=_EX_REGISTRY_GAPS,
        ),
        TabKpi(
            "Evidence pack readiness", "84", unit="%", tone="good", explain=_EX_EVIDENCE_READINESS
        ),
    ]
    columns = [
        TabColumn("name", "Traitement", "text"),
        TabColumn("purpose", "Finalite", "text"),
        TabColumn("basis", "Base legale", "text"),
        TabColumn("data", "Donnees", "text"),
        TabColumn("retention", "Duree de retention", "text", "right"),
        TabColumn("controls", "Controles", "num", "right"),
        TabColumn("owner", "Owner", "owner"),
        TabColumn("status", "Statut", "badge"),
    ]
    rows = [
        TabRow(
            "scoring",
            {
                "name": "Scoring credit",
                "purpose": "Evaluation de solvabilite",
                "basis": "Contrat - RGPD Art. 6",
                "data": "Donnees financieres",
                "retention": "5 ans",
                "controls": "8",
                "owner": _SOPHIE,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "fraud",
            {
                "name": "Lutte anti-fraude",
                "purpose": "Detection de fraude",
                "basis": "Interet legitime",
                "data": "Transactions",
                "retention": "3 ans",
                "controls": "7",
                "owner": _NADIA,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "support",
            {
                "name": "Support client IA",
                "purpose": "Assistance conversationnelle",
                "basis": "Consentement",
                "data": "Identifiant, contenu",
                "retention": "180 jours",
                "controls": "6",
                "owner": _CLAIRE,
                "status": _badge("Partiel", "warning"),
            },
        ),
        TabRow(
            "auth",
            {
                "name": "Authentification & KYC",
                "purpose": "Verification d'identite",
                "basis": "Obligation legale",
                "data": "Identite, documents",
                "retention": "5 ans",
                "controls": "9",
                "owner": _DAMIEN,
                "status": _badge("Conforme", "success"),
            },
        ),
        TabRow(
            "kyc_screen",
            {
                "name": "KYC Screening",
                "purpose": "Sanctions & PEP",
                "basis": "Obligation legale - LCB-FT",
                "data": "Identite, listes",
                "retention": "5 ans",
                "controls": "7",
                "owner": _THOMAS,
                "status": _badge("Partiel", "warning"),
            },
        ),
    ]
    detail = TabDetail(
        eyebrow="Traitement",
        title="Scoring credit",
        status_label="Conforme",
        status_tone="success",
        summary="Evaluation de solvabilite sur base contractuelle, sans decision automatisee.",
        explain=_EX_REGISTRY_DETAIL,
        fields=[
            DetailField("Categorie de donnees", "Donnees financieres"),
            DetailField("Finalite", "Evaluation de solvabilite"),
            DetailField("Base legale", "Execution du contrat"),
            DetailField("Transferts", "Aucun hors UE", "success"),
            DetailField("Sous-traitants", "2 (UE)"),
            DetailField("Duree", "5 ans"),
            DetailField("Prochaine revue", "20 jun 2026"),
        ],
        lists=[
            DetailList(
                "Controles lies (4)",
                [
                    {"label": "C-08.2 - Minimisation", "badge": "Conforme", "tone": "success"},
                    {"label": "C-22.1 - Decision auto", "badge": "Conforme", "tone": "success"},
                    {"label": "C-13.2 - Donnees", "badge": "Partiel", "tone": "warning"},
                    {"label": "C-06.6 - Retention", "badge": "Conforme", "tone": "success"},
                ],
            ),
        ],
        actions=[
            "Ajouter un traitement",
            "Ouvrir les preuves",
            "Planifier une revue",
            "Generer evidence pack",
        ],
    )
    sections = [
        TabSection(
            "Registres a completer (4)",
            "list",
            explain=_EX_REGISTRY_TODO,
            items=[
                SectionItem(
                    "Privacy Impact Assessment",
                    "Support client IA",
                    badge="A faire",
                    badge_tone="warning",
                ),
                SectionItem(
                    "Base legale a justifier",
                    "KYC Screening",
                    badge="A faire",
                    badge_tone="warning",
                ),
                SectionItem(
                    "Sous-traitant a documenter",
                    "Lutte anti-fraude",
                    badge="A faire",
                    badge_tone="warning",
                ),
                SectionItem(
                    "Duree a confirmer", "Support client IA", badge="A faire", badge_tone="warning"
                ),
            ],
            cta="Voir les registres a completer",
        ),
        TabSection(
            "Revues programmees (4)",
            "list",
            explain=_EX_SCHEDULED_REVIEWS,
            items=[
                SectionItem(
                    "Scoring credit", "revue annuelle", "20 jun 2026", badge_tone="neutral"
                ),
                SectionItem(
                    "Lutte anti-fraude", "revue annuelle", "30 jun 2026", badge_tone="neutral"
                ),
                SectionItem("KYC Screening", "revue annuelle", "12 jul 2026", badge_tone="neutral"),
            ],
            cta="Voir toutes les revues",
        ),
        TabSection(
            "Activites recentes",
            "activity",
            explain=_EX_RECENT_ACTIVITY,
            items=[
                SectionItem("Traitement Scoring credit mis a jour", "il y a 3 h"),
                SectionItem("AIPD Support client IA ouverte", "il y a 6 h"),
                SectionItem("Base legale KYC Screening signalee", "hier"),
            ],
            cta="Voir toutes les activites",
        ),
        TabSection(
            "Exceptions liees (4)",
            "list",
            explain=_EX_LINKED_EXCEPTIONS,
            items=[
                SectionItem(
                    "EXC-2026-007", "Support client IA", badge="Partiel", badge_tone="warning"
                ),
                SectionItem(
                    "EXC-2026-009", "KYC Screening", badge="Approuvee", badge_tone="success"
                ),
                SectionItem(
                    "EXC-2026-011", "Lutte anti-fraude", badge="Approuvee", badge_tone="success"
                ),
            ],
            cta="Voir toutes les exceptions",
        ),
    ]
    return CatalogTab(
        "Registre des traitements",
        table_explain=_EX_REGISTRY_TABLE,
        kpis=kpis,
        columns=columns,
        rows=rows,
        detail=detail,
        sections=sections,
    )


def _build_fr_tabs() -> dict[str, CatalogTab]:
    """Return the deterministic French per-tab payloads (the source of truth)."""
    return {
        "mapping": _tab_mapping(),
        "obligations": _tab_obligations(),
        "evaluations": _tab_evaluations(),
        "incidents": _tab_incidents(),
        "retention": _tab_retention(),
        "evidence": _tab_evidence(),
        "registry": _tab_registry(),
    }


# Generic translation layer (same approach as ``incidents_tabs``): the catalogue
# is authored in French; for DE / EN every string leaf of the assembled tab tree
# is mapped through ``_TR``. Unmapped strings (codes, person names, standards,
# tech, role titles) fall through verbatim, so a missing entry is a French label,
# never a crash.
_LANG_IDX = {"fr": 0, "de": 1, "en": 2}

_TR: dict[str, tuple[str, str]] = {
    # --- KPI / status / chrome vocabulary -----------------------------------
    "Cadres actifs": ("Aktive Rahmenwerke", "Active frameworks"),
    "Cadres a surveiller": ("Zu beobachtende Rahmenwerke", "Frameworks to watch"),
    "Cadres en baisse": ("Ruecklaeufige Rahmenwerke", "Declining frameworks"),
    "Obligations actives": ("Aktive Pflichten", "Active obligations"),
    "Obligations a risque": ("Gefaehrdete Pflichten", "Obligations at risk"),
    "Obligations mappees": ("Zugeordnete Pflichten", "Mapped obligations"),
    "Controles mappes": ("Zugeordnete Kontrollen", "Mapped controls"),
    "Controles a revoir": ("Zu pruefende Kontrollen", "Controls to review"),
    "Controles degrades": ("Verschlechterte Kontrollen", "Degraded controls"),
    "Controles passes": ("Bestandene Kontrollen", "Passed controls"),
    "Controles lies": ("Verknuepfte Kontrollen", "Linked controls"),
    "Couverture": ("Abdeckung", "Coverage"),
    "Couverture par cadre": ("Abdeckung nach Rahmenwerk", "Coverage by framework"),
    "Couverture par systeme": ("Abdeckung nach System", "Coverage by system"),
    "Couverture preuve": ("Nachweisabdeckung", "Evidence coverage"),
    "Score de conformite": ("Konformitaetsscore", "Compliance score"),
    "Echecs critiques": ("Kritische Fehler", "Critical failures"),
    "Exceptions actives": ("Aktive Ausnahmen", "Active exceptions"),
    "Exceptions approuvees": ("Genehmigte Ausnahmen", "Approved exceptions"),
    "Exceptions depassees": ("Ueberfaellige Ausnahmen", "Overdue exceptions"),
    "Exceptions a echeance proche": ("Ausnahmen mit naher Frist", "Exceptions due soon"),
    "Incidents ouverts": ("Offene Vorfaelle", "Open incidents"),
    "Ecarts ouverts": ("Offene Abweichungen", "Open gaps"),
    "Gaps de couverture": ("Abdeckungsluecken", "Coverage gaps"),
    "Legal holds actifs": ("Aktive Legal Holds", "Active legal holds"),
    "Attestations valides": ("Gueltige Bescheinigungen", "Valid attestations"),
    "Preuves disponibles": ("Verfuegbare Nachweise", "Available evidence"),
    "Preuves manquantes": ("Fehlende Nachweise", "Missing evidence"),
    "Preuves expirantes": ("Ablaufende Nachweise", "Expiring evidence"),
    "Preuves rejouees": ("Wiederholte Nachweise", "Replayed evidence"),
    "Preuves liees": ("Verknuepfte Nachweise", "Linked evidence"),
    "Bases legales valides": ("Gueltige Rechtsgrundlagen", "Valid legal bases"),
    "Finalites documentees": ("Dokumentierte Zwecke", "Documented purposes"),
    "Durees de retention conformes": (
        "Konforme Aufbewahrungsfristen",
        "Compliant retention periods",
    ),
    "Delais de purge respectes": ("Eingehaltene Loeschfristen", "Purge deadlines met"),
    "Jobs de purge planifies": ("Geplante Loeschjobs", "Scheduled purge jobs"),
    "Ressources sous retention": ("Ressourcen unter Aufbewahrung", "Resources under retention"),
    "Traitements enregistres": ("Registrierte Verarbeitungen", "Registered processings"),
    "Ecarts de registre": ("Registerabweichungen", "Register gaps"),
    "Ecarts de retention": ("Aufbewahrungsabweichungen", "Retention gaps"),
    "Owners sollicites": ("Angefragte Owner", "Owners requested"),
    "Evidence pack readiness": ("Evidence-Pack-Bereitschaft", "Evidence pack readiness"),
    # --- statuses / badges ---------------------------------------------------
    "Conforme": ("Konform", "Compliant"),
    "Partiel": ("Teilweise", "Partial"),
    "Partielle": ("Teilweise", "Partial"),
    "Applicable partielle": ("Teilweise anwendbar", "Partially applicable"),
    "Applicable des classification": (
        "Anwendbar ab Klassifizierung",
        "Applicable from classification",
    ),
    "Echec": ("Fehler", "Failure"),
    "Critique": ("Kritisch", "Critical"),
    "Eleve": ("Hoch", "High"),
    "Moyen": ("Mittel", "Medium"),
    "Faible": ("Niedrig", "Low"),
    "Ouvert": ("Offen", "Open"),
    "En cours": ("Laufend", "In progress"),
    "En attente": ("Ausstehend", "Pending"),
    "En retard": ("Verspaetet", "Late"),
    "Retard": ("Verspaetung", "Late"),
    "Approuvee": ("Genehmigt", "Approved"),
    "Validee": ("Validiert", "Validated"),
    "Valide": ("Gueltig", "Valid"),
    "Signee": ("Signiert", "Signed"),
    "Prete": ("Bereit", "Ready"),
    "Nouveau": ("Neu", "New"),
    "Depassee": ("Ueberfaellig", "Overdue"),
    "Expirante": ("Ablaufend", "Expiring"),
    "Bloque": ("Blockiert", "Blocked"),
    "Manquante": ("Fehlend", "Missing"),
    "Manquant / corrompu": ("Fehlend / beschaedigt", "Missing / corrupted"),
    "Proposition en cours": ("Vorschlag laufend", "Proposal in progress"),
    "Automatique": ("Automatisch", "Automatic"),
    "Manuel": ("Manuell", "Manual"),
    "A corriger": ("Zu korrigieren", "To fix"),
    "A faire": ("Zu erledigen", "To do"),
    "Aucun": ("Keiner", "None"),
    "Aucun hors UE": ("Keiner ausserhalb der EU", "None outside the EU"),
    # --- column headers / field labels --------------------------------------
    "Cadre": ("Rahmenwerk", "Framework"),
    "Cadre / obligation": ("Rahmenwerk / Pflicht", "Framework / obligation"),
    "Article / Domaine": ("Artikel / Bereich", "Article / Domain"),
    "Articles applicables": ("Anwendbare Artikel", "Applicable articles"),
    "Obligation": ("Pflicht", "Obligation"),
    "Obligation liee": ("Verknuepfte Pflicht", "Linked obligation"),
    "Controle": ("Kontrolle", "Control"),
    "Controle principal": ("Hauptkontrolle", "Main control"),
    "Controles": ("Kontrollen", "Controls"),
    "Statut": ("Status", "Status"),
    "Score": ("Score", "Score"),
    "Type": ("Typ", "Type"),
    "Date": ("Datum", "Date"),
    "Duree": ("Dauer", "Duration"),
    "Duree cible": ("Zieldauer", "Target duration"),
    "Duree de retention": ("Aufbewahrungsdauer", "Retention period"),
    "Duree a confirmer": ("Dauer zu bestaetigen", "Duration to confirm"),
    "Echeance": ("Frist", "Due date"),
    "Owner": ("Owner", "Owner"),
    "Proprietaire": ("Eigentuemer", "Owner"),
    "Proprietaire & signature": ("Eigentuemer & Signatur", "Owner & signature"),
    "Ressource": ("Ressource", "Resource"),
    "Resolution": ("Loesung", "Resolution"),
    "Risque residuel": ("Restrisiko", "Residual risk"),
    "Niveau de risque residuel": ("Restrisikoniveau", "Residual risk level"),
    "Categorie de donnees": ("Datenkategorie", "Data category"),
    "Base legale": ("Rechtsgrundlage", "Legal basis"),
    "Base legale / cadre": ("Rechtsgrundlage / Rahmen", "Legal basis / framework"),
    "Finalite": ("Zweck", "Purpose"),
    "Traitement": ("Verarbeitung", "Processing"),
    "Campagne": ("Kampagne", "Campaign"),
    "Campagne / domaine": ("Kampagne / Bereich", "Campaign / domain"),
    "Methode de purge": ("Loeschmethode", "Purge method"),
    "Regle de retention": ("Aufbewahrungsregel", "Retention rule"),
    "Stockage": ("Speicher", "Storage"),
    "Cause mere": ("Grundursache", "Root cause"),
    "Empreinte": ("Fingerabdruck", "Fingerprint"),
    "Signal": ("Signal", "Signal"),
    "Signaux": ("Signale", "Signals"),
    "Signaux lies": ("Verknuepfte Signale", "Linked signals"),
    "Signaux par preuve": ("Signale pro Nachweis", "Signals per evidence"),
    "Validite": ("Gueltigkeit", "Validity"),
    "Veille": ("Beobachtung", "Watch"),
    "Mesure compensatoire": ("Ausgleichsmassnahme", "Compensating measure"),
    "Chaine d'approbation": ("Genehmigungskette", "Approval chain"),
    "Niveau de risque": ("Risikoniveau", "Risk level"),
    # --- section / tab titles -----------------------------------------------
    "Cartographie reglementaire": ("Regulatorische Kartierung", "Regulatory mapping"),
    "Obligations & controles": ("Pflichten & Kontrollen", "Obligations & controls"),
    "Evaluations": ("Evaluierungen", "Evaluations"),
    "Incidents & exceptions": ("Vorfaelle & Ausnahmen", "Incidents & exceptions"),
    "Purge & retention": ("Loeschung & Aufbewahrung", "Purge & retention"),
    "Registre des traitements": ("Verarbeitungsverzeichnis", "Processing register"),
    "Inventaire des preuves & attestations": (
        "Inventar der Nachweise & Bescheinigungen",
        "Evidence & attestations inventory",
    ),
    "Campagnes d'evaluation": ("Evaluierungskampagnen", "Evaluation campaigns"),
    "Jeux d'evaluation": ("Evaluierungssets", "Evaluation sets"),
    "Echeances reglementaires": ("Regulatorische Fristen", "Regulatory deadlines"),
    "Echeances de remediation": ("Behebungsfristen", "Remediation deadlines"),
    "Tendances des scores": ("Score-Trends", "Score trends"),
    "Tendances d'ecarts": ("Abweichungstrends", "Gap trends"),
    "Actions rapides": ("Schnellaktionen", "Quick actions"),
    "Activites recentes": ("Letzte Aktivitaeten", "Recent activities"),
    "Dernieres attestations": ("Letzte Bescheinigungen", "Latest attestations"),
    "Dernieres preuves": ("Letzte Nachweise", "Latest evidence"),
    "Derniere campagne": ("Letzte Kampagne", "Latest campaign"),
    "Dernier artefact de purge": ("Letztes Loesch-Artefakt", "Latest purge artifact"),
    "Controles lies (3)": ("Verknuepfte Kontrollen (3)", "Linked controls (3)"),
    "Controles lies (4)": ("Verknuepfte Kontrollen (4)", "Linked controls (4)"),
    "Controles mappes (4)": ("Zugeordnete Kontrollen (4)", "Mapped controls (4)"),
    "Obligations liees (3)": ("Verknuepfte Pflichten (3)", "Linked obligations (3)"),
    "Exceptions liees (4)": ("Verknuepfte Ausnahmen (4)", "Linked exceptions (4)"),
    "Preuves a renouveler (312)": ("Zu erneuernde Nachweise (312)", "Evidence to renew (312)"),
    "Registres a completer (4)": (
        "Zu vervollstaendigende Register (4)",
        "Registers to complete (4)",
    ),
    "Revues programmees (4)": ("Geplante Pruefungen (4)", "Scheduled reviews (4)"),
    "Purges a venir (7 jours)": ("Kommende Loeschungen (7 Tage)", "Upcoming purges (7 days)"),
    "Prochaine purge": ("Naechste Loeschung", "Next purge"),
    "Prochaine revue": ("Naechste Pruefung", "Next review"),
    "Gestion du risque": ("Risikomanagement", "Risk management"),
    "Plan de remediation": ("Behebungsplan", "Remediation plan"),
    "Strategie de suppression": ("Loeschstrategie", "Deletion strategy"),
    "Controle de purge": ("Loeschkontrolle", "Purge control"),
    "Logs d'agent": ("Agent-Protokolle", "Agent logs"),
    "Exports SIEM": ("SIEM-Exporte", "SIEM exports"),
    "Tickets support": ("Support-Tickets", "Support tickets"),
    "Transcriptions": ("Transkripte", "Transcripts"),
    "Transactions": ("Transaktionen", "Transactions"),
    "Transferts": ("Uebertragungen", "Transfers"),
    "Sous-traitants": ("Auftragsverarbeiter", "Processors"),
    "Sous-traitance TIC": ("IKT-Auslagerung", "ICT outsourcing"),
    "Donnees": ("Daten", "Data"),
    "Donnees financieres": ("Finanzdaten", "Financial data"),
    "Consentement": ("Einwilligung", "Consent"),
    "Interet legitime": ("Berechtigtes Interesse", "Legitimate interest"),
    "Obligation legale": ("Rechtliche Verpflichtung", "Legal obligation"),
    "Execution du contrat": ("Vertragserfuellung", "Contract performance"),
    "Lutte anti-fraude": ("Betrugsbekaempfung", "Anti-fraud"),
    "Detection de fraude": ("Betrugserkennung", "Fraud detection"),
    "Evaluation de solvabilite": ("Bonitaetspruefung", "Creditworthiness assessment"),
    "Scoring credit": ("Kredit-Scoring", "Credit scoring"),
    "Verification d'identite": ("Identitaetspruefung", "Identity verification"),
    "Authentification & KYC": ("Authentifizierung & KYC", "Authentication & KYC"),
    "Sanctions & PEP": ("Sanktionen & PEP", "Sanctions & PEP"),
    "Assistance conversationnelle": ("Konversationsunterstuetzung", "Conversational assistance"),
    "Support client IA": ("KI-Kundensupport", "AI customer support"),
    "Pseudonymisation renforcee": ("Verstaerkte Pseudonymisierung", "Reinforced pseudonymization"),
    "Identite, documents": ("Identitaet, Dokumente", "Identity, documents"),
    "Identite, listes": ("Identitaet, Listen", "Identity, lists"),
    "Identifiant, contenu": ("Kennung, Inhalt", "Identifier, content"),
    "Code de conduite IA": ("KI-Verhaltenskodex", "AI code of conduct"),
    "Politiques internes": ("Interne Richtlinien", "Internal policies"),
    "Privacy Impact Assessment": ("Datenschutz-Folgenabschaetzung", "Privacy Impact Assessment"),
    "AIPD a finaliser": ("DSFA abzuschliessen", "DPIA to finalize"),
    "AIPD Support client IA ouverte": (
        "DSFA KI-Kundensupport offen",
        "DPIA AI customer support open",
    ),
    "Attestation": ("Bescheinigung", "Attestation"),
    "Exception": ("Ausnahme", "Exception"),
    "Exceptions": ("Ausnahmen", "Exceptions"),
    "Incident": ("Vorfall", "Incident"),
    "Incidents": ("Vorfaelle", "Incidents"),
    "Obligations": ("Pflichten", "Obligations"),
    "Preuve": ("Nachweis", "Evidence"),
    "Preuve liee": ("Verknuepfter Nachweis", "Linked evidence"),
    "Preuves": ("Nachweise", "Evidence"),
    "Rapport": ("Bericht", "Report"),
    "Legal hold": ("Legal Hold", "Legal hold"),
    "Gap": ("Luecke", "Gap"),
    # --- CTAs ----------------------------------------------------------------
    "Ajouter un traitement": ("Verarbeitung hinzufuegen", "Add a processing"),
    "Ajouter une preuve": ("Nachweis hinzufuegen", "Add evidence"),
    "Mapper une obligation": ("Pflicht zuordnen", "Map an obligation"),
    "Nouvelle exception": ("Neue Ausnahme", "New exception"),
    "Lancer une evaluation": ("Evaluierung starten", "Launch an evaluation"),
    "Planifier une revue": ("Pruefung planen", "Schedule a review"),
    "Forcer revue": ("Pruefung erzwingen", "Force review"),
    "Generer evidence pack": ("Evidence-Pack erzeugen", "Generate evidence pack"),
    "Combiner evidence pack": ("Evidence-Pack kombinieren", "Combine evidence pack"),
    "Voir evidence pack": ("Evidence-Pack anzeigen", "View evidence pack"),
    "Ouvrir la preuve": ("Nachweis oeffnen", "Open the evidence"),
    "Ouvrir les preuves": ("Nachweise oeffnen", "Open the evidence"),
    "Telecharger preuve": ("Nachweis herunterladen", "Download evidence"),
    "Export": ("Export", "Export"),
    "Voir le detail": ("Details anzeigen", "View detail"),
    "Voir le detail par cadre": ("Detail nach Rahmenwerk anzeigen", "View detail by framework"),
    "Voir les ecarts": ("Abweichungen anzeigen", "View gaps"),
    "Voir les gaps": ("Luecken anzeigen", "View gaps"),
    "Voir les registres a completer": (
        "Zu vervollstaendigende Register anzeigen",
        "View registers to complete",
    ),
    "Voir tous les cadres": ("Alle Rahmenwerke anzeigen", "View all frameworks"),
    "Voir tous les cadres a surveiller": (
        "Alle zu beobachtenden Rahmenwerke anzeigen",
        "View all frameworks to watch",
    ),
    "Voir tous les controles a revoir": (
        "Alle zu pruefenden Kontrollen anzeigen",
        "View all controls to review",
    ),
    "Voir tous les ecarts": ("Alle Abweichungen anzeigen", "View all gaps"),
    "Voir toutes les activites": ("Alle Aktivitaeten anzeigen", "View all activities"),
    "Voir toutes les attestations": ("Alle Bescheinigungen anzeigen", "View all attestations"),
    "Voir toutes les echeances": ("Alle Fristen anzeigen", "View all deadlines"),
    "Voir toutes les exceptions": ("Alle Ausnahmen anzeigen", "View all exceptions"),
    "Voir toutes les preuves": ("Alle Nachweise anzeigen", "View all evidence"),
    "Voir toutes les preuves a renouveler": (
        "Alle zu erneuernden Nachweise anzeigen",
        "View all evidence to renew",
    ),
    "Voir toutes les purges": ("Alle Loeschungen anzeigen", "View all purges"),
    "Voir toutes les revues": ("Alle Pruefungen anzeigen", "View all reviews"),
    "Voir toutes les tendances": ("Alle Trends anzeigen", "View all trends"),
    # --- article / control labels (FR clause translated) --------------------
    "Art. 5 - Principes (a-f)": ("Art. 5 - Grundsaetze (a-f)", "Art. 5 - Principles (a-f)"),
    "Art. 9 - Gestion du risque": ("Art. 9 - Risikomanagement", "Art. 9 - Risk management"),
    "Art. 9 - Systeme a haut risque": ("Art. 9 - Hochrisikosystem", "Art. 9 - High-risk system"),
    "Art. 9 - Monitoring post-marche": (
        "Art. 9 - Post-Market-Monitoring",
        "Art. 9 - Post-market monitoring",
    ),
    "Art. 10 - Gouvernance des donnees": (
        "Art. 10 - Daten-Governance",
        "Art. 10 - Data governance",
    ),
    "Art. 10 - Qualite des donnees": ("Art. 10 - Datenqualitaet", "Art. 10 - Data quality"),
    "Art. 13 - Transparence": ("Art. 13 - Transparenz", "Art. 13 - Transparency"),
    "Art. 13 - Transparence & info": (
        "Art. 13 - Transparenz & Info",
        "Art. 13 - Transparency & info",
    ),
    "Art. 15 - Exactitude": ("Art. 15 - Genauigkeit", "Art. 15 - Accuracy"),
    "Art. 17 - SMQ": ("Art. 17 - QMS", "Art. 17 - QMS"),
    "Art. 30 - Registre des activites": (
        "Art. 30 - Taetigkeitsverzeichnis",
        "Art. 30 - Records of activities",
    ),
    "RGPD - Article 30 (registre)": (
        "DSGVO - Artikel 30 (Verzeichnis)",
        "GDPR - Article 30 (register)",
    ),
    "DORA - Art. 28 (sous-traitance TIC)": (
        "DORA - Art. 28 (IKT-Auslagerung)",
        "DORA - Art. 28 (ICT outsourcing)",
    ),
    "DORA - Art. 28 (test de resilience)": (
        "DORA - Art. 28 (Resilienztest)",
        "DORA - Art. 28 (resilience test)",
    ),
    "EU AI Act - Art. 15 (rapport annuel)": (
        "EU AI Act - Art. 15 (Jahresbericht)",
        "EU AI Act - Art. 15 (annual report)",
    ),
    "C-04.1 - Tests adverses": ("C-04.1 - Adversariale Tests", "C-04.1 - Adversarial tests"),
    "C-05.2 - Transparence": ("C-05.2 - Transparenz", "C-05.2 - Transparency"),
    "C-05.2 - Transparence UX": ("C-05.2 - Transparenz UX", "C-05.2 - Transparency UX"),
    "C-05.2 - Transparence utilisateur": (
        "C-05.2 - Nutzertransparenz",
        "C-05.2 - User transparency",
    ),
    "C-06.1 - Roles & responsabilites": (
        "C-06.1 - Rollen & Verantwortlichkeiten",
        "C-06.1 - Roles & responsibilities",
    ),
    "C-06.6 - Retention": ("C-06.6 - Aufbewahrung", "C-06.6 - Retention"),
    "C-08.1 - Pseudonymisation": ("C-08.1 - Pseudonymisierung", "C-08.1 - Pseudonymization"),
    "C-08.2 - Minimisation": ("C-08.2 - Minimierung", "C-08.2 - Minimization"),
    "C-09.1 - Surveillance": ("C-09.1 - Ueberwachung", "C-09.1 - Monitoring"),
    "C-10.1 - Securite": ("C-10.1 - Sicherheit", "C-10.1 - Security"),
    "C-12.2 - Disponibilite": ("C-12.2 - Verfuegbarkeit", "C-12.2 - Availability"),
    "C-12.4 - Journalisation": ("C-12.4 - Protokollierung", "C-12.4 - Logging"),
    "C-13.2 - Donnees": ("C-13.2 - Daten", "C-13.2 - Data"),
    "C-13.2 - Gouvernance des donnees": (
        "C-13.2 - Daten-Governance",
        "C-13.2 - Data governance",
    ),
    "C-13.2 - Plan de remediation": ("C-13.2 - Behebungsplan", "C-13.2 - Remediation plan"),
    "C-15.1 - Gestion du risque": ("C-15.1 - Risikomanagement", "C-15.1 - Risk management"),
    "C-15.2 - Mesures d'attenuation": (
        "C-15.2 - Minderungsmassnahmen",
        "C-15.2 - Mitigation measures",
    ),
    "C-17.1 - Effacement": ("C-17.1 - Loeschung", "C-17.1 - Erasure"),
    "C-22.1 - Decision auto": ("C-22.1 - Auto-Entscheidung", "C-22.1 - Auto decision"),
    "C-30.1 - Registre": ("C-30.1 - Verzeichnis", "C-30.1 - Register"),
    "C-30.1 - Tenue du registre": ("C-30.1 - Verzeichnisfuehrung", "C-30.1 - Register keeping"),
    "C-DORA.1 - Risques TIC": ("C-DORA.1 - IKT-Risiken", "C-DORA.1 - ICT risks"),
    "C-DORA.1 - Test resilience": ("C-DORA.1 - Resilienztest", "C-DORA.1 - Resilience test"),
    # --- legal-basis full strings -------------------------------------------
    "Consentement - RGPD Art. 6": ("Einwilligung - DSGVO Art. 6", "Consent - GDPR Art. 6"),
    "Contrat - RGPD Art. 6": ("Vertrag - DSGVO Art. 6", "Contract - GDPR Art. 6"),
    "Interet legitime - RGPD Art. 6": (
        "Berechtigtes Interesse - DSGVO Art. 6",
        "Legitimate interest - GDPR Art. 6",
    ),
    "Obligation legale - LCB-FT": ("Rechtliche Verpflichtung - GwG", "Legal obligation - AML-CFT"),
    "Obligation legale - LPF": ("Rechtliche Verpflichtung - LPF", "Legal obligation - LPF"),
    "Base legale a justifier": ("Rechtsgrundlage zu begruenden", "Legal basis to justify"),
    "Base legale a reconfirmer": ("Rechtsgrundlage neu zu bestaetigen", "Legal basis to reconfirm"),
    "Sous-traitant a documenter": ("Auftragsverarbeiter zu dokumentieren", "Processor to document"),
    # --- detail prose --------------------------------------------------------
    "Maintenir un systeme de gestion des risques pour l'IA a haut risque.": (
        "Ein Risikomanagementsystem fuer Hochrisiko-KI aufrechterhalten.",
        "Maintain a risk-management system for high-risk AI.",
    ),
    "Systemes d'IA a haut risque, GPAI, transparence et surveillance humaine.": (
        "Hochrisiko-KI-Systeme, GPAI, Transparenz und menschliche Aufsicht.",
        "High-risk AI systems, GPAI, transparency and human oversight.",
    ),
    "Evaluation de solvabilite sur base contractuelle, sans decision automatisee.": (
        "Bonitaetspruefung auf Vertragsbasis, ohne automatisierte Entscheidung.",
        "Creditworthiness assessment on a contractual basis, without automated decision.",
    ),
    "Derogation temporaire RGPD - Art. 6 (3) en attente de mesure compensatoire.": (
        "Befristete DSGVO-Ausnahme - Art. 6 (3), wartet auf Ausgleichsmassnahme.",
        "Temporary GDPR waiver - Art. 6 (3), pending compensating measure.",
    ),
    "Retention 90 jours sur interet legitime, purge automatique nocturne.": (
        "90 Tage Aufbewahrung auf berechtigtem Interesse, naechtliche Auto-Loeschung.",
        "90-day retention on legitimate interest, nightly automatic purge.",
    ),
    "Rapport de gestion du risque EU AI Act - Art. 9, signe et horodate.": (
        "EU-AI-Act-Risikomanagementbericht - Art. 9, signiert und mit Zeitstempel.",
        "EU AI Act risk-management report - Art. 9, signed and timestamped.",
    ),
    "Score de conformite 82 % - 11 echecs critiques, 248 controles evalues.": (
        "Konformitaetsscore 82 % - 11 kritische Fehler, 248 bewertete Kontrollen.",
        "Compliance score 82% - 11 critical failures, 248 controls evaluated.",
    ),
    # --- activity-log entries (code kept, FR clause translated) -------------
    "Controle CTRL-09 mis a jour (RGPD)": (
        "Kontrolle CTRL-09 aktualisiert (DSGVO)",
        "Control CTRL-09 updated (GDPR)",
    ),
    "Controle CTRL-13 repasse conforme": (
        "Kontrolle CTRL-13 wieder konform",
        "Control CTRL-13 back to compliant",
    ),
    "Controle depasse": ("Kontrolle ueberfaellig", "Control overdue"),
    "Obligation Art. 13 marquee partielle": (
        "Pflicht Art. 13 als teilweise markiert",
        "Obligation Art. 13 marked partial",
    ),
    "Obligation OBL-1123 marquee conforme (RGPD)": (
        "Pflicht OBL-1123 als konform markiert (DSGVO)",
        "Obligation OBL-1123 marked compliant (GDPR)",
    ),
    "Exception EXC-2026-004 creee (DORA)": (
        "Ausnahme EXC-2026-004 erstellt (DORA)",
        "Exception EXC-2026-004 created (DORA)",
    ),
    "EXC-2026-009 approuvee": ("EXC-2026-009 genehmigt", "EXC-2026-009 approved"),
    "Ecart EXC-2026-007 ouvert (DORA)": (
        "Abweichung EXC-2026-007 offen (DORA)",
        "Gap EXC-2026-007 open (DORA)",
    ),
    "INC-2026-001 marquee depassee": (
        "INC-2026-001 als ueberfaellig markiert",
        "INC-2026-001 marked overdue",
    ),
    "INC-2026-003 escalade a Sophie Bernard": (
        "INC-2026-003 an Sophie Bernard eskaliert",
        "INC-2026-003 escalated to Sophie Bernard",
    ),
    "Evaluation EU AI Act terminee": (
        "EU-AI-Act-Evaluierung abgeschlossen",
        "EU AI Act evaluation completed",
    ),
    "Evaluation ISO 27001 completee": (
        "ISO-27001-Evaluierung abgeschlossen",
        "ISO 27001 evaluation completed",
    ),
    "Evaluation ISO 27001 terminee": (
        "ISO-27001-Evaluierung abgeschlossen",
        "ISO 27001 evaluation finished",
    ),
    "Evidence pack EU AI Act genere": (
        "Evidence-Pack EU AI Act erzeugt",
        "EU AI Act evidence pack generated",
    ),
    "Campagne RGPD relancee": ("DSGVO-Kampagne neu gestartet", "GDPR campaign relaunched"),
    "Attestation DORA renouvelee": ("DORA-Bescheinigung erneuert", "DORA attestation renewed"),
    "Legal hold ajoute sur Jeux d'evaluation": (
        "Legal Hold auf Evaluierungssets hinzugefuegt",
        "Legal hold added on evaluation sets",
    ),
    "Regle Exports SIEM mise a jour": (
        "Regel SIEM-Exporte aktualisiert",
        "SIEM exports rule updated",
    ),
    "Traitement Scoring credit mis a jour": (
        "Verarbeitung Kredit-Scoring aktualisiert",
        "Credit-scoring processing updated",
    ),
    "Purge auto Logs d'agent executee": (
        "Auto-Loeschung Agent-Protokolle ausgefuehrt",
        "Auto-purge agent logs executed",
    ),
    "Transcriptions purge en retard signalee": (
        "Transkript-Loeschung verspaetet gemeldet",
        "Transcripts purge reported late",
    ),
    "Base legale KYC Screening signalee": (
        "Rechtsgrundlage KYC-Screening gemeldet",
        "KYC screening legal basis flagged",
    ),
    "Revue C-30.1 planifiee": ("Pruefung C-30.1 geplant", "Review C-30.1 scheduled"),
    "Revue trimestrielle dediee": ("Dedizierte Quartalspruefung", "Dedicated quarterly review"),
    "PRV-2026-06-0102 horodatee (ISO)": (
        "PRV-2026-06-0102 mit Zeitstempel (ISO)",
        "PRV-2026-06-0102 timestamped (ISO)",
    ),
    "PRV-2026-06-0118 exportee (RGPD)": (
        "PRV-2026-06-0118 exportiert (DSGVO)",
        "PRV-2026-06-0118 exported (GDPR)",
    ),
    "PRV-2026-06-0123 signee (EU AI Act)": (
        "PRV-2026-06-0123 signiert (EU AI Act)",
        "PRV-2026-06-0123 signed (EU AI Act)",
    ),
    "PRV-2026-06-0130 generee (SOC 2)": (
        "PRV-2026-06-0130 erzeugt (SOC 2)",
        "PRV-2026-06-0130 generated (SOC 2)",
    ),
    "Preuve EV-2026-06-0204 ajoutee": (
        "Nachweis EV-2026-06-0204 hinzugefuegt",
        "Evidence EV-2026-06-0204 added",
    ),
    "Preuve EV-2026-06-0318 liee a C-15.1": (
        "Nachweis EV-2026-06-0318 mit C-15.1 verknuepft",
        "Evidence EV-2026-06-0318 linked to C-15.1",
    ),
    "Preuve EV-2026-06-0321 ajoutee a EU AI Act": (
        "Nachweis EV-2026-06-0321 zu EU AI Act hinzugefuegt",
        "Evidence EV-2026-06-0321 added to EU AI Act",
    ),
    "Preuve PRV-2026-04-0044 marquee manquante": (
        "Nachweis PRV-2026-04-0044 als fehlend markiert",
        "Evidence PRV-2026-04-0044 marked missing",
    ),
    # --- misc ----------------------------------------------------------------
    "Comite Conformite": ("Konformitaetskomitee", "Compliance committee"),
    "Purge automatique": ("Automatische Loeschung", "Automatic purge"),
    "Securite - ISO 27001": ("Sicherheit - ISO 27001", "Security - ISO 27001"),
    "purge auto": ("Auto-Loeschung", "auto purge"),
    "purge manuelle": ("manuelle Loeschung", "manual purge"),
    "purge manuelle en retard": ("manuelle Loeschung verspaetet", "manual purge late"),
    "Genere le": ("Erstellt am", "Generated on"),
    "Log signe": ("Signiertes Protokoll", "Signed log"),
    "Derogation temporaire": ("Befristete Ausnahme", "Temporary waiver"),
    "il y a 1 h": ("vor 1 Std", "1 h ago"),
    "il y a 2 h": ("vor 2 Std", "2 h ago"),
    "il y a 3 h": ("vor 3 Std", "3 h ago"),
    "il y a 4 h": ("vor 4 Std", "4 h ago"),
    "il y a 5 h": ("vor 5 Std", "5 h ago"),
    "il y a 6 h": ("vor 6 Std", "6 h ago"),
    "il y a 7 h": ("vor 7 Std", "7 h ago"),
    "dans 6 jours": ("in 6 Tagen", "in 6 days"),
    "dans 11 jours": ("in 11 Tagen", "in 11 days"),
    "dans 12 jours": ("in 12 Tagen", "in 12 days"),
    "dans 15 jours": ("in 15 Tagen", "in 15 days"),
    "dans 18 jours": ("in 18 Tagen", "in 18 days"),
    "dans 22 jours": ("in 22 Tagen", "in 22 days"),
    "dans 30 jours": ("in 30 Tagen", "in 30 days"),
    "dans 45 jours": ("in 45 Tagen", "in 45 days"),
    "dans 60 jours": ("in 60 Tagen", "in 60 days"),
}


# DE / EN for the grounded explain prose authored as _EX_* constants above.
# Keyed by the exact FR string (referenced, never retyped), merged into _TR so
# _localize renders every info popover in all three languages. Keys are typed
# ``str | None`` because ``TabExplain.how`` / ``.source`` are optional fields;
# only the present (non-None) ones are ever written, and None is filtered out at
# merge time below.
_EX_TR: dict[str | None, tuple[str, str]] = {
    # EXPLAIN_TR_ANCHOR (do not remove) -- per-tab DE/EN pairs inserted below.
    _EX_REGISTERED_PROCESSINGS.what: (
        "Anzahl der im Verzeichnis nach DSGVO Art. 30 eingetragenen Datenverarbeitungen.",
        "Number of data processing activities recorded in the GDPR Art. 30 register.",
    ),
    _EX_REGISTERED_PROCESSINGS.source: (
        "Verzeichnis von Verarbeitungstaetigkeiten (DSGVO Art. 30).",
        "Records of processing activities (GDPR Art. 30).",
    ),
    _EX_DOCUMENTED_PURPOSES.what: (
        "Verarbeitungen, deren Zweck foermlich dokumentiert ist.",
        "Processing activities whose purpose is formally documented.",
    ),
    _EX_VALID_LEGAL_BASES.what: (
        "Verarbeitungen mit gueltiger Rechtsgrundlage im Sinne von DSGVO Art. 6.",
        "Processing activities with a valid legal basis under GDPR Art. 6.",
    ),
    _EX_COMPLIANT_RETENTION.what: (
        "Verarbeitungen, deren Aufbewahrungsdauer der Aufbewahrungsrichtlinie entspricht.",
        "Processing activities whose retention duration complies with the retention policy.",
    ),
    _EX_REGISTRY_GAPS.what: (
        "Verarbeitungen, deren Verzeichniseintrag unvollstaendig ist oder aktualisiert werden "
        "muss.",
        "Processing activities whose register entry is incomplete or needs updating.",
    ),
    _EX_REGISTRY_TABLE.what: (
        "Verzeichnis der Verarbeitungen: Zweck, Rechtsgrundlage, Datenkategorien, "
        "Aufbewahrungsdauer, Kontrollen, Owner und Status.",
        "Register of processing activities: purpose, legal basis, data categories, retention "
        "duration, controls, owner and status.",
    ),
    _EX_REGISTRY_TABLE.how: (
        "Eine Zeile je im Verzeichnis nach DSGVO Art. 30 eingetragener Verarbeitung.",
        "One row per processing activity recorded in the GDPR Art. 30 register.",
    ),
    _EX_REGISTRY_DETAIL.what: (
        "Datenblatt der gewaehlten Verarbeitung: Datenkategorie, Zweck, Rechtsgrundlage, "
        "Uebermittlungen, Auftragsverarbeiter, Dauer und verknuepfte Kontrollen.",
        "Selected processing activity's data sheet: data category, purpose, legal basis, "
        "transfers, processors, duration and linked controls.",
    ),
    _EX_REGISTRY_TODO.what: (
        "Unvollstaendige Verzeichniseintraege: DSFA, Rechtsgrundlage, Auftragsverarbeiter oder "
        "Dauer zu dokumentieren.",
        "Incomplete register entries: DPIA, legal basis, processor or duration to document.",
    ),
    _EX_SCHEDULED_REVIEWS.what: (
        "Geplante periodische Ueberpruefungen der Verarbeitungseintraege.",
        "Scheduled periodic reviews of the processing entries.",
    ),
    _EX_SCHEDULED_REVIEWS.how: (
        "Verarbeitungen mit anstehender Ueberpruefung, nach Datum sortiert.",
        "Processing activities with an upcoming review, sorted by date.",
    ),
    _EX_LINKED_EXCEPTIONS.what: (
        "Ausnahmen und Abweichungen, die den Verarbeitungen des Verzeichnisses zugeordnet sind.",
        "Exceptions and derogations attached to the register's processing activities.",
    ),
    _EX_VALID_ATTESTATIONS.what: (
        "Signierte und mit Zeitstempel versehene Bescheinigungen, die noch gueltig (nicht "
        "abgelaufen) sind.",
        "Signed and timestamped attestations that are still valid (unexpired).",
    ),
    _EX_EXPIRING_EVIDENCE.what: (
        "Nachweise, deren Gueltigkeit auslaeuft und die erneuert werden muessen.",
        "Evidence whose validity is approaching expiry and that will need renewal.",
    ),
    _EX_MISSING_CORRUPT.what: (
        "Erwartete Nachweise, die fehlen oder deren Integritaet beeintraechtigt ist.",
        "Expected evidence that is missing or whose integrity is compromised.",
    ),
    _EX_EVIDENCE_COVERAGE.what: (
        "Anteil der Pflichten mit mindestens einem gueltigen Nachweis.",
        "Share of obligations that have at least one valid piece of evidence.",
    ),
    _EX_EVIDENCE_COVERAGE.how: (
        "Pflichten mit gueltigem Nachweis geteilt durch die anwendbaren Pflichten.",
        "Obligations with valid evidence divided by the applicable obligations.",
    ),
    _EX_EVIDENCE_PACK_STATE.what: (
        "Bereitschaftszustand des Evidence-Packs: ob alle geforderten Nachweise zusammengestellt "
        "und exportiert werden koennen.",
        "Readiness state of the evidence pack: whether all required evidence can be assembled and "
        "exported.",
    ),
    _EX_EVIDENCE_TABLE.what: (
        "Nachweisinventar: Rahmen, Kontrolle, Typ, Owner, Datum, Gueltigkeit und Status.",
        "Evidence inventory: framework, control, type, owner, date, validity and status.",
    ),
    _EX_EVIDENCE_TABLE.how: (
        "Eine Zeile je Nachweis; die Gueltigkeit zeigt die verbleibende Zeit bis zum Ablauf.",
        "One row per evidence item; validity shows the remaining time before expiry.",
    ),
    _EX_EVIDENCE_DETAIL.what: (
        "Datenblatt des gewaehlten Nachweises: Rahmen, Kontrolle, Typ, Erstellungsdatum, "
        "Gueltigkeit, kryptografischer Fingerabdruck, verknuepfte Pflichten und Signatur.",
        "Selected evidence item's data sheet: framework, control, type, generation date, "
        "validity, cryptographic fingerprint, linked obligations and signature.",
    ),
    _EX_EVIDENCE_RENEW.what: (
        "Nachweise kurz vor dem Ablauf, die zur Aufrechterhaltung der Abdeckung zu erneuern sind.",
        "Evidence close to expiry to renew in order to maintain coverage.",
    ),
    _EX_EVIDENCE_RENEW.how: (
        "Nachweise nach Ablaufnaehe sortiert.",
        "Evidence sorted by proximity to expiry.",
    ),
    _EX_LATEST_ATTESTATIONS.what: (
        "Zuletzt erzeugte, signierte oder mit Zeitstempel versehene Bescheinigungen, vom neuesten "
        "zum aeltesten.",
        "Latest attestations generated, signed or timestamped, from newest to oldest.",
    ),
    _EX_COVERAGE_BY_FRAMEWORK.what: (
        "Anteil der durch einen gueltigen Nachweis abgedeckten Pflichten je Regulierungsrahmen.",
        "Share of obligations covered by a valid piece of evidence, per regulatory framework.",
    ),
    _EX_COVERAGE_BY_FRAMEWORK.how: (
        "Gueltige Nachweise zu erwarteten Pflichten je Rahmen; der Ring zeigt die "
        "Gesamtabdeckung.",
        "Valid evidence to expected obligations per framework; the ring shows overall coverage.",
    ),
    _EX_RESOURCES_RETAINED.what: (
        "Datenkategorien, die in Tessera einer Aufbewahrungs- und Loeschregel unterliegen.",
        "Data categories subject to a retention and purge rule in Tessera.",
    ),
    _EX_RESOURCES_RETAINED.source: (
        "Aufbewahrungs- und Loeschrichtlinie.",
        "Retention and purge policy.",
    ),
    _EX_PURGE_ON_TIME.what: (
        "Anzahl der im Zielzeitraum ausgefuehrten Loeschungen im Berichtszeitraum.",
        "Number of purges executed within the target deadline over the period.",
    ),
    _EX_PURGE_JOBS.what: (
        "Anzahl der geplanten Loeschauftraege, automatisch oder manuell.",
        "Number of scheduled purge jobs, automatic or manual.",
    ),
    _EX_LEGAL_HOLDS.what: (
        "Durch eine gesetzliche Aufbewahrungspflicht eingefrorene, von der Loeschung "
        "ausgenommene Ressourcen.",
        "Resources frozen by a legal retention obligation and exempt from purge.",
    ),
    _EX_RETENTION_GAPS.what: (
        "Ressourcen mit ueberfaelliger Loeschung oder nicht konformer Aufbewahrungsdauer.",
        "Resources whose purge is overdue or whose retention duration is non-conformant.",
    ),
    _EX_RETENTION_TABLE.what: (
        "Aufbewahrungsregeln je Ressource: Rechtsgrundlage, Zieldauer, Loeschmodus, Signal, "
        "Owner und Status.",
        "Retention rules per resource: legal basis, target duration, purge mode, signal, owner "
        "and status.",
    ),
    _EX_RETENTION_TABLE.how: (
        "Eine Zeile je Datenkategorie; der Modus gibt eine automatische oder manuelle Loeschung "
        "an.",
        "One row per data category; the mode indicates an automatic or manual purge.",
    ),
    _EX_RETENTION_DETAIL.what: (
        "Datenblatt der gewaehlten Regel: Speicherung, Loeschstrategie und -methode, Legal Hold, "
        "naechste Loeschung und verknuepfte Kontrollen.",
        "Selected rule's data sheet: storage, purge strategy and method, legal hold, next purge "
        "and linked controls.",
    ),
    _EX_UPCOMING_PURGES.what: (
        "In den naechsten sieben Tagen geplante Loeschungen, automatisch oder manuell.",
        "Purges scheduled in the next seven days, automatic or manual.",
    ),
    _EX_UPCOMING_PURGES.how: (
        "Loeschauftraege nach Ausfuehrungsdatum sortiert.",
        "Purge jobs sorted by execution date.",
    ),
    _EX_RETENTION_EXCEPTIONS.what: (
        "Ressourcen mit blockierter oder ueberfaelliger Loeschung: Legal Hold, zu korrigierende "
        "manuelle Loeschung.",
        "Resources whose purge is blocked or overdue: legal hold, manual purge to fix.",
    ),
    _EX_COVERAGE_BY_SYSTEM.what: (
        "Anteil der je Speichersystem korrekt der Aufbewahrung unterliegenden Ressourcen.",
        "Share of resources correctly subject to retention per storage system.",
    ),
    _EX_COVERAGE_BY_SYSTEM.how: (
        "Konforme Ressourcen je System, normiert auf das am besten abgedeckte.",
        "Conformant resources per system, normalized to the best covered.",
    ),
    _EX_OPEN_INCIDENTS.what: (
        "Derzeit offene Konformitaetsvorfaelle (ueberschrittene Kontrolle, nicht erfuellte "
        "Pflicht).",
        "Compliance incidents currently open (breached control, unmet obligation).",
    ),
    _EX_OPEN_INCIDENTS.source: (
        "Verzeichnis der Vorfaelle und Ausnahmen.",
        "Incident and exception register.",
    ),
    _EX_APPROVED_EXCEPTIONS.what: (
        "Foermlich genehmigte Ausnahmen mit Ausgleichsmassnahme und Frist.",
        "Formally approved exceptions, each with a compensating measure and a deadline.",
    ),
    _EX_OVERDUE_EXCEPTIONS.what: (
        "Ausnahmen, deren Frist ohne Regularisierung verstrichen ist; Risiko der "
        "Nichtkonformitaet.",
        "Exceptions whose deadline has passed without regularization; a non-conformity risk.",
    ),
    _EX_MISSING_EVIDENCE.what: (
        "Fuer einen Vorfall oder eine Ausnahme erwartete und noch nicht gelieferte Nachweise.",
        "Evidence expected for an incident or exception and not yet provided.",
    ),
    _EX_INCIDENTS_TABLE.what: (
        "Liste der Vorfaelle und Ausnahmen mit Typ, Rahmen, ueberschrittener Kontrolle, Signal, "
        "Owner, Frist und Status.",
        "List of incidents and exceptions with type, framework, breached control, signal, owner, "
        "deadline and status.",
    ),
    _EX_INCIDENTS_TABLE.how: (
        "Eine Zeile je Vorfall oder Ausnahme; das Signal gibt den Schweregrad an.",
        "One row per incident or exception; the signal indicates severity.",
    ),
    _EX_INCIDENTS_DETAIL.what: (
        "Datenblatt der gewaehlten Ausnahme: Grundursache, verknuepfte Pflicht und Kontrolle, "
        "Nachweis, Frist, Restrisiko, Ausgleichsmassnahme und Genehmigungskette.",
        "Selected exception's data sheet: root cause, linked obligation and control, evidence, "
        "deadline, residual risk, compensating measure and approval chain.",
    ),
    _EX_EXCEPTIONS_DUE.what: (
        "Ausnahmen mit naher Frist, die zu regularisieren oder zu erneuern sind.",
        "Exceptions whose deadline is approaching and that must be regularized or renewed.",
    ),
    _EX_EXCEPTIONS_DUE.how: (
        "Ausnahmen nach Fristnaehe sortiert.",
        "Exceptions sorted by deadline proximity.",
    ),
    _EX_GAP_TRENDS.what: (
        "Entwicklung der Anzahl von Vorfaellen, Ausnahmen und Loesungen ueber die letzten fuenf "
        "Zeitraeume.",
        "Evolution of the number of incidents, exceptions and resolutions over the last five "
        "periods.",
    ),
    _EX_GAP_TRENDS.how: (
        "Anzahl je Zeitraum, eine Kurve je Reihe (Vorfaelle, Ausnahmen, Loesungen).",
        "Count per period, one line per series (incidents, exceptions, resolutions).",
    ),
    _EX_OWNERS_LOAD.what: (
        "Relative Last der Verantwortlichen: Anteil der ihnen zugewiesenen offenen Vorfaelle und "
        "Ausnahmen.",
        "Relative load of owners: share of open incidents and exceptions assigned to each.",
    ),
    _EX_OWNERS_LOAD.how: (
        "Offene Vorfaelle und Ausnahmen je Owner, normiert auf den am staerksten belasteten.",
        "Open incidents and exceptions per owner, normalized to the most loaded.",
    ),
    _EX_EVAL_CAMPAIGNS.what: (
        "Anzahl der durchgefuehrten Konformitaets-Evaluationskampagnen ueber die "
        "Regulierungsrahmen.",
        "Number of compliance evaluation campaigns run across the regulatory frameworks.",
    ),
    _EX_EVAL_CAMPAIGNS.source: (
        "Konformitaets-Evaluationskampagnen.",
        "Compliance evaluation campaigns.",
    ),
    _EX_CONFORMITY_SCORE.what: (
        "Anteil der bestandenen bewerteten Kontrollen, gewichtet nach Schweregrad; globale "
        "Konformitaetsmessung des Bereichs.",
        "Share of evaluated controls that pass, weighted by severity; the scope's overall "
        "conformity measure.",
    ),
    _EX_CONFORMITY_SCORE.how: (
        "Gewichtete bestandene Kontrollen geteilt durch die bewerteten Kontrollen der letzten "
        "Kampagne.",
        "Weighted passed controls divided by the evaluated controls, over the latest campaign.",
    ),
    _EX_CONTROLS_PASSED.what: (
        "Anzahl der Kontrollen, die ihre letzte Bewertung bestanden haben.",
        "Number of controls that passed their latest evaluation.",
    ),
    _EX_OPEN_GAPS.what: (
        "Von den Evaluationen erkannte und noch nicht behobene Konformitaetsabweichungen.",
        "Compliance gaps detected by the evaluations and not yet remediated.",
    ),
    _EX_EVIDENCE_REPLAYED.what: (
        "Anzahl der erneut ausgefuehrten Nachweise, um zu bestaetigen, dass eine Kontrolle "
        "weiterhin besteht.",
        "Number of evidence items re-run to confirm a control still passes.",
    ),
    _EX_EVAL_TABLE.what: (
        "Ansicht je Kampagne: Abdeckung, Score, Pflichten, Kontrollen, Signale, Nachweise, Owner "
        "und Status.",
        "View per campaign: coverage, score, obligations, controls, signals, evidence, owner and "
        "status.",
    ),
    _EX_EVAL_TABLE.how: (
        "Eine Zeile je bewertetem Rahmen; der Score gewichtet die bestandenen Kontrollen nach "
        "Schweregrad.",
        "One row per evaluated framework; the score weights passed controls by severity.",
    ),
    _EX_EVAL_DETAIL.what: (
        "Datenblatt der gewaehlten Kampagne: Score, bestandene Kontrollen, kritische Fehler, "
        "erneut ausgefuehrte Nachweise und letzte Ausfuehrung.",
        "Selected campaign's data sheet: score, passed controls, critical failures, replayed "
        "evidence and last run.",
    ),
    _EX_REMEDIATION_PLAN.what: (
        "Verteilung der offenen Abweichungen nach Schweregrad (kritisch, hoch, mittel, niedrig), "
        "im Behebungsplan abzuarbeiten.",
        "Breakdown of open gaps by severity (critical, high, medium, low), to be worked off in "
        "the remediation plan.",
    ),
    _EX_REMEDIATION_PLAN.how: (
        "Offene Abweichungen nach Schweregrad gezaehlt; die Summe entspricht den offenen "
        "Abweichungen.",
        "Open gaps counted by severity level; the total matches the open gaps.",
    ),
    _EX_SCORE_TRENDS.what: (
        "Entwicklung des Konformitaetsscores je Rahmen ueber die letzten fuenf Kampagnen.",
        "Evolution of the conformity score per framework over the last five campaigns.",
    ),
    _EX_SCORE_TRENDS.how: (
        "Gewichteter Score je Kampagne, eine Kurve je Rahmen.",
        "Weighted score per campaign, one line per framework.",
    ),
    _EX_DECLINING_FRAMEWORKS.what: (
        "Rahmen, deren Konformitaetsscore von einer Kampagne zur naechsten zurueckgeht.",
        "Frameworks whose conformity score declines from one campaign to the next.",
    ),
    _EX_DECLINING_FRAMEWORKS.how: (
        "Rahmen mit negativer Score-Veraenderung, nach Ausmass sortiert.",
        "Frameworks with a negative score change, sorted by magnitude.",
    ),
    _EX_OBLIGATIONS_ACTIVE.what: (
        "Regulierungspflichten, die derzeit fuer den Bereich gelten und im Verzeichnis gefuehrt "
        "werden.",
        "Regulatory obligations currently applicable to the scope and tracked in the register.",
    ),
    _EX_COVERAGE_OBLIGATIONS.what: (
        "Anteil der Pflichten des Bereichs, die durch eine aktive Kontrolle und einen gueltigen "
        "Nachweis abgedeckt sind.",
        "Share of the scope's obligations covered by an active control and a valid piece of "
        "evidence.",
    ),
    _EX_COVERAGE_OBLIGATIONS.how: (
        "Abgedeckte Pflichten (Kontrolle plus Nachweis) geteilt durch die anwendbaren Pflichten.",
        "Covered obligations (control plus evidence) divided by the applicable obligations.",
    ),
    _EX_SIGNALS_PER_EVIDENCE.what: (
        "Durchschnittliche Anzahl der Ausfuehrungssignale (Traces, Tests, Protokolle), die jedem "
        "Nachweis zugeordnet sind.",
        "Average number of execution signals (traces, tests, logs) linked to each piece of "
        "evidence.",
    ),
    _EX_SIGNALS_PER_EVIDENCE.how: (
        "Summe der verknuepften Signale geteilt durch die Anzahl der Nachweise im Bereich.",
        "Total linked signals divided by the number of evidence items in the scope.",
    ),
    _EX_DEGRADED_CONTROLS.what: (
        "Kontrollen, deren letztes Ergebnis teilweise oder fehlgeschlagen ist und die eine "
        "Behebung erfordern.",
        "Controls whose latest result is partial or failing and that require remediation.",
    ),
    _EX_DEGRADED_CONTROLS.how: (
        "Kontrollen mit Status verschlechtert ueber alle verfolgten Pflichten.",
        "Controls in degraded status across all tracked obligations.",
    ),
    _EX_DEGRADED_CONTROLS.source: (
        "Regulatorische Zuordnung (Kontrollstatus).",
        "Regulatory mapping (control status).",
    ),
    _EX_OBLIGATIONS_TABLE.what: (
        "Liste der Pflichten mit Rahmen, Hauptkontrolle, Signalen, Nachweisen, Owner, Status und "
        "Abdeckung.",
        "List of obligations with their framework, main control, signals, evidence, owner, status "
        "and coverage.",
    ),
    _EX_OBLIGATIONS_TABLE.how: (
        "Eine Zeile je verfolgter Pflicht; der Balken zeigt verfuegbare zu erwarteten Nachweisen, "
        "die Anzeige die Kontrollabdeckung.",
        "One row per tracked obligation; the bar shows available versus expected evidence, the "
        "gauge the control coverage.",
    ),
    _EX_OBLIGATIONS_DETAIL.what: (
        "Datenblatt der gewaehlten Pflicht: Rahmen, Hauptkontrolle, zugeordnete Signale und "
        "Nachweise, Restrisiko, naechste Pruefung und zugeordnete Kontrollen.",
        "Selected obligation's data sheet: framework, main control, linked signals and evidence, "
        "residual risk, next review and mapped controls.",
    ),
    _EX_OBLIGATIONS_DETAIL.source: (
        "Regulatorische Zuordnung (Pflicht-Datenblatt).",
        "Regulatory mapping (obligation data sheet).",
    ),
    _EX_CONTROLS_REVIEW.what: (
        "Kontrollen mit Status teilweise oder mittel, deren Ergebnis erneut zu pruefen ist.",
        "Controls in partial or medium status whose result must be re-checked.",
    ),
    _EX_COVERAGE_GAPS.what: (
        "Pflichten ohne ausreichende Kontrolle oder ausreichenden Nachweis; zu schliessende "
        "Konformitaetsluecke.",
        "Obligations lacking a sufficient control or evidence; a compliance gap to close.",
    ),
    _EX_REMEDIATION_DEADLINES.what: (
        "Behebungsplaene mit Stichtag fuer Kontrollen oder Pflichten mit Abweichung.",
        "Remediation plans with a due date for controls or obligations in gap.",
    ),
    _EX_REMEDIATION_DEADLINES.how: (
        "Behebungsmassnahmen sortiert nach Fristnaehe.",
        "Remediation actions sorted by deadline proximity.",
    ),
    _EX_EVIDENCE_READINESS.what: (
        "Anteil der vom Rahmenwerk geforderten Nachweise, die verfuegbar, gueltig und nicht "
        "abgelaufen sind und somit auf Anfrage eines Pruefers zu einem Evidence-Pack "
        "zusammengestellt werden koennen.",
        "Share of the evidence required by the framework that is available, valid and unexpired, "
        "and therefore ready to be assembled into an evidence pack on an auditor's request.",
    ),
    _EX_EVIDENCE_READINESS.how: (
        "Gueltige, den Pflichten des Bereichs zugeordnete Nachweise geteilt durch die erwarteten "
        "Nachweise; ein abgelaufener oder fehlender Nachweis senkt die Quote.",
        "Valid evidence linked to the scope's obligations divided by the expected evidence; an "
        "expired or missing item lowers the ratio.",
    ),
    _EX_AVAILABLE_EVIDENCE.source: ("Nachweisinventar.", "Evidence inventory."),
    _EX_RECENT_ACTIVITY.what: (
        "Chronologisches Protokoll der juengsten Governance-Aktionen in diesem Bereich: "
        "hinzugefuegte Nachweise, aktualisierte Kontrollen, Ausnahmen, Pruefungen.",
        "Chronological log of the latest governance actions in this scope: evidence added, "
        "controls updated, exceptions, reviews.",
    ),
    _EX_RECENT_ACTIVITY.source: (
        "Governance-Katalog Konformitaet (Referenzdaten).",
        "Compliance governance catalogue (reference data).",
    ),
    _EX_LINKED_CONTROLS.what: (
        "Anzahl interner Kontrollen, die einer Pflicht dieses Bereichs zugeordnet sind.",
        "Number of internal controls linked to an obligation in this scope.",
    ),
    _EX_LINKED_CONTROLS.how: (
        "Eindeutige Pflicht-Kontroll-Verknuepfungen, aggregiert ueber den angezeigten Bereich.",
        "Unique obligation-control links, aggregated across the displayed scope.",
    ),
    _EX_LINKED_CONTROLS.source: (
        "Regulatorische Zuordnung (Pflichten-Kontrollen).",
        "Regulatory mapping (obligations-to-controls).",
    ),
    _EX_AVAILABLE_EVIDENCE.what: (
        "Anzahl der verfuegbaren, als Nachweis nutzbaren Belege und Bescheinigungen fuer diesen "
        "Bereich.",
        "Number of evidence items and attestations available and usable as evidence for this "
        "scope.",
    ),
    _EX_FRAMEWORKS_ACTIVE.what: (
        "Anzahl der derzeit in Tessera verfolgten und zugeordneten Regulierungsrahmen "
        "(EU AI Act, DSGVO, DORA, ISO, SOC 2, interne Richtlinien).",
        "Number of regulatory frameworks currently tracked and mapped in Tessera "
        "(EU AI Act, GDPR, DORA, ISO, SOC 2, internal policies).",
    ),
    _EX_FRAMEWORKS_ACTIVE.how: (
        "Rahmen mit Status aktiv in der Zuordnung; ein reiner Beobachtungsrahmen zaehlt nicht.",
        "Frameworks with active status in the mapping; a watch-list-only framework is not counted.",
    ),
    _EX_FRAMEWORKS_ACTIVE.source: (
        "Regulatorische Zuordnung (Rahmenverzeichnis).",
        "Regulatory mapping (framework register).",
    ),
    _EX_OBLIGATIONS_MAPPED.what: (
        "Anzahl der Regulierungspflichten, die mindestens einer internen Kontrolle zugeordnet "
        "sind.",
        "Number of regulatory obligations linked to at least one internal control.",
    ),
    _EX_OBLIGATIONS_MAPPED.how: (
        "Summe der zugeordneten Pflichten ueber alle aktiven Rahmenwerke.",
        "Sum of mapped obligations across all active frameworks.",
    ),
    _EX_OBLIGATIONS_AT_RISK.what: (
        "Pflichten mit unzureichender Kontroll- oder Nachweisabdeckung oder mit naher Frist.",
        "Obligations with insufficient control or evidence coverage, or with an approaching "
        "deadline.",
    ),
    _EX_OBLIGATIONS_AT_RISK.how: (
        "Pflichten mit Status teilweise oder nicht konform oder mit naher Frist, einmal gezaehlt.",
        "Obligations that are partial or non-conformant, or due soon, counted once.",
    ),
    _EX_OBLIGATIONS_AT_RISK.source: (
        "Regulatorische Zuordnung (Pflichtenstatus).",
        "Regulatory mapping (obligation status).",
    ),
    _EX_MAPPING_TABLE.what: (
        "Ansicht je Regulierungsrahmen: zugeordnete Pflichten, Kontrollen, Signale und Nachweise "
        "mit Owner und Konformitaetsstatus.",
        "View per regulatory framework: linked obligations, controls, signals and evidence, with "
        "owner and conformity status.",
    ),
    _EX_MAPPING_TABLE.how: (
        "Eine Zeile je aktivem Rahmenwerk; die Zaehler aggregieren zugeordnete Pflichten und "
        "Kontrollen, der Balken zeigt verfuegbare zu erwarteten Nachweisen.",
        "One row per active framework; counters aggregate mapped obligations and controls, the "
        "bar shows available versus expected evidence.",
    ),
    _EX_MAPPING_TABLE.source: (
        "Regulatorische Zuordnung (Pflichten-Kontroll-Verzeichnis).",
        "Regulatory mapping (obligations-controls register).",
    ),
    _EX_MAPPING_DETAIL.what: (
        "Datenblatt des gewaehlten Rahmens: geltende Artikel, zugeordnete Pflichten und "
        "Kontrollen, verfuegbare Nachweise, Restrisiko und naechste Pruefung.",
        "Selected framework's data sheet: applicable articles, mapped obligations and controls, "
        "available evidence, residual risk and next review.",
    ),
    _EX_MAPPING_DETAIL.source: (
        "Regulatorische Zuordnung (Rahmen-Datenblatt).",
        "Regulatory mapping (framework data sheet).",
    ),
    _EX_FRAMEWORKS_WATCH.what: (
        "Aufkommende oder kuenftige Regelwerke, die demnaechst in die Zuordnung aufzunehmen sind "
        "(NIS2, Data Act, KI-Haftungsrichtlinie).",
        "Emerging or upcoming frameworks to add to the mapping soon (NIS2, Data Act, AI Liability "
        "Directive).",
    ),
    _EX_FRAMEWORKS_WATCH.how: (
        "Rahmen im Beobachtungsstatus mit geschaetztem Quartal der Anwendbarkeit.",
        "Watch-list frameworks with their estimated quarter of applicability.",
    ),
    _EX_FRAMEWORKS_WATCH.source: ("Regulatorische Beobachtung.", "Regulatory watch."),
    _EX_REG_DEADLINES.what: (
        "Naechste durch die Rahmenwerke vorgegebene Fristen: Jahresberichte, Resilienztests, "
        "Aktualisierungen des Verzeichnisses.",
        "Next deadlines imposed by the frameworks: annual reports, resilience tests, register "
        "updates.",
    ),
    _EX_REG_DEADLINES.how: (
        "Pflichten mit Stichtag, sortiert nach Fristnaehe.",
        "Obligations with a due date, sorted by deadline proximity.",
    ),
    _EX_REG_DEADLINES.source: (
        "Regulatorische Zuordnung (Fristen).",
        "Regulatory mapping (deadlines).",
    ),
}
_TR.update({k: v for k, v in _EX_TR.items() if k is not None})


def _localize(value: object, idx: int) -> object:
    """Recursively map every translatable string leaf to locale ``idx`` (de/en)."""
    if isinstance(value, str):
        pair = _TR.get(value)
        return pair[idx] if pair else value
    if isinstance(value, dict):
        return {k: _localize(v, idx) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return type(value)(_localize(v, idx) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        kwargs = {f.name: _localize(getattr(value, f.name), idx) for f in fields(value)}
        return type(value)(**kwargs)
    return value


def build_tabs(lang: str = "fr") -> dict[str, CatalogTab]:
    """Return the per-tab payloads for the Conformite command bar in ``lang``.

    The fixture is authored in French (the source of truth); for ``de`` / ``en``
    each string leaf is mapped through ``_TR`` (unmapped strings fall through
    verbatim), so the governance catalogues are localized end to end.
    """
    tabs = _build_fr_tabs()
    idx = _LANG_IDX.get(lang, 0)
    if idx == 0:
        return tabs
    return {key: cast("CatalogTab", _localize(tab, idx - 1)) for key, tab in tabs.items()}
