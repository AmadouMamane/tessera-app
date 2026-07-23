# Cockpit clarity — run status

## Scope

Humanise every cockpit page without changing data contracts, identifiers used as evidence, or
uncertainty. The work covers first-reading copy, dense tables, filters, actions, empty states and
shared spacing. Technical identifiers remain available when they are themselves the audited fact;
they no longer carry the explanation alone.

## Live audit — 2026-07-22

- Reference tree: `main` at `b32951c1`, frontend `:3097`, backend `:8099`.
- `/fr/agents`: the first summary exposes `Conversations (org, dédupliqué)`, `Somme naïve par
  agent`, `Dédoublonnées`; the page subtitle adds `eval-gate`, `run de référence` and `totaux
  org`. These are internal aggregation and delivery terms, not operator language.
- `/fr/surveiller/qualite-ia`: the same reconciliation appears in the per-agent table. Live DOM
  before correction: `Somme naïve 430 · 0 dédoublonnées · 0 conversations partagées`, then
  `37` transfers attested and `0` conversations found under two agents. The numbers are retained;
  only their explanation changes.
- On the same page, the SLO ribbon ends at y=249 and the temporal controls start at y=275: a
  26 px visual interruption. The source confirms a 20 px wrapper margin whose only purpose is to
  clear a 16 px upward background fill. The overview page repeats the pattern with 24 px / 20 px.
- The fleet page itself is already compact (summary ends at y=204; controls begin at y=216).
  Its spacing is not reduced.
- Representative live pages were then inspected across `À traiter`, `À faire`, `Surveiller`,
  `Agir`, `Prouver`, `Configurer` and `Admin`. The heaviest remaining first-reading debt is in the
  inbox/task queues, evidence centre, state-at-date view, signal catalogue and shared role labels.
- Preview review on `:3098` confirmed the compact alert-to-rail transition, the rewritten fleet
  reconciliation, the evidence-centre hierarchy, the signal catalogue and both work queues. A
  second pass on `/fr/a-faire` found raw English evaluation titles in the table; the backend now
  gives every case currently present in the real queue a human FR/DE/EN display title while its
  case id remains visible as the evidence reference.
- Final live pass after restarting the preview confirmed the queue vocabulary in all three
  languages: the Livret A case is humanised in French and German, the encoded-instruction case is
  humanised in English, and self-assignment renders as `Moi`, `Me` and `Ich` without altering the
  stored assignee.
- A final overview DOM sweep removed the remaining first-reading delivery shorthand: release
  gates, burn rate, RAG/Privacy impact labels, roadmap headings, live probes and release-state
  columns now use operator language in FR/DE/EN. Route slugs and exact signal identifiers remain
  unchanged because they are contracts or evidence.
- System profile and raw audit rows intentionally retain exact product names, versions, rule IDs
  and event fields: those values are evidence, not interface jargon.

## Ratchets

- `cockpit-clarity.test.ts`: rejects the opaque fleet vocabulary in FR/EN/DE, preserves all six
  reconciliation placeholders, and rejects internal project terms in French page introductions.
- The same test rejects alert margins above the compact spacing scale and sticky background fills
  deeper than 8 px. Both rules include an explicit mutation reproducing the former code.
- Page-family ratchets now cover the primary incident, curation, release-control and automation
  vocabulary. Each family has a mutation proving that a removed internal term makes the test red.
- The same ratchet now covers evidence objects, work queues, signal names, shared scope wording,
  authority labels, date controls and overview delivery shorthand. It contains 51 checks,
  including explicit mutations for every protected family.

## Progress

- [x] Fresh branch `codex/cockpit-clarity` from `origin/main`.
- [x] Sole-writer claim acquired (`e911d673-305e-4b5f-a47d-61e9cc643c63`).
- [x] Source and live-browser inventory completed on representative pages in every sidebar family.
- [x] Slice 1 — fleet language, page introductions, shared alert/rail density.
- [x] Incidents — coordination, deadlines, response plans, actions and backend catalogue rewritten.
- [x] Evaluation set — review workflow, coverage gaps, approval and readiness language rewritten.
- [x] Release control — human first reading plus exact raw diagnostic in an explicit detail panel.
- [x] Automatic rules — rule names, triggers, actions, states and governance language rewritten.
- [x] Slice 2 — inbox/task queues, proof surfaces, signal catalogue and shared role labels.
- [x] Real queue titles, categories, sources and self-assignment localised in FR/DE/EN without
  mutating the imported evaluation evidence.
- [x] Slice 3 — `make gate-twice`, final preview restart and FR/DE/EN spot-check.

## Targeted checks already green

- Frontend targeted suite: 73 tests (51 clarity ratchets, 17 fleet reconciliations, 5 launch
  controls).
- Backend targeted suite: 93 tests across queues, signal catalogue, state-at-date, incidents,
  evaluation-set review, automatic rules, lifecycle and launch decisions.
- Queue-specific suite after the live finding: 28 tests.
- Frontend `tsc --noEmit` and targeted Biome checks are green.
- Full `make gate-twice` is green twice on the same tree (`a751c935482f`): 503 frontend tests and
  2,578 non-integration Python tests passed on each run, with Ruff, formatting, mypy, TypeScript
  and Biome green.

## Known limits and owed follow-up

- `/prouver/etat-a-date` is intentionally unavailable to the seeded administrator session used by
  the browser (`Accès opérateur requis`); its payload and component remain covered by targeted
  backend and frontend tests.
- Preserve specialised terms inside evidence/source panels when they are the fact being audited;
  introduce or explain them instead of silently weakening their meaning.

## Correctif total de flotte — 2026-07-23

- Finding live : `Avant correction`, `doublons retirés` et `total non confirmé` signalaient une
  incertitude sans expliquer son origine au visiteur.
- Correction : la première ligne décrit désormais le calcul (addition des volumes par agent,
  conversations retrouvées chez plusieurs agents, retraits du total). La seconde explique le
  mécanisme concret : une conversation transférée peut apparaître chez l'agent de départ et chez
  l'agent d'arrivée tant que les deux passages ne sont pas reliés.
- Les six valeurs de réconciliation et leurs contrats restent inchangés.

## Correctif racine des faux transferts — 2026-07-23

- Branche fraîche `codex/handoff-initial-route` depuis `origin/main=43edbba3`, claim
  `5510f279-ed9f-498f-8821-3c66278330bc`.
- Diagnostic live avant correction : 37 événements bruts `support-client → onboarding` dans
  37 conversations. La jointure sur le transcript en retrouve 35 uniquement sous `onboarding`,
  2 absentes et aucune sous deux agents.
- Cause : `route_turn(None, …)` substituait le défaut technique `support-client`, puis appelait
  « handoff » la première orientation vers `onboarding`. Support n'avait jamais traité le
  parcours.
- Émission corrigée : une conversation neuve rend `initial-><agent>` ou
  `intent-><agent> (initial route)`, avec `handoff=false` et sans événement
  `tessera.agent.handoff`. Un vrai handoff exige un agent courant persistant.
- Lecture historique corrigée sans réécrire le journal append-only : le compteur flotte exige
  un tour réel de l'agent source antérieur à l'événement et le tour cible exact, réel et
  persistant. Même règle en mode Postgres et dans l'échappatoire fichier.
- Preview `:8098` après correction : `handoff_events=0`, `handoff_conversations=0`,
  `handoff_conversations_seen_shared=0`; les compteurs entrants/sortants des cartes sont tous
  à zéro. Les 37 entrées brutes restent consultables dans le journal comme preuve historique.
- Tests ciblés : 20 verts, dont mutations « premier message directement Onboarding »,
  « cible seule rejetée » et « source antérieure + cible exacte conservées ».
- Gate complet : `make gate-twice` vert deux fois sur le même arbre
  `b729bda53c4f` ; chaque passage a validé 2 582 tests Python hors intégration et 503
  tests frontend, avec Ruff, formatage, mypy, TypeScript et Biome verts.

## Correctif de formulation à zéro — 2026-07-23

- Finding live : la phrase « 0 sont retrouvées […] ; 0 sont retirées » exposait correctement
  les valeurs, mais produisait une lecture mécanique et peu naturelle.
- Correction : lorsque aucune conversation n'apparaît chez plusieurs agents et qu'aucun doublon
  n'est retiré, une variante dédiée explique que l'addition donne le total affiché et que ce
  total reste inchangé. Les valeurs non nulles conservent la formulation détaillée.
- La variante existe dans les catalogues FR/DE/EN. Un test de rendu et un ratchet trilingue
  protègent le cas zéro ; 70 tests frontend ciblés, TypeScript et Biome sont verts.
- `make gate-twice` est vert deux fois sur le même arbre `2586c873269b` : 2 582 tests
  Python hors intégration et 505 tests frontend par passage.

## Résumé de flotte piloté par l’état — 2026-07-23

- Le pied de table choisit désormais une phrase métier complète : aucun transfert constaté,
  transferts vérifiés et comptés une seule fois, ou rapprochement incomplet expliqué.
- En présence de transferts vérifiés, il nomme le nombre de conversations passées entre agents,
  explique leur présence dans l’activité des deux agents concernés et donne le total de la flotte.
- Le sous-titre générique « Données réelles observées […] » est supprimé du tableau de suivi ;
  les notes propres aux vues qualité, sécurité, conformité, fiabilité, observabilité et preuve
  restent affichées car elles expliquent leurs colonnes.
- Validation : 72 tests ciblés puis la suite frontend complète de 507 tests, TypeScript et
  Biome verts. `make gate-twice` n’a pas été exécuté, conformément à l’instruction utilisateur
  de le suspendre jusqu’à nouvel ordre.

## Correctif période du total de flotte — 2026-07-23

- Finding live avant correction sur le backend de référence `:8099` : `h24=430`, `d7=430`,
  `d30=430`. Le changement de période mettait à jour le store Zustand du rail, mais la table
  restait un composant serveur chargé par `loadFleet()` sans période ; la route
  `/observability/fleet` et ses requêtes SQL ne connaissaient elles-mêmes aucune fenêtre.
- Correction de bout en bout : le choix de période devient une navigation Next partageable,
  les pages SURVEILLER passent leurs paramètres au loader, la route traduit `h24/d7/d30` avec le
  seam déjà utilisé par la Synthèse, et un même intervalle borne les volumes par agent, les tours,
  le total dédupliqué et les transferts. `/agents`, qui n’a pas ce rail, conserve volontairement
  son contrat tout historique.
- Mesure sur le preview `:8098` après correction : `h24=0 conversation / 0 tour`,
  `d7=15 conversations / 17 tours`, `d30=430 conversations / 500 tours` ; l’appel sans période
  reste à `430 / 500`.
- Validation ciblée : 35 tests Python (scope, transferts, contrat HTTP), 4 tests frontend
  (navigation et loader), Ruff, formatage, mypy, TypeScript et Biome verts. Le navigateur
  d’automatisation n’avait
  pas la session opérateur du navigateur utilisateur et a honnêtement rendu « Accès opérateur
  requis » ; aucune tentative de contournement. `make gate-twice` non exécuté, conformément à
  l’instruction toujours active.

## Correctif commit du curseur temporel — 2026-07-23

- Branche fraîche `codex/cursor-drives-cockpit` depuis `origin/main=dac9c5a9`, claim sole-writer
  conservé (`5510f279-ed9f-498f-8821-3c66278330bc`).
- Diagnostic par l’historique : le câblage client as-of-T des commits `a012445d`, `356e90d3` et
  `de602f10` existe toujours. Les requêtes React Query changent bien avec `asOf`, mais la table
  de flotte est rendue côté serveur. Le curseur publiait `at` avec `history.replaceState`, sans
  navigation Next : les composants serveur continuaient donc à lire l’ancienne URL.
- Preuve rouge avant correction : à l’instant choisi au début de la fenêtre, l’API renvoyait
  `0` conversation, tandis que le DOM restait à `430`. Le coût, alimenté côté client, changeait
  déjà correctement.
- Correction : le glissé reste un aperçu local sans requête. Une fois l’instant stabilisé par le
  debounce, le rail effectue une seule navigation Next vers l’URL temporelle déjà publiée. Un
  simple `router.refresh()` a été testé et rejeté : il rechargeait encore l’ancien arbre routeur.
- Vérification live sur `:3098` : le même commit de curseur a fait passer le total de flotte de
  `430` à `0` et le coût de `0,02 €` à `0,00 €`, avec `lecture=history&at=…` dans l’URL.
- Validation ciblée : les deux E2E « aperçu sans commit » et « métriques client + flotte serveur à
  T » sont verts ; 2 tests unitaires du rail, TypeScript et Biome sont verts. `make gate-twice`
  reste volontairement non exécuté conformément à l’instruction utilisateur.
- Dette lifecycle observée à l’arrêt : `make dev-down PORT=3098` ignore `PORT` et a arrêté la
  référence `:3097/:8099` au lieu du preview. Les deux PID exacts du preview ont été terminés
  séparément et les six ports vérifiés libres. Rendre `dev-down` paramétrable est hors de ce lot.

## Correctif latence du curseur temporel — 2026-07-23

- Branche fraîche `codex/fast-temporal-cursor` depuis `origin/main=1aba7979`, claim sole-writer
  repris explicitement sous `c3f8dfe2-3594-45d3-ba6b-1dfb46649dc3`.
- Diagnostic chiffré : la correction de cohérence précédente déclenchait une navigation RSC de
  toute la page à chaque instant stabilisé. Les lectures observées prenaient de `3,9 s` à `11 s`.
  Sous la rafale des requêtes historiques, la flotte seule arrivait après `7,295 s`.
- Correction : la table de suivi de la flotte est désormais un îlot client hydraté par le payload
  serveur initial. Un commit de curseur ne relit que `/observability/fleet` ; l’URL partageable
  continue d’être publiée, sans navigation RSC de toute la page. Les autres cartes conservent leur
  valeur précédente et ne relisent le même instant qu’après la réponse flotte.
- Mesure sur le preview stabilisé `:3098` : la lecture flotte à T répond en `474 ms`, puis les
  autres cartes se mettent à jour sans page blanche. Le test impose un changement visible en
  moins de `2,5 s` et vérifie qu’une seule requête flotte temporelle est émise.
- Matrice vérifiée contre l’agrégat backend : `Maintenant` avec la fenêtre `d7`, `À un instant`
  avec le même T que le deep-link, `Historique` au début de `d30`, puis retour à `Maintenant`.
  Les totaux DOM égalent l’oracle backend dans les quatre états ; le scénario historique conserve
  aussi l’oracle coût.
- Validation ciblée : 3 E2E de lecture temporelle verts, dont le cycle
  live → historique → live ; 33 tests unitaires ciblés verts ; TypeScript, Biome et
  `git diff --check` verts. `make gate-twice` reste volontairement non exécuté conformément à
  l’instruction utilisateur.
- Dette distincte : le premier chargement à froid de Vue d’ensemble lance encore un fan-out de
  lectures non temporelles. Il ne bloque plus le changement de curseur une fois la page stabilisée,
  mais mérite un lot dédié de regroupement backend/BFF plutôt qu’un nouveau délai frontend.

## Densification verticale de Vue d’ensemble — 2026-07-23

- Branche fraîche `codex/compact-overview` depuis `origin/main=87899211`, claim sole-writer
  `166823e1-f82f-4d79-a335-3aad48eb10e9`.
- Diagnostic DOM avant correction sur le preview `:3098` : les actions occupaient seules une
  ligne de 36 px ; le bandeau commençait à `y=166`, le rail à `y=264` et mesurait 324 px, puis
  « Vue par agent » commençait à `y=612`. Les espaces venaient de l’addition du `gap-4`, du
  `mb-1.5` des actions, du `mb-3` du bandeau et des marges internes du rail.
- Correction : sur les grands écrans du cockpit, le bandeau et les actions de preuve partagent
  la même bande d’ouverture ; sur un écran standard à 1440 px ils restent empilés pour préserver
  la largeur de la jauge. Après revue live, toutes les surfaces sœurs adoptent une trame exacte
  de 10 × 10 px : premier niveau, KPI, deux colonnes, cartes empilées et triptyque analytique.
  Le fond sticky reste à 4 px et le rail réduit ses paddings, sa marge avant l’axe, l’espacement
  de la légende, le détail sélectionné et le lien PROUVER.
- Mesure après correction, bandeau chargé : bande d’ouverture `y=108..174`, rail
  `y=184..452/456` selon le rafraîchissement asynchrone, « Vue par agent » à `y=466`. Le premier
  tableau remonte donc de 146 px. Le curseur tient exactement dans ses 52 px
  (`clientHeight=scrollHeight=52`) : aucun chevauchement avec la légende.
- Mesure DOM de la trame finale : quatre écarts verticaux de premier niveau à 10 px, cinq écarts
  horizontaux KPI à 10 px, séparation des colonnes à 10 px et cinq écarts verticaux des cartes
  de gauche à 10 px.
- Un ratchet rejette désormais le retour d’un autre rythme entre surfaces sœurs, du padding
  vertical de commande supérieur à `1.5` ou de la marge `mt-6` devant l’axe. Validation ciblée :
  55 tests de clarté verts, Biome vert sur les fichiers frontend touchés, TypeScript et
  `git diff --check` verts.
- `make gate-twice` n’a pas été exécuté, conformément à l’instruction utilisateur toujours active.

## Trame 10 × 10 étendue à tout le cockpit — 2026-07-23

- La trame validée sur Vue d’ensemble devient un contrat du shell : ses enfants directs sont
  séparés de 10 px et toute collection flex/grid de cartes partagées reçoit 10 px dans les deux
  axes. Les espacements internes des cartes restent propres à chaque composant.
- Les anciens tableaux qui n’utilisaient pas la carte partagée marquent désormais explicitement
  leurs zones, panneaux et tuiles comme surfaces. Cela couvre notamment incidents, rejeu,
  automatismes, jeux d’évaluation, preuves, conformité, observabilité, politiques, accès,
  intégrations, système, sources, files et paramètres.
- Les marges locales qui doublaient le rythme du shell ont été retirées des pages Surveiller,
  Agir, Prouver, Configurer et Admin. Finding live supplémentaire : le sélecteur des deux vues
  Qualité conservait `mb-4`, soit 26 px réels avec le shell ; après correction ses deux écarts
  verticaux et son écart horizontal sont tous à 10 px.
- Mesures DOM sur le preview `:3098` :
  - Sécurité : bandeau → dashboard 10 px ; six zones, KPI, panneaux et rail à 10 × 10 px ;
  - Qualité : trois écarts de premier niveau à 10 px et portes de vue séparées de 10 px ;
  - Rejeu : racine, deux colonnes, huit KPI, zones, panneaux et rail à 10 × 10 px ;
  - Flotte : racine et grille de six agents à 10 × 10 px ;
  - Modèles : filtre → catalogue 10 px, huit KPI 10 × 10 px, tableau → détail 10 px ;
  - Incidents : quatre zones, huit KPI, colonnes et panneaux à 10 × 10 px ;
  - Conformité : bandeau → dashboard 10 px, zones, sept KPI, panneaux et rail à 10 × 10 px.
- Le ratchet passe de 55 à 61 tests et protège le shell, la carte partagée, les composants
  historiques, les racines de page et le sélecteur Qualité. TypeScript et `git diff --check`
  sont verts.
- Le `biome check` large reste rouge sur 51 fichiers historiques pour une dérive de formatage
  globale (principalement indentation espaces contre tabs) qui existait avant les changements de
  classes ; aucune réécriture massive hors lot n’a été faite. `make gate-twice` reste suspendu
  conformément à l’instruction utilisateur.
