# Refonte `/comprendre` v2 — statut de run

- **Date :** 2026-07-22
- **Worktree :** `agents/codex`
- **Branche :** `codex/comprendre-v2`
- **Base fraîche :** `origin/main` à `679d8d82`
- **Source fermée :** `Tessera_private/contenu-page-comprendre-v2.md`
- **Maquettes lues :** `E.png` (page cible), `D.png` (schéma uniquement). `C.png` n'a pas été ouverte : hors lot.
- **HALT :** obligatoire après le `dev-preview` supervisé et les captures FR/DE/EN, avant tout merge.

## Préconditions et discipline

- `AGENTS.md`, la spec privée, puis `docs/functional-page-playbook.md` ont été lus dans cet ordre avant tout code.
- Le worktree `agents/codex` était garé sur `codex/headers-refonte`, branche antérieure aux cibles `make session` / `make claim` et aux scripts du garde. La première tentative a donc refusé avec « No rule to make target » ; le garde de `main` a ensuite refusé honnêtement un checkout qui ne portait pas son fichier de référence. Bootstrap consigné : identité de session créée depuis la cible de `main`, branche coupée de `origin/main`, puis `make claim` vert sur le checkout frais.
- Bail sole-writer acquis par la session `e911d673-305e-4b5f-a47d-61e9cc643c63`.
- Staging ciblé uniquement ; jamais `git add -A`.
- `make gate-twice` à la fin de chaque lot, résultat et arbre nommés ci-dessous.

## Écarts de noms de seams constatés avant code

Ces écarts ne changent ni les définitions ni les décisions de la spec ; ils nomment le chemin réel trouvé sur `main`.

1. **T1/T2 — flotte observée et fraîcheur.** Aucun read seam unique ne retourne aujourd'hui « agents ayant publié dans les dernières 24 h + max horodatage ». Le seam flotte existant combine le registre, le transcript, la preuve de tours Prometheus et des descripteurs de quality nets. La preuve Prometheus actuelle est cumulative et documente explicitement qu'elle ne mesure pas une fenêtre. Le lot étendra ce read model de flotte sur les événements horodatés déjà lus par la spine ; aucun compteur de process ne sera présenté comme une fraîcheur.
2. **T3 — contrôlés / bloqués aujourd'hui.** Le read seam journal existe (`read_ledger_entries(since=…)`) et les entrées guard portent le résultat et les décisions. En revanche, les entrées `tessera.guard.audit` ne portent pas encore le booléen `synthetic`, même si le contexte de tour le connaît et si les événements d'invocation synthétique le portent. Le lot fermera ce trou au point d'émission, puis comptera uniquement les entrées guard réelles depuis minuit `Europe/Paris`. Aucun compteur Prometheus n'entre dans ce chemin.
3. **T4 — prêts / à évaluer ou réévaluer.** Sur le `main` frais, `/eval` redirige vers la vue Évaluations ; la tuile publique correspondante lit les `AgentRelease` du payload flotte et calcule ses buckets depuis `agent_release.py`, lequel applique déjà `eval_floor.py`. Il n'existe pas de bucket équivalent dans `routes/observability/evals.py`. Le lot factorisera et réutilisera le seam `AgentRelease` existant pour que la tuile et `/comprendre` partagent exactement les mêmes buckets, sans recalcul concurrent.
4. **T5 — intégrité.** Le seam attendu existe : `api/routes/audit.py::audit_integrity`, avec vérification incrémentale et `AuditIntegrity.full_verified_at`.

## Récolte de `b1dcd5d5`

- Lecture seule effectuée via `git show` ; la branche `codex/comprendre-3-minutes` reste intacte.
- Récoltables confirmés : le bloc `journey` (mini-cas), les cartes `roles`, et leurs sous-arbres i18n FR/DE/EN dans `comprendreCodex.content`.
- `timeline-nav.tsx` a été inspecté uniquement par son import ; il ne sera ni repris ni recréé.
- Le tag `archive/comprendre-A-codex` et la suppression de branche restent strictement après merge, donc hors de ce run avant HALT.

## Ledger des lots

| Lot | Statut | Commit | Gate twice | Preuves |
|---|---|---|---|---|
| 1 — backend | terminé | `49828247` | `8f3f9f9a7fc6` · twice-green | 59 tests ciblés verts ; mutations T1/T3/T4/T5 ; synthétique inchangé ; égalité T4 |
| 2 — page | terminé | `2e643ebf` | `355e7e1404c3` · twice-green | FR verbatim ; DE/EN ; BFF + zod ; 5 liens ; `/en-detail` |
| 3 — ratchets | terminé | `659c3c55` | `5c930c580bbd` · twice-green | mutation `214` rouge ; 5 e2e verts ; captures vide/FR/EN/DE |

## Mutations et captures

### Lot 1 — backend

- Endpoint ajouté : `GET /observability/comprendre`, agrégat de lecture sans store propre.
- T1/T2 : `turn_evidence.recent_turn_evidence` interroge le store Prometheus du spine par
  incréments bornés à la fenêtre ; le nombre ne retient que les identifiants du registre et la
  fraîcheur est le maximum des horodatages d'incrément, jamais la valeur courante du compteur.
  Le seuil de silence est classifié par le backend afin que le frontend ne l'invente pas.
- T3 : `guard_activity.exchange_counts_since` replie `read_ledger_entries(since=…)`, depuis
  minuit civil `Europe/Paris`, et ignore `synthetic=true`. Les nouvelles entrées guard-audit sont
  estampillées au point d'émission ; l'historique sans ce champ reste réel, sans rétrofiction.
- T4 : `agent_release.fleet_release_buckets` porte les buckets exclusifs `ready/review` et reste
  le seam unique à raccorder à la tuile `/eval` au lot 2 ; le test compare directement le payload
  à ce résultat sans recalcul.
- T5 : la route appelle effectivement `routes/audit.py::audit_integrity`; aucune date n'est
  servie si la vérification effective est absente, rouge ou vide.
- Mutation synthétique : une entrée `denied` avec `synthetic=true` injectée dans le journal laisse
  `controlled=2` et `blocked=1` strictement inchangés.
- Mutation par tuile : flotte vide → ajout d'un signal enregistré ne change ni guard ni eval ; un
  signal d'agent hors registre ne change pas T1 ; vérification rouge avec date forgée → T5 reste
  vide ; buckets T4 égaux au seam partagé.
- Preuves exécutées :
  - `uv run pytest tests/unit/test_observability_comprendre.py tests/unit/test_governed_acts_name_their_author.py tests/unit/test_guard_activity.py -q` → **59 passed**.
  - Ruff ciblé → **vert** ; format ciblé → **vert** ; mypy strict ciblé → **vert**.
- Mémoire : Insight 201 ajouté aux mémoires privées sur l'obligation de porter l'exclusion
  synthétique dans le contrat durable de l'événement.

- Premier essai du gate : rouge attendu des deux inventaires figés de routes publiques
  (`131→132` et `126→127`) ; les cliquets ont imposé la déclaration explicite du nouveau read
  aggregate sans donnée sujet. Mise à jour ciblée puis **56 tests de posture + endpoint verts**.
- `make gate-twice` final : **TWICE-GREEN sur un seul arbre `8f3f9f9a7fc6`** ; chaque passage
  valide TypeScript, Biome (27 warnings historiques), 429 tests frontend, Ruff, format, mypy
  strict et 2 560 tests backend hors intégration.

### Lot 2 — page

- Récolte en lecture seule depuis `b1dcd5d5` : structure visuelle du mini-cas et des cartes de
  rôles, plus les traductions FR/DE/EN des sous-arbres `journey` et `roles`. Les divergences de
  la branche A face au texte fermé (titre `Direction · DRH`, prochaine action proposée côté
  manager) n'ont pas été reprises ; le texte de la spec reste souverain.
- `/comprendre` lit l'agrégat côté serveur, le rafraîchit via `GET /api/comprendre`, et valide les
  deux chemins avec le même schéma Zod discriminé. Une indisponibilité ou un payload invalide
  devient `{available:false}` et conserve les honest-empty par tuile.
- La tuile publique `/eval` du launcher consomme désormais les buckets `ready/review` de ce même
  agrégat ; le test de mutation lui injecte un ancien rollup `passedAgents=99` et prouve qu'il est
  ignoré au profit du seam partagé.
- La prose v1 et ses catalogues existants sont servis par `/comprendre/en-detail`. Le nouveau shell
  public partagé maintient une seule occurrence d'autorisation explicite. `timeline-nav.tsx` n'a
  été ni copié ni recréé.
- Les cinq liens fermés sont câblés vers `/recouvrement`, `/agents`, `/surveiller`, `/eval` et
  `/prouver`. L'index `/prouver`, absent sur `main`, est matérialisé comme redirection locale vers
  le journal d'audit afin que la route demandée résolve sans texte supplémentaire.
- Preuves ciblées pré-gate : **42 tests verts** (`comprendre.test.ts` + `signal-band.test.tsx`) ;
  TypeScript strict frontend vert ; catalogues JSON valides ; Biome ciblé remis en forme.
- Premier essai du gate : rouge attendu du ratchet de nature de page sur le nouvel index
  `/prouver`. La route et son snapshot figé sont désormais explicitement déclarés `redirect` ;
  `page-nature.test.ts` repasse avec **12 tests verts**.
- `make gate-twice` final : **TWICE-GREEN sur un seul arbre `355e7e1404c3`** ; chaque passage
  valide TypeScript, Biome (27 avertissements historiques), 436 tests frontend, Ruff, format,
  mypy strict et 2 560 tests backend hors intégration.

### Lot 3 — ratchets

- `chrome-honesty.test.ts` couvre désormais les sources JSX de `/comprendre` et rejette tout
  littéral numérique visible hors liste blanche structurelle. Mutation physique exécutée :
  l'ajout de `<p>214</p>` dans `comprendre-v2-overview.tsx` produit exactement un contrevenant
  (`literal: "214"`) et fait passer le fichier à **1 échec / 30 succès** ; mutation retirée, le
  ratchet repasse à **31 tests verts**.
- E2E ciblé sur `make dev-preview PORT=3098` : base vierge simulée via le BFF → quatre tirets et
  leurs quatre raisons FR exactes ; les cinq liens de preuve résolvent leurs routes localisées
  réelles ; les titres, divulgations de fiction et liens de lecture détaillée rendent en FR, EN
  et DE. Résultat final ciblé : **5 passed**.
- La revue visuelle du diagramme a révélé que le bouclier absolu masquait le texte des cartes
  métier et agent. Le bouclier occupe désormais sa propre colonne de grille ; une nouvelle
  inspection du preview confirme l'absence de chevauchement sans changer texte ni contrat.
- Captures générées et inspectées :
  - base vierge FR : `/tmp/tessera-comprendre-v2-empty-fr.png` ;
  - FR : `/tmp/tessera-comprendre-v2-fr.png` ;
  - EN : `/tmp/tessera-comprendre-v2-en.png` ;
  - DE : `/tmp/tessera-comprendre-v2-de.png`.
- TypeScript strict ciblé : **vert** ; Biome ciblé : **vert** ; aucun texte ni claim fermé n'a
  été modifié pendant le ratchet.
- `make gate-twice` final : **TWICE-GREEN sur un seul arbre `5c930c580bbd`** ; chaque passage
  valide TypeScript, Biome (27 avertissements historiques), 442 tests frontend, Ruff, format,
  mypy strict et 2 560 tests backend hors intégration.

### Revue corrective après HALT — hiérarchie et lisibilité

- Retour opérateur : le grand titre du corps dupliquait le `h1` du header cockpit et créait une
  ouverture disproportionnée ; plusieurs intertitres et citations restaient trop grands, le
  diagramme arrivait sans transition et ses flèches directionnelles n'étaient pas décodables.
- Le header standard (`1.45rem`) reste l'unique titre de page visible. Le corps commence directement
  par le récit, sur une largeur de lecture bornée ; les halos, espacements, intertitres, titres de
  cartes, citations et conclusion sont ramenés à l'échelle typographique des pages cockpit.
- Le texte existant « Une seule porte, à sens unique… » sert désormais de transition avant le
  diagramme. Celui-ci n'utilise plus aucune flèche : trois zones stables, le contrôle en ligne en
  règle transversale, le registre séparé, puis les quatre flux expliqués par leur libellé et leur
  détail directionnel déjà présents dans les catalogues.
- Aucun catalogue FR/DE/EN, claim, fait, route ou contrat de données n'a changé. TypeScript ciblé
  vert ; **58 tests ciblés verts** (contrat `/comprendre` + ratchet numérique). Le preview
  `:3098/:8098` compile sans erreur et sert le worktree courant.
- `make gate-twice` correctif : **TWICE-GREEN sur un seul arbre `eabf62e12ee3`** ; chaque passage
  valide TypeScript, Biome (27 avertissements historiques), 443 tests frontend, Ruff, format,
  mypy strict et 2 560 tests backend hors intégration.
- Limite de revue : la politique du navigateur intégré refuse toute lecture de l'URL locale ; aucun
  navigateur alternatif n'a été utilisé. La validation visuelle finale reste donc à faire dans
  l'onglet opérateur déjà ouvert avant de considérer cette correction comme validée visuellement.

### Seconde revue corrective — plafond typographique, philosophie du schéma, largeur en détail

- Retour opérateur : aucun texte du corps ne doit dépasser « Comprendre Tessera — en 3 minutes »
  dans le header ; le schéma restait réducteur en faisant de la porte à sens unique son introduction
  et du contrôle en ligne son bandeau principal ; la forme souhaitée est plus proche de D pour les
  couleurs, les icônes et l'entête. `/comprendre/en-detail` était trop étroit.
- Relecture avant code : `AGENTS.md` → spec privée → playbook, puis `README.md`, `docs/design.md`,
  `docs/safety.md`, `docs/differentiation.md` et ADR 0011, 0013, 0015, 0019, 0021, 0022, 0028.
  L'intention retenue n'est pas « un firewall central » : Tessera assemble le plan métier, des agents
  qui publient leurs faits, un plan de gouvernance, une invocation déclarée, quatre couches de qualité
  et un registre possédé pour ce qui gate ou prouve.
- Le schéma reste un composant HTML/CSS responsive, accessible et trilingue. Il reprend la grammaire
  visuelle de D : bleu pour les espaces métier, émeraude pour les agents, violet pour le cockpit,
  ambre pour le registre ; cartes iconographiées, entête de « salle des machines », deux rails nommés
  pour télémétrie/tests. Le bouclier est replacé sur sa couture, le registre reste séparé et la phrase
  de la porte descend en note de frontière. Aucun texte fermé n'est modifié ni supprimé.
- `SectionHeader` et la conclusion passent à `text-xl` (1,25 rem), donc sous le `h1` standard du
  cockpit (1,45 rem). Un ratchet parcourt les sources et refuse les tailles Tailwind `2xl+` ainsi que
  toute taille arbitraire supérieure à 1,45 rem.
- `/comprendre/en-detail` adopte le même conteneur `max-w-[76rem]` que `/comprendre`. Ses sections
  utilisent une grille éditoriale titre/prose afin d'occuper la largeur sans produire des lignes de
  texte illisiblement longues.
- Aucun catalogue FR/DE/EN, claim, fait, route ou contrat de données n'a changé. TypeScript vert ;
  Biome ciblé vert ; **59 tests ciblés verts** (28 contrat `/comprendre` + 31 ratchet numérique).
  Les routes `/fr/comprendre` et `/fr/comprendre/en-detail` répondent toutes deux HTTP 200 sur le
  preview `:3098`. La validation visuelle reste celle de l'opérateur dans l'onglet ouvert, la politique
  du navigateur intégré interdisant toujours la lecture automatisée de localhost.
- `make gate-twice` : **TWICE-GREEN sur un seul arbre `b3fcb1124083`** ; chaque passage valide
  TypeScript, Biome (27 avertissements historiques), 444 tests frontend, Ruff, format, mypy strict
  et 2 560 tests backend hors intégration.

### Troisième revue corrective — vue d'ensemble Tessera et agents IA incarnés

- Retour opérateur sur capture : le diagramme restait centré sur « La salle des machines de la
  flotte » et traitait les agents IA comme une simple liste, alors que D leur donnait une présence
  iconographique forte et que l'image doit raconter Tessera dans son ensemble.
- L'entête du schéma ne reprend plus la légende locale du cockpit. Il s'ouvre sur le nom Tessera et
  la phrase fermée de conclusion, déjà catalogués dans les trois langues. La mention « salle des
  machines » reste à sa place exacte : comme caption du seul panneau Cockpit.
- Les Agents IA deviennent le centre visuel : panneau émeraude élargi, noyau illustré, motif de
  constellation et quatre cartes iconographiées distinctes pour les quatre entrées fermées. Les
  espaces métier et le cockpit gardent leurs propres panneaux bleu/violet et leurs icônes ; le
  registre ambre reste une mémoire séparée sous les agents.
- Les invariants du schéma sont conservés sans déplacement de sens : bouclier sur la couture de
  l'échange, deux rails nommés entre agents et cockpit, quatre flux avec directions explicites et
  phrase de la porte visible mais rattachée au seul flux d'accès utilisateur.
- Aucun catalogue FR/DE/EN, claim, fait, route ou contrat de données n'a changé. Le nouveau ratchet
  exige les trois plans, le cadrage global via les catalogues, le panneau dédié aux agents et
  l'absence de `cockpitCaption` promu en entête. TypeScript vert, Biome vert et **60 tests ciblés
  verts** (29 contrat `/comprendre` + 31 honnêteté du chrome).
- Le navigateur intégré a pu être connecté pendant cette passe : rendu réel contrôlé au viewport
  courant, puis au breakpoint large temporaire `1600×1100` ; trois plans présents, quatre nœuds
  agents rendus, viewport restauré avant la fin. Le preview reste servi sur `:3098`.
- `make gate-twice` : **TWICE-GREEN sur un seul arbre `0043e8645f63`** ; chaque passage valide
  TypeScript, Biome (27 avertissements historiques), 445 tests frontend, Ruff, format, mypy strict
  et 2 560 tests backend hors intégration.

### Quatrième revue corrective — collision du guard et contraste des micro-libellés

- La capture opérateur a isolé une collision au premier connecteur : au breakpoint `xl`, la voie
  interne du guard était forcée à `h-px` tandis que le badge bouclier gardait une hauteur de 44 px.
  Le badge débordait donc de son conteneur et masquait le début de « Sécurité à chaque échange ».
- La voie réserve désormais `h-12` au badge. Les textes « Quatre questions simples », « Les quatre
  flux », la phrase complète de la porte et les quatre moments gagnent un niveau de contraste
  ciblé (`text-muted`, graisse 500/600) ; les moments reçoivent aussi le fond secondaire existant.
  Aucun autre texte secondaire n'est éclairci globalement.
- Un ratchet source exige les marqueurs des quatre familles de contraste, la hauteur réservée du
  guard et ses deux surfaces mesurables. Aucun catalogue FR/DE/EN ni texte fermé n'a changé.
- TypeScript vert, Biome ciblé vert et **61 tests ciblés verts** (30 contrat `/comprendre` + 31
  honnêteté du chrome). Mesure dans le navigateur après recompilation : `overlap=false`, espace
  badge→libellé = **10 px**, couleur calculée des sept libellés contrôlés = `rgb(154, 159, 161)`,
  graisses 500 pour questions/flux/porte et 600 pour les quatre moments.
- Un premier lancement du gate a signalé uniquement un doublon d'Insight 207 créé en parallèle
  dans la mémoire privée. L'entrée concurrente la plus récente a été renumérotée 208 conformément
  au ratchet ; les 4 tests du registre mémoire sont alors redevenus verts.
- `make gate-twice` relancé sur l'arbre corrigé : **TWICE-GREEN sur un seul arbre
  `cc1d4f5c5df7`** ; chaque passage valide TypeScript, Biome (27 avertissements historiques),
  446 tests frontend, Ruff, format, mypy strict et 2 560 tests backend hors intégration.

### Correctifs d'audit live

- Source : Addendum 2 de `Tessera_private/revue-comprendre-v2-2026-07-22.md`, audit DOM live
  du preview `:3098`. Verdict : approuvé sous condition AL-1 + AL-2 ; AL-3/4/5 pris dans la
  même fenêtre.
- **AL-1, mesure avant correction** : le backend du preview répond directement
  `controlled_today=2365`, `blocked_today=2365`, `since=2026-07-22T00:00:00+02:00` ; le DOM
  ne duplique donc pas `controlled_today` et l'hypothèse (a) est fausse. La requête sur le même
  ledger Postgres donne 34 023 entrées `tessera.guard.audit/user_input` historiques, dont 2 365
  depuis minuit Paris ; la borne SQL est donc appliquée et 2 365 n'est pas l'historique entier :
  l'hypothèse (b) est fausse elle aussi.
- **AL-1, vraie jambe** : les 2 365 entrées du jour sont toutes des refus
  `injection.limes.deny`, émis par rafales de cas d'épreuve ; 2 249 prédatent le champ
  `synthetic`, 116 portent `synthetic=false`, et aucune ne porte d'identité de tour. Le lecteur
  comptait toute entrée d'audit `user_input` comme un échange contrôlé, alors que le seam
  n'émet une entrée que lors d'un refus ou d'une transformation, jamais pour l'autorisation
  ordinaire. Le dénominateur était donc le journal des exceptions, pas celui des échanges.
- Correction retenue sur le seam S1 existant : corréler chaque décision de guard au `turn_id`
  du tour chat, journaliser aussi l'autorisation ordinaire, puis ne compter que les décisions
  liées à un tour et non synthétiques. Les appels directs d'épreuve sans tour ne deviennent plus
  des chiffres métier ; les tours réels autorisés alimentent enfin le dénominateur.
- **AL-1, mesure après correction** : sur le même ledger et la même borne
  `2026-07-22T00:00:00+02:00`, le backend du preview répond
  `controlled_today=null`, `blocked_today=null`. C'est l'honest-empty attendu : le stock du jour
  ne contient aucun tour chat corrélé que le lecteur puisse honnêtement promouvoir en échange
  métier. Le test frontend rend explicitement `{controlled: 3, blocked: 1}` et exige `3` puis `1` ;
  la mutation qui relie `blocked` à `controlled_today` échoue, puis l'arbre restauré repasse vert.
  Côté backend, une entrée d'avant minuit, une sonde directe et un tour synthétique sont exclus,
  tandis qu'un tour réel autorisé et un tour réel refusé donnent exactement `2/1`.
- **AL-2 à AL-5** : la phrase finale ne vit plus que dans la finale 8b ; le panneau reçoit une
  caption neutre dédiée en FR/DE/EN. Les pastilles de légende supérieures ont disparu et les cartes
  directionnelles restent l'unique légende, avec les couleurs déjà reprises par les flèches. Le
  paragraphe introductif s'arrête avant la liste des quatre questions, portée uniquement par sa
  carte, et une transition trilingue introduit désormais la géographie du schéma.
- Validation ciblée avant atterrissage : 62 tests backend verts, 65 tests frontend verts,
  TypeScript et Biome verts. Le contrôle DOM via le navigateur intégré est bloqué par sa politique
  d'accès à l'URL locale ; aucun contournement n'a été tenté. La validation visuelle finale reste
  donc celle du preview opérateur pendant le HALT éclair.
- **Premier gate sur l'arbre rebasé, rouge utile** : la nouvelle entrée d'autorisation révélait
  qu'une rectification mémoire authentifiée écrivait d'abord `actor=system:guard`, avant son acte
  métier correctement attribué. Le ratchet transversal
  `test_every_governed_act_names_the_principal_who_performed_it` l'a refusé. Correction : `Actor`
  est désormais obligatoire sur `check_user_input` et `screen_memory`, sans valeur par défaut ;
  les routes humaines propagent `actor_of(session)` et chaque sonde/tâche système nomme son acteur.
  La proposition de prompt transporte elle aussi l'`Actor` vérifié au lieu de dupliquer une chaîne
  `author`. Validation après correction : 122 tests ciblés verts, dont les 45 témoins d'auteur,
  Ruff, format et mypy verts. Le gate-twice complet est à relancer sur ce nouvel arbre.
- Owed hors lot, sans action : le monde du preview reste incohérent pour une démo tant que son
  seed ne produit pas ensemble une spine et un ledger représentatifs. Le seed d'un monde cohérent
  appartient à une passe dédiée.

## Questions bloquantes / déviations proposées

Aucune. Si une déviation de contenu, de contrat ou de structure devenait nécessaire, elle sera écrite ici et le run s'arrêtera avant de la prendre.
