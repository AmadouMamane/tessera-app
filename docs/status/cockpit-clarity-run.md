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
