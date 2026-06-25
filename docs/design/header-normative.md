# Header — normative (source de vérité)

Statut : normatif. Tout header de l'application DOIT être rendu par **un seul
composant paramétré**, `webapp/frontend/components/layout/app-header.tsx`
(`<AppHeader>`). Il n'y a **pas de header par-page** et **pas un header identique
partout** : il y a **un shell unique, trois variantes par PLAN**.

Cette page corrige l'état antérieur (« pas de normative » + headers éclatés par
surface : `topbar.tsx`, `<header>` inline du lanceur, `<header>` inline d'espaces,
header de la console recouvrement).

## 1. Principe

> Le header **REFLÈTE** le contexte ; le **RBAC GATE** l'accès.

Le header n'est jamais un mécanisme de sécurité : il affiche ce que le rôle
courant permet, mais ne remplace aucun garde-fou. On ne doit jamais affaiblir une
gate pour satisfaire l'affichage.

## 2. Shell unique — trois zones

```
┌───────────────────────────────────────────────────────────────────────────┐
│  GAUCHE                     CENTRE                                    DROITE │
│  marque / titre             (titre+sous-titre selon plan)   contextuel ‖ global │
└───────────────────────────────────────────────────────────────────────────┘
```

- **GAUCHE** — la marque (un seul *mark*, voir §5) **ou** le titre quand la
  marque vit déjà dans un rail latéral (cockpit, console recouvrement).
- **CENTRE** — titre + sous-titre. **Absent sur le lanceur.**
- **DROITE** — **ordre FIXE, identique partout** :

  ```
  [ chips statut · recherche · notifs · aide · bascule contexte · Voir le produit ]  ‖  [ langue · thème · compte ]
  ```

  - **Avant `‖` = contextuel** (par plan ; voir §3). Peut être vide.
  - **Après `‖` = global** (partout, **même ordre** : `langue · thème · compte`).

Le groupe global est rendu dans le **même ordre sur chaque surface**, sans
exception. C'est l'invariant le plus important de cette norme.

## 3. Variantes par plan

| Plan | Marque (gauche) | Titre (centre) | Contextuel (droite, avant `‖`) | Global (après `‖`) | Auth |
|------|-----------------|----------------|--------------------------------|--------------------|------|
| **LANCEUR** | marque, pas de titre | — | *rien* | langue · thème · compte | `demo` |
| **COCKPIT** | (rail latéral) → titre | titre + sous-titre | chips Opérationnel/modèle · recherche · notifs · aide · explorer les espaces · « Voir le produit » (opérateur) | langue · thème · compte | `gated` |
| **BUSINESS** | marque (ou `lead`) | titre selon surface | *rien* (ou minimal) | langue · thème · compte | `optional` *(override `gated` si la surface est déjà gated, ex. console recouvrement)* |

« BUSINESS » couvre **espaces** et la **console recouvrement**. Le produit client
(`/produit`) est **hors périmètre** : il porte sa propre identité de banque
fictive (« Crédit Aurore ») et garde son chrome bancaire ; l'illusion du portail
client prime.

Le cockpit et la console recouvrement portent la marque dans leur **rail latéral**,
donc la zone gauche du header montre le **titre** (jamais une seconde marque
redondante collée au rail).

## 4. Auth — qui voit quoi

L'affordance compte (`<AuthControl context=…>`) change **uniquement son repli
anonyme** ; connecté, c'est toujours le même menu (QUI + Déconnexion).

| Contexte | Anonyme | Connecté |
|----------|---------|----------|
| `optional` (espaces, produit) | **« Se connecter »** (auth optionnelle qui débloque : anonymous → customer) | menu (QUI + Déconnexion) |
| `gated` (cockpit, console recouvrement) | **rien** — la route est déjà gardée, l'anonyme n'y arrive jamais. **Jamais « Se connecter ».** | menu (QUI + Déconnexion) |
| `demo` (lanceur) | **session de DÉMONSTRATION étiquetée** (pas un vrai login) | menu (QUI + Déconnexion) |

**« Se connecter » n'apparaît donc QUE sur produit/espaces.** Sur le cockpit et la
console recouvrement, l'utilisateur est déjà authentifié (gate RBAC), donc le
header montre QUI il est + Déconnexion, jamais une invite à se connecter.

## 5. Marque — un seul mark, une seule couleur

- **Un seul *mark*** partout : `components/brand/tessera-logo.tsx` (`<TesseraLogo>`,
  le lockup), et sa forme compacte neutre `TesseraMark` (rail replié) **dérivée du
  même mark**.
- **Une seule couleur de marque**, appliquée partout. Fini « vert-cockpit vs
  cyan-lanceur » : ces couleurs sont des **accents de surface**, pas la marque.
- **Aucun statut encodé dans la marque.** Le vert « opérationnel » appartient aux
  **chips de statut**, jamais au logo (voir le standard marque & icônes).

## 6. Invariants vérifiables

1. Un seul composant header (`<AppHeader plan=…>`) — pas de `<header>` ad hoc par
   surface.
2. Le groupe global droite est dans le **même ordre** (`langue · thème · compte`)
   sur **toutes** les surfaces.
3. « Se connecter » n'apparaît **que** sur produit/espaces.
4. Un seul *mark* de marque, une seule couleur de marque.
5. `tsc` + `lint` + tests verts.
</content>
</invoke>
