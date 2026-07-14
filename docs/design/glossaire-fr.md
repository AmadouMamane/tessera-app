# Glossaire de façade — FR / DE / EN

> **Objet** : la **terminologie métier visible par l'utilisateur** sur le cockpit (GOUVERNER /
> PLATEFORME) et les surfaces métier. Règle absolue : **aucun mot anglais, slug technique ou code
> interne en façade**. Le code interne (slug de rôle, identifiant de rail, code `S*`) reste dans le
> backend/les données ; l'UI montre **toujours** le label humain ci-dessous.
>
> Ce fichier est **normatif** pour les libellés. Quand une chaîne i18n est créée ou relabellée,
> elle suit ce tableau. Voir `presentation-conformance.md` (P6 — vocabulaire cohérent).

## 1. Rôles (plan d'accès)

| Terme interne (slug) | FR (façade) | DE | EN |
| --- | --- | --- | --- |
| `collections` | **Recouvrement** | Inkasso | Collections |
| `admin` | **Administrateur** | Administrator | Administrator |
| `auditor` | **Auditeur** | Auditor | Auditor |
| `superadmin` | **Super-administrateur** | Super-Administrator | Super-admin |
| `operator` (rollup admin/auditor/superadmin) | **Opérateur de plateforme** | Plattform-Operator | Platform operator |

> Le slug `collections` ne doit **jamais** apparaître en façade (badge, note, bouton). Seul le nom de
> **compte de démo** sur la page de connexion peut afficher l'identifiant brut (c'est une saisie).

## 2. Qualité & évaluation

| Terme | FR (façade) | DE | EN |
| --- | --- | --- | --- |
| SLO | **Objectif de service (SLO)** | Service-Ziel (SLO) | Service objective (SLO) |
| faithfulness | **fidélité** | Treue | faithfulness |
| grounding | **ancrage** | Verankerung | grounding |
| hallucination | **hallucination** | Halluzination | hallucination |
| non-regression | **non-régression** | Nicht-Regression | non-regression |
| calibration | **calibration** | Kalibrierung | calibration |
| burn rate (error budget) | **vitesse de consommation (budget d'erreur)** | Verbrauchsrate (Fehlerbudget) | burn rate (error budget) |

## 3. Preuve & audit

| Terme | FR (façade) | DE | EN |
| --- | --- | --- | --- |
| evidence pack / evidence store | **dossier de preuves** | Beweismappe | evidence pack |
| what-changed | **changements (vs dernière release)** | Änderungen (vs. letztes Release) | what changed |
| as-of / « Relire à T » | **Rejouer à une date** | Auf ein Datum zurückspielen | replay at a date |
| hash-chain / hash-chaîne | **chaîne d'intégrité (hash)** | Integritätskette (Hash) | integrity hash-chain |
| audit log | **journal d'audit** | Audit-Protokoll | audit log |
| opposable | **opposable** *(FR métier légitime — garder)* | belastbar | defensible |

## 4. Sécurité & garde-fous

| Terme | FR (façade) | DE | EN |
| --- | --- | --- | --- |
| red-team | **test d'intrusion** | Angriffstest | red-team |
| guardrail | **garde-fou** | Schutzregel | guardrail |
| firewall (first-party guard) | **pare-feu** | Firewall | firewall |
| PII leak | **fuite de données personnelles** | Datenleck (PII) | PII leak |
| prompt injection | **injection de requête** | Prompt-Injection | prompt injection |
| override / waiver | **dérogation gouvernée** *(garder « dérogation »)* | gesteuerte Ausnahme | governed waiver |

## 5. Exploitation & gouvernance

| Terme | FR (façade) | DE | EN |
| --- | --- | --- | --- |
| playbooks | **procédures** | Verfahren | playbooks |
| on-prem | **sur site** | vor Ort | on-prem |
| release | **release** *(garder — terme produit)* / sinon **mise en service** | Release | release |
| release gate | **gate de mise en service** *(garder « gate »)* | Release-Gate | release gate |
| socle | **socle** *(FR métier légitime — garder)* | Basis | baseline set |
| cœur non dérogeable | **cœur non dérogeable** *(garder)* | nicht abdingbarer Kern | non-overridable core |
| tenant | **tenant** *(garder — terme infra)* / façade **client / organisation** | Mandant | tenant |
| fleet | **flotte** | Flotte | fleet |

## 6. Codes internes — JAMAIS en façade

Les codes ci-dessous sont des identifiants de données/rail. En façade, on montre **le label humain**,
jamais le code (le code peut rester en attribut `title`/tooltip technique au plus).

| Code interne | Label humain de façade (FR) |
| --- | --- |
| `S1` (journal d'événements) | **Journal d'événements** |
| `S4` (store …) | **selon la fonction du store** — jamais « S4 » |
| `OT-01`, `XT-01`, `TE-01`, `T0/T1/T2` (codes de rail/tier) | **nom du rail / du palier** (ex. « rail temporel », « palier mémoire ») — jamais le code |
| `T` (as-of) | **date** (« à cette date », « Rejouer à une date ») |

## 7. Application

- À chaque page touchée : aucun mot anglais isolé, slug ou code `S*`/rail en façade — substituer le
  label ci-dessus.
- Termes FR métier **légitimes à conserver** : socle, opposable, dérogation, cœur non dérogeable, gate,
  as-of (libellé « Rejouer à une date »).
- Quand un terme manque ici, l'ajouter au tableau **avant** de l'employer en façade.
