import { describe, expect, it } from "vitest";

import { recouvrementProductCopy } from "./recouvrement-product-copy";

const FRENCH_BUSINESS_COPY =
  /\b(?:dossier|échéancier|relance|paiement|autorisé|aujourd'hui|chargée|vérifier|règles|aucun|aucune|préparer|montant|retard|jours|soumettre|insérer)\b/i;

describe("recouvrementProductCopy", () => {
  it.each(["en", "de"] as const)("contains no French business copy in %s", (locale) => {
    const copy = recouvrementProductCopy(locale);

    expect(JSON.stringify(copy)).not.toMatch(FRENCH_BUSINESS_COPY);
    expect(copy.actions).toHaveLength(5);
    expect(copy.tabs).toHaveLength(5);
    expect(copy.nav).toHaveLength(6);
  });

  it("carries native prompts instead of translated chrome around a French conversation", () => {
    expect(recouvrementProductCopy("en").systemPrompt).toContain("Reply in English");
    expect(recouvrementProductCopy("de").systemPrompt).toContain("Antworten Sie auf Deutsch");
    expect(recouvrementProductCopy("en").dossierContext).toContain("Amount due");
    expect(recouvrementProductCopy("de").dossierContext).toContain("Fälliger Betrag");
  });
});
