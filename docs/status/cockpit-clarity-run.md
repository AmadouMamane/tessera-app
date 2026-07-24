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

## Carte de connexion et menu de compte — 2026-07-23

- Branche fraîche `codex/account-menu` depuis `origin/main`, claim sole-writer repris sous
  `c1ee5184-a3e0-45d9-b3e2-85246c358e90`.
- Diagnostic live avant correction : la barre latérale mesurait 218 px, tandis que le menu
  principal mesurait 240 px et dépassait donc son bord droit de 22 px. La carte utilisait un
  petit bouton en pilule et mêlait directement compte, langues et thèmes dans un seul panneau.
- Correction : la barre ouverte mesure 252 px ; la carte de connexion occupe toute sa largeur
  intérieure avec avatar, rôle réel et nature du compte. Le menu principal reprend exactement
  la largeur de son déclencheur. Les détails du compte, la personnalisation et l’aide vivent
  dans des sous-panneaux latéraux ; un seul sous-panneau peut rester ouvert à la fois.
- Les entrées ne simulent aucun produit absent : le rôle affiché provient de la session et chaque
  lien mène à une route existante (`/login`, `/admin/profil-systeme`,
  `/configurer/parametres`, `/comprendre`, `/comprendre/en-detail`, `/settings`). Les langues et
  thèmes existants sont conservés dans Personnalisation. Tous les libellés sont catalogués en
  FR/DE/EN.
- Mesure après correction sur le preview `:3098` : barre 252 px, carte et menu 227 px, marges
  gauche/droite de 12/13 px ; le menu reste donc entièrement contenu. Le panneau Aide commence
  immédiatement à droite du menu principal et, après l’animation, remplace bien le panneau de
  compte au lieu de se superposer à lui.
- Validation : 18 tests de contrat du chrome verts, dont une mutation qui réintroduit la largeur
  indépendante de 15 rem et devient rouge ; TypeScript, Biome ciblé et `git diff --check` verts.
  `make gate-twice` reste volontairement non exécuté conformément à l’instruction utilisateur.
- Correctif de revue sur la surface de sélection : l’identité visible dans la carte n’est plus
  répétée mot pour mot en tête du menu. Cette ligne devient « Comptes » et ouvre le même
  sous-panneau, où le compte actuel reste affiché une seule fois. Le petit identifiant technique
  `admin` est supprimé. Sur les surfaces de sélection, le déclencheur devient un avatar seul de
  40 px et le menu s’ouvre dessous, aligné à droite ; le cockpit conserve sa carte complète avec
  rôle et type de compte. Un ratchet dédié protège cette distinction de contexte et rejette le
  retour du nom ou de l’avatar dans l’entrée « Comptes ».
- Correctif d’authentification de `select-space` : le badge Démonstration qualifie désormais
  uniquement l’environnement et ne remplace plus l’accès au compte. Comme `/espaces`, la page
  utilise le contexte `optional` : hors session, le header affiche « Connexion » ; en session,
  il affiche le même avatar circulaire seul. Le cockpit reste `gated` et conserve sa carte
  d’identité complète. Les deux états de `select-space` ont été vérifiés dans le DOM live sur
  `:3098` ; les 18 tests de chrome et TypeScript restent verts.
- Le CTA « Entrer dans le cockpit » ne connecte plus silencieusement l’anonyme au compte
  administrateur seedé. Il est désormais un lien normal vers `/surveiller/vue-ensemble` :
  le garde RBAC laisse entrer une session autorisée sans la modifier et redirige l’anonyme vers
  `/login`. Le parcours live `select-space → login` et l’absence de session créée ont été
  vérifiés ; l’E2E de non-régression ciblé est vert.
- Le garde conserve maintenant la destination demandée dans
  `next=/surveiller/vue-ensemble`. Après une authentification réussie, le formulaire revient
  directement dans le cockpit au lieu de repasser par la racine puis `select-space`. La valeur
  `next` est validée comme chemin interne non localisé : URL externes, chemins protocol-relative,
  antislash, boucle `/login` et préfixe de langue sont refusés. Validation : 11 tests unitaires
  du validateur, 18 tests de chrome, TypeScript et l’E2E complet
  `select-space → login → cockpit` verts ; URL live confirmée sur `:3098`.
- Correctif Espaces / Recouvrement : `/espaces` reste consultable hors session et ne reçoit plus
  d’identifiants seedés côté client. Ses cartes sont des liens ordinaires ; seule la route
  `/recouvrement` porte la décision d’accès. Pour un anonyme, elle redirige vers
  `/login?next=/recouvrement`, puis une connexion collections réussie revient directement dans
  la console. Le parcours E2E public → login → recouvrement est vert et la page Espaces a été
  vérifiée en DOM live hors session.
- Refonte visuelle de login : même fond nuit, vague, marque et tokens que le launcher ; composition
  éditoriale à gauche, illustration orbitale discrète, formulaire vitré à droite, champs plus
  lisibles, CTA champagne et identifiants de démonstration structurés. Le bloc d’identité
  connecté qui flottait sous le formulaire a été retiré et « Retour à la démo » ramène maintenant
  vers `/select-space`. Revue visuelle live effectuée sur `:3098`.
- Incident live après connexion : Next compilait bien `/[locale]/recouvrement`, mais le chunk
  attendu `app/[locale]/recouvrement/page.js` restait absent et répondait 404. La cause n’était
  pas le routage login : un lancement Playwright avec la mauvaise variable d’environnement avait
  démarré un second serveur Next.js dans le même checkout ; les deux processus écrivaient dans
  le même `.next` et avaient corrompu le cache. Le preview `:3098/:8098` a été arrêté avec ses
  ports explicites, le cache écarté dans `/tmp/tessera-next-recovery.n0c2WT/.next-corrupt`, puis
  un seul preview a été relancé. Après réparation, le chunk répond 200 (5 594 124 octets), la
  route anonyme redirige bien vers `/login?next=/recouvrement` et l’E2E public → login →
  recouvrement repasse en 1,6 s. Aucun correctif applicatif supplémentaire n’était nécessaire.
- Amélioration premium de login après revue live : la composition passe de 1 180 à 1 540 px
  maximum afin de ne plus flotter au milieu des grands écrans, l’illustration d’accès gagne en
  présence et trois repères lisibles explicitent identité, droits et traçabilité. Le panneau
  guide désormais le visiteur : chaque profil démo est une vraie option de rôle qui remplit
  identifiant et mot de passe au clic sans soumettre le formulaire ; la saisie manuelle reste
  possible et le mot de passe peut être affiché ou masqué. Les libellés sont catalogués en
  FR/EN/DE. À 1 440 × 900, le panneau reste entièrement visible, la page mesure 1 440 px de
  large sans débordement horizontal et les deux parcours public → login → destination passent
  en 5,2 s. Biome ciblé, TypeScript et `git diff --check` sont verts ; `make gate-twice` reste
  suspendu sur instruction.
- Correctif de revue : la largeur maximale de la composition ne contraint plus le header. Sur
  le viewport live de 3 087 px, la marque retrouve une marge gauche de 40 px et « Retour à la
  démo » une marge droite de 40 px. La plaque qui entourait l’illustration a été supprimée :
  son conteneur calculé n’a plus ni fond, ni bordure, ni arrondi, ni ombre ; les orbites et
  pictogrammes flottent directement sur le fond. Le panneau de connexion reste donc l’unique
  carte dominante. TypeScript, Biome ciblé et diff-check restent verts.
- Essai visuel option 1 : la carte flottante de connexion devient un panneau latéral intégré,
  bord à bord sous le header. Sur le viewport live de 1 770 × 1 354 px, il commence exactement
  à `y=82` après le header de 82 px, mesure 640 × 1 272 px, touche le bord droit à 0 px et
  n’a ni arrondi ni ombre calculés. Une ligne lumineuse très discrète suffit à séparer le fond
  éditorial de la zone d’accès. Le header reste en pleine largeur et aucun overflow horizontal
  n’est présent. Biome ciblé, TypeScript et diff-check sont verts ; twice-green reste suspendu.
- Verdict live : option 1 rejetée, panneau latéral jugé trop massif et trop « back-office ».
  Variante suivante en preview : aucune grande carte ni fond de panneau ; le formulaire est
  posé directement sur le fond et séparé du contenu par une ligne verticale en dégradé. À
  1 770 × 1 354, la zone de formulaire est transparente, sans background-image, radius ou
  shadow ; le formulaire mesure 456 × 469 px et se termine à `y=1001`, sans overflow. Les trois
  profils démo passent d’une pile de grandes barres à trois tuiles compactes sur une ligne,
  tout en gardant identifiant et mot de passe visibles et le même nom accessible. Biome ciblé,
  TypeScript, diff-check et les deux E2E destinationnels sont verts en 6,0 s.
- Essai « portail orbital » intégré : le séparateur et l’illustration autonome disparaissent.
  Une seule orbite traverse maintenant l’ensemble du main ; le logo Tessera sert de charnière
  entre l’introduction et le formulaire, prolongé par un trait vers la zone d’accès. Les profils
  ne sont plus des tuiles : trois médaillons reliés sur l’orbite portent rôle et credentials,
  puis remplissent les champs au clic. À 1 770 px, le logo occupe `x=1024..1116`, avec 37 px
  après la zone éditoriale et 19 px avant le formulaire. La première mesure à 1 440 px révélait
  un chevauchement de 19 px ; l’orbite passe à 58 % sous 1 536 px et recrée 39 px de respiration.
  Le formulaire se termine à `y=769` dans 900 px, sans overflow. DOM accessible intact, Biome,
  TypeScript, diff-check et les deux E2E destinationnels verts en 5,9 s.
- Verdict live : portail orbital rejeté. Malgré la géométrie du logo corrigée, les ellipses
  décoratives traversaient visuellement le formulaire et brouillaient la hiérarchie. L’essai a
  été entièrement retiré, pas masqué : aucun `[data-login-orbit]` ne subsiste. Retour à la
  dernière version acceptée, avec illustration confinée à gauche, séparateur discret et
  formulaire sans grande carte. Mesure live : l’illustration se termine à `x=835`, la zone
  formulaire commence à `x=1095`, soit 260 px sans aucun trait orbital partagé ; aucun overflow.
  Biome, TypeScript, diff-check et les deux E2E destinationnels restent verts en 5,5 s.
- Ajustement typographique live : « Connexion opérateur » reprend exactement la typographie du
  titre de `select-space` — 30 px sur tous les écrans, semibold, interlignage 1,1 et approche
  -0,02 em. Le titre reste le premier niveau sans écraser le formulaire ni les autres repères.

## Header — dock de contrôle — 2026-07-23

- Branche `codex/header-control-dock`, claim sole-writer
  `3c85bb68-a332-471b-9f70-f114ab2026c0`, coupée du `main` local à `89d89587`.
- La grande barre de recherche centrale disparaît. La ligne principale devient une composition
  à deux zones — titre à gauche, dock global à droite — et conserve sa hauteur normative de
  88 px. Le compte reste exclusivement dans le panneau gauche du cockpit.
- Le dock regroupe la recherche compacte `⌘K`, le sélecteur d’espaces, la posture système, les
  notifications et l’aide dans une seule capsule de 44 px. Toutes les icônes principales ont
  une boîte cliquable de 36 px et un glyphe de 18 px.
- Le sélecteur d’espaces devient un panneau de 336 px avec deux destinations décrites et
  inchangées (`/espaces`, `/produit`). L’aide devient un lien direct vers `/comprendre` avec
  tooltip partagé, sans grand menu à une seule ligne.
- La posture système passe à 384 px. Environnement, modèle et résidence sont alignés ; le verdict
  d’intégrité occupe une ligne pleine largeur et conserve `LedgerIntegrityText`, donc exactement
  les mêmes données et la même sémantique que le footer.
- La cloche conserve les faits réels de `/observability/chrome` et leurs liens. Le badge visuel
  devient un point d’attention, car aucun store de lecture ne permet de revendiquer un nombre
  de notifications « non lues » ; le nom accessible conserve le nombre réel de faits à traiter.
  Les faits sont regroupés par leur destination stable (`/a-traiter`, `/a-faire`,
  `/surveiller/observabilite`, `/prouver/etat-a-date`), jamais par analyse du texte traduit.
- Les libellés backend de file ne disent plus « élément(s) » : ils nomment les validations et
  évaluations avec des formes singulier/pluriel naturelles en FR/DE/EN.
- Vérifications ciblées vertes : Biome sur huit fichiers frontend, `tsc --noEmit`,
  `header-components.test.ts` + `chrome-honesty.test.ts` (50 tests), Ruff check + format et
  `test_operator_items.py` (29 tests), `git diff --check`. `make gate-twice` reste suspendu sur
  instruction.
- Preview `:3098/:8098` sain ; compilation de `/fr/surveiller/vue-ensemble?period=d30` en HTTP
  200 sans erreur serveur. Le contrôleur de l’onglet intégré n’a pas pu rattacher un onglet
  après le redémarrage du preview ; la validation visuelle finale reste donc à faire par Amadou
  au rafraîchissement.
- Raffinement « quiet luxury » validé avant code : capsule à fond translucide sans ombre portée,
  contrôles sans bordure individuelle, raccourci `⌘K` purement typographique, glyphes Lucide
  principaux à 18 px et `strokeWidth=1.75`. Les panneaux Espaces, Actions et Posture perdent
  leurs boîtes internes colorées au profit de lignes plates et de séparateurs fins. Le libellé
  du statut devient neutre ; seule sa pastille porte encore la couleur du verdict. Les panneaux
  partagent désormais un fondu/déplacement de 150 ms.
- Passe minimaliste finale : la loupe devient seule visible et porte « Rechercher — ⌘K » dans
  le tooltip partagé ; le séparateur qui la suivait disparaît. Les icônes des espaces deviennent
  monochromes et leurs descriptions tiennent sur une ligne. La posture retire les icônes
  décoratives de ses trois lignes et passe en grille libellé / valeur. Entre 1 024 et 1 279 px,
  son déclencheur se réduit au point de verdict avec tooltip localisé ; à partir de 1 280 px,
  le libellé et le chevron réapparaissent.
- Correctif « moins de cartes » : Espaces, Posture système et Actions ne créent plus trois
  popovers flottants indépendants. Les trois déclencheurs pilotent un seul tiroir de contrôle
  de 384 px, attaché exactement sous la règle du header et aligné au bord droit du dock. Un clic
  sur une autre icône remplace le contenu dans ce même tiroir ; un second clic, `Échap`, un clic
  extérieur ou une navigation le referme. Le tiroir reprend le fond du header, sans ombre, sans
  bord supérieur et sans arrondi supérieur ; seuls les côtés, le bas et un léger arrondi
  inférieur le délimitent. Le contenu reste plat, séparé par des filets, sans carte imbriquée.
  Le statut système est désormais découpé en seam de données, déclencheur et contenu afin de
  conserver une seule lecture santé/intégrité pour les deux états du header.
- Validation du correctif : Biome ciblé, `tsc --noEmit`, `git diff --check`,
  `header-components.test.ts` et `chrome-honesty.test.ts` verts (50 tests). Le ratchet échoue si
  le tiroir reprend une ombre, un arrondi complet ou une bordure supérieure. Le preview
  `:3098/:8098` répond 200 et l’authentification jusqu’au cockpit est vérifiée dans le navigateur
  intégré ; son viewport de 672 px reste toutefois sous le breakpoint desktop du dock, donc la
  dernière appréciation visuelle du tiroir large est laissée au rafraîchissement d’Amadou.
  `make gate-twice` reste suspendu sur instruction.
- Correctif de revue « rectangle autour » : la capsule englobante du dock est supprimée. Les
  cinq contrôles reposent directement dans le header ; leurs zones cliquables et états de survol
  restent inchangés. Mesure DOM live à 1 440 × 900 : fond `rgba(0, 0, 0, 0)`, bordure `0px`,
  rayon `0px`, ombre `none`. Un ratchet interdit le retour de l’ancienne classe de capsule.
  Biome ciblé, TypeScript et les 50 tests header/chrome restent verts.
- Raffinement final après validation : les cinq commandes ont désormais la même boîte de
  36 × 36 px, y compris la posture système réduite à son pictogramme. L’état actif n’ajoute plus
  de fond rectangulaire : une ligne verte d’un pixel sur la règle du header suffit. Le tiroir ne
  dessine plus de carte complète ; seule une ligne verticale gauche guide le regard, sans rayon,
  ombre ni bordures supérieure, droite ou basse.
- Le centre d’actions ne répète plus deux phrases portant le même total. Chaque groupe affiche
  désormais son nom et son volume (`Validations — 57`, `Évaluations — 18` dans le monde du
  preview), puis une seule synthèse de délai. Les regroupements et les volumes reposent sur les
  identifiants et compteurs structurés du backend, jamais sur l’analyse du texte traduit.
- Diagnostic du contrat live : le compositeur produisait correctement `count`, mais
  `/api/observability/chrome` le supprimait. La cause était le `response_model` Pydantic
  `ChromeNotificationsItemsItem`, qui ne déclarait pas le champ — FastAPI filtre silencieusement
  les clés absentes du modèle. Le contrat est maintenant complet sur les quatre jambes :
  compositeur, modèle Python, schéma Zod et rendu. Après correction, le BFF sert bien les
  compteurs `57`, `57`, `18`, `18` pour les quatre lignes de file.
- Preuves ciblées : Ruff et format Python verts ; 74 tests backend verts, dont un test HTTP qui
  échoue si FastAPI retire à nouveau `count` ; Biome ciblé et TypeScript verts ; 50 tests
  header/chrome verts, dont la mutation qui relie le volume du groupe au compteur de retard.
  Le preview `:3098/:8098` est sain. Le rechargement automatisé du navigateur intégré a été
  refusé par sa politique d’URL locale ; aucun contournement n’a été tenté. La revue finale est
  disponible au rafraîchissement manuel. `make gate-twice` reste suspendu sur instruction.

## Aide contextuelle — pilote Vue d’ensemble — 2026-07-24

- Le bouton d’aide du header devient contextuel sur `/surveiller/vue-ensemble` : il ouvre
  `/comprendre/surveiller/vue-ensemble` et transporte la route complète d’origine dans un
  paramètre `from` validé. La page d’aide peut ainsi ramener le visiteur à la même lecture,
  avec sa période, son mode temporel, son instant et son filtre agent. Sur les pages qui ne
  disposent pas encore d’un guide, l’aide conserve son repli vers `/comprendre`.
- Le routage repose sur un registre explicite `route cockpit → guide` plutôt que sur une
  fabrication de chemin. Un ratchet vérifie que chaque guide déclaré existe réellement, que
  le retour n’accepte que la route opérationnelle autorisée et que les catalogues FR/EN/DE
  exposent exactement la même structure.
- Le pilote explique la page dans l’ordre où elle se lit et dans un registre humain :
  repérer, comprendre, décider ; bandeau d’objectif, rail de lecture, vue par agent, signaux
  essentiels, détails et actions. Il explicite aussi les modes Maintenant, Historique et
  État à date, la portée du filtre agent et les conventions d’honnêteté — un tiret n’est pas
  un zéro, un badge temps réel n’est pas réinterprété dans le passé et certains indicateurs
  restent globaux.
- La composition est éditoriale et linéaire, sans nouvelle pile de cartes. Les quatre sorties
  d’action pointent vers les routes réelles de qualité, incidents, contrôle de mise en ligne
  et preuve à date. Tous les textes visibles, métadonnées et libellés d’accessibilité sont
  catalogués dans le même lot en FR/EN/DE ; aucun nombre visible n’est écrit en dur dans le JSX.
- Vérifications ciblées vertes : Biome sur les dix fichiers frontend concernés,
  `tsc --noEmit`, puis 57 tests Vitest (`contextual-help`, header et honnêteté du chrome).
  Le ratchet numérique couvre aussi la nouvelle route et son composant. Le preview
  `:3098/:8098` est sain et les trois routes FR/EN/DE répondent HTTP 200 sans erreur de
  compilation. La politique d’URL locale du navigateur intégré interdit la lecture automatisée
  du preview ; aucun contournement n’a été tenté et la validation visuelle reste donc au
  rafraîchissement d’Amadou. `make gate-twice` reste suspendu sur instruction.
- Extension validée après revue : le guide reconstruit maintenant la lecture exacte transportée
  dans `from` — Maintenant, Historique ou À un instant ; fenêtre `h24`, `d7` ou `d30` ; flotte
  ou agent précis ; instant valide lorsqu’il existe. Les valeurs hors contrat retombent sur les
  défauts défendables au lieu d’être reprises comme du texte. Les libellés de période et de mode
  sont ceux du rail opérationnel, pas une seconde traduction.
- Une ligne éditoriale « Votre lecture » restitue ce contexte avant l’introduction. En bas du
  guide, une divulgation pleine largeur et fermée par défaut explique l’origine, le périmètre,
  les calculs, la fraîcheur et les limites. Elle détaille ensuite quatre calculs susceptibles
  de surprendre — total de flotte, qualité, contrôles et risques ouverts — puis propose un
  second niveau « Voir le contrat technique » pour les routes de lecture, le contrat temporel,
  les jambes qui restent actuelles et la validation FastAPI → Zod. Aucun nouveau panneau en
  carte n’est introduit.
- Le navigateur live a confirmé le contexte « toute la flotte · Historique · 30 jours » et
  l’instant localisé, le retour avec les mêmes paramètres, les deux divulgations accessibles et
  la composition sans débordement au viewport desktop. Biome ciblé et TypeScript sont verts ;
  les ratchets passent désormais 59 tests, dont les nouveaux cas de normalisation du contexte.
  `make gate-twice` reste suspendu sur instruction.
- Correctif de compréhension : « Votre lecture » devient « Contexte de départ ». Chaque mode
  possède désormais une phrase propre afin de ne plus faire croire que « Maintenant » dure une
  période : au présent, la phrase sépare l’état actuel de la fenêtre utilisée par certains
  indicateurs ; en Historique et À un instant, elle nomme la lecture choisie. Une seconde ligne
  dit explicitement que le même guide couvre Maintenant, Historique et À un instant.
- Découverte du guide : sur une route déclarée dans le registre, une indication discrète est
  attachée une seule fois au `?` du header. Elle explique que la page possède son guide et
  propose de l’ouvrir. Fermeture ou ouverture écrit un acquittement versionné et propre à la
  route dans le stockage local du navigateur ; les pages sans guide n’affichent rien. Le
  coachmark disparaît temporairement lorsqu’un tiroir global du header est ouvert, ne porte
  ni ombre, ni arrondi, ni boîte complète, et laisse ensuite le tooltip permanent
  « Comprendre cette page » comme unique repère.
- Preuve live : l’indication est apparue sous le `?` sur Vue d’ensemble en lecture Historique,
  avec le bon lien profond ; sa fermeture l’a retirée du DOM et un rechargement de la même URL
  l’a laissée absente. Le contexte du guide rend désormais « Contexte de départ », la lecture
  Historique, 30 jours, l’instant sélectionné et la mention des trois modes. Biome, TypeScript,
  diff-check et 60 tests ciblés sont verts. `make gate-twice` reste suspendu sur instruction.
- Simplification après revue opérateur : le bloc visible « Contexte de départ » est supprimé.
  Il n’expliquait pas la page et répétait un état que le visiteur venait de quitter. Le paramètre
  `from` reste conservé silencieusement afin que « Retour à la vue d’ensemble » restaure la
  lecture, la période, le périmètre et l’instant d’origine sans exposer cette plomberie dans le
  guide. Le parseur désormais orphelin et les clés devenues inutiles sont retirés. Le navigateur
  live confirme l’absence des trois phrases et un retour exact vers
  `Historique · 30 jours · instant sélectionné`; Biome, TypeScript, diff-check et 58 tests
  ciblés sont verts. `make gate-twice` reste suspendu sur instruction.

## Aide contextuelle — généralisation au cockpit — 2026-07-24

- Le registre couvre désormais les 29 destinations réellement exposées par la barre latérale,
  les 9 onglets du workspace agent et la page de paramètres personnels : 39 guides en comptant
  le pilote Vue d’ensemble. Les redirections techniques et les expériences métier hors cockpit
  restent volontairement hors programme.
- Vue d’ensemble conserve son guide éditorial sur mesure. Les 38 autres destinations passent
  par une route contrôlée `/comprendre/[...segments]` et un gabarit commun sans empilement de
  cartes : question utile, point de départ, parcours de lecture propre à la famille, décision
  possible et divulgation repliée sur la source et les limites. Chaque page porte un contenu
  propre en FR/EN/DE ; aucun texte visible n’est écrit dans le JSX.
- Les routes agent normalisent l’identifiant dans le guide
  (`/agents/<id>/prompts` → `/comprendre/agents/prompts`) tout en conservant silencieusement le
  `from` complet. Le retour restitue donc l’agent, l’onglet, les filtres et, pour Historique, la
  session détaillée. L’acquittement du coachmark est partagé entre agents pour un même onglet,
  afin de ne pas réenseigner la même affordance à chaque sélection.
- Les ratchets comparent désormais le registre aux feuilles réelles de `sidebar.tsx` et aux
  onglets réels de `agent-tabs.tsx`, refusent une destination sans guide, vérifient la parité
  structurelle des trois catalogues et soumettent le gabarit générique au cliquet anti-nombres
  visibles. Ce dernier a été vu rouge sur le dégradé écrit dans le JSX, puis corrigé en déplaçant
  la valeur structurelle hors rendu.
- Preuves : les 117 URL issues de `39 guides × 3 langues` répondent 200 sur le preview. La revue
  live du guide Sécurité confirme la composition sans débordement, la profondeur technique
  fermée par défaut et le retour exact vers `Sécurité & confidentialité · 30 jours`. Biome,
  TypeScript, diff-check, 63 tests frontend ciblés et 74 tests Python du périmètre stagé sont
  verts. `make gate-twice` reste suspendu sur instruction.

## Aide contextuelle — profondeur des pages et des onglets — 2026-07-24

- Diagnostic après revue opérateur : la première généralisation prouvait la couverture des
  routes mais pas leur profondeur éditoriale. Les 38 guides génériques partageaient trois
  paragraphes de lecture par famille et ne connaissaient aucun onglet interne. La critique est
  fondée : une route d’aide existait, mais elle n’expliquait pas la surface réellement ouverte.
- Les 12 tableaux de bord à onglets locaux utilisent désormais un seam commun
  `useUrlBackedView`. La vue par défaut conserve l’URL canonique ; une vue ciblée écrit
  `?vue=<clé>` en préservant période, agent et autres filtres. Qualité IA conserve son contrat
  existant : `vue` distingue Suivi continu et Évaluations, tandis que `tab` distingue les
  sous-vues. Le header transporte donc silencieusement la vue réelle dans `from`.
- Le gabarit d’aide comporte maintenant un atlas éditorial sans nouvelle pile de cartes. Il
  réutilise les libellés d’onglets des catalogues opérationnels, signale la vue d’origine,
  explique la question propre à chaque onglet et permet de l’ouvrir en conservant les filtres.
  Qualité IA documente ses 2 portes, les 6 sous-vues de suivi continu et les 3 sous-vues
  d’évaluation. Sécurité, conformité, fiabilité, amélioration, incidents, replay, curation,
  automations, preuves, politiques, sources et paramètres documentent chacun toutes leurs vues.
- Les trois catalogues contiennent exactement 97 explications de vues en FR, EN et DE. Le volet
  de données des guides génériques gagne une lecture structurée de l’origine, de la portée, de
  la fraîcheur et des limites, avec la règle explicite qu’une absence expliquée vaut mieux
  qu’une précision trompeuse.
- Nouveau ratchet : les constantes `TABS`, `SEC_TABS` et `VIEWS` des 12 composants sont comparées
  à l’atlas documenté ; chaque libellé réutilisé et chaque explication doivent exister dans les
  trois langues. Ajouter un onglet sans aide rend désormais le test rouge.
- Vérifications vertes : `tsc --noEmit`, Biome ciblé, `git diff --check` et 15 tests dédiés.
  `next build` compile l’application puis échoue pendant le prérendu sur le défaut préexistant
  `AppHeader/useSearchParams` sans frontière Suspense pour `/comprendre` et
  `/comprendre/en-detail` ; aucun fichier de ce chantier ne modifie `app-header.tsx`.
  Le preview `:3098/:8098` a été redémarré proprement après le build et ses deux healthchecks
  sont verts. Le navigateur intégré n’avait plus de session opérateur, puis sa politique d’URL
  locale a refusé le rechargement automatisé ; aucun contournement n’a été tenté. La revue
  visuelle reste donc au rafraîchissement manuel d’Amadou. `make gate-twice` reste suspendu sur
  instruction.
- Approfondissement après seconde revue : le volet « Comprendre comment ces données sont
  établies » reprend désormais toute la progression du pilote Vue d’ensemble. Après origine,
  portée, fraîcheur et limites, il présente trois situations concrètes propres à la famille de
  page, puis un second disclosure « Voir le contrat technique » détaillant lecture, portée,
  temps, effet des actions, validation et absences. Un footer « À retenir » conclut chaque guide
  avec son rôle et l’action défendable. Les exemples et contrats existent dans la même structure
  en FR/EN/DE ; TypeScript, Biome et les 15 ratchets ciblés restent verts.

## Polissage des guides et retour à l’accueil — 2026-07-24

- Branche `codex/contextual-help-polish` depuis le `main` local `e98061a2`, claim sole-writer
  conservé (`0850b3b1-9d31-4035-9105-fe2875f90b98`).
- Finding live avant correction : le premier texte du panneau commençait exactement sur sa
  bordure (`x=276` pour les deux), et le trait du parcours ne couvrait que `814,8 px` dans une
  section de `970 px`. Il apparaissait donc seulement après le premier cercle.
- Correction : le panneau d’ouverture reçoit un retrait horizontal de `20 px` ; le connecteur
  du parcours couvre désormais les `970 px` de la section, de bord à bord. Le logo Tessera du
  rail devient un lien localisé FR/EN/DE vers la page d’accueil, dans les états déployé et réduit.
- Preuve live sur `:3098` : bord du panneau `x=276`, début du texte `x=296`, trait
  `x=276 → 1246`, et activation du lien « Retour à l’accueil » confirmée vers `/fr`.
- Le ratchet numérique a révélé un `viewGroups.length > 0` antérieur dans le JSX du guide ;
  le littéral a été retiré sans élargir la liste blanche. Biome, TypeScript et 65 tests ciblés
  sont verts. `make gate-twice` reste suspendu conformément à l’instruction utilisateur.
- Extension Vue d’ensemble : son guide sur mesure conservait indépendamment l’ancien retrait
  de `8 %`. Ce n’était pas une régression du correctif précédent, mais une seconde implémentation
  non couverte. Elle utilise désormais le même ancrage de bord à bord ; mesure live sur `:3098`,
  trait et conteneur ont tous deux `x=276 → 1246`, soit `970 px`. Le ratchet couvre maintenant
  les deux composants. Biome, TypeScript et 45 tests ciblés sont verts.

## Correctif du masque de scroll du rail — 2026-07-24

- Finding live : une fois Vue d’ensemble défilée, le header finissait à `y=88` mais le rail
  sticky commençait à `y=108`. Dans la bande intermédiaire de `20 px`, `elementFromPoint`
  retrouvait un lien de carte du contenu : la page restait donc réellement visible et
  interactive au-dessus du rail.
- Cause : le scrollport commun porte `py-5`, tandis que le rail utilisait `top-0`. Le plan
  sticky se calait sur le bord intérieur du padding ; l’ombre opaque de `4 px` ne pouvait pas
  masquer les `20 px`. Cette régression a été introduite lors de l’uniformisation de la trame.
- Correction : le rail de Vue d’ensemble utilise `-top-5`, exactement l’inverse du padding du
  scrollport. Après le même scroll de `566 px`, header et rail se rencontrent à `y=88` et le
  point `y=98` appartient à un bouton du rail, plus au contenu sous-jacent.
- Biome, TypeScript, diff-check et 62 tests ciblés sont verts. Une mutation qui rétablit
  `top-0` rend le ratchet rouge. `make gate-twice` reste suspendu.
