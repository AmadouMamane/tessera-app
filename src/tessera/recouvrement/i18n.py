"""Deterministic presentation catalogue for the structured Recouvrement workflow.

Business identifiers, reason codes and status values stay language-neutral. Only the
human-facing strings in artifacts, cards and replies cross this seam. Keeping the
translation before audit emission means the reply shown to an operator is the reply
witnessed by the business event.
"""

# The catalogue intentionally keeps each source/translation regex on one line so reviewers can
# compare the three sentences atomically; splitting raw patterns makes those reviews error-prone.
# ruff: noqa: E501

from __future__ import annotations

import re
from typing import TYPE_CHECKING, TypeVar, cast

if TYPE_CHECKING:
    from tessera.agent.recouvrement import RecouvrementArtifact
    from tessera.recouvrement.message_templates import RecouvrementLanguage

T = TypeVar("T")

_COPY: dict[str, tuple[str, str]] = {
    "appel sortant": ("outbound call", "ausgehender Anruf"),
    "email de confirmation": ("confirmation email", "Bestätigungs-E-Mail"),
    "amiable et factuel": ("courteous and factual", "freundlich und sachlich"),
    "Aucun lien de paiement créé": ("No payment link created", "Kein Zahlungslink erstellt"),
    "Aucun lien de paiement créé ou envoyé": (
        "No payment link created or sent",
        "Kein Zahlungslink erstellt oder versendet",
    ),
    "Aucun lien de paiement envoyé": ("No payment link sent", "Kein Zahlungslink versendet"),
    "Aucun message client généré": (
        "No customer message generated",
        "Keine Kundennachricht erstellt",
    ),
    "Aucun message envoyé": ("No message sent", "Keine Nachricht versendet"),
    "Aucun appel préparé": ("No call prepared", "Kein Anruf vorbereitet"),
    "Aucun paiement initié": ("No payment initiated", "Keine Zahlung ausgelöst"),
    "Aucun échéancier créé": ("No payment plan created", "Kein Ratenplan erstellt"),
    "Aucune action exécutée": ("No action executed", "Keine Aktion ausgeführt"),
    "Aucune action client exécutée": (
        "No customer action executed",
        "Keine Kundenaktion ausgeführt",
    ),
    "Aucun artefact métier modifié": (
        "No business artifact changed",
        "Kein Geschäftsartefakt geändert",
    ),
    "Aucune donnée hors dossier ajoutée": (
        "No data added from outside the case",
        "Keine Daten außerhalb des Vorgangs hinzugefügt",
    ),
    "Aucune menace ni pression injustifiée": (
        "No threat or undue pressure",
        "Keine Drohung oder unangemessener Druck",
    ),
    "Aucune validation d'échéancier requise dans ce brouillon": (
        "No payment-plan approval required for this draft",
        "Keine Ratenplanfreigabe für diesen Entwurf erforderlich",
    ),
    "Action refusée avant tout effet métier.": (
        "Action refused before any business effect.",
        "Aktion vor jeder Geschäftswirkung abgelehnt.",
    ),
    "Accès refusé avant exécution de la règle métier.": (
        "Access refused before the business rule was executed.",
        "Zugriff vor Ausführung der Geschäftsregel abgelehnt.",
    ),
    "La surface demandée n'est pas autorisée pour le workflow Recouvrement.": (
        "The requested surface is not authorised for the Collections workflow.",
        "Die angeforderte Oberfläche ist für den Inkasso-Workflow nicht zulässig.",
    ),
    "Cette surface n'est pas autorisée pour les actions Recouvrement. Aucune action client n'a été exécutée.": (
        "This surface is not authorised for Collections actions. No customer action was executed.",
        "Diese Oberfläche ist für Inkasso-Aktionen nicht zulässig. Es wurde keine Kundenaktion ausgeführt.",
    ),
    "Cette surface n'est pas autorisée pour l'assistant Recouvrement. Ouvrez le dossier depuis l'espace Recouvrement ou depuis le cockpit opérateur.": (
        "This surface is not authorised for the Collections assistant. Open the case from the Collections workspace or the operator cockpit.",
        "Diese Oberfläche ist für den Inkasso-Assistenten nicht zulässig. Öffnen Sie den Vorgang im Inkasso-Arbeitsbereich oder im Operator-Cockpit.",
    ),
    "Accord client nécessaire": ("Customer agreement required", "Kundenzustimmung erforderlich"),
    "Accord client nécessaire avant création": (
        "Customer agreement required before creation",
        "Kundenzustimmung vor der Erstellung erforderlich",
    ),
    "Accord client requis": ("Customer agreement required", "Kundenzustimmung erforderlich"),
    "Accord client requis avant mise en place": (
        "Customer agreement required before setup",
        "Kundenzustimmung vor der Einrichtung erforderlich",
    ),
    "Action à conserver dans un cadre amiable et tracé": (
        "Keep the action courteous and traceable",
        "Aktion freundlich und nachvollziehbar halten",
    ),
    "Ajuster la durée": ("Adjust duration", "Laufzeit anpassen"),
    "Comparer les options": ("Compare options", "Optionen vergleichen"),
    "Confirmer les moyens disponibles dans le dossier, puis préparer un échéancier indicatif si une validation est obtenue.": (
        "Confirm the methods available in the case, then prepare an indicative payment plan if approval is obtained.",
        "Die im Vorgang verfügbaren Zahlungsarten bestätigen und anschließend bei erteilter Freigabe einen unverbindlichen Ratenplan vorbereiten.",
    ),
    "Conserver l'artefact": ("Keep artifact", "Artefakt beibehalten"),
    "Retour au dossier": ("Back to case", "Zurück zum Vorgang"),
    "Ouvrir l'espace Recouvrement": (
        "Open the Collections workspace",
        "Inkasso-Arbeitsbereich öffnen",
    ),
    "Retourner au cockpit opérateur": (
        "Return to the operator cockpit",
        "Zum Operator-Cockpit zurückkehren",
    ),
    "Voir la demande": ("View request", "Anfrage anzeigen"),
    "Annuler": ("Cancel", "Abbrechen"),
    "Confirmer l'insertion": ("Confirm insertion", "Einfügen bestätigen"),
    "Voir le dossier": ("View case", "Vorgang anzeigen"),
    "Voir le rappel préparé": (
        "View prepared callback",
        "Vorbereiteten Rückruf anzeigen",
    ),
    "Rédiger un email": ("Draft an email", "E-Mail entwerfen"),
    "Action locale uniquement": ("Local action only", "Nur lokale Aktion"),
    "Validation préparée": ("Approval request prepared", "Freigabeanfrage vorbereitet"),
    "Insertion préparée": ("Insertion prepared", "Einfügen vorbereitet"),
    "Écriture définitive : non exécutée": (
        "Final write: not executed",
        "Endgültige Änderung: nicht ausgeführt",
    ),
    "Artefact courant conservé": (
        "Current artifact preserved",
        "Aktuelles Artefakt beibehalten",
    ),
    "Aucun nouveau brouillon généré": (
        "No new draft generated",
        "Kein neuer Entwurf erstellt",
    ),
    "Aucune écriture définitive exécutée": (
        "No final write executed",
        "Keine endgültige Änderung ausgeführt",
    ),
    "Rappel demain préparé": ("Callback for tomorrow prepared", "Rückruf für morgen vorbereitet"),
    "Événement calendrier réel : non créé": (
        "Real calendar event: not created",
        "Realer Kalendereintrag: nicht erstellt",
    ),
    "Aucun événement calendrier créé": (
        "No calendar event created",
        "Kein Kalendereintrag erstellt",
    ),
    "Aucun appel préparé hors plage": (
        "No call prepared outside the permitted window",
        "Kein Anruf außerhalb des zulässigen Zeitfensters vorbereitet",
    ),
    "Copier le message": ("Copy message", "Nachricht kopieren"),
    "Dossier déjà dans la file prioritaire Recouvrement": (
        "Case already in the priority collections queue",
        "Vorgang bereits in der priorisierten Inkassowarteschlange",
    ),
    "Effet externe : aucun": ("External effect: none", "Externe Wirkung: keine"),
    "Contexte utilisé : snapshot RC-2048 centralisé": (
        "Context used: central RC-2048 snapshot",
        "Verwendeter Kontext: zentraler RC-2048-Snapshot",
    ),
    "Engagement de paiement non respecté": (
        "Payment commitment not met",
        "Zahlungszusage nicht eingehalten",
    ),
    "Insérer dans le dossier": ("Insert into case", "In den Vorgang einfügen"),
    "Insérer une note préparée dans le dossier": (
        "Insert a prepared note into the case",
        "Vorbereitete Notiz in den Vorgang einfügen",
    ),
    "Le canal recommandé est l'appel sortant.": (
        "The recommended channel is an outbound call.",
        "Der empfohlene Kanal ist ein ausgehender Anruf.",
    ),
    "Message préparé sans envoi": (
        "Message prepared but not sent",
        "Nachricht vorbereitet, aber nicht versendet",
    ),
    "Modifier le message": ("Edit message", "Nachricht bearbeiten"),
    "Moyens disponibles à confirmer dans le dossier": (
        "Available methods must be confirmed in the case",
        "Verfügbare Zahlungsarten müssen im Vorgang bestätigt werden",
    ),
    "Ne pas citer de moyen de paiement spécifique sans donnée confirmée.": (
        "Do not name a specific payment method without confirmed data.",
        "Keine konkrete Zahlungsart ohne bestätigte Daten nennen.",
    ),
    "Ne pas contacter hors plage autorisée": (
        "Do not make contact outside the permitted window",
        "Nicht außerhalb des zulässigen Zeitfensters kontaktieren",
    ),
    "Ne pas créer d'échéancier sans validation": (
        "Do not create a payment plan without approval",
        "Keinen Ratenplan ohne Freigabe erstellen",
    ),
    "Ne pas envoyer de message automatiquement": (
        "Do not send a message automatically",
        "Keine Nachricht automatisch versenden",
    ),
    "Ne pas exécuter d'écriture définitive dans le dossier": (
        "Do not perform a final write to the case",
        "Keine endgültige Änderung am Vorgang ausführen",
    ),
    "Options de règlement préparées sans initier de paiement": (
        "Payment options prepared without initiating payment",
        "Zahlungsoptionen vorbereitet, ohne eine Zahlung auszulösen",
    ),
    "Options à confirmer selon les moyens disponibles dans le dossier.": (
        "Options must be confirmed against the methods available in the case.",
        "Optionen müssen anhand der im Vorgang verfügbaren Zahlungsarten bestätigt werden.",
    ),
    "Planifier un rappel demain": ("Schedule a call tomorrow", "Rückruf für morgen planen"),
    "Préparer le message client": ("Prepare customer message", "Kundennachricht vorbereiten"),
    "Préparer un échéancier indicatif soumis à validation": (
        "Prepare an indicative payment plan subject to approval",
        "Unverbindlichen Ratenplan zur Freigabe vorbereiten",
    ),
    "Proposer un échéancier": ("Propose a payment plan", "Ratenplan vorschlagen"),
    "Reporter le contact": ("Reschedule contact", "Kontakt verschieben"),
    "Risque de nouvelle absence de réponse": (
        "Risk of another unanswered contact",
        "Risiko einer erneuten ausbleibenden Antwort",
    ),
    "Rédiger un email de confirmation": (
        "Draft a confirmation email",
        "Bestätigungs-E-Mail entwerfen",
    ),
    "Rédiger une relance": ("Draft a reminder", "Mahnung entwerfen"),
    "Rédiger une relance amiable": (
        "Draft a courteous reminder",
        "Freundliche Mahnung entwerfen",
    ),
    "Soumettre à validation": ("Submit for approval", "Zur Freigabe einreichen"),
    "Validation interne requise avant proposition": (
        "Internal approval required before proposal",
        "Interne Freigabe vor dem Vorschlag erforderlich",
    ),
    "Validation interne requise avant proposition au client": (
        "Internal approval required before proposing to the customer",
        "Interne Freigabe vor dem Kundenvorschlag erforderlich",
    ),
    "Validation interne requise avant toute option d'échéancier": (
        "Internal approval required for any payment-plan option",
        "Interne Freigabe für jede Ratenplanoption erforderlich",
    ),
    "Validation requise avant proposition": (
        "Approval required before proposal",
        "Freigabe vor dem Vorschlag erforderlich",
    ),
    "Validation requise si une option d'échéancier est retenue": (
        "Approval required if a payment-plan option is selected",
        "Freigabe erforderlich, wenn eine Ratenplanoption gewählt wird",
    ),
    "Voir la règle de contact": ("View contact rule", "Kontaktregel anzeigen"),
    "Vérifier la règle de contact": ("Check contact rule", "Kontaktregel prüfen"),
    "Vérifier une règle": ("Check a rule", "Regel prüfen"),
    "Vérifier le canal de contact puis préparer une relance amiable.": (
        "Check the contact channel, then prepare a courteous reminder.",
        "Kontaktkanal prüfen und anschließend eine freundliche Mahnung vorbereiten.",
    ),
    "Échéancier non créé": ("Payment plan not created", "Ratenplan nicht erstellt"),
    "Statut : validation requise avant proposition": (
        "Status: approval required before proposal",
        "Status: Freigabe vor dem Vorschlag erforderlich",
    ),
    "Solution d'échelonnement évoquée uniquement comme option à valider": (
        "Instalment arrangement mentioned only as an option requiring approval",
        "Ratenzahlung nur als freigabepflichtige Option erwähnt",
    ),
    "Aucun moyen de paiement spécifique n'est disponible dans le snapshot RC-2048.": (
        "No specific payment method is available in the RC-2048 snapshot.",
        "Im Snapshot RC-2048 ist keine konkrete Zahlungsart verfügbar.",
    ),
    "Contact conseiller / rappel : préparer un échange pour confirmer la solution adaptée.": (
        "Adviser contact / callback: prepare a discussion to confirm the suitable solution.",
        "Beraterkontakt / Rückruf: Gespräch zur Bestätigung der passenden Lösung vorbereiten.",
    ),
    "Paiement partiel : montant et modalités à confirmer avant toute proposition.": (
        "Partial payment: amount and terms must be confirmed before any proposal.",
        "Teilzahlung: Betrag und Bedingungen vor jedem Vorschlag bestätigen.",
    ),
    "Paiement total : option à confirmer selon les moyens disponibles dans le dossier.": (
        "Full payment: confirm this option against the methods available in the case.",
        "Vollzahlung: Option anhand der im Vorgang verfügbaren Zahlungsarten bestätigen.",
    ),
    "Échéancier indicatif : possible uniquement après validation interne et accord client.": (
        "Indicative payment plan: possible only after internal approval and customer agreement.",
        "Unverbindlicher Ratenplan: nur nach interner Freigabe und Kundenzustimmung möglich.",
    ),
}


def _dynamic(text: str, language: RecouvrementLanguage) -> str | None:
    """Translate variable-bearing strings emitted by the deterministic builders."""
    en = language == "en"
    patterns: tuple[tuple[str, str, str], ...] = (
        (r"^Dossier : (.+)$", r"Case: \1", r"Vorgang: \1"),
        (r"^Client : (.+)$", r"Customer: \1", r"Kunde: \1"),
        (r"^Montant dû : (.+)$", r"Amount due: \1", r"Offener Betrag: \1"),
        (r"^Montant cohérent : (.+)$", r"Amount consistent: \1", r"Betrag konsistent: \1"),
        (
            r"^Montant total conservé : (.+)$",
            r"Total preserved: \1",
            r"Gesamtbetrag beibehalten: \1",
        ),
        (r"^Total : (.+)$", r"Total: \1", r"Gesamt: \1"),
        (r"^Retard : (\d+) jours$", r"Overdue: \1 days", r"Überfällig: \1 Tage"),
        (r"^Retard de (\d+) jours$", r"\1 days overdue", r"Seit \1 Tagen überfällig"),
        (
            r"^Durée demandée : (\d+) mois$",
            r"Requested duration: \1 months",
            r"Gewünschte Laufzeit: \1 Monate",
        ),
        (
            r"^Étalement demandé : (\d+) mois$",
            r"Requested instalment period: \1 months",
            r"Gewünschte Ratenlaufzeit: \1 Monate",
        ),
        (
            r"^Durée indicative : (\d+) mois$",
            r"Indicative duration: \1 months",
            r"Unverbindliche Laufzeit: \1 Monate",
        ),
        (
            r"^Mensualité indicative : (.+)$",
            r"Indicative monthly payment: \1",
            r"Unverbindliche Monatsrate: \1",
        ),
        (
            r"^(\d+) mensualités indicatives de (.+)$",
            r"\1 indicative monthly payments of \2",
            r"\1 unverbindliche Monatsraten à \2",
        ),
        (
            r"^Version indicative — (\d+) mois$",
            r"Indicative version — \1 months",
            r"Unverbindliche Version — \1 Monate",
        ),
        (
            r"^Échéancier indicatif — (\d+) mois$",
            r"Indicative payment plan — \1 months",
            r"Unverbindlicher Ratenplan — \1 Monate",
        ),
        (r"^Canal recommandé : (.+)$", r"Recommended channel: \1", r"Empfohlener Kanal: \1"),
        (r"^Canal conseillé : (.+)$", r"Suggested channel: \1", r"Empfohlener Kanal: \1"),
        (r"^Alternative : (.+)$", r"Alternative: \1", r"Alternative: \1"),
        (r"^Plage de contact : (.+)$", r"Contact window: \1", r"Kontaktzeitfenster: \1"),
        (r"^Plage autorisée : (.+)$", r"Permitted window: \1", r"Zulässiges Zeitfenster: \1"),
        (
            r"^Contact autorisé aujourd'hui : (.+)$",
            r"Contact permitted today: \1",
            r"Kontakt heute zulässig: \1",
        ),
        (
            r"^Appel à (.+) : non autorisé$",
            r"Call at \1: not permitted",
            r"Anruf um \1: nicht zulässig",
        ),
        (r"^Cadre de contact — (.+)$", r"Contact rules — \1", r"Kontaktregeln — \1"),
        (r"^Résumé du dossier — (.+)$", r"Case summary — \1", r"Vorgangszusammenfassung — \1"),
        (r"^Brouillon de relance — (.+)$", r"Reminder draft — \1", r"Mahnungsentwurf — \1"),
        (r"^Options de paiement — (.+)$", r"Payment options — \1", r"Zahlungsoptionen — \1"),
        (
            r"^Proposition d'échéancier — (.+)$",
            r"Payment-plan proposal — \1",
            r"Ratenplanvorschlag — \1",
        ),
        (
            r"^Accès non autorisé — (.+)$",
            r"Unauthorised access — \1",
            r"Unzulässiger Zugriff — \1",
        ),
        (
            r"^Action non autorisée — (.+)$",
            r"Unauthorised action — \1",
            r"Unzulässige Aktion — \1",
        ),
        (r"^Version (\d+) — (.+)$", r"Version \1 — \2", r"Version \1 — \2"),
        (r"^Ton (.+)$", r"Tone: \1", r"Ton: \1"),
        (r"^Artefact ciblé : (.+)$", r"Target artifact: \1", r"Zielartefakt: \1"),
        (r"^Statut : (.+)$", r"Status: \1", r"Status: \1"),
        (r"^Surface demandée : (.+)$", r"Requested surface: \1", r"Angeforderte Oberfläche: \1"),
        (
            r"^Cette action n'est pas disponible pour (.+)\. Aucune action client n'a été exécutée\.$",
            r"This action is not available for \1. No customer action was executed.",
            r"Diese Aktion ist für \1 nicht verfügbar. Es wurde keine Kundenaktion ausgeführt.",
        ),
        (
            r"^Soumission à validation préparée pour (.+)\. Aucune action client n'a été exécutée\.$",
            r"Approval submission prepared for \1. No customer action was executed.",
            r"Freigabeanfrage für \1 vorbereitet. Es wurde keine Kundenaktion ausgeführt.",
        ),
        (
            r"^Insertion préparée dans le dossier (.+)\. Aucune écriture définitive n'a encore été exécutée\.$",
            r"Insertion prepared in case \1. No final write has been executed yet.",
            r"Einfügen in Vorgang \1 vorbereitet. Es wurde noch keine endgültige Änderung ausgeführt.",
        ),
        (
            r"^Rappel préparé pour demain pour (.+)\. Aucun événement calendrier réel n'a été créé\.$",
            r"Callback prepared for tomorrow for \1. No real calendar event was created.",
            r"Rückruf für morgen für \1 vorbereitet. Es wurde kein realer Kalendereintrag erstellt.",
        ),
        (
            r"^Copie préparée localement pour (.+)\. Aucune action client n'a été exécutée\.$",
            r"Local copy prepared for \1. No customer action was executed.",
            r"Lokale Kopie für \1 vorbereitet. Es wurde keine Kundenaktion ausgeführt.",
        ),
        (
            r"^Action préparée pour (.+)\. Aucune action client n'a été exécutée\.$",
            r"Action prepared for \1. No customer action was executed.",
            r"Aktion für \1 vorbereitet. Es wurde keine Kundenaktion ausgeführt.",
        ),
        (
            r"^promesse de paiement non tenue le (.+)$",
            r"payment commitment dated \1 not met",
            r"Zahlungszusage vom \1 nicht eingehalten",
        ),
        (
            r"^Résumé du dossier (.+) mis à jour\.$",
            r"Case summary \1 updated.",
            r"Vorgangszusammenfassung \1 aktualisiert.",
        ),
        (
            r"^Options de paiement du dossier (.+) préparées\.$",
            r"Payment options for case \1 prepared.",
            r"Zahlungsoptionen für Vorgang \1 vorbereitet.",
        ),
        (
            r"^J'ai préparé un brouillon de relance amiable pour (.+)\. Aucun message n'a été envoyé\.$",
            r"I prepared a courteous reminder draft for \1. No message was sent.",
            r"Ich habe einen freundlichen Mahnungsentwurf für \1 vorbereitet. Keine Nachricht wurde versendet.",
        ),
        (
            r"^J'ai préparé un message client prudent pour (.+)\. Il mentionne une solution d'échelonnement uniquement comme option à valider ; aucun message n'a été envoyé et aucun échéancier n'a été créé\.$",
            r"I prepared a careful customer message for \1. It mentions an instalment arrangement only as an option requiring approval; no message was sent and no payment plan was created.",
            r"Ich habe eine vorsichtige Kundennachricht für \1 vorbereitet. Eine Ratenzahlung wird darin nur als freigabepflichtige Option erwähnt; keine Nachricht wurde versendet und kein Ratenplan erstellt.",
        ),
        (
            r"^(.+) concerne (.+), avec (.+) dus, (\d+) jours de retard et une promesse de paiement non tenue le (.+)\.$",
            r"\1 concerns \2, with \3 outstanding, \4 days overdue and a payment commitment dated \5 that was not met.",
            r"\1 betrifft \2 mit einem offenen Betrag von \3, \4 Tagen Verzug und einer nicht eingehaltenen Zahlungszusage vom \5.",
        ),
        (
            r"^(.+) concerne (.+), avec (.+) dus et (\d+) jours de retard\.$",
            r"\1 concerns \2, with \3 outstanding and \4 days overdue.",
            r"\1 betrifft \2 mit einem offenen Betrag von \3 und \4 Tagen Verzug.",
        ),
        (
            r"^Pour (.+), un étalement sur (\d+) mois représenterait environ (.+) par mois pour un montant dû de (.+)\. Cette proposition reste indicative, nécessite une validation interne et l'accord du client\. Aucun échéancier n'a été créé\.$",
            r"For \1, an arrangement over \2 months would represent approximately \3 per month against \4 due. This proposal is indicative and requires internal approval and customer agreement. No payment plan was created.",
            r"Für \1 würde eine Ratenzahlung über \2 Monate ungefähr \3 pro Monat bei einem offenen Betrag von \4 ergeben. Dieser Vorschlag ist unverbindlich und erfordert die interne Freigabe sowie die Zustimmung des Kunden. Es wurde kein Ratenplan erstellt.",
        ),
        (
            r"^Non, vous ne devez pas appeler (.+) à (.+)\. Le contact téléphonique est autorisé aujourd'hui uniquement entre (.+) et (.+)\. Je peux vous aider à planifier un rappel demain ou à préparer un (.+)\.$",
            r"No, you must not call \1 at \2. Telephone contact is permitted today only between \3 and \4. I can help schedule a call tomorrow or prepare a \5.",
            r"Nein, Sie dürfen \1 nicht um \2 anrufen. Telefonischer Kontakt ist heute nur zwischen \3 und \4 zulässig. Ich kann einen Rückruf für morgen planen oder eine \5 vorbereiten.",
        ),
        (
            r"^Pour (.+), vous pouvez contacter (.+) aujourd'hui entre (.+) et (.+)\. Le canal conseillé est l'(.+)\. En alternative, vous pouvez préparer un (.+)\.$",
            r"For \1, you may contact \2 today between \3 and \4. The suggested channel is \5. Alternatively, you may prepare a \6.",
            r"Für \1 dürfen Sie \2 heute zwischen \3 und \4 kontaktieren. Der empfohlene Kanal ist \5. Alternativ können Sie eine \6 vorbereiten.",
        ),
        (
            r"^Vous pouvez contacter (.+) aujourd'hui entre (.+) et (.+)\.$",
            r"You may contact \1 today between \2 and \3.",
            r"Sie dürfen \1 heute zwischen \2 und \3 kontaktieren.",
        ),
        (
            r"^Un appel à (.+) n'est pas autorisé\. Reportez le contact sur une plage autorisée ou utilisez un canal autorisé si applicable\.$",
            r"A call at \1 is not permitted. Move the contact to a permitted window or use an authorised channel where applicable.",
            r"Ein Anruf um \1 ist nicht zulässig. Verschieben Sie den Kontakt in ein zulässiges Zeitfenster oder verwenden Sie gegebenenfalls einen erlaubten Kanal.",
        ),
    )
    for pattern, english, german in patterns:
        if re.match(pattern, text):
            translated = re.sub(pattern, english if en else german, text)
            for source, target in _COPY.items():
                translated = translated.replace(source, target[0 if en else 1])
            month_pairs = {
                "janvier": ("January", "Januar"),
                "février": ("February", "Februar"),
                "mars": ("March", "März"),
                "avril": ("April", "April"),
                "mai": ("May", "Mai"),
                "juin": ("June", "Juni"),
                "juillet": ("July", "Juli"),
                "août": ("August", "August"),
                "septembre": ("September", "September"),
                "octobre": ("October", "Oktober"),
                "novembre": ("November", "November"),
                "décembre": ("December", "Dezember"),
            }
            for source, target in month_pairs.items():
                translated = translated.replace(source, target[0 if en else 1])
            return translated
    return None


def localize_text(text: str, language: RecouvrementLanguage) -> str:
    """Translate one known human-facing workflow string, preserving canonical values."""
    if language == "fr":
        return text
    direct = _COPY.get(text)
    if direct is not None:
        return direct[0 if language == "en" else 1]
    dynamic = _dynamic(text, language)
    if dynamic is not None:
        return dynamic
    return text


def localize_value(value: T, language: RecouvrementLanguage) -> T:
    """Recursively localize strings in a presentation value without changing its shape."""
    if language == "fr":
        return value
    if isinstance(value, str):
        return cast(T, localize_text(value, language))
    if isinstance(value, list):
        return cast(T, [localize_value(item, language) for item in value])
    if isinstance(value, dict):
        return cast(T, {key: localize_value(item, language) for key, item in value.items()})
    return value


def localize_artifact(
    artifact: RecouvrementArtifact,
    language: RecouvrementLanguage,
) -> RecouvrementArtifact:
    """Localize a structured artifact while retaining its typed contract."""
    return localize_value(artifact, language)
