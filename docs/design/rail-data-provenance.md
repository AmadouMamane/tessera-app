# Provenance des données sous le rail temporel SR-01 (Vue d'ensemble)

> Audit · 2026-06-29 · périmètre : `SURVEILLER / Vue d'ensemble`
> (`webapp/frontend/components/overview/overview-dashboard.tsx`).
> Référence substrats & modes : [`registre-rails-temporels.md`](./registre-rails-temporels.md).

## 1. Question posée

Chaque valeur affichée **sous le rail SR-01** doit être une **projection réelle du
mode actif** — pas une valeur *live* déguisée par un badge, pas un fixture :

- **Maintenant** (live) — valeur courante, `?at` omis, **aucun chip**.
- **À un instant** (as-of T) — reconstruction `S4 as-of T` (séries) / `S1 as-of T`
  (état), `?at=<ISO>`, chip **« À cet instant »**.
- **Historique** — agrégat / évolution sur la fenêtre, `?at=<ISO>` (curseur),
  chip **« Sur la période »**.

Règle d'honnêteté (registre §1/§5, et la consigne d'audit) : un élément **non
projetable** pour le mode actif **ne porte pas** le badge de mode → *fallback
honnête* (« valeur courante / live ») ou masqué. **Jamais** un badge menteur.

## 2. Méthode — preuve par variation + reproductibilité

Les endpoints d'observabilité sont non authentifiés (`ADR 0009`). Chaque
consommateur a été audité par : (a) **lecture du code** (handler de route +
module) pour vérifier que `?at=` est bien *threadé* jusqu'à un filtre de substrat
**append-only** (`persisted_scores(scored_at ≤ T)` pour S4, `occurred_before(ts,
T)` sur le journal d'audit S1, `captured_at ≤ T` sur les bundles de replay) ;
(b) **sonde à trois instants** sur le backend en cours (`:8392`) :

```
live            (pas de ?at)
?at=2026-06-24T12:00:00Z   (juste après le début des données — fenêtre éparse)
?at=2026-06-26T12:00:00Z   (milieu de fenêtre)
```

Plage de données réelle observée : `2026-06-24T08:53 … 2026-06-29T14:17` (`n=24 290`).
Une valeur qui **varie** entre ces instants prouve la projection ; une valeur
**constante** n'est honnête que si elle est *justifiée* (sonde sur corpus figé de
la politique courante, ou contrôle structurel « au présent »).

Classes : **projeté-réel** · **invariant-justifié** · **live-sans-badge** ·
**écart (live badgé / fixture)**.

## 3. Matrice — élément × source × preuve

| Consommateur (bloc) | Endpoint | Substrat | `?at` threadé | Preuve de variation (live → as-of 06-24) | Classe | Badge honnête |
|---|---|---|---|---|---|---|
| KPI **Score qualité** · contrôle *Fidélité* · gate *qualité* · *Confiance* (footer) | `/observability/slo` | S4 score log (`scored_at ≤ T`) | oui | `good_rate 0.41 / n=17` → `0.50 / n=4` | projeté-réel | ✅ |
| KPI Score *sparkline* · Analytics *Scores récents* | `/observability/trend` | S4 score log | oui | `first/second 0.53/0.37` (8 buckets) → `0.8/0.2` (4 buckets) | projeté-réel | ✅ |
| KPI **Régression release** · ReleaseCard *score_before→after* | `/observability/what-changed` | bundles (`captured_at ≤ T`) | oui | `before 0.8 / after 0.4` (06-24T10) → `before 0.2 / after 0.8` (06-25T21) | projeté-réel | ✅ |
| Contrôle **Toxicité** · gate *sécurité* | `/observability/toxicity` | bundles | oui | `n_turns 15` → `4` (taux 0 — données réellement plates) | projeté-réel | ✅ |
| Contrôle **Fuite PII** · gate *sécurité* | `/observability/pii-leak` | bundles | oui | `n_turns 15` → `4` | projeté-réel | ✅ |
| Contrôle **Conformité format** · gate *conformité* | `/observability/conformance` | S1 journal d'audit (`occurred_at ≤ T`) | oui | `n_calls 31` → `12` | projeté-réel | ✅ |
| Contrôle **Validité des outils** | `/observability/tool-validity` | S1 journal d'audit | oui | `total 31` → `12` | projeté-réel | ✅ |
| KPI **Risques ouverts** · IncidentsCard (sessions) | `/observability/anomalies` | bundles | oui | `n_sessions 11 / anomalous 2` → `4 / 0` | projeté-réel | ✅ |
| KPI Risques · **Incidents à traiter** · IncidentsCard | `/observability/playbooks` | S4 score log + bundles | oui | déclencheur `59% < SLO` → `50% < SLO` | projeté-réel | ✅ |
| **Actions gouvernées** (Governance) | `/observability/roadmap` | S4 + bundles | oui | `n_turns 17 / n_items 4` → `4 / 3` | projeté-réel | ✅ |
| KPI **Coût LLM** | `/observability/cost` | bundles | oui | `0.043 € / 21 527 tok` → `0.014 € / 7 082 tok` | projeté-réel | ✅ |
| KPI **Preuves d'audit** (nombre) | `/audit/integrity` (`length`) | S1 journal d'audit | oui | `length 24 270` → `1 780` | projeté-réel | ✅ |
| Analytics **Distribution des langues** | `/observability/funnel` | S4 score log | oui | `n_turns 51 [fr39/en6/de6]` → `12 [fr12]` | projeté-réel | ✅ |
| **Scores récents** (RecentActivities) | `/observability/scores` | S4 score log | oui | `count 51` → `12` | projeté-réel | ✅ |
| **Rail SR-01** (marqueurs d'événements) | `/observability/timeline` | S4 + S1 (`≤ T`) | oui | `n_events 93` → `16` | projeté-réel | ✅ (rail non badgé, live par conception) |
| Contrôle **Calibration des refus** | `/observability/refusal` | sonde corpus figé (politique courante) | non | invariant (`0.0 / 0.6 / n=8/10`) | **invariant-justifié** | ✅ (FE `asOfCapable=false` → tooltip « valeur courante », pas de chip) |
| Contrôle **Efficacité firewall** | `/observability/firewall-efficacy` | sonde corpus figé adversarial | non | invariant (`recall 0.5454 / n=33`) | **invariant-justifié** | ✅ (FE `asOfCapable=false`, pas de chip) |
| ReleaseCard gate **conformité** (`compliance_rate`) | `/observability/ai-act` | obligations de politique courante + `verify_audit_chain` (contrôle structurel au présent) | partiel¹ | invariant (`1.0`) | **invariant-justifié** | ✅ (pas de chip par-gate ; le chip est au niveau **carte**, mérité par SLO/toxicité/PII/conformité as-of) |
| TrustFooter **Chaîne d'audit** (`verified`) | `/audit/integrity` (`verified`) | S1 — vérification structurelle de **toute** la chaîne (au présent) | non (par nature) | invariant (`true`) | **invariant-justifié** | ⚠️→✅ *durci* (§5) : le **nombre** est as-of-T, l'**intégrité** est au présent ; tooltip ajouté |
| TrustFooter **Systèmes** + `liveStatus` | `/healthz` · `/readyz` | aucun (sonde de vivacité du process + LLM) | non (par nature) | invariant (`ok` / `ready`) | **live-sans-badge** | ⚠️→✅ *durci* (§5) : marqueur « live » ajouté quand un chip de mode est présent |

¹ `?at` est threadé pour `n_turns`/`oversight` (texte de preuve) mais **pas** pour
les booléens de gate ni la vérification de chaîne — qui sont, à dessein, des
contrôles « au présent » (cf. docstring `observability_ai_act`).

### Métriques dérivées (calculées côté FE à partir des lignes ci-dessus)

- **Contrôles en échec** (`x/y`), **Confiance des signaux** (% au seuil),
  **Impact par signal** — dérivés des contrôles (tous as-of-projetés) → honnêtes
  par héritage. Aucun substrat propre ; pas de badge propre.

## 4. Verdict

**15 projeté-réel · 3 invariant-justifié · 0 écart confirmé.**

Toute valeur portant le badge **« À cet instant » / « Sur la période »** est une
**vraie projection** du substrat à T (variation prouvée, ou platitude réelle des
données). Les valeurs constantes le sont pour une **raison justifiée** : sonde sur
corpus figé de la politique *courante* (refus, firewall) ou contrôle *structurel
au présent* (intégrité de chaîne, AI Act). La reproductibilité tient : même
`(mode, scope, T)` ⇒ même valeur (re-dérivée du substrat append-only ; sondes
répétées identiques).

### Deux écarts *suspectés* — réfutés (vérification adversariale)

1. **ReleaseCard / gate conformité** — *réfuté*. Il n'existe **pas** de chip
   par-gate : le seul `TimeTagChip` est au niveau **carte** (`overview-dashboard.tsx`
   titre ReleaseCard) et il est **mérité** par les autres entrées de la carte
   (qualité←SLO, sécurité←toxicité+PII, conformité←`conformance` — toutes
   threadées par `at`). `compliance_rate` n'est pas badgé individuellement.
2. **Systèmes / `/healthz`** — *réfuté* comme « badge menteur » : il n'existe
   **aucun substrat d'historique de santé** à projeter ; « système opérationnel »
   est une binaire **présent** par nature. Mais le footer ne portait pas de
   marqueur *live* explicite → **durci** au §5 par honnêteté (registre §4).

## 5. Durcissements appliqués (honnêteté, registre §4)

Aucun écart *menteur* n'existait ; deux finitions d'honnêteté ont néanmoins été
appliquées au TrustFooter pour que **chaque** valeur soit, sans ambiguïté, soit
une projection, soit explicitement marquée *live/présent* :

- **Systèmes** (`systemsOk`) — quand un chip de mode est actif (À un instant /
  Historique), la pastille porte désormais un **marqueur « live »** (`TimeTagChip
  kind="live"`, tooltip « Signal courant — mesuré maintenant ») : la santé du
  process est une valeur *courante*, jamais reconstruite à T.
- **Chaîne d'audit** — tooltip ajouté quand un chip de mode est actif : le
  **nombre d'entrées** est à l'instant choisi, mais **l'intégrité de la chaîne est
  vérifiée au présent** (contrôle structurel de tout le journal).

Ces deux éléments n'ont **pas** de substrat d'historique projetable ; le *fallback
honnête* (marquer « live / au présent ») est donc le bon correctif, pas une
projection fabriquée.

## 6. Tests

- `tests/integration/test_rail_provenance.py` — sur un échantillon représentatif
  (S4 : `slo`, `funnel` ; S1 : `tool-validity` ; bundles : `cost` ; invariant :
  `firewall`), via `TestClient` : (a) **variation** — `?at` ancien ⇒ valeur
  différente (sous-ensemble) ; (b) **reproductibilité** — même `?at` deux fois ⇒
  valeur identique ; (c) **invariance justifiée** — la sonde corpus-figé est
  constante ; (d) **monotonie** — `n(T_ancien) ≤ n(live)`.
- `e2e/surveiller-temporal.spec.ts` — en *À un instant*, le footer **Systèmes**
  porte le marqueur *live* et la **Confiance** porte le chip de mode (séparation
  honnête projeté vs live).
