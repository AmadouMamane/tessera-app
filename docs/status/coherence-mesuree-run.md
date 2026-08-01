# Cohérence mesurée — chantier CLOS le 2026-08-01

> **Les 12 lots sont faits.** `main` ← `claude/coherence-mesuree`, twice-green sur un seul arbre
> (digest `be3f0cd9a207`). Ce qui suit est le plan d'origine, conservé tel quel : il porte les
> constats avec leur preuve `fichier:ligne`, et les commits ci-dessous portent ce qui en a été
> fait. Un plan réécrit après coup ne dit plus ce qu'on ignorait au départ.
>
> | lot | livré | commit |
> |---|---|---|
> | 1 · cliquets ×4 | 4 classes gelées, 5 mutations rouges | `4d6c5edd` |
> | 2 · registre unique | 3 surfaces câblées, classe A **23 → 0** | `00926a3b` |
> | 3 · routes propriétaires | `?tab=&signal=`, id vérifié contre `capabilities.py` | `00926a3b` |
> | 4 · fenêtre temporelle | la charge utile flotte dit son intervalle | `b9bc4c5e` |
> | 5 · entonnoir des signaux | « 42/200 » → funnel mesuré ; 4 raisons d'indisponibilité | `2591cad7` |
> | 6 · registres de capacités | 3 divergences, dont une fixture rendue comme réelle | `05eb6659` |
> | 7 · localisation | 100 % sur 0 catalogue lu → union + échec bruyant | `b6827cac` |
> | 8 · sondes honnêtes | « 0 incident » sur 0 mesure ; 2 sondes tautologiques | `deed9e93` |
> | 9 · effacement RGPD | 138 sujets hors portée, mesurés et outillés | `857b8c5b` |
> | 10 · file opérateur | 77 lignes / 11 phrases → 77 / 77 | `d3e925bd`, `23bdbf82` |
> | 11 · démo réamorcée | run du 01/08, `llama3.2:3b` — et **refusé** par la règle 1 | `b1f3610c` |
> | 12 · orphelins | 14 classés, `catalogue-consumers` monté | `b1f3610c` |
>
> **Ce que le chantier a trouvé de plus lourd, et que l'audit page par page ne pouvait pas voir :**
> `/observability/localization` annonçait **100 % de complétude** parce qu'il ne pouvait lire
> aucun catalogue (le conteneur n'embarque pas `webapp/`), et l'effacement RGPD laissait
> **138 sujets** dans un schéma qu'aucun chemin de suppression n'atteint.
>
> **Il reste UNE action opérateur** : purger `public` —
> `uv run python scripts/purge_orphan_schema.py --schema public --apply`. Rien n'a été supprimé.

---

# Cohérence mesurée — plan d'exécution (ouvert)

**Branche** `claude/coherence-mesuree`, coupée de `main = 1cbc965b`.
**État : RIEN N'EST COMMITÉ, gate non passée.** Un seul fichier écrit à ce stade :
`webapp/frontend/lib/control-registry.ts` (la source unique, pas encore câblée).

Ce fichier est la source de vérité de ce chantier. Une session qui reprend le lit d'abord,
puis exécute le premier lot `à faire`.

---

## Pourquoi ce chantier existe

L'audit du 2026-08-01 a été mené **page par page** : pour chaque écran, « ce nombre est-il
honnête au regard de son endpoint ? ». Cette question se tranche localement, et la réponse
était oui presque partout. Elle ne peut structurellement pas voir la question qui ne se pose
**qu'entre** les écrans : « ce nombre dit-il la même chose ailleurs ? ».

C'est ADR 0026 retourné contre l'auditeur : j'ai interrogé le **voisinage** de chaque écran
(son endpoint) au lieu de **la chose** — le système parlant d'une seule voix. L'opérateur, lui,
ne lit pas un endpoint ; il lit deux pages et les compare.

**Conséquence méthodologique, valable pour la suite : on n'audite plus des pages, on énumère
les invariants qu'un plan de contrôle doit tenir et on teste chacun sur tout le dépôt.**
Exhaustif par construction plutôt que par diligence.

**La cause est unique dans tous les cas trouvés : une dérivation recopiée au lieu d'être
partagée.** Deux copies des seuils, trois de l'efficacité firewall, deux du chargeur de flotte,
deux systèmes de traduction, deux registres de capacités. Aucune paire n'est réconciliée par
quoi que ce soit.

---

## Les sondes (à promouvoir en cliquets)

Copiées dans `scripts/audit/`. Chacune porte **un contrôle positif et un contrôle négatif** —
trois de mes sondes jetables ont menti pendant cet audit (préfixe de fichier dans `rg -o` ;
imports relatifs `./x` ignorés ; heuristique « catalogue » qui excluait un vrai coupable). Une
sonde sans contrôle est un témoin qui ne dit pas ce qu'il n'a pas regardé.

| script | classe détectée | état au 2026-08-01 |
|---|---|---|
| `scan_control_divergence.py` | un champ rendu avec plusieurs seuils / plusieurs valeurs | 4 champs divergents, 3 copies pour le firewall |
| `scan_i18n_mechanism.py` | texte affiché sans mécanisme de traduction · second mécanisme parallèle | 307 chaînes nues · 342 `pick()` |
| `scan_ui_invariants.py` | boutons sans action · liens morts · fenêtres temporelles | 60 candidats · **0 lien mort** · 16 sites de fenêtre |

---

## Constats, avec leur preuve

### A — Une mesure, plusieurs vérités  ⟵ *le cœur du chantier*

| id | constat | preuve |
|---|---|---|
| A1 | **Efficacité firewall = 3 nombres sur 3 pages** : 24 % (taux d'attaque = 1−rappel), 76 % (rappel), 86 % (F1) | `security-dashboard.tsx:667` · `overview-dashboard.tsx:736` · `signals-table.tsx:273` |
| A2 | **Calibration des refus = 2 valeurs, 2 seuils** : 60 % `max(over,under)` ≤ 5 % vs 0 % `over` ≤ 10 % | `overview-dashboard.tsx:690` · `signals-table.tsx:311` |
| A3 | **Le statut ne dérive pas de la valeur affichée** : statut calculé sur `worst`, cellule affichant `over` → « 0 % · seuil ≤ 10 % · **Critique** » | `signals-table.tsx:305-313` |
| A4 | Toxicité : `≤ 0.10%` / `= 0` / `< 0.1%` | `overview:665` · `signals-table:286` · `security:712` |
| A5 | Fuite PII : `≤ 0.50%` / `= 0` / `0%` | `overview:679` · `signals-table:298` · `security:684` |
| A6 | Conformité des arguments : `≥ 95%` vs `= 100%` | `overview:708` · `signals-table:331` |
| A7 | Fidélité : `≥ slo.target` (95 %, backend) vs `≥ 0.80` (littéral) | `overview:648` · `signals-table` |
| A8 | **Libellés divergents** pour les 7 mêmes contrôles | `overview.signals.*` vs `observability.*.title` |
| A9 | **Fenêtre temporelle** : `agents/page.tsx:19` redéfinit son propre `loadFleet` **sans période** → 432 conversations ; `surveiller/vue-ensemble/page.tsx:28` utilise le partagé → `d7` → 0. La page Flotte n'affiche **aucune** fenêtre. | mesuré : `?period=d7`→0, `d30`→412, sans période→432 |
| A10 | **« Investiguer » ne mène pas à la surface propriétaire** : route sans onglet ni ancre | `src/tessera/observability/control_signals.py:46-55` |

### B — Deux systèmes de traduction

| id | constat | preuve |
|---|---|---|
| B1 | **307 chaînes françaises sans aucun mécanisme** — un opérateur DE/EN les lit en français | ex. `agent-console.tsx:1769-1775` : `k="Modèle"`, `k="Coût estimé"`, `entrée · sortie · total` |
| B2 | **342 appels `pick(locale, fr, de, en)`**, helper **défini 3 fois**, invisible de `messages/*.json` donc du contrôle de complétude | `agent-subtab-shared.tsx:22` · `agent-evaluations.tsx:49` · `evaluation-run-rail.tsx:29` |
| B3 | 2 clés présentes **seulement en `fr`** et appelées par le code → libellé a11y cassé en EN/DE sur le widget client | `product.apercu.widget.{maximize,minimize}` ← `chat-widget.tsx:226` |
| B4 | **`/observability/localization` répond « 100 % complet » sur ZÉRO catalogue lu** : le conteneur n'embarque que `src/` et `eval/`, la route lit `parents[5]/webapp/frontend/messages`, `except → {}`. Et même quand il lit, il compare tout à `en` — il ne **peut pas** voir B3. | mesuré live : `n_default_keys: 0` |

⚠️ **Le « 7 158/7 158 » publié dans l'audit initial est donc faux** : il ne couvre pas ce qui est
réellement affiché (B1 + B2).

### C — Compteurs en dur rendus comme des mesures

| id | constat | preuve |
|---|---|---|
| C1 | `QUALITY_SIGNALS = 42` et `QUALITY_CATALOGUE = 200` en dur, rendus « 42/200 signaux qualité » dans la barre d'état. Réel : **44** déclarés sur la page (25 `active`), **202** au catalogue (78 `active`), **18** câblés. Faux sur les trois nombres. Le commentaire qui s'en défend (« coverage framing, not a fabricated metric ») est le symptôme. | `observability-dashboard.tsx:132-135` |
| C2 | **L'entonnoir est invisible** : 202 déclarés → 44 sur la page → **18 avec un lecteur** → 6 avec échantillon → 3 en dépassement. **184 signaux du catalogue n'ont aucun lecteur** et rien ne le dit. | `docs/signal-catalog.yaml` · 18 `rows.push` dans `signals-table.tsx` |

### D — « Indisponible » confond quatre états

| id | constat | preuve |
|---|---|---|
| D1 | `status: "na"` posé quand **l'échantillon est vide** (`n_turns === 0`, `total === 0`, …). « Indisponible » veut donc dire *il ne s'est rien passé*, jamais distingué de *pas de lecteur*, *lecture en échec*, *`planned`*. Le projet a construit exactement cette distinction (`no-sample` / `unavailable` / `not-honoured` …) le 2026-07-14 pour `selectHonouredSignal` ; jamais appliquée ici. | `signals-table.tsx` (règles `na`) |
| D2 | Même cause, deux rendus : `0/0 = 0` pour les unes, `—` pour les autres | 12 lignes « Indispo. » sur la page |

### E — Fixtures non signalés (registres désynchronisés)

| id | constat | preuve |
|---|---|---|
| E1 | `capabilities.py` déclare `embedding_inversion`, `embedding_skew`, `disclosure` **synthetic** ; `signal-registry.ts` déclare le premier **non-synthetic** et **ignore** les deux autres. `<SyntheticNotice>` lit le **front** → aucun bandeau. | diff des 2 registres |
| E2 | Conséquence : « **Inversion embedding · Critique · 100 % (3/3) · objectif 0 % · action : masquer avant embedding** » calculé sur **3 chaînes en dur** (`DEMO_MEMORIES`), mémoïsées par process, jamais le vrai magasin mémoire. Et ces 3 faux échecs sont **agrégés** dans « Répartition des échecs (22) → 3 · 14 % » et « Risque par domaine ». | probe live · `safety.py:108-125` |
| E3 | **Aucun cliquet ne compare les deux fichiers**, et chacun se déclare source de vérité (commentaire `capabilities.py` vs `signal-registry.ts:43`). | grep exhaustif des tests |

### F — L'absence de mesure se rend en vert

| id | constat | preuve |
|---|---|---|
| F1 | `jailbreak_success_rate` vaut 0.0 quand aucun instantané red-team n'existe (et il n'y en a **aucun**) → « 0 procédure déclenchée · situation nominale ». Le module applique pourtant `n_scores > 0` pour l'hallucination : la précaution existe, elle n'a pas été portée aux 3 autres déclencheurs. | `src/tessera/observability/playbooks.py:72,87,102,117` |
| F2 | `embedding_skew` : la route pose `corpus = query` → `skew: false` **toujours**. Un contrôle qui ne peut pas échouer. | `safety.py:219-237` |
| F3 | Panneau **« Test d'intrusion continu (7 j) »** alimenté par `firewall_efficacy`, sonde à **corpus fixe sans dimension temporelle**. L'infobulle dit vrai, le titre fabrique la fenêtre. | `security.panel.redteam` · `security-dashboard.tsx:827-836` |

### G — RGPD : un schéma hors gouvernance

| id | constat | preuve |
|---|---|---|
| G1 | Le schéma `public` garde **2 920 messages, 1 357 mémoires long terme, 138 sujets** (dont **4** aussi présents dans le schéma vivant `tessera_local`). Les `DELETE` d'effacement ne portent **aucun schéma** → ils résolvent sur `search_path = <env>, public` et ne touchent jamais `public`. Un effacement laisse la mémoire du sujet intacte. ADR 0014 a chiffré le coût comme « démarre vide — honnête, pas perdu » ; sa section *Consequences* ne nomme pas cette conséquence-là. | requêtes Postgres · `memory/persistent.py:363` · `transcript.py:395` |

### H — Produit / lisibilité

| id | constat |
|---|---|
| H1 | File opérateur « À traiter · 57 » = **56 titres strictement identiques** « Validation à donner — RC-2048 », tous « En retard », issus de runs de checkpoint de dev (`checkpoint-lot0-live`, `ckpt2-metier-live`). Le champ `synthetic` des business events ne couvre que le canari, pas les runs de validation manuels. Aucune déduplication. |
| H2 | **Démo structurellement vide** : dernière conversation le **24/07**, fenêtre par défaut de GOUVERNER = **7 jours**. Ce n'est pas un bug (`d7`→0, `d30`→412 vérifiés) mais les pages phares sont vides et les 6 agents lisent « DÉCLARÉ · AUCUNE PREUVE ». |
| H3 | Le coachmark d'aide **recouvre** le bouton *Exporter* (Vue d'ensemble) et la 4ᵉ carte KPI (Flotte). |
| H4 | Deux filtres « Agents : Tous les agents » sur le même écran (rail temporel + au-dessus du tableau). |

### I — Dette

| id | constat |
|---|---|
| I1 | **14 composants orphelins** (2 140 lignes). **Deux sont des doublons morts** — `language-switcher.tsx` et `theme-toggle.tsx`, réimplémentés inline dans `user-menu.tsx` / `app-header.tsx`. **Douze sont des fonctionnalités jamais montées** : `recouvrement-console`, `session-theater`, `apercu-host`, `customer-session-bar`, `catalogue-consumers`, `eval-runs`, `replay-panel`, `scaffold-view`, `model-badge`, `status-badge`, `ui/scroll-area`, `ui/separator`. |
| I2 | 3 routes HTTP sans consommateur : `/observability/{agent-lifecycle, business-events, quality-nets}`. `catalogue-consumers` a **et** sa route **et** son composant orphelins — la fonctionnalité entière n'a jamais été branchée. |
| I3 | README annonce 2 517 tests ; 2 752 collectés. |
| I4 | `src/tessera/llm/local.py` documente « Llama 3.3 70B » alors que le défaut est `llama3.2:3b`. |
| I5 | 60 boutons candidats sans action — **à lire un par un**, sur-rapport probable. |

---

## Lots — dans l'ordre d'exécution

**Principe imposé par l'opérateur : on AJOUTE de la fonctionnalité, on n'en retire pas.**
Un orphelin se remonte, un compteur faux se rend juste, un signal `planned` se montre comme
tel — jamais un écran appauvri.
**Modèle : `llama3.2:3b` (le plus petit, pour la latence). L'opérateur donnera le go pour
basculer.**

### Lot 1 — Les cliquets d'abord  ⟵ *à faire*

Promouvoir les 3 sondes en tests, **offenseurs actuels gelés, compte qui ne peut que baisser**
(idiome du dépôt, cf. `_FROZEN_COLLISIONS`). Balise tout le territoire immédiatement, y
compris les pages jamais lues à la main.

- `webapp/frontend/lib/control-registry.test.ts` — pour un **même payload**, la ligne rendue
  par chaque surface est **égale champ par champ** ; aucun `Math.max` sur deux faces opposées ;
  le statut dérive de la valeur affichée. Mutation-tester dans les 3 sens.
- Un cliquet **par classe** : seuils divergents (A), chaînes hors mécanisme (B), compteurs en
  dur (C), raison d'indisponibilité manquante (D).
- Critère d'acceptation : chaque cliquet **rouge sous mutation**, vert sur l'arbre, avec sa
  liste gelée nommée et comptée.

### Lot 2 — Câbler les 3 surfaces sur `control-registry.ts`  ⟵ *à faire*

`webapp/frontend/lib/control-registry.ts` est **écrit** (source unique : valeur, seuil, règle
d'état, sévérité, route propriétaire, `calibrated: true/false`). Restent :

- brancher `overview-dashboard.tsx`, `signals-table.tsx`, `security-dashboard.tsx` dessus ;
- **scinder le refus en deux contrôles** (`refusalOver` ≤ 10 %, `refusalUnder` ≤ 5 % — la barre
  stricte va à la face sécurité ; les deux sont **déclarées, non calibrées**, et le disent) ;
- firewall sur **F1** (l'id de métrique du catalogue tranche : `guard.firewall.f1`) ; rappel et
  précision descendent en ligne de détail ;
- unifier les 7 libellés (garder les plus précis, ceux de `observability.*.title`) ;
- `ControlDetail` est **de la donnée**, jamais une chaîne pré-formatée — l'ancien
  `` `sous ${pct(...)}` `` était du français en dur dans un composant trilingue.

### Lot 3 — Routes propriétaires  ⟵ *à faire*

`control_signals.py:46-55` : chaque contrôle route vers **la surface qui le possède**, avec
onglet et ancre — `/surveiller/qualite-ia?tab=signals&signal=<clé>`. Le param `?signal=` existe
déjà (`lib/signal-focus.ts`). Ajouter les deux ids de refus.

### Lot 4 — Une seule fenêtre  ⟵ *à faire*

Fusionner le `loadFleet` privé de `app/[locale]/agents/page.tsx:19` avec celui de
`lib/server/fleet.ts`, et **afficher la fenêtre** sur la page Flotte (aujourd'hui muette).
Cliquet : aucune page ne redéfinit un chargeur qui existe déjà.

### Lot 5 — L'entonnoir des signaux, rendu visible (points C + D)  ⟵ *à faire*

- Remplacer `QUALITY_SIGNALS`/`QUALITY_CATALOGUE` par un **comptage réel** du catalogue.
- **Ajouter** au registre les signaux `planned` et sans lecteur, avec leur état propre — les
  184 déclarés-non-servis existent, on les montre plutôt que de les taire.
- Éclater « Indisponible » en `no-sample` / `no-reader` / `read-failed` / `planned`, chacun
  avec sa raison affichée, et un rendu unique par cause.

### Lot 6 — Registres de capacités réconciliés (point E)  ⟵ *à faire*

Cliquet back↔front sur `capabilities.py` ↔ `signal-registry.ts` : égalité d'ensembles **et**
du drapeau `synthetic`. Puis `<SyntheticNotice>` sur les tuiles concernées de
`security-dashboard.tsx` (aujourd'hui : zéro notice dans tout le fichier), et **sortir les
chiffres de fixture des agrégats réels** (répartition des échecs, risque par domaine).

### Lot 7 — Localisation réellement mesurée (point B)  ⟵ *à faire*

- La route **échoue bruyamment** si elle ne peut pas lire les catalogues (aujourd'hui `{}` →
  100 %). Un témoin qui ne voit pas ne dit jamais « ok ».
- Comparer **l'union** des clés, pas seulement contre `en`.
- Mesurer aussi **les clés que le code appelle** (`t("…")`), pas seulement celles des fichiers.
- Ajouter les 2 clés manquantes ; décider du sort de `pick()` (unifier vers next-intl, ou le
  déclarer et l'inclure dans la mesure — mais une seule mesure).

### Lot 8 — Sondes honnêtes (point F)  ⟵ *à faire*

- `PlaybookSignals` gagne `n_snapshots` / `n_turns` : *jamais mesuré* ≠ *mesuré propre*.
- Retirer le « (7 j) » du titre du panneau red-team ; nommer la sonde pour ce qu'elle est.
- `embedding_skew` : soit lire l'empreinte réelle du corpus à l'ingestion, soit dire que le
  contrôle ne peut pas conclure.

### Lot 9 — Effacement complet (point G)  ⟵ *à faire*

Qualifier les `DELETE` par schéma, purger ou migrer `public.*`, et **prouver** l'effacement
total par un test qui écrit dans les deux schémas et vérifie qu'il ne reste rien.

### Lot 10 — File opérateur (point H1)  ⟵ *à faire*

Dédupliquer par dossier + capacité, marquer les runs de validation, et faire porter au titre
ce qui distingue deux items.

### Lot 11 — Réamorcer la démo (point H2)  ⟵ *à faire*

Un run récent avec **`llama3.2:3b`** pour que les pages phares aient de quoi montrer.
⚠️ L'agent tourne en conteneur (`tessera-local-agent`) : un changement de `src/` exige un
**rebuild d'image**, `make gate` ne lance pas `next build`.

### Lot 12 — Remonter les orphelins (point I)  ⟵ *à faire*

Les 12 fonctionnalités jamais montées sont **remontées**, pas supprimées ; les 2 doublons morts
(`language-switcher`, `theme-toggle`) sont les seuls candidats à la suppression, et seulement
après confirmation que l'inline les remplace intégralement. `catalogue-consumers` : composant +
route à brancher ensemble.

---

## Pièges à ne pas rejouer

- **Deux schémas Postgres portent les mêmes tables.** `psql` par défaut atterrit sur `public`
  (périmé, 2 920 messages, dernier 24/06) ; le vivant est `tessera_local` (1 004 messages,
  dernier 24/07). Toujours `set search_path to tessera_local;` avant de conclure quoi que ce
  soit sur les données.
- **`rg -o` sans `--no-filename` préfixe le chemin** — une sonde de comparaison croisée devient
  fausse en silence.
- **Les imports relatifs `./x` échappent** à une recherche sur `components/<dir>/<base>`.
- **Le conteneur agent n'embarque que `src/` et `eval/`** — toute route lisant un chemin du
  dépôt hors de ces deux dossiers échoue silencieusement en production.
- `make gate-twice`, jamais `make gate` deux fois ; commiter avant de muter.
