"""CLASS B — a rendered string reaches the operator through a translation mechanism.

Tessera claims three languages on its front page. The claim is honoured by `next-intl`
catalogues under `webapp/frontend/messages/{fr,de,en}.json`… and undermined by two things the
localization endpoint cannot see, because it counts catalogue keys and a string that never
became a key is invisible to it:

* **307 bare French literals** rendered straight into the DOM. A German operator reads them in
  French. `/observability/localization` reports 100 % complete while they are on screen —
  ADR 0026's failure exactly: it interrogates the catalogues, not the page.
* **342 `pick(locale, fr, de, en)` calls** — a SECOND, inline mechanism. It works, and it is
  not a defect in itself; it is a second place to look, and a second place to forget.

This ratchet holds both populations at their exact measured size on 2026-08-01 so they can
only shrink, and imports its detector from `scripts/audit/scan_i18n_mechanism.py` rather than
re-deriving it — a ratchet that re-implements its probe is a third copy of the derivation this
chantier exists to remove.

Lot 7 of `docs/status/coherence-mesuree-run.md` settles the fate of both.
"""

from __future__ import annotations

from collections import Counter

from scripts.audit.scan_i18n_mechanism import scan, scan_text

#: Files rendering French with no mechanism, at their exact size on 2026-08-01.
#:
#: Not all 307 are the same debt, and the map deliberately does not pretend otherwise:
#:
#: * `recouvrement-assistant-backend.ts` (109) is a simulated French banking back-office —
#:   its strings are the *content being demonstrated*, closer to corpus than to chrome. It is
#:   the largest entry and the least likely to become catalogue keys.
#: * `credit-aurore-logo.tsx` (1) is a brand name. "Crédit Aurore" does not translate.
#: * everything else is cockpit chrome an operator reads, and is a genuine gap.
#:
#: The distinction is settled in Lot 7. Until then every one of them is held DOWNWARD-ONLY,
#: which is the only property a ratchet needs to be worth having.
#:
#: 307 → 306 on the way through Lot 2: `signals-table.tsx` built its refusal detail as
#: ``sous ${pct(under)}`` — a French literal in a trilingual component, read in French by a
#: German operator. It is now a `controlDetail` key like every other supporting line. One
#: string, and it only left because the row around it was being rewritten for another reason;
#: that is the pace this debt actually moves at, which is why it is counted.
_FROZEN_BARE_FRENCH: dict[str, int] = {
    "components/recouvrement/recouvrement-assistant-backend.ts": 109,
    "components/observability/workflow-runs-panel.tsx": 42,
    "components/recouvrement/recouvrement-product-experience.tsx": 27,
    "components/product/credit-aurore-mes-comptes-host.tsx": 18,
    "components/agent/agent-console.tsx": 15,
    "components/agent/agent-historique.tsx": 15,
    "components/overview/temporal-rail.tsx": 11,
    "components/chat/chat-room.tsx": 10,
    "components/agent/agent-cross-links.tsx": 8,
    "lib/recouvrement/artifact-status.ts": 8,
    "components/surveiller/signal-command-bar.tsx": 6,
    "components/overview/overview-dashboard.tsx": 5,
    "components/agent/agent-evaluations.tsx": 4,
    "components/agent/agent-synthese.tsx": 4,
    "components/agent/agent-configurations.tsx": 3,
    "components/agent/evaluation-tabs.tsx": 3,
    "components/landing/landing-launcher.tsx": 3,
    "components/proofs/etat-a-date.tsx": 3,
    "components/observability/signals-table.tsx": 1,
    "lib/api/sse.ts": 2,
    "app/[locale]/produit/page.tsx": 1,
    "app/api/chat/route.ts": 1,
    "components/agent/agent-prompts.tsx": 1,
    "components/agent/new-agent-button.tsx": 1,
    "components/brand/credit-aurore-logo.tsx": 1,
    "components/layout/model-badge.tsx": 1,
    "components/proofs/proofs-overview.tsx": 1,
    "i18n/routing.ts": 1,
    "lib/api/recouvrement-assistant.ts": 1,
}

#: The second mechanism, held at its size. It may shrink (calls migrating to the catalogues);
#: it may not grow, because a third place to look is not a thing this codebase needs.
_FROZEN_PICK_CALLS = 342

#: Anti-vacuity. The scan must actually see a tree: ~300 sources, 2 in-TS catalogues. A floor
#: under each is what separates "nothing is wrong" from "the walk found no files" — the
#: distinction three of this repo's guard-rails have already got wrong (ADR 0026).
_MIN_SOURCES = 250
_MIN_CATALOGUES = 2


def test_scan_sees_a_tree() -> None:
    """A witness that cannot see may never report ok."""
    from scripts.audit.scan_i18n_mechanism import sources

    assert len(sources()) >= _MIN_SOURCES
    _, catalogues, _ = scan()
    assert len(catalogues) >= _MIN_CATALOGUES


def test_no_bare_french_outside_the_frozen_files() -> None:
    """A new file rendering French without a mechanism is refused outright."""
    hits, _, _ = scan()
    offenders = sorted({str(h["file"]) for h in hits} - set(_FROZEN_BARE_FRENCH))
    assert offenders == [], (
        "\nthese files render French with no translation mechanism:\n  "
        + "\n  ".join(offenders)
        + "\n\nuse next-intl (`useTranslations`) so /observability/localization can SEE the "
        "string.\nA catalogue that does not contain it reports 100 % complete while a German "
        "operator\nreads French on screen."
    )


def test_frozen_bare_french_holds_its_exact_size() -> None:
    """Downward-only: fixing a file means lowering its number here, on the record."""
    hits, _, _ = scan()
    actual = {
        f: n for f, n in Counter(str(h["file"]) for h in hits).items() if f in _FROZEN_BARE_FRENCH
    }
    assert actual == _FROZEN_BARE_FRENCH, (
        "\nthe bare-French population moved. If it SHRANK, excellent — lower the numbers in\n"
        f"_FROZEN_BARE_FRENCH so the debt goes down on the record (it stands at "
        f"{sum(_FROZEN_BARE_FRENCH.values())}).\nIf it GREW, a string was rendered without a "
        "mechanism: route it through next-intl."
    )


def test_the_second_mechanism_does_not_grow() -> None:
    """`pick()` is legitimate and duplicated. It may shrink; it may not spread."""
    _, _, picks = scan()
    assert picks <= _FROZEN_PICK_CALLS, (
        f"\n{picks} `pick(locale, …)` calls, up from {_FROZEN_PICK_CALLS}. This is the SECOND\n"
        "translation mechanism — prefer next-intl for anything new, so there is one place to\n"
        "look when a locale is wrong."
    )
    assert picks == _FROZEN_PICK_CALLS, (
        f"\n`pick()` calls fell to {picks} from {_FROZEN_PICK_CALLS} — good. Lower "
        "_FROZEN_PICK_CALLS\nso the second mechanism's retreat is recorded."
    )


def test_the_detector_has_teeth() -> None:
    """Mutation-test the witness itself, in all three directions.

    The first version of this detector reported 780 and was wrong twice; the version before
    the current one silently exempted `agent-console.tsx` — a file that genuinely hardcodes 15
    strings — because it recognised locale catalogues by their *body* instead of their *path*.
    Only the negative control caught it. These three assertions are that control, kept.
    """
    # [+] a bare French literal MUST be reported.
    bare, _ = scan_text("components/x/panel.tsx", 'const label = "Résumé de la réponse";')
    assert [h["literal"] for h in bare] == ["Résumé de la réponse"]

    # [-] the same string inside `pick(locale, …)` must NOT be — it is translated.
    picked, n_picks = scan_text(
        "components/x/panel.tsx",
        'const label = pick(locale, "Résumé", "Zusammenfassung", "Summary");',
    )
    assert picked == []
    assert n_picks == 1

    # [-] …and a per-locale catalogue file is a catalogue, not hardcoded text.
    catalogued, _ = scan_text(
        "components/x/x-product-copy.ts", 'export const copy = { fr: { a: "Résumé" } };'
    )
    assert catalogued == []
