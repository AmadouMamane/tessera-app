# Registre des rails temporels — Tessera

> Section destinée à `docs/design/ui-contract.md` · v1.11 (2026-07-22)
>
> v1.11 — deux promotions AGENT. (1) **AT-01 Implémenté** : « Voir à date » revient sur la
> Synthèse — retiré en v1.5 parce qu'il mentait, il ne revient que parce que le contenu
> l'honore : `compute_agent_synthese(agent_id, period, at)` relit transcript, CSAT et journal
> S1 sur la **fenêtre finissant à T** (SQL borné des deux côtés via `_transcript_scope`, seam
> ledger `read_ledger_entries(since=, until=)` — la dette du cliquet ledger descend 17→16) ;
> `?asof=` URL, mode affiché, bannière scopée (connaissances / prompts / badge de chaîne
> restent live, dit tel quel). (2) **CT-01 Implémenté** : la timeline de conversation gagne
> les **filtres C2 dérivés de l'URL** (`?turn_agent=`, `?routed=1` — chips servies serveur,
> deep-linkables, honest-empty quand le filtre ne matche rien) et le chrome instrument ; et
> les conversations RÉELLES sortent du sous-onglet fixture : elles mènent la page Historique,
> la zone d'éval déterministe passe dessous, estampillée `SyntheticNotice`.
>
> v1.10 — le chantier SR-01 « Qualité IA / Amélioration » est soldé, avec une correction de
> vérité au passage. (1) **Qualité IA était DÉJÀ câblée** : son composant s'appelle
> `observability-dashboard.tsx` (piège de nom — il ne sert PAS la page Observabilité), et il
> rend le command bar avec des requêtes as-of/scope réelles depuis la v1.8 ; les mentions v1.8
> « Observabilité câblée » et §10 « Qualité IA : aucune » décrivaient donc le monde à l'envers,
> corrigées ici. Sa vue éval (`ScorecardView`) est la lentille d'éval (domaine ER-01), pas un
> scrubber. (2) **Amélioration est câblée pour de vrai** : `compute_improvement(lang, at)`
> borne `read_scores(at)`, `recent_bundles(at=)` et `load_quality_datasets(at=)` (runs d'éval
> filtrés par l'instant du run ≤ T, fraîcheur pipeline relative à T) ; la fraîcheur du corpus
> reste vive (les fichiers corpus ne portent pas d'historique) — dit tel quel. Le bar y est
> `scopeFilter=false` (posture org-wide). (3) **Observabilité requalifiée** : `health-dashboard`
> lit quatre états de processus vivants (health / readiness / budget / tail-sampling) sans
> substrat S4 persisté — un scrubber y serait le mode cosmétique purgé en v1.5 ; verdict
> motivé : pas de rail.
>
> v1.9.1 — le chantier « paramètres à T » nommé en v1.9 est **exécuté** (périmètre overrides) :
> `override_rows_as_of(asof)` fold RÉEL du ledger (`config_overrides.<clé>`, écritures et
> reverts, auteur vérifié au top-level, lecture bornée `until`), route
> `GET /observability/parameters?asof=`, et CONFIGURER / Paramètres rend la composition §6
> As-of + Live via **LE même composant** `AgirRail` — enrichi de deux notes scopées
> (`liveNote` / `asofNote`) pour que la lecture « État au T » dise EXACTEMENT ce qu'elle
> couvre : les paramètres gouvernés sont relus à T, le socle process reste celui d'aujourd'hui
> (la relecture du socle — git/policy à T — reste un chantier, dit tel quel). Témoins :
> `TestOverrideRowsAsOf` (dernier write ≤ T par clé, revert = retour au socle, réécriture
> post-revert, auteur + instant réels).
>
> v1.9 — câblage réel et complétude, sur trois fronts. (1) **Preuves & exporteurs devient
> as-of RÉEL** : `compute_proofs_overview(lang, asof=)` borne chaque compteur réel à T
> (préfixe du ledger — SQL en postgres, seam fichier sinon —, scores/bundles/rapports/packs à
> T ; verdict de chaîne AU PRÉFIXE : une rupture après la borne T laisse l'état à T sain), la
> page passe `temporal.asOf` à sa requête, et « Créer un pack » est **gelé dans le passé** (on
> n'agit pas dans le passé, règle agir-rail). Le bar SR-01 y est donc pilotant, plus seulement
> contextuel. (2) **AU-01 enregistré et promu** : la barre de fenêtre du Journal d'audit
> (période 24h/7j/30j + plage réelle + saut à date, qui borne les requêtes en SQL) est un rail
> de plein droit — elle monte **au-dessus** de la carte « Vue par agent » et porte le chrome
> instrument (`WindowControl variant="instrument"`). (3) **Inventaire page-par-page** (§10) :
> chaque route porte un verdict rail/pas-rail motivé ; OT-01 gagne le home CONFIGURER /
> Paramètres avec son chemin de promotion — le substrat « paramètres à T » EXISTE (chaque
> mutation de knob au ledger hash-chaîné porte `{value, base, reason}` et les reverts sont
> journalisés : l'état des knobs à T est un fold réel), il manque le fold et la lentille.
>
> v1.8 — convergence visuelle et honnêteté des instances SR-01, après balayage **page par
> page** (l'unité d'audit v1.5 était le rail ; celle-ci est la page). (1) **Un rail porte la
> surface instrument** (`sr01-strip`, laque sombre à liseré cyan) — il se distingue de toute
> carte de contenu ; appliqué au rail standalone (Prompts, Garde-fous, Évaluations), à
> l'agir-rail et à l'ER-01 ; le PeriodRail (Fiabilité & coût) reste une **carte d'agrégats**,
> pas un instrument de navigation — il ne porte pas ce chrome. (2) **Preuves & exporteurs rend
> désormais LE `SignalCommandBar`** de la Vue d'ensemble (même composant, même substrat S4)
> au lieu d'une variante appauvrie — sans filtre Agents (les magasins de preuve sont org-wide,
> un filtre qui ne filtre rien est un contrôle fantôme) et sans baseline objectif (l'ancien
> rail affichait « Comparer à objectif » sans jamais pouvoir le calculer ; désormais
> désactivé-avec-raison). Écart dit tel quel : les zones métier de la page restent **live** —
> la relecture as-of du payload proofs (`compute_proofs_overview` n'a pas de paramètre `asof`)
> est le chemin de promotion, pas simulée. (3) Écarts constatés au balayage, nommés :
> **Qualité IA** et **Amélioration** ne rendent **aucun** scrubber (la note SR-01 v1.3
> prétendait Qualité IA ; c'était faux) — à faire ; le composant orphelin
> `assistant-overview.tsx` (rail fantôme jamais routé) est **supprimé**.
>
> v1.7 — WF-01 passe à **Implémenté** : le substrat manquant est construit — journal
> **append-only** des transitions de cas (`operator_items_transitions.jsonl`,
> `{item_id, at, kind, from, to, by}`, jamais réécrit) écrit par `set_item_state(..., by=)` dont
> l'auteur est **obligatoire et sans défaut** ; les deux endpoints de transition passent au
> patron gouverné (session vérifiée, `actor_of`, `emit_governance_mutation` — l'écart ADR 0024
> est clos, actes 15/16 du cliquet d'attribution). La timeline C2 est rendue dans les DEUX
> drawers (À faire : onglet Historique ; À traiter : bloc Transitions), chaque ligne nomme son
> auteur vérifié, et la sélection de cas dérive de l'URL (`?item=`) sur les deux pages. La note
> « transitions non journalisées » est retirée — elle disait vrai, elle ne l'est plus.
>
> v1.6 — XT-01 passe à **Implémenté** : la capture S2 est complétée à la couture de capture
> (prompt LLM assemblé, échantillonnage résolu, appels d'outils portant leur nœud parent réel,
> offsets de départ mesurés, durée du reporter ; pas de seed — aucun backend n'en expose un, en
> capturer serait un mensonge), et la lentille cassette vit sur AGIR / Replay (onglet Cassettes :
> sélection `?bundle=` dérivée de l'URL, mode toujours affiché, honest-empty, arbre C3
> nœuds→outils, rejeu par le POST gouverné existant). Note datée XT-01 ci-dessous.
>
> v1.5 — audit complet des 8 rails contre le code (SR-01 confirmé conforme et pris comme norme
> de référence, validée produit). Le registre se trompait dans les deux sens : TE-01 passe à
> **Implémenté** (la page État à date existait au complet ; le deep-link `?asof=` et la puce de
> mode, seuls manquants, sont posés) ; AT-01 et CT-01 passent à **Partiel** (feed et timeline
> réels, branchés) ; OT-01 est requalifié (la note v1.4 « Connaissances cadré » ne décrivait pas
> la réalité). Trois mensonges d'UI purgés au passage : le mode « État à date » cosmétique de la
> Synthèse (bandeau « données reconstituées » sur des données live), les boutons as-of/comparer
> sans `onClick` des snapshots Garde-fous/Prompts, et l'historique overlay servi mais jamais
> rendu (Prompts, désormais affiché). Notes datées par rail ci-dessous ; §9 documente le 5e état
> de badge que le code expose depuis Hica.
>
> v1.4 — ER-01 passe à **Implémenté** (rail des runs d'évaluation, page AGENT / Évaluations) : `webapp/frontend/components/agent/evaluation-run-rail.tsx`, payload `src/tessera/observability/agent_evaluations.py` (`_runs_rail`).
>
> v1.3 — SR-01 passe à **Implémenté** (scrubber de signaux SURVEILLER) ; le rail de la Vue d'ensemble, jadis mal nommé « XT-01 » et porteur d'un « rejeu », est réaligné sur SR-01 (modes Live/Historique/Comparé/À une date, zéro replay d'exécution, deep-link URL). XT-01 reste « À faire » sur son home Console/AGIR.

## 1. Principe

Un **rail temporel** est un composant de navigation dans le temps, réutilisable et adressable par code (`TE-01`, …).

- **Reproductibilité** — chaque rail est une **projection déterministe** d'un substrat **append-only, horodaté, taggé `agentId`**. Même `(rail, scope, T)` ⇒ même vue, re-vérifiable.
- **Modularité** — les rails qui lisent le **même substrat** partagent le **même composant de base**. On construit **4 composants**, pas 8 rails.
- **Contexte global borné** — le sélecteur « voir à date » (instant `T` / plage) peut être propagé par l'URL et suivre l'utilisateur, **mais** chaque page doit **afficher explicitement le mode actif** : `Live`, `Historique`, `As-of` ou `Replay`. **Aucune page ne bascule implicitement en mode historique sans indicateur visible.**

Règle de placement : **config → versions · signaux → scrubber (Surveiller) · preuve → as-of (Prouver).**

## 2. Substrats

| Code | Substrat | Propriétés |
|------|----------|------------|
| **S1** | Journal config / état | bitemporal (valid/transaction), **hash-chaîné**, append-only |
| **S2** | Traces d'exécution (spans / inférence) | append-only ; capture des entrées **nécessaires au replay** : retrieval, prompt assemblé, params, tools, modèle, runtime, seed *si disponible* |
| **S3** | Journaux métier (runs, conversations, cases) | append-only, événements non réécrits |
| **S4** | Séries de signaux / métriques | time-series (rétention, agrégation, downsampling) |

## 3. Composants de base

| Code | Composant | Lit | Projections |
|------|-----------|-----|-------------|
| **C1** | Fold engine | S1 | as-of · par-objet · feed récent |
| **C2** | Timeline-over-X | S3 | liste ordonnée + filtres (WF : + machine à états) |
| **C3** | Trace viewer | S2 | arbre de spans d'une exécution |
| **C4** | Signal Scrubber | S4 | Live · Historique · **Baseline** · comparaison de périodes |

> **Replay = AGIR uniquement** (via `XT-01`). Le C4 ne rejoue pas une exécution : il navigue dans les signaux et compare des périodes.

## 4. Registre des rails

États : `Proposé` · `Cadré` (spécifié) · `Normatif validé` (design validé, impl. non confirmée) · `Implémenté` (code complet) · `À faire`.

| Code | Nom canonique | Usage | Pages | Substrat | Composant | État |
|------|---------------|-------|-------|----------|-----------|------|
| **TE-01** | Temporal Evidence Rail | Preuve opposable / reconstitution à T | `PROUVER / État à date` | S1 | C1 (as-of) | Implémenté |
| **OT-01** | Object Trace Rail | Historique local d'un objet agent / de config | Configurations, Connaissances, Garde-fous, Prompts, Sources & mémoire, `CONFIGURER / Paramètres` (v1.9) | S1 | C1 (par-objet) | Partiel — amorces (note) |
| **AT-01** | Agent Activity Rail | Activité récente (feed) — *pas* les signaux | `AGENT / Synthèse` | S1 | C1 (feed) | Implémenté — Voir à date réel (note v1.11) |
| **ER-01** | Evaluation Run Rail | Historique des runs d'évaluation | `AGENT / Évaluations` | S3 | C2 | Implémenté |
| **CT-01** | Conversation Timeline Rail | Chronologie conversationnelle | `AGENT / Historique` | S3 | C2 | Implémenté — filtres + sortie du fixture (note v1.11) |
| **WF-01** | Workflow Case Rail | Cycle de traitement humain | `AGENT / À traiter`, `À faire` | S3 | C2 + état | Implémenté — journal + timeline (note) |
| **XT-01** | Execution Trace Rail | Trace technique d'une exécution | `AGENT / Console`, `AGIR / Replay` | S2 | C3 | Implémenté — cassette (note) |
| **SR-01** | Signal Scrubber Rail | Surveillance continue dans le temps | `SURVEILLER` (5/7 pages, dont Qualité IA et Amélioration — note v1.10) · `PROUVER / Preuves & exporteurs` (payload as-of réel, v1.9) · standalone : Prompts, Garde-fous, Évaluations (note v1.8) | S4 | C4 | Implémenté (v1.10) |
| **AU-01** | Audit Window Rail | Fenêtrage réel du journal d'audit (période + saut à date) | `PROUVER / Journal d'audit` | S1 | C2 (fenêtre) | Implémenté — instrument (v1.9) |

> **SR-01 (état au 2026-06-27)** — implémenté comme `components/overview/temporal-rail.tsx`, rendu par les pages SURVEILLER (Vue d'ensemble, Qualité IA, Conformité, Sécurité & privacy). Modes **Live · Historique · Comparé (baseline) · À une date** — navigation de **signaux** uniquement (S4/C4). **Aucun replay d'exécution** : ce composant ne rejoue jamais un tour/trace (déplacement d'un curseur T sur les signaux persistés, lus as-of-T). Mode actif **toujours affiché** ; état dérivé de l'**URL** (deep-link `?asof=&period=` — le paramètre de fenêtre s'appelle `period`, corrigé v1.5, plus `at`/`to`/`compare`), pas d'un état local ; fenêtre (Période) lue depuis le **window-store partagé**, non dupliquée (§8). Le code de rail (`SR-01`) reste interne — **jamais affiché** (§ glossaire). Auparavant mal nommé « XT-01 » sur la Vue d'ensemble : corrigé.

> **SR-01 (état au 2026-07-22, v1.8) — homes réels et chrome instrument.** Le **command bar**
> (`signal-command-bar.tsx`, enveloppe premium du composant de base `temporal-rail.tsx` en mode
> `embedded`) est rendu par **4 pages SURVEILLER** (Vue d'ensemble, Sécurité & privacy,
> Conformité, Observabilité — leurs requêtes de contenu consomment `asOf`/`scope`) **et par
> PROUVER / Preuves & exporteurs** (v1.8 : même composant, `scopeFilter=false` car les magasins
> de preuve sont org-wide, pas de baseline objectif ; les zones métier restent live — la
> relecture as-of du payload proofs est un chantier nommé, jamais simulée). Le **rail
> standalone** (même composant de base, chrome instrument, sans filtre org) est rendu par
> Prompts, Garde-fous et Évaluations (cf. note OT-01 : ces pages rendent SR-01, pas un OT-01).
> **Écart** : Qualité IA et Amélioration ne rendent aucun scrubber (la note v1.3 « rendu par
> Qualité IA » était fausse) ; Fiabilité & coût rend le `PeriodRail` (agrégats de période —
> volontairement pas un scrubber). Promotion : brancher le bar sur ces pages **exige** que
> leurs requêtes consomment `asOf` (le poser sans câblage recréerait le mode cosmétique purgé
> en v1.5). **Norme visuelle (§5)** : tout rail temporel porte la surface instrument
> (`sr01-strip`) — jamais le chrome d'une carte de contenu.

> **SR-01 / Preuves & exporteurs (état au 2026-07-22, v1.9) — as-of RÉEL.**
> `compute_proofs_overview(lang, asof=)` borne chaque compteur réel à T : préfixe du ledger
> (`ledger_length_as_of` en SQL sur postgres ; seam `read_ledger_entries` + `occurred_before`
> en mode fichier), `read_scores(at=)`, `persisted_bundles(at=)`, rapports (instant du run
> dans le nom `<run-id>_<lang>.json`, repli mtime pour les alias `latest*.json`), packs par
> `created_at`. **Verdict de chaîne au préfixe** : l'intégrité de contenu de la chaîne
> entière implique celle de tout préfixe — une rupture à l'indice b laisse l'état à T sain si
> b ≥ borne(T) (témoin `test_the_chain_verdict_at_t_is_the_prefix_verdict`). Le frontend passe
> `temporal.asOf` (débouncé) dans la clé de requête ; « Créer un pack » est gelé en as-of avec
> raison (« on n'agit pas dans le passé »). Restent démonstration, dits tels quels : SIEM /
> exporteurs / journal d'export (`SyntheticNotice evidence_export`).

> **SR-01 (état au 2026-07-22, v1.10) — Qualité IA démasquée, Amélioration câblée,
> Observabilité requalifiée.** Correction de vérité : la note v1.8 listait « Observabilité »
> parmi les pages câblées et l'écart « Qualité IA ne rend aucun scrubber » — c'était le monde
> à l'envers, induit par un piège de nom : le composant `observability-dashboard.tsx` sert
> `surveiller/qualite-ia` (la page Observabilité rend `health-dashboard.tsx`). Constat lu du
> code : **Qualité IA** rend le command bar avec requêtes as-of/scope réelles depuis v1.8 ;
> sa vue éval (`ScorecardView`) est la lentille d'éval — domaine ER-01, pas un scrubber.
> **Amélioration** (v1.10) : `compute_improvement(lang, at)` borne `read_scores(at)`,
> `recent_bundles(at=)` et `load_quality_datasets(at=)` — les runs d'éval sont filtrés par
> l'instant du run (`run_at` ≤ T, un run non datable est exclu d'une vue as-of), la fraîcheur
> pipeline est relative à T ; la fraîcheur du **corpus** reste vive (fichiers sans historique),
> dit tel quel. `GET /observability/improvement?at=` ; le dashboard porte le command bar en
> `scopeFilter=false` (posture org-wide, pas de `?agent=` dans sa requête) et coupe le polling
> en mode Historique. **Observabilité** : health / readiness / budget / tail-sampling sont des
> états de processus vivants sans substrat S4 persisté — verdict motivé : pas de rail (un
> scrubber y serait le mode cosmétique purgé en v1.5).

> **AU-01 (état au 2026-07-22, v1.9) — Implémenté, promu instrument.** La barre de fenêtre du
> Journal d'audit était déjà **réelle** (préréglages 24h/7j/30j + plage affichée depuis le
> payload + saut à date ; `since`/`until` bornent les requêtes overview/table en SQL sur
> l'index `occurred_at`) mais rendue comme une carte quelconque SOUS la carte « Vue par
> agent » — invisible comme rail. v1.9 : elle monte **en tête** (la carte agent se glisse
> dessous via le slot `breakdown` d'`AuditTable`) et porte le chrome instrument
> (`WindowControl variant="instrument"` — le défaut `card` préserve l'usage du header).
> Pas de scrubber d'instant ici : le journal se consulte par FENÊTRE (C2), l'état à T est le
> domaine de TE-01.

> **OT-01 / Paramètres (état au 2026-07-22, v1.9) — chemin de promotion, substrat PROUVÉ.**
> « Voir mes paramètres d'il y a 3 h » est constructible sans nouveau substrat : chaque
> mutation de knob passe par le patron gouverné et le ledger hash-chaîné porte
> `{value, base, reason}` et les reverts (`{"reverted": True, ...}`) — les deux sites
> d'émission vivent dans `api/routes/settings.py`, horodatés `occurred_at`. L'état des knobs à T = base + fold des
> mutations ≤ T (dernier write non reverté). Chantier : `compute_parameters_overview(asof=)`
> (fold), lentille as-of sur CONFIGURER / Paramètres (mode affiché, `?asof=` URL, mutations
> gelées à T — règle agir-rail), témoin unitaire du fold. Même patron ensuite pour Modèles /
> Garde-fous / Politiques (leurs mutations sont au même ledger).

> **XT-01** — homes `AGENT / Console` (waterfall live du tour courant, SSE) et `AGIR / Replay` (lentille cassette sur les captures persistées). Il **n'est plus** sur la Vue d'ensemble. Implémenté au 2026-07-22 — voir la note datée XT-01 plus bas.

> **ER-01 (état au 2026-07-15)** — implémenté comme `webapp/frontend/components/agent/evaluation-run-rail.tsx`, rendu par `AGENT / Évaluations` ; payload `runs` de `src/tessera/observability/agent_evaluations.py` (`_runs_rail`). Il parcourt les **runs d'évaluation** de l'agent (S3/C2 — journal de runs lu depuis `eval/reports/<env>/`, convergent avec la table `eval_gating` mesurée le 2026-07-15 : 29/29 runs partagés identiques) — **pas** les signaux (domaine du SR-01, S4/C4), **aucun replay**. Chaque point = un run portant sa **provenance stockée** (date + version de catalogue + modèle, `eval-gate-policy.md` § provenance — jamais une « dernière éval » unique) et le **verdict gate enregistré au moment du run** (absent = « non enregistré », jamais recalculé contre les dérogations d'aujourd'hui). Modes **Live (dernier run) · Historique (run sélectionné)**, toujours affichés ; sélection dérivée de l'**URL** (deep-link `?run=<run_at>`), jamais d'un état local. Honest-empty : agent sans run ⇒ rail explicitement vide (« Éval non exécutée ») ; 1 run ⇒ 1 point sans tendance ; **Δ** de taux seulement entre **deux** runs de la **même** version de catalogue. Le code de rail (`ER-01`) reste interne — **jamais affiché**. Portes d'entrée : la Vue par agent (lentille qualité de `SURVEILLER / Qualité IA`) et la Flotte mènent à la page Évaluations de l'agent.

> **TE-01 (état au 2026-07-21) — Implémenté.** Page `PROUVER / État à date` complète :
> `components/proofs/etat-a-date.tsx` + `observability/etat_a_date.py` (`build_etat_a_date`,
> projection as-of réelle) ; badge d'opposabilité **calculé à l'affichage** par
> `active_ledger_opposability(at=T)`, mention obligatoire rendue, honest-empty partout, e2e
> `etat-a-date.spec.ts`. Les deux derniers écarts à la norme sont clos en v1.5 : l'instant T est
> **dérivé de l'URL** (`?asof=`, partageable, honoré aussi par le prefetch serveur) comme
> `?sources=` et `?agent=`, et le **mode est une puce toujours visible** (`meta.as_of_label`,
> Live vert / instant violet) à côté du badge.

> **AT-01 (état au 2026-07-21) — Partiel.** Le **feed C1 est implémenté et réel** :
> `agent_synthese.py` (`_scan_journal` sur le journal S1 hash-chaîné + tours du transcript,
> `_activity_rows`), rendu sur `AGENT / Synthèse` ; honest-empty ; aucun signal d'éval dans le
> feed (la règle §7 tient). En v1.5 le rail a été **réduit à ce qu'il honore** : Live + Période.
> Le segment « Voir à date » et son bandeau « données reconstituées au point sélectionné »
> mentaient — `compute_agent_synthese` n'a **aucun paramètre as-of** (fenêtre glissante finissant
> maintenant) ; le segment « Comparaison » était un texte statique. Promotion à Implémenté =
> borner `_fetch_transcript`/`_scan_journal` par `until=T`, passer T du client au backend, et
> alors seulement ré-offrir le mode.

> **AT-01 (état au 2026-07-22, v1.11) — Implémenté.** La promotion nommée ci-dessus est
> exécutée telle quelle : `compute_agent_synthese(agent_id, period_days, at)` — le scope
> transcript/CSAT devient la fenêtre `period` **finissant à T** (`_transcript_scope`,
> `created_at <= T AND created_at >= T - interval`, SQL paramétré), le scan du journal S1
> est borné **au seam** (`read_ledger_entries(since=, until=)`, SQL en postgres ; les filtres
> côté appelant restent la ceinture du mode fichier, un événement sans instant parseable est
> exclu d'une vue à T) — `agent_synthese` sort du set OWED du cliquet ledger (17→16). Le rail
> ré-offre « Voir à date » (datetime-local → `?asof=` URL, patron agir-rail), porte le chrome
> instrument (`sr01-strip`) et une bannière **scopée** : conversations, satisfaction et
> journal relus à T ; connaissances, prompts, identité registre et badge de chaîne restent
> live. Témoins : `test_transcript_scope_at_t_bounds_both_ends`,
> `test_scan_journal_until_excludes_later_and_unplaceable_events`, `test_parse_at_is_tolerant`.

> **CT-01 (état au 2026-07-21) — Partiel.** La **timeline tour-par-tour est implémentée et
> réelle** : `agents/[agentId]/historique/[sessionId]/page.tsx` (sélection par l'URL de route),
> payload `observability/session_detail.py` sur le transcript durable (ADR 0040), honest-empty,
> distinction denied/empty (F-4). v1.5 la **désorpheline** : chaque conversation du bloc
> « Conversations en direct » (`agent-historique.tsx`) est un lien vers sa chronologie, la plus
> récente porte « Dernière », la page détail affiche la puce de mode « Historique · conversation
> sélectionnée », et `transcript.list_conversations` **exclut enfin les tours synthétiques**
> (un essai d'opérateur ne se présente plus comme une conversation client). Promotion =
> filtres C2 sur la timeline et sortie du fixture éval qui partage l'écran.

> **CT-01 (état au 2026-07-22, v1.11) — Implémenté.** Les deux conditions de promotion sont
> exécutées. (1) **Filtres C2 sur la timeline** : chips dérivées de l'URL (`?turn_agent=<id>`,
> `?routed=1`), rendues serveur sur la page de session — par agent (avec compte de tours,
> seulement quand la conversation en implique plusieurs) et « tours routés » ; deep-linkables,
> honest-empty explicite quand le filtre ne matche rien ; le bandeau de chronologie porte le
> chrome instrument (`sr01-strip`). (2) **Sortie du fixture** : le bloc « Conversations en
> direct » (l'entrée réelle vers la chronologie) ne partage plus le sous-onglet Messages avec
> l'échangeur d'éval déterministe — il mène la page Historique, au-dessus des sous-onglets ;
> la zone fixture restante est estampillée (`SyntheticNotice agent_historique`, capacité déjà
> déclarée `synthetic`). Le tableau de bord d'éval déterministe reste sur la page, dit tel
> quel — sa suppression totale est une décision produit non prise en silence.

> **OT-01 (état au 2026-07-21) — Partiel, requalifié.** La note v1.4 (« Connaissances cadré »)
> ne décrivait pas la réalité : le seul bloc **Versions** réel (runs d'ingestion + honest-empty)
> vit sur **CONFIGURER / Sources & mémoire** (`sources-overview.tsx` `VersionsBlock`,
> `sources.py` `_corpus_versions`) — home ajouté au tableau. **Garde-fous** et **Prompts**
> rendent le rail **SR-01** (signaux S4) — ce n'est pas un OT-01 ; leurs snapshots portaient des
> contrôles as-of/comparer **sans `onClick`**, retirés en v1.5 (un contrôle qui promet un as-of
> inexistant est un mensonge). **Prompts** : l'historique du cycle overlay (ADR 0037 — proposé /
> approuvé / rejeté / révoqué, chaque événement nommant son auteur) était servi par le backend et
> jamais rendu — **affiché depuis v1.5** ; c'est la première vraie trace par-objet à l'écran.
> **Configurations** : l'historique mêlait tous les agents — **filtré per-objet** (`agent_id`)
> en v1.5, les mtimes de fichiers dépôt restant comme provenance commune. Promotion = un vrai
> C1 par-objet (versions consultables à T) sur chaque home.

> **WF-01 (état au 2026-07-21) — À faire, le substrat manque.** Le magasin d'état des cas
> (`operator_items.py`, `operator_items_state.json`) est à **écrasement** : `set_item_state`
> mute l'entrée et réécrit le fichier — aucune liste de transitions horodatées, et les deux
> endpoints de transition (`mutations.py`) ne capturent **pas l'auteur** (pas de session, pas
> d'émission gouvernance — écart ADR 0024). L'onglet Historique du drawer l'avoue (« Les
> transitions de statut ne sont pas journalisées »). Un rail est une projection d'un substrat
> append-only (§1) : sans journal de transitions `{from, to, at, by}`, WF-01 ne peut pas
> exister. Déjà bons et à conserver : partition par nature (ADR 0038), horloge SLA depuis
> l'entrée en file (ADR 0039), badge d'état courant, mode Live affiché, honest-empty.

> **WF-01 (état au 2026-07-22) — Implémenté (journal + timeline + attribution).** Le substrat
> est construit : `operator_items_transitions.jsonl` (même dossier que le magasin d'état),
> **append-only** — jamais réécrit, une ligne `{item_id, at, kind, from, to, by}` par changement
> effectif (un no-op n'écrit rien : une transition qui ne change rien n'est pas une transition).
> `set_item_state(..., by=)` exige l'auteur **sans défaut** (ADR 0024 — une transition non
> attribuée est impossible à écrire) ; les deux endpoints (`inbox/item-state`,
> `agent-a-faire/item-state`) passent au patron gouverné : session vérifiée → `actor_of` →
> journal → `emit_governance_mutation` (actes 15/16 du cliquet `governed_acts_name_their_author`,
> `governed_prefixes` élargi en même temps — protocole Insight 177). Projection C2 rendue sur
> les **deux homes** : drawer À faire (onglet Historique — lignes `de → vers · auteur · date`,
> lues du journal par `_transition_rows`) et drawer À traiter (bloc Transitions, décoré en une
> **seule** lecture du journal par backlog via `transitions_by_item`). Sélection de cas dérivée
> de l'**URL** (`?item=`, deep-link) sur les deux pages ; honest-empty : un cas jamais déplacé
> depuis l'ouverture du journal (2026-07-22) le dit tel quel — l'historique d'avant le journal
> n'existe pas et n'est **pas** reconstitué. Témoins : `TestTheTransitionsJournal`
> (append-only, auteur requis par signature, no-op silencieux, scope par cas), e2e `a-faire`
> (deep-link + transition → ligne attribuée). Restent au magasin d'état (écrasement, voulu) :
> le statut courant et `first_seen` (ADR 0039).

> **XT-01 (état au 2026-07-21) — À faire, amorces précisées.** `agir-rail.tsx` n'est **pas**
> XT-01 : c'est l'implémentation conforme de la **composition §6** (As-of + Live, `?asof` URL,
> mode affiché, mutations gelées à T) rendue sur curation / automations / replay-shadow. La
> Console rend un **waterfall plat** du tour live (`TraceColumn` — pas d'arbre parent/enfant
> persisté) ; les spans OTel partent vers des backends externes (pas de magasin S2 relisible par
> exécution). Le **backend replay existe** (`replay.py` : bundles append-only, `POST
> /observability/replay`, re-génère + re-juge avec `score_delta`) mais la capture S2 est
> incomplète (prompt assemblé, params, tools, seed absents du `ReplayBundle`) et la **lentille
> replay UI reste due** — la page AGIR / Replay est un dashboard analytique, aucune cassette.
> Chemin : compléter la capture S2 → lentille replay (mode « Replay » affiché, dérivé de l'URL)
> → arbre C3.

> **XT-01 (état au 2026-07-22) — Implémenté (cassette + arbre à 2 niveaux).** La capture S2 est
> complétée à la couture `chat.py → capture_bundle` : prompt LLM assemblé exact
> (`debug_prompt_messages`, question masquée — fidèle à ce que le modèle a vu), échantillonnage
> résolu au seam (ADR 0031) + plafond de sortie, appels d'outils (nom / nœud / issue / durée —
> jamais les arguments ni les résultats, potentiellement PII), offsets réels de départ des
> nœuds et durée mesurée du reporter streamé. Chaque `ToolCallRecord` porte désormais son nœud
> créateur (`node=NODE_NAME`, posé par le worker lui-même, 5 sites) — la parenté de l'arbre est
> **réelle**, jamais déduite du timing. Pas de champ seed : aucun backend de génération n'en
> expose ou n'en fixe un aujourd'hui (S2 dit « si disponible »). Les bundles antérieurs
> relisent `None` partout et s'affichent « non capturé » (témoin
> `test_a_legacy_row_without_the_s2_fields_still_reads`). La **lentille cassette** vit sur
> `AGIR / Replay`, onglet Cassettes (`components/replay/replay-cassette.tsx`) : sélection
> **dérivée de l'URL** (`?bundle=`, un deep-link ouvre l'onglet), **mode toujours affiché**
> (« Live · dernières captures » / « Replay · cassette sélectionnée »), honest-empty, arbre C3
> nœuds→outils avec waterfall positionné aux offsets réels (`lib/replay-cassette.ts`, pur et
> testé ; sans offsets : durées seules, **aucun total fabriqué** — les nœuds parallèles se
> chevauchent), prompt et sampling affichés, rejeu contre un modèle candidat par le
> `POST /observability/replay` existant (gouverné ; gelé en lecture as-of — on n'agit pas dans
> le passé). Hors périmètre, dits tels quels : les spans OTel restent export-only (le substrat
> S2 relisible est `bundles.jsonl`, append-only) ; l'arbre est à 2 niveaux (nœuds → outils),
> pas de profondeur arbitraire ; le waterfall Console (`TraceColumn`) reste la vue live SSE du
> tour courant.

## 5. Contrat de composant (commun)

```
Rail({
  code,                                         // TE-01 … SR-01
  scope: { tenant, agentId, objectId? },
  time:  { mode, T?, range? },                  // mode = live | historique | as-of | baseline | replay
  source                                        // substrat S1…S4
})
```

Le **mode actif est toujours affiché** dans le rail, et l'état/surlignage **dérive de l'URL** (deep-link), jamais d'un état local.

**Norme visuelle (v1.8)** — un rail est un **instrument de contrôle temporel**, pas du contenu :
il porte la surface instrument (`sr01-strip` — laque sombre, liseré cyan, `rounded-2xl`) qui le
distingue au premier regard des cartes de contenu de la page. Un panneau d'**agrégats** (ex.
`PeriodRail`) n'est pas un instrument de navigation et ne porte pas ce chrome. Corollaire
d'honnêteté : un contrôle du rail qui ne pilote rien sur la page (filtre de scope ignoré,
baseline incalculable) est **masqué ou désactivé-avec-raison**, jamais rendu actif.

## 6. Compositions autorisées

- `AGIR` : **As-of** (lire l'état à T, via `TE-01`) **+ Live** (agir maintenant) — implémentée
  par `components/agir/agir-rail.tsx` (`?asof` URL, mode affiché, mutations gelées à T ; rendu
  sur curation, automations, replay-shadow).
- `Console` : **XT-01** (trace de l'exécution de test) **+ Live**.

## 7. Garanties de reproductibilité & écarts

- **S1** — reproductible (immuable, hash-chaîné). Base de `TE-01` / `OT-01` / `AT-01`.
- **S2 / XT-01** — `XT-01` permet de **rejouer ou diagnostiquer** une exécution ; il **ne garantit pas toujours une sortie strictement identique** si le runtime modèle n'est pas déterministe (API, non-déterminisme matériel). On capture tout le nécessaire ; la repro bit-à-bit n'est pas promise.
- **S3** — reproductible **si** les événements métier sont append-only et non réécrits.
- **S4** — ne garantit la reproductibilité que **sur la période de rétention brute** ; au-delà, les vues peuvent dépendre d'**agrégats** (downsampling).
- **AT-01** — ne doit **pas** afficher de *signaux* (domaine de Surveiller) → feed d'activité uniquement + lien vers Surveiller.
- **SR-01** — ne rejoue pas une exécution. Il permet de **naviguer dans les signaux, comparer des périodes et contextualiser des anomalies**. Le replay d'exécution appartient à AGIR via `XT-01`.

## 8. Séparation des responsabilités

| Domaine | Rôle temporel |
|---------|---------------|
| **SURVEILLER** | scrubber de **signaux** (Live · Historique · Baseline) |
| **PROUVER** | **état opposable à T** (as-of) |
| **AGIR** | **replay d'exécution** |
| **AGENT** | **activité & historique opérationnel** |

## 9. Badge d'opposabilité (TE-01 / État à date)

Le badge est **dynamique** : calculé **à l'affichage** à partir du résultat de la vérification — jamais stocké, jamais cosmétique.

| Badge | Condition | Implication |
|-------|-----------|-------------|
| **Scellé · opposable** | chaîne de hash vérifiée **ET** sceau tiers (Hica) vérifié | état pleinement opposable |
| **Scellé (non qualifié)** | chaîne vérifiée **ET** sceau tiers vérifié, mais TSA **non qualifié** eIDAS | opposable techniquement ; qualification juridique du sceau non établie *(état exposé par le code depuis Hica, documenté v1.5)* |
| **Intégrité partielle** | chaîne valide **mais** sceau absent / non vérifiable | fiable en interne ; opposabilité tierce non garantie |
| **Non scellé** | échec d'intégrité (chaîne rompue) | état **non opposable** — à investiguer |
| *(transitoire)* **Vérification en cours** | `verify(chain)` non terminé | aucun statut d'opposabilité affiché tant que la vérif n'a pas abouti |

Mention obligatoire sous le badge : « *Statut attribué uniquement après vérification réussie.* »

> La numérotation `1 · 2 · 3 · A · D` n'est **pas** requise sur l'écran opérationnel (lecture en scan) ; elle est **réservée à l'export Evidence Pack** (artefact légal, lecture séquentielle type affidavit).

> **Règle de production** : ne pas régénérer une page validée pour ce genre d'évolution — encoder l'invariant ici. Une régénération risque de réintroduire des régressions (visuelles, textuelles ou de navigation).

## 10. Inventaire page-par-page (v1.9)

Verdict temporel de CHAQUE route (l'unité v1.5 était le rail ; celle-ci est la page). « — »
signifie : pas de besoin temporel prouvé, pas de rail — en mettre un serait du chrome.

| Route | Affordance temporelle | Verdict |
|-------|----------------------|---------|
| `surveiller/vue-ensemble` · `securite-privacy` · `conformite` | SR-01 command bar, contenu as-of/scope | Implémenté |
| `surveiller/qualite-ia` | SR-01 command bar, requêtes as-of/scope réelles (composant `observability-dashboard.tsx` — piège de nom, note v1.10) | Implémenté (v1.8, constaté v1.10) — vue éval = lentille ER-01 |
| `surveiller/amelioration` | SR-01 command bar `scopeFilter=false`, posture minée bornée à T (scores/bundles/runs) | Implémenté (v1.10) — fraîcheur corpus vive, dit tel quel |
| `surveiller/observabilite` | aucune | — états de processus vivants (health/readiness/budget/tail-sampling), aucun substrat S4 : pas de rail (v1.10) |
| `surveiller/fiabilite-cout` | PeriodRail (agrégats de période) | Voulu tel quel — agrégats, pas un scrubber |
| `prouver/audit-logs` | AU-01 fenêtre réelle + saut à date, instrument, en tête | Implémenté (v1.9) |
| `prouver/evidence-store` | SR-01 command bar + payload as-of réel, création gelée à T | Implémenté (v1.9) |
| `prouver/etat-a-date` | TE-01 reconstruction as-of + badge d'opposabilité | Implémenté |
| `agir/automations` · `curation-eval-set` · `replay-shadow` | agir-rail (As-of + Live, mutations gelées à T) | Implémenté |
| `agir/incidents-playbooks` | aucune | **À évaluer** — mêmes mutations gelables que ses sœurs AGIR ; l'agir-rail devrait s'y étendre |
| `agir/release-control` | aucune | — release = acte au présent ; l'historique est au ledger (Journal d'audit) |
| `agents/[id]/synthese` | AT-01 feed (Live · Période · Voir à date réel, `?asof=`) | Implémenté (v1.11) — bannière scopée |
| `agents/[id]/evaluations` | ER-01 run rail + SR-01 standalone | Implémenté |
| `agents/[id]/historique` (+ `[sessionId]`) | CT-01 timeline + filtres URL (`?turn_agent=`, `?routed=1`), conversations réelles en tête | Implémenté (v1.11) — fixture estampillé dessous |
| `agents/[id]/console` | XT-01 waterfall live (SSE) | Implémenté |
| `agents/[id]/configurations` · `connaissances` · `garde-fous` · `prompts` · `metier` | amorces OT-01 (versions, overlay, renvois) | Partiel — promotion = C1 par-objet consultable à T |
| `a-traiter` · `a-faire` | WF-01 timeline de transitions dans les drawers | Implémenté — un scrubber de file n'a pas de sens (SLA = présent) |
| `configurer/parametres` | AgirRail As-of + Live (`?asof=`), overrides refoldés du ledger à T, claim scopé | Implémenté — overrides (v1.9.1) ; socle git/policy à T : chantier |
| `configurer/modeles` · `garde-fous` · `politiques` | historique par mtimes / overlay | Partiel OT-01 — même chemin de fold que Paramètres |
| `configurer/sources-memoire` | VersionsBlock + renvois TE-01 (`?sources=`) | Partiel OT-01 — le renvoi est voulu (preuve → PROUVER) |
| `configurer/connecteurs` · `integrations` · `signal-catalog` | aucune | — catalogues descriptifs ; leurs mutations gouvernées sont au ledger |
| `admin/*` | aucune | — gestion d'accès, pas de navigation temporelle ; les actes sont au ledger |
| `flotte` (`agents`) | états live + liens | — porte d'entrée ; le temporel vit sur les pages d'agent |
| `comprendre` · `produit*` · `espaces` · `recouvrement` · `eval` · `login` · `select-space` · `settings` | aucune | — pages publiques / démo / utilitaires |
