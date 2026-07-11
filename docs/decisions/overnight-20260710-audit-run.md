# Run de nuit 2026-07-10 → 07-11 — remédiation d'audit

Journal d'exécution de la remédiation intégrale de l'audit
`Tessera_private/audit-code-2026-07-10.md` (main `ece4f1bf`). Un lot = une branche =
un merge. Une passe `make gate` par lot avant merge ; le CI est la deuxième passe
(asynchrone). Rouge deux fois → parké. Contradiction de design → parké, pas tranché.

---

## RÉSUMÉ MATIN (mis à jour au fil de la nuit)

**État au démarrage** : gate (workflow *CI*) **vert** sur `ece4f1bf` ; workflows
*Security* + *Supply chain* **rouges** — pré-existants, hors périmètre de correction
cette nuit (voir « État de base » ci-dessous).

| Fenêtre | Lot | Sujet | Verdict | Hash |
|---|---|---|---|---|
| — | 0 | Journal + état de base | 🟢 en cours | — |
| 1 | 1.1 | Tests d'intégration (job CI + tri) | ⏳ | — |
| 1 | 1.2 | 49 `except … pass/continue` | ⏳ | — |
| 1 | 1.3 | 7 SQL f-string + coverage informatif | ⏳ | — |
| 1 | 1.4 | Trio recouvrement + kicker credit-aurore | ⏳ | — |
| 2 | 2.1 | Rate-limit `/agents/{id}/invoke` | ⏳ | — |
| 2 | 2.2 | Sauvegarde ledger + drill restauration | ⏳ | — |
| 2 | 2.3 | Inventaire config généré | ⏳ | — |
| 3 | 3.0 | Prototype codegen OpenAPI→zod (fleet) | ⏳ | — |
| 3 | 3.1 | Scission `observability.py` | ⏳ | — |
| 3 | 3.2 | Extraction tabs communs | ⏳ | — |
| 4 | 4.1 | Doc posture prod | ⏳ | — |
| 4 | 4.2 | Job CI deps/CVE informatif | ⏳ | — |
| 4 | 4.3 | Échantillon biome-ignore | ⏳ | — |
| 4 | 4.4 | Fixture-trafic → flip e2e | ⏳ | — |

**Chiffres avant → après** (remplis en fin de nuit) : except classés · SQL fermés ·
coverage % · routes supprimées · rate-limit · drill OK/KO · verdict codegen · flip e2e.

**Ce qui attend Amadou / Claude** : (rempli en fin de nuit).

---

## État de base (mesuré au démarrage, `ece4f1bf`)

### Gate = vert, mais deux workflows séparés sont rouges (pré-existants)

Le workflow **CI** (= `make gate`, hermétique, bloquant) est **vert** sur `ece4f1bf`.
Deux autres workflows sont rouges **avant** ce run, indépendamment de tout lot ci-dessous :

**`security.yml`** — 4 jobs rouges :
- `bandit` : 20 findings (14 Low, 6 Medium, 0 High ; confiance High×20) → exit 1.
  Le job échoue sur **tout** finding (pas de seuil). Le lot 1.3 (SQL f-string) en
  retirera une partie mais ne le rendra pas vert seul. **Hors périmètre nuit** (c'est
  `security.yml`, pas le gate).
- `pip-audit` : CVEs réelles — `starlette 0.52.1` (CVE-2026-48817, CVE-2026-48818,
  fix 1.1.0), `vcrpy 8.1.1` (GHSA-rpj2-4hq8-938g, fix 8.2.1). Le mandat **interdit
  toute montée de version cette nuit** → documenté (posture prod 4.1), pas corrigé.
- `CodeQL (python)` : rouge (analyse) — probablement upload SARIF sur repo privé sans
  GitHub Advanced Security. Structurel.
- `trivy (container)` : `Run Trivy` + `Upload Trivy SARIF` rouges — même cause SARIF.

**`supply-chain.yml`** — `provenance / final` rouge : le générateur SLSA **halte
volontairement** sur repo privé (« Repository is private … Set 'private-repository'
to override ») + exit 127 dans le générateur. Structurel, lié au repo privé.

**Lecture** : ces rouges tiennent à des réglages de dépôt (Advanced Security, override
SLSA private-repo) et à des CVEs qu'on n'a pas le droit de patcher cette nuit — pas à
une régression de code. Ils sont **consignés pour Amadou** (posture prod, lot 4.1) et
ne déclenchent pas STOP-THE-LINE, qui lit le workflow *CI* (le gate). Dependabot est
déjà configuré (branches `dependabot/*` ouvertes pour ces CVEs).

### Mécanique de merge (worktree `agents/claude`)

`main` est checked-out dans `/tessera`, donc pas de `checkout main` ici. Chaque lot :
`git fetch origin` → `git checkout -b claude/<sujet> origin/main` → edits →
`make gate` (une passe) → commit ciblé (jamais `git add -A`) →
`git push -u origin claude/<sujet>` + `git push origin HEAD:main` (ff). Branch
protection **absente** (confirmé 403 GitHub Pro), ff-push direct autorisé.

---

## Log par lot

### Lot 0 — Journal + état de base
Ce fichier. Ouverture du run, état de base mesuré et consigné ci-dessus.
