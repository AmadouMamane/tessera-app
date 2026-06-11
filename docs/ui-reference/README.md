# Tessera UI reference images

These screenshots are visual references for Codex while implementing the Tessera redesign.

## Priority references

Use these first:

1. `00-overview-live-final.png` — target **Vue d’ensemble / Live** state. Live must stay compact.
2. `01-overview-replay-expanded-final.png` — target **Vue d’ensemble / Historique-Replay expanded** state.
3. `04-inbox-a-traiter-control-cases.png` — target **À traiter** / Control Cases inbox.
4. `05-quality-ai-dashboard.png` — target **Qualité IA** dashboard.
5. `11-replay-shadow-time-travel-dashboard.png` — target detailed time-travel / replay interactions.
6. `12-release-control-dashboard.png` — target Release Control.

## Important implementation rules

These images are visual references only. The written product spec wins if there is any conflict.

Preserve:
- dark premium Tessera style;
- sidebar grouped as Produit / Cockpit / Agir / Prouver / Configurer;
- user identity block: Amadou D. · ML Engineer · Admin · Prod · Crédit Aurore · FR · on-prem;
- Control Case as the central operational object;
- Live compact temporal rail by default;
- expanded time-travel rail only after clicking “Relire à T”;
- evidence, audit and role affordances on action-oriented cards;
- dense but readable enterprise dashboard layout.

Do not copy image artifacts blindly:
- Do **not** duplicate “Générer evidence pack”. It should appear once as a global CTA.
- In local cards, use “Voir le pack courant”, “Ouvrir les preuves”, or “Voir Evidence Pack”.
- Keep Live mode compact: `Live · Données en temps réel · Période · Relire à T`.
- In Historique / Replay mode, show comparer à, baseline, scrubber, badge “État relu au …”, Rejouer and Retour au Live.
- Time-travel is a second state of the same page, not a separate page.

## Suggested page mapping

- `00-overview-live-final.png` -> Cockpit / Vue d’ensemble / Live
- `01-overview-replay-expanded-final.png` -> Cockpit / Vue d’ensemble / Replay expanded
- `04-inbox-a-traiter-control-cases.png` -> Produit / À traiter
- `05-quality-ai-dashboard.png` -> Cockpit / Qualité IA
- `06-security-privacy-dashboard.png` -> Cockpit / Sécurité & Privacy
- `07-compliance-dashboard.png` -> Cockpit / Conformité
- `08-reliability-cost-dashboard.png` -> Cockpit / Fiabilité & coût
- `09-improvement-continuous-dashboard.png` -> Cockpit / Amélioration
- `10-incidents-playbooks-dashboard.png` -> Agir / Incidents & playbooks
- `11-replay-shadow-time-travel-dashboard.png` -> Agir / Replay, shadow & time travel
- `12-release-control-dashboard.png` -> Agir / Release Control
- `13-curation-eval-set-dashboard.png` -> Agir / Curation eval set
- `14-signal-control-architecture.png` -> Architecture / Signal Catalog concept
