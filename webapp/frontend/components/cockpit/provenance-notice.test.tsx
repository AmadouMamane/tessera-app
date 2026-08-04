// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

import { ProvenanceNotice } from "./provenance-notice";

const MESSAGES = { fr, en, de } as const;

const CASES = {
  fr: [
    ["compliance_catalog", "reference", "Référentiel versionné"],
    ["agent_historique", "evaluation", "Données d’évaluation"],
    ["embedding_inversion", "simulation", "Simulation contrôlée"],
    ["policy_versioning", "preview", "Aperçu de fonctionnalité"],
    ["assistant", "fallback", "Mode de secours"],
    ["disclosure", "declaration", "Contrôle déclaré"],
  ],
  en: [
    ["compliance_catalog", "reference", "Versioned reference"],
    ["agent_historique", "evaluation", "Evaluation data"],
    ["embedding_inversion", "simulation", "Controlled simulation"],
    ["policy_versioning", "preview", "Feature preview"],
    ["assistant", "fallback", "Fallback mode"],
    ["disclosure", "declaration", "Declared control"],
  ],
  de: [
    ["compliance_catalog", "reference", "Versionierte Referenz"],
    ["agent_historique", "evaluation", "Evaluationsdaten"],
    ["embedding_inversion", "simulation", "Kontrollierte Simulation"],
    ["policy_versioning", "preview", "Funktionsvorschau"],
    ["assistant", "fallback", "Fallback-Modus"],
    ["disclosure", "declaration", "Deklarierte Kontrolle"],
  ],
} as const;

afterEach(cleanup);

function renderNotice(locale: keyof typeof MESSAGES, signalId: string) {
  return render(
    <NextIntlClientProvider
      locale={locale}
      messages={MESSAGES[locale] as unknown as AbstractIntlMessages}
    >
      <ProvenanceNotice signalId={signalId} />
    </NextIntlClientProvider>,
  );
}

describe("ProvenanceNotice", () => {
  it.each(Object.entries(CASES))(
    "renders precise %s copy for all provenance types",
    (locale, cases) => {
      for (const [signalId, provenance, title] of cases) {
        const view = renderNotice(locale as keyof typeof MESSAGES, signalId);
        const note = screen.getByRole("note");
        expect(note.getAttribute("data-provenance")).toBe(provenance);
        expect(note.textContent).toContain(title);
        view.unmount();
      }
    },
  );

  it("renders nothing for live and undeclared signals", () => {
    const live = renderNotice("fr", "embedding_skew");
    expect(screen.queryByRole("note")).toBeNull();
    live.unmount();

    renderNotice("fr", "does-not-exist");
    expect(screen.queryByRole("note")).toBeNull();
  });
});
