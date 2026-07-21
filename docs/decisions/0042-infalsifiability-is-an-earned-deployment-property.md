# 0042 — « Registre infalsifiable » est une propriété gagnée du déploiement

**Statut : accepté — 2026-07-21**
**Complète :** ADR 0015 et ADR 0022
**Remplace uniquement :** ADR 0022 R8 pour les environnements exposés ; le scellement reste hors
du chemin des requêtes et n'empêche jamais l'écriture du journal, mais sa configuration devient
une condition de démarrage en staging/production.

## Contexte

Tessera emploie « registre infalsifiable » dans son parcours pédagogique. Une chaîne de hachage
seule rend une modification visible tant que l'ancien sommet reste connu ; un administrateur qui
contrôle à la fois le stockage et l'application pourrait cependant réécrire la chaîne et présenter
un nouveau sommet. Le mot ne peut donc être tenu commercialement que si le sommet est régulièrement
ancré auprès d'un tiers et si la preuve reste vérifiable sans Tessera.

ADR 0022 a déjà construit le bon mécanisme : jeton d'horodatage RFC 3161 sur le hash du sommet,
racine de confiance épinglée, vérification OpenSSL hors ligne, état dynamique et dégradation honnête.
Le trou restant était opérationnel : le provider `none` restait autorisé partout et Terraform ne
provisionnait ni endpoint TSA ni certificat. La vitrine pouvait donc prononcer la promesse sans
que le déploiement soit capable de la gagner.

## Décision

### 1. Propriété technique annoncée

Dans le périmètre de menace publié, « infalsifiable » signifie :

> toute altération, suppression, substitution ou réécriture postérieure au scellement du journal
> est détectable indépendamment, en comparant sa chaîne de hachage au jeton RFC 3161 signé par un
> prestataire de confiance qualifié extérieur à Tessera.

Ce n'est ni une permission de modifier les octets ni un adjectif cosmétique. C'est une propriété
observable composée de quatre preuves :

1. intégrité de contenu de toute la chaîne ;
2. ordre linéaire ou divergence explicitement attestée ;
3. dernier jeton RFC 3161 vérifié contre une racine de confiance épinglée ;
4. service d'horodatage qualifié et jeton encore frais selon la cadence publiée.

Le backend est la seule autorité du verdict. `scelle_opposable` — et toute copie qui emploie
« infalsifiable » comme état présent — n'est constructible que lorsque ces quatre preuves sont
vraies. Le provider, l'instant du dernier scellement, le sommet scellé et la fraîcheur restent
visibles. Un écran en cours de vérification, sans jeton, périmé ou divergent ne reçoit jamais ce
verdict.

### 2. Posture de déploiement

- `local` et `ci` conservent `seal_provider=none` afin de rester hermétiques. Ils montrent l'état
  réellement calculé, jamais un vert simulé.
- `staging` et `production` refusent de démarrer sans : provider `rfc3161`, URL TSA HTTPS, certificat
  de vérification présent et lisible, déclaration `qualified=true`, intervalle positif, budget de
  fraîcheur compris entre un et deux intervalles et vérification intégrale au moins aussi fréquente
  que le scellement.
- Terraform monte le certificat depuis Secret Manager et injecte explicitement toute la posture.
  Le certificat est fourni hors état Terraform ; l'URL est une variable obligatoire.
- Le scheduler tente un cycle dès son démarrage puis poursuit toutes les `τ` secondes. Une panne TSA
  ne bloque ni une requête ni une écriture : elle empêche simplement le verdict d'être gagné et
  déclenche l'état observable dégradé.

La valeur `seal_tsa_qualified=true` est une déclaration opérateur, pas une preuve autonome. Le
runbook impose de choisir le service exact dans la liste de confiance UE et de conserver cette
vérification dans le dossier fournisseur. Un prochain lot pourra automatiser la résolution de la
Trusted List ; en attendant, le certificat épinglé et le contrôle d'approvisionnement sont les deux
témoins distincts.

### 3. Preuve transportable

Le paquet de preuve exporte le sommet scellé, le jeton RFC 3161, le certificat public de validation,
les métadonnées de provider et la commande OpenSSL déterministe. Un auditeur doit pouvoir conclure
sans accès à Tessera, à sa base, à ses secrets ou à son code source. Aucune clé HMAC contrôlée par
Tessera ne compte comme scellement externe.

## Fondement primaire

- [RFC 3161 — Internet X.509 Public Key Infrastructure Time-Stamp Protocol](https://www.rfc-editor.org/rfc/rfc3161) : le TSA est un tiers de confiance qui fournit une preuve d'existence d'une donnée à un instant.
- [Règlement eIDAS, article 41](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014R0910) : l'horodatage électronique qualifié bénéficie d'une présomption d'exactitude de la date/heure et d'intégrité des données liées.
- [Commission européenne — listes de confiance](https://digital-strategy.ec.europa.eu/en/policies/eu-trusted-lists) : un service n'est qualifié que s'il figure comme tel dans une liste nationale de confiance.
- [Navigateur officiel des listes de confiance UE/EEE](https://eidas.ec.europa.eu/efda/tl-browser/) : source opérationnelle pour sélectionner et contrôler le service d'horodatage qualifié.

## Conséquences

- Oui, Tessera conserve et construit l'affirmation « registre infalsifiable » ; elle devient plus
  forte parce que son verdict est impossible à fabriquer sans témoin externe vérifié.
- Un déploiement exposé mal configuré échoue tôt, avec la liste exacte des prérequis manquants.
- Une panne TSA reste un incident visible et mesurable, pas une panne du support bancaire.
- La qualification juridique dépend du service réellement acheté et inscrit sur la Trusted List ;
  le code prépare et vérifie la preuve, il ne peut pas auto-attribuer un statut réglementaire au
  fournisseur.
- Le secret Terraform historique `audit_signing_key` ne doit jamais être présenté comme ce sceau :
  une clé contrôlée par Tessera n'est pas un tiers.

## Vérification

- tests unitaires de matrice `local/ci/staging/production` et de chaque prérequis fail-closed ;
- ratchet Terraform sur les variables, secrets montés et deux images déployées ;
- vérification OpenSSL du paquet exporté ;
- smoke déployé sur `/healthz`, `/api/healthz` et `/audit/integrity`, avec exigence
  `badge=scelle_opposable` avant qu'une vitrine publique n'annonce l'état présent.
