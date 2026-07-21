import type { Locale } from "@/i18n/routing";

const COPY: Record<string, readonly [string, string]> = {
  "La vérification backend est indisponible. Aucune action n'a été exécutée.": [
    "The backend check is unavailable. No action was executed.",
    "Die Backend-Prüfung ist nicht verfügbar. Es wurde keine Aktion ausgeführt.",
  ],
  "Montant dû : 840,00 €": ["Amount due: €840.00", "Fälliger Betrag: 840,00 €"],
  "Statut : validation requise avant proposition": [
    "Status: approval required before proposal",
    "Status: Freigabe vor dem Vorschlag erforderlich",
  ],
  "Échéancier non créé": ["Payment plan not created", "Ratenplan nicht erstellt"],
  "Aucun échéancier créé": ["No payment plan created", "Kein Ratenplan erstellt"],
  "Ajuster la durée": ["Adjust duration", "Laufzeit anpassen"],
  "Comparer les options": ["Compare options", "Optionen vergleichen"],
  "Préparer le message client": ["Prepare customer message", "Kundennachricht vorbereiten"],
  "Soumettre à validation": ["Submit for approval", "Zur Freigabe einreichen"],
  "Dossier : RC-2048": ["Case: RC-2048", "Vorgang: RC-2048"],
  "Client : M. D.": ["Customer: M. D.", "Kunde: M. D."],
  "Retard : 32 jours": ["32 days overdue", "32 Tage überfällig"],
  "Échéancier indicatif uniquement après validation": [
    "Indicative payment plan only after approval",
    "Unverbindlicher Ratenplan erst nach Freigabe",
  ],
  "Validation requise avant proposition au client": [
    "Approval required before proposing to the customer",
    "Freigabe vor dem Kundenvorschlag erforderlich",
  ],
  "Validation requise avant proposition": [
    "Approval required before proposal",
    "Freigabe vor dem Vorschlag erforderlich",
  ],
  "Accord client nécessaire avant création": [
    "Customer agreement required before creation",
    "Kundenzustimmung vor der Erstellung erforderlich",
  ],
  "Montant total conservé : 840,00 €": [
    "Total amount preserved: €840.00",
    "Gesamtbetrag beibehalten: 840,00 €",
  ],
  "Rédiger une relance": ["Draft a reminder", "Mahnung entwerfen"],
  "Proposer un échéancier": ["Propose a payment plan", "Ratenplan vorschlagen"],
  "Vérifier une règle": ["Check a rule", "Regel prüfen"],
  "Voici le résumé opérationnel de RC-2048 : M. D. doit 840,00 €, le retard est de 32 jours et la promesse de paiement du 12 juin n'a pas été tenue.":
    [
      "Operational summary for RC-2048: M. D. owes €840.00, the payment is 32 days overdue and the payment promise made for 12 June was missed.",
      "Operative Zusammenfassung für RC-2048: M. D. schuldet 840,00 €, die Zahlung ist 32 Tage überfällig und die Zahlungszusage für den 12. Juni wurde nicht eingehalten.",
    ],
  "Résumé du dossier — RC-2048": ["Case summary — RC-2048", "Vorgangszusammenfassung — RC-2048"],
  "Promesse de paiement non tenue le 12 juin": [
    "Payment promise missed on 12 June",
    "Zahlungszusage am 12. Juni nicht eingehalten",
  ],
  "Contexte dossier conservé": ["Case context preserved", "Vorgangskontext beibehalten"],
  "Aucune action exécutée": ["No action executed", "Keine Aktion ausgeführt"],
  "Aucun message client généré": [
    "No customer message generated",
    "Keine Kundennachricht erstellt",
  ],
  "Préparer un rappel pour demain": [
    "Schedule a callback tomorrow",
    "Rückruf für morgen vorbereiten",
  ],
  "Rédiger un email de confirmation": [
    "Draft a confirmation email",
    "Bestätigungs-E-Mail entwerfen",
  ],
  "Reporter le contact": ["Reschedule contact", "Kontakt verschieben"],
  "Insérer la note dans le dossier": [
    "Insert the note into the case",
    "Notiz in den Vorgang einfügen",
  ],
  "Cadre de contact — RC-2048": ["Contact framework — RC-2048", "Kontaktrahmen — RC-2048"],
  "Vérification indisponible": ["Check unavailable", "Prüfung nicht verfügbar"],
  "Vérification backend indisponible": [
    "Backend check unavailable",
    "Backend-Prüfung nicht verfügbar",
  ],
  "Le cadre connu indique une plage 08:00–20:00, mais la règle n'a pas été revérifiée.": [
    "The known framework specifies an 08:00–20:00 window, but the rule could not be checked again.",
    "Der bekannte Rahmen sieht ein Zeitfenster von 08:00–20:00 vor, die Regel konnte jedoch nicht erneut geprüft werden.",
  ],
  "Aucun appel ne doit être préparé tant que la vérification backend est indisponible.": [
    "No call may be prepared while the backend check is unavailable.",
    "Solange die Backend-Prüfung nicht verfügbar ist, darf kein Anruf vorbereitet werden.",
  ],
  "Modifier le message": ["Edit message", "Nachricht bearbeiten"],
  "Copier le message": ["Copy message", "Nachricht kopieren"],
  "Insérer dans le dossier": ["Insert into case", "In den Vorgang einfügen"],
  "La préparation backend du message est indisponible. Aucun message n'a été envoyé et aucun échéancier n'a été créé.":
    [
      "Backend message preparation is unavailable. No message was sent and no payment plan was created.",
      "Die Backend-Nachrichtenvorbereitung ist nicht verfügbar. Es wurde keine Nachricht versendet und kein Ratenplan erstellt.",
    ],
  "Message client préparé — RC-2048": [
    "Customer message prepared — RC-2048",
    "Kundennachricht vorbereitet — RC-2048",
  ],
  "Brouillon de relance — RC-2048": ["Reminder draft — RC-2048", "Mahnungsentwurf — RC-2048"],
  "Préparation backend indisponible": [
    "Backend preparation unavailable",
    "Backend-Vorbereitung nicht verfügbar",
  ],
  "Aucun message envoyé": ["No message sent", "Keine Nachricht versendet"],
  "Action non disponible": ["Action unavailable", "Aktion nicht verfügbar"],
  "Validation requise avant toute proposition": [
    "Approval required before any proposal",
    "Freigabe vor jedem Vorschlag erforderlich",
  ],
  "La préparation backend des options de paiement est indisponible. Aucun paiement n'a été initié et aucune action client n'a été exécutée.":
    [
      "Backend preparation of payment options is unavailable. No payment was initiated and no customer action was executed.",
      "Die Backend-Vorbereitung der Zahlungsoptionen ist nicht verfügbar. Es wurde keine Zahlung ausgelöst und keine Kundenaktion ausgeführt.",
    ],
  "Options de paiement — RC-2048": ["Payment options — RC-2048", "Zahlungsoptionen — RC-2048"],
  "Options de paiement indisponibles côté backend": [
    "Payment options unavailable in the backend",
    "Zahlungsoptionen im Backend nicht verfügbar",
  ],
  "Aucun paiement initié": ["No payment initiated", "Keine Zahlung ausgelöst"],
  "Aucun lien de paiement créé ou envoyé": [
    "No payment link created or sent",
    "Kein Zahlungslink erstellt oder versendet",
  ],
  "Options à confirmer selon les moyens disponibles dans le dossier.": [
    "Options must be confirmed against the methods available in the case.",
    "Optionen müssen anhand der im Vorgang verfügbaren Zahlungsarten bestätigt werden.",
  ],
  "Échéancier indicatif uniquement après validation interne et accord client.": [
    "Indicative payment plan only after internal approval and customer agreement.",
    "Unverbindlicher Ratenplan erst nach interner Freigabe und Kundenzustimmung.",
  ],
  "Aucun lien de paiement créé": ["No payment link created", "Kein Zahlungslink erstellt"],
  "Aucun lien de paiement envoyé": ["No payment link sent", "Kein Zahlungslink versendet"],
  "Aucune action client exécutée": ["No customer action executed", "Keine Kundenaktion ausgeführt"],
  "Conserver l'artefact actuel": ["Keep the current artifact", "Aktuelles Artefakt beibehalten"],
  "Cette modification s'applique à un brouillon de relance ou à un message client. Aucun nouvel artefact n'a été généré.":
    [
      "This edit applies to a reminder draft or customer message. No new artifact was generated.",
      "Diese Änderung gilt für einen Mahnungsentwurf oder eine Kundennachricht. Es wurde kein neues Artefakt erstellt.",
    ],
  "Action non disponible — RC-2048": [
    "Action unavailable — RC-2048",
    "Aktion nicht verfügbar — RC-2048",
  ],
  aucune: ["none", "keine"],
  "Modification de ton non appliquée": ["Tone edit not applied", "Tonanpassung nicht angewendet"],
  "Un brouillon de relance ou message client est nécessaire": [
    "A reminder draft or customer message is required",
    "Ein Mahnungsentwurf oder eine Kundennachricht ist erforderlich",
  ],
  "Note de règle préparée pour RC-2048. Aucune écriture définitive n'a été exécutée.": [
    "Rule note prepared for RC-2048. No final write was executed.",
    "Regelnotiz für RC-2048 vorbereitet. Es wurde keine endgültige Änderung ausgeführt.",
  ],
  "Insertion préparée pour RC-2048. Aucune écriture définitive n'a été exécutée.": [
    "Insertion prepared for RC-2048. No final write was executed.",
    "Einfügung für RC-2048 vorbereitet. Es wurde keine endgültige Änderung ausgeführt.",
  ],
  "Statut : insertion préparée": ["Status: insertion prepared", "Status: Einfügung vorbereitet"],
  "Écriture réelle : non exécutée": [
    "Actual write: not executed",
    "Tatsächliche Änderung: nicht ausgeführt",
  ],
  "Artefact courant conservé": ["Current artifact preserved", "Aktuelles Artefakt beibehalten"],
  "Aucune réponse client régénérée": [
    "No customer reply regenerated",
    "Keine Kundenantwort neu erstellt",
  ],
  "Aucune action irréversible exécutée": [
    "No irreversible action executed",
    "Keine irreversible Aktion ausgeführt",
  ],
  "Confirmer l'insertion": ["Confirm insertion", "Einfügen bestätigen"],
  Annuler: ["Cancel", "Abbrechen"],
  "Voir le dossier": ["View case", "Vorgang anzeigen"],
  "Demande de validation préparée pour RC-2048. Aucun message n'a été envoyé et aucune action définitive n'a été exécutée.":
    [
      "Approval request prepared for RC-2048. No message was sent and no final action was executed.",
      "Freigabeanfrage für RC-2048 vorbereitet. Es wurde keine Nachricht versendet und keine endgültige Aktion ausgeführt.",
    ],
  "Statut : validation préparée": [
    "Status: approval request prepared",
    "Status: Freigabeanfrage vorbereitet",
  ],
  "Action réelle : non exécutée": [
    "Actual action: not executed",
    "Tatsächliche Aktion: nicht ausgeführt",
  ],
  "Validation requise": ["Approval required", "Freigabe erforderlich"],
  "Confirmer la demande": ["Confirm request", "Anfrage bestätigen"],
  "Rappel préparé pour demain pour RC-2048. Aucun événement calendrier réel n'a été créé.": [
    "Callback prepared for tomorrow for RC-2048. No actual calendar event was created.",
    "Rückruf für morgen für RC-2048 vorbereitet. Es wurde kein tatsächlicher Kalendereintrag erstellt.",
  ],
  "Événement calendrier réel : non créé": [
    "Actual calendar event: not created",
    "Tatsächlicher Kalendereintrag: nicht erstellt",
  ],
  "Statut : reminder_prepared": ["Status: reminder prepared", "Status: Rückruf vorbereitet"],
  "Aucun événement calendrier créé": ["No calendar event created", "Kein Kalendereintrag erstellt"],
  "Aucun appel préparé hors plage": [
    "No call prepared outside the permitted window",
    "Kein Anruf außerhalb des zulässigen Zeitfensters vorbereitet",
  ],
  "Voir le rappel préparé": ["View prepared callback", "Vorbereiteten Rückruf anzeigen"],
  "Rédiger un email": ["Draft an email", "E-Mail entwerfen"],
};

function dynamicCopy(value: string, locale: Exclude<Locale, "fr">): string {
  const languageIndex = locale === "en" ? 0 : 1;
  const rules: Array<[RegExp, (match: RegExpMatchArray) => readonly [string, string]]> = [
    [
      /^Échéancier indicatif — (\d+) mois$/,
      (m) => [
        `Indicative payment plan — ${m[1]} months`,
        `Unverbindlicher Ratenplan — ${m[1]} Monate`,
      ],
    ],
    [
      /^Durée demandée : (\d+) mois$/,
      (m) => [`Requested duration: ${m[1]} months`, `Gewünschte Laufzeit: ${m[1]} Monate`],
    ],
    [
      /^Mensualité indicative : (.+)$/,
      (m) => [`Indicative monthly payment: ${m[1]}`, `Unverbindliche Monatsrate: ${m[1]}`],
    ],
    [
      /^Étalement demandé : (\d+) mois$/,
      (m) => [
        `Requested instalment period: ${m[1]} months`,
        `Gewünschte Ratenlaufzeit: ${m[1]} Monate`,
      ],
    ],
    [
      /^Pour RC-2048, un étalement sur (\d+) mois représenterait environ (.+) par mois pour un montant dû de 840,00 €. Cette proposition reste indicative, nécessite validation avant d'être proposée au client, et aucun échéancier n'a été créé.$/,
      (m) => [
        `For RC-2048, a ${m[1]}-month plan would be approximately ${m[2]} per month on an amount due of €840.00. This proposal remains indicative, requires approval before being offered to the customer, and no payment plan was created.`,
        `Für RC-2048 ergäbe ein Ratenplan über ${m[1]} Monate ungefähr ${m[2]} pro Monat bei einem fälligen Betrag von 840,00 €. Dieser Vorschlag ist unverbindlich, muss vor dem Kundenvorschlag freigegeben werden und es wurde kein Ratenplan erstellt.`,
      ],
    ],
    [
      /^Famille d'artefact active : (.+)$/,
      (m) => [
        `Active artifact family: ${m[1] === "aucune" ? "none" : m[1]}`,
        `Aktive Artefaktfamilie: ${m[1] === "aucune" ? "keine" : m[1]}`,
      ],
    ],
    [/^Artefact ciblé : (.+)$/, (m) => [`Target artifact: ${m[1]}`, `Zielartefakt: ${m[1]}`]],
  ];
  for (const [pattern, render] of rules) {
    const match = value.match(pattern);
    if (match) return render(match)[languageIndex];
  }
  return value;
}

function localizeString(value: string, locale: Locale): string {
  if (locale === "fr") return value;
  const translated = COPY[value];
  return translated ? translated[locale === "en" ? 0 : 1] : dynamicCopy(value, locale);
}

export function localizeRecouvrementFallback<T>(value: T, locale: Locale): T {
  if (locale === "fr") return value;
  if (typeof value === "string") return localizeString(value, locale) as T;
  if (Array.isArray(value)) {
    return value.map((item) => localizeRecouvrementFallback(item, locale)) as T;
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, localizeRecouvrementFallback(item, locale)]),
    ) as T;
  }
  return value;
}
