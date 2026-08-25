// @vitest-environment jsdom
//
// The fleet-total footer used to close with "(handoff = 1)" — a sentence about
// handoffs computed from a table that had never been asked about handoffs. Found live:
// the S1 journal attested 34 transfers over 34 conversations while `shared_conversations`
// read 0, and the footer implied that no duplicates existed as though a reconciliation had
// happened. These tests pin the honest footer: when the journal's claim and the store's
// answer disagree, the gap is STATED; when they agree, that is said too; and the wire
// schema carries the three reconciliation fields (zod strips undeclared keys, so a missing
// declaration would silently re-arm the bug).
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider, createTranslator } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

const MESSAGES = { fr, de, en } as const;

vi.mock("next-intl/server", () => ({
  getTranslations: async ({ locale, namespace }: { locale: string; namespace: string }) =>
    createTranslator({
      locale,
      messages: MESSAGES[locale as keyof typeof MESSAGES] as never,
      namespace: namespace as never,
    }),
}));

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import type {
  AlarmLens,
  ComplianceLens,
  MaskedLens,
  ObservabilityLens,
  QualityLens,
  ReliabilityLens,
  SecurityLens,
} from "@/lib/agent-lens";
import { FleetSchema } from "@/lib/api/schemas";

afterEach(cleanup);

/** Render under the intl provider — lenses whose agent names are doors (client Links) need it. */
function renderWithIntl(node: ReactNode) {
  return render(
    <NextIntlClientProvider locale="fr" messages={fr as unknown as AbstractIntlMessages}>
      {node}
    </NextIntlClientProvider>,
  );
}

/** Row `i` of the rendered table, or a loud failure — never a silently skipped assertion. */
function rowAt(rows: HTMLElement[], i: number): HTMLElement {
  const el = rows[i];
  if (el === undefined) throw new Error(`no rendered row at index ${i} (got ${rows.length})`);
  return el;
}

/** A wire-shaped fleet payload, parsed through the REAL schema — never a hand-typed object. */
function fleetFromWire(
  reconciliation: {
    handoff_events: number;
    handoff_conversations: number;
    handoff_conversations_seen_shared: number;
  },
  totals: {
    naive?: number;
    total?: number;
    shared?: number;
    saved?: number;
  } = {},
) {
  return FleetSchema.parse({
    available: true,
    agents: [
      {
        id: "support-client",
        name: "Support Client",
        owner: "ops",
        conversations: 274,
        turns: 300,
        messages: 600,
        escalation_rate: 26.8,
        latency_ms: 4600,
        handoffs_in: 0,
        handoffs_out: 34,
        health: "green",
        release: null,
      },
    ],
    org: { conversations: totals.total ?? 415, turns: 483 },
    naive_sum_conversations: totals.naive ?? 415,
    shared_conversations: totals.shared ?? 0,
    dedup_saved: totals.saved ?? 0,
    ...reconciliation,
  });
}

const NO_HANDOFFS = {
  handoff_events: 0,
  handoff_conversations: 0,
  handoff_conversations_seen_shared: 0,
};

/** Two agents, so a table can name WHICH one burns the SLO. */
function twoAgentFleet() {
  return FleetSchema.parse({
    available: true,
    agents: [
      {
        id: "support-client",
        name: "Support Client",
        owner: "ops",
        conversations: 274,
        turns: 300,
        messages: 600,
        escalation_rate: 26.8,
        latency_ms: 4600,
        handoffs_in: 0,
        handoffs_out: 34,
        health: "green",
        release: null,
      },
      {
        id: "onboarding",
        name: "Onboarding",
        owner: "ops",
        conversations: 141,
        turns: 183,
        messages: 300,
        escalation_rate: 11.2,
        latency_ms: 2300,
        handoffs_in: 34,
        handoffs_out: 0,
        health: "green",
        release: null,
      },
    ],
    org: { conversations: 415, turns: 483 },
    naive_sum_conversations: 415,
    shared_conversations: 0,
    dedup_saved: 0,
    ...NO_HANDOFFS,
  });
}

describe("the transfer verification line under the fleet total", () => {
  it("the schema carries the reconciliation fields — zod must not strip them", () => {
    const fleet = fleetFromWire({
      handoff_events: 34,
      handoff_conversations: 34,
      handoff_conversations_seen_shared: 0,
    });
    expect(fleet.handoff_events).toBe(34);
    expect(fleet.handoff_conversations).toBe(34);
    expect(fleet.handoff_conversations_seen_shared).toBe(0);
  });

  it("states the gap when the journal attests journeys the store cannot see shared", async () => {
    const fleet = fleetFromWire({
      handoff_events: 34,
      handoff_conversations: 34,
      handoff_conversations_seen_shared: 0,
    });

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    const gap = screen.getByText(/Pourquoi vérifier/);
    expect(gap.textContent).toMatch(/34 transferts/);
    expect(gap.textContent).toMatch(/agent de départ/);
    expect(gap.textContent).toMatch(/agent d'arrivée/);
    expect(gap.textContent).toMatch(/une conversation peut être comptée deux fois/);
    expect(screen.queryByText(/Transferts vérifiés/)).toBeNull();
    // And the old unearned claim is gone from the dedup line itself.
    expect(screen.queryByText(/handoff = 1/)).toBeNull();
  });

  it("explains verified transfers in plain language and gives the fleet total once", async () => {
    const fleet = fleetFromWire(
      {
        handoff_events: 3,
        handoff_conversations: 2,
        handoff_conversations_seen_shared: 2,
      },
      {
        naive: 417,
        total: 415,
        shared: 2,
        saved: 2,
      },
    );

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    const explanation = screen.getByText(/2 conversations sont passées d'un agent à un autre/);
    expect(explanation.textContent).toContain("l'activité des deux agents concernés");
    expect(explanation.textContent).toContain("qu'une fois dans le total de la flotte");
    expect(explanation.textContent).toContain("415 conversations");
    expect(screen.queryByText(/Pourquoi vérifier/)).toBeNull();
    expect(screen.queryByText(/doublons|retirées du total/)).toBeNull();
  });

  it("stays silent when the journal attests no handoffs at all", async () => {
    const fleet = fleetFromWire({
      handoff_events: 0,
      handoff_conversations: 0,
      handoff_conversations_seen_shared: 0,
    });

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    expect(screen.queryByText(/Le total ne peut pas encore être confirmé/)).toBeNull();
    expect(screen.queryByText(/Transferts vérifiés/)).toBeNull();
  });

  it("states no transfers as one direct, natural sentence", async () => {
    const fleet = fleetFromWire(NO_HANDOFFS);

    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    // One sentence, one unit, no arithmetic lesson (operator feedback 2026-08-25: the
    // previous copy explained WHY the sum equals the total instead of stating the facts).
    const explanation = screen.getByText(/aucun transfert entre agents/i);
    expect(explanation.textContent).toContain("415 conversations traitées sur la période");
    expect(explanation.textContent).not.toMatch(/donne donc directement/);
    expect(explanation.textContent).not.toMatch(/0 sont retrouvées|0 sont retirées/);
  });

  it("removes the redundant generic note above the monitoring table", async () => {
    render(await AgentBreakdown({ fleet: fleetFromWire(NO_HANDOFFS), scope: "all", locale: "fr" }));

    expect(screen.queryByText(/Données réelles observées pour chaque agent/)).toBeNull();
    expect(
      screen.queryByText(/Le total de la flotte compte chaque conversation une fois/),
    ).toBeNull();
  });

  it("renders the gap sentence in every locale", async () => {
    for (const locale of ["fr", "de", "en"] as const) {
      cleanup();
      const fleet = fleetFromWire({
        handoff_events: 34,
        handoff_conversations: 34,
        handoff_conversations_seen_shared: 0,
      });
      render(await AgentBreakdown({ fleet, scope: "all", locale }));
      const pattern = {
        fr: /Pourquoi vérifier/,
        de: /Warum prüfen/,
        en: /Why check this/,
      }[locale];
      expect(screen.getByText(pattern)).toBeTruthy();
    }
  });
});

// ── The lens ────────────────────────────────────────────────────────────────────────────
//
// The columns used to be hardcoded, and the docstring said so: "this is the MONITORING view".
// On Qualité IA that meant the banner cried "faithfulness 71,6 % < 95 %, 19/67 bad" and the
// table below answered with LATENCY and HANDOFFS — the page asked a question at the top and
// its own table occupied the space where the answer belonged. The columns are a lens now.

describe("the default (monitoring) lens is UNCHANGED — the non-regression", () => {
  it("keeps the historical columns and their numbers", async () => {
    const fleet = fleetFromWire(NO_HANDOFFS);
    render(await AgentBreakdown({ fleet, scope: "all", locale: "fr" }));

    for (const col of [
      "Volume",
      "Refus/escalade",
      "Latence",
      "Transferts (e/s)",
      "Mise en ligne",
    ]) {
      expect(screen.getByText(col)).toBeTruthy();
    }
    expect(screen.getByText("26,8 %")).toBeTruthy(); // escalation_rate
    expect(screen.getByText("4,6 s")).toBeTruthy(); // latency_ms
    expect(screen.getByText("0 / 34")).toBeTruthy(); // handoffs in / out
    expect(screen.getByText("Non évalué")).toBeTruthy();
    // And no lens column has leaked into it.
    expect(screen.queryByText(/Écart à l'objectif/)).toBeNull();
    expect(screen.queryByText(/Contribution/)).toBeNull();
  });
});

describe("the alarm lens: the banner says 19 bad — the table says WHOSE", () => {
  const alarm: AlarmLens = {
    kind: "alarm",
    signalId: "slo",
    metric: "faithfulness",
    target: 0.95,
    orgNBad: 19,
    orgN: 67,
    sumNBad: 19,
    rows: [
      { agentId: "support-client", value: 0.65, gapPp: -30, nBad: 14, n: 40, refusal: null },
      { agentId: "onboarding", value: 0.81, gapPp: -14, nBad: 5, n: 27, refusal: null },
    ],
  };

  it("answers the breached signal per agent, sorted by contribution, and names the culprit", async () => {
    renderWithIntl(
      await AgentBreakdown({ fleet: twoAgentFleet(), scope: "all", locale: "fr", lens: alarm }),
    );

    expect(screen.getByText("Valeur (Fidélité)")).toBeTruthy();
    expect(screen.getByText("Écart à l'objectif")).toBeTruthy();
    expect(screen.getByText("Réponses concernées")).toBeTruthy();
    // The release column is the other lane's work — it rides in every lens, untouched.
    expect(screen.getByText("Mise en ligne")).toBeTruthy();
    // The heaviest contributor is first, and its numbers are named.
    const rows = screen.getAllByRole("row");
    expect(rowAt(rows, 1).textContent).toMatch(/Support Client/);
    expect(rowAt(rows, 1).textContent).toMatch(/14 \/ 40/);
    expect(rowAt(rows, 1).textContent).toMatch(/−30,0 pt|-30,0 pt/);
    expect(rowAt(rows, 2).textContent).toMatch(/Onboarding/);
    // Monitoring columns are GONE — they answered a different question.
    expect(screen.queryByText("Latence")).toBeNull();
    expect(screen.queryByText("Transferts (e/s)")).toBeNull();
    // The door survives the alarm: each culprit's name leads to ITS evaluations page.
    const doors = screen
      .getAllByRole("link")
      .map((l) => l.getAttribute("href") ?? "")
      .filter((h) => h.includes("/evaluations"));
    expect(doors).toContain("/fr/agents/support-client/evaluations");
  });

  it("stays silent when the per-agent detail matches the fleet total", async () => {
    // A check that passes says nothing (operator decision 2026-08-25: the reconciled
    // sentence restated the table's own numbers as doctrine). Silence stays unambiguous
    // because BOTH other states still speak — the gap line (next test) and the
    // cannot-verify line — so an absent note can only mean checked-and-equal.
    renderWithIntl(
      await AgentBreakdown({ fleet: twoAgentFleet(), scope: "all", locale: "fr", lens: alarm }),
    );
    expect(screen.queryByText(/Détail par agent/)).toBeNull();
    expect(screen.queryByText(/est supérieur au total de la flotte/)).toBeNull();
    expect(screen.queryByText(/ne peut pas encore être vérifié/)).toBeNull();
  });

  it("WRITES the gap when the per-agent detail does not match the fleet total", async () => {
    // A handed-off journey touches two agents and counts ONCE in the org: ∑ slices = org would
    // be a coincidence, not a proof. The same discipline as the handoff footer above.
    const unreconciled: AlarmLens = { ...alarm, sumNBad: 19, orgNBad: 17 };
    renderWithIntl(
      await AgentBreakdown({
        fleet: twoAgentFleet(),
        scope: "all",
        locale: "fr",
        lens: unreconciled,
      }),
    );
    const line = screen.getByText(
      /Le détail par agent \(19\) est supérieur au total de la flotte \(17\)/,
    );
    expect(line.textContent).toMatch(/une seule fois dans le total/);
  });

  it("a refused cell shows a dash that SAYS WHY — never a fabricated number", async () => {
    const blind: AlarmLens = {
      ...alarm,
      rows: [
        { agentId: "support-client", value: 0.65, gapPp: -30, nBad: 14, n: 40, refusal: null },
        {
          agentId: "onboarding",
          value: null,
          gapPp: null,
          nBad: null,
          n: null,
          refusal: "not-honoured",
        },
      ],
    };
    renderWithIntl(
      await AgentBreakdown({ fleet: twoAgentFleet(), scope: "all", locale: "fr", lens: blind }),
    );
    const rows = screen.getAllByRole("row");
    expect(rowAt(rows, 2).textContent).toMatch(/Onboarding/);
    expect(rowAt(rows, 2).textContent).toMatch(/—/);
    expect(
      screen.getAllByTitle(
        "La lecture n'a pas appliqué le filtre par agent ; la valeur n'est pas affichée.",
      ).length,
    ).toBeGreaterThan(0);
  });
});

describe("an ORG-WIDE signal gets NO table — and the operator is told why", () => {
  it("masks the table and states the reason, read from the capability registry", async () => {
    const masked: MaskedLens = { kind: "masked", signalId: "firewall" };
    render(
      await AgentBreakdown({ fleet: twoAgentFleet(), scope: "all", locale: "fr", lens: masked }),
    );
    expect(screen.getByText(/ce signal concerne toute la flotte/)).toBeTruthy();
    // No table at all — an inapplicable breakdown must not render as an empty one.
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByText("Support Client")).toBeNull();
  });
});

describe("each GOUVERNER domain page gets ITS OWN columns — no more monitoring everywhere", () => {
  it("security: PII / toxicity / guard denials, and the monitoring columns are GONE", async () => {
    const security: SecurityLens = {
      kind: "security",
      rows: [
        {
          agentId: "support-client",
          piiLeaks: 2,
          piiN: 7,
          piiRefusal: null,
          toxCount: 0,
          toxN: 7,
          toxRefusal: null,
          guardDenied: 133,
          guardTotal: 521,
          guardRefusal: null,
        },
        {
          agentId: "onboarding",
          piiLeaks: null,
          piiN: 0,
          piiRefusal: "no-sample",
          toxCount: null,
          toxN: 0,
          toxRefusal: "no-sample",
          guardDenied: null,
          guardTotal: null,
          guardRefusal: "unavailable",
        },
      ],
    };
    render(
      await AgentBreakdown({ fleet: twoAgentFleet(), scope: "all", locale: "fr", lens: security }),
    );
    expect(screen.getByText("Fuites PII (fuites / tours)")).toBeTruthy();
    expect(screen.getByText("Toxicité (toxiques / tours)")).toBeTruthy();
    expect(screen.getByText("Refus garde (refus / appels)")).toBeTruthy();
    expect(screen.getByText("Mise en ligne")).toBeTruthy();
    expect(screen.getByText("2 / 7")).toBeTruthy();
    expect(screen.getByText("133 / 521")).toBeTruthy();
    // The empty window and the dead read are BOTH dashes, but they say different things.
    expect(
      screen.getAllByTitle("Aucune donnée de cet agent pour ce signal sur la période.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByTitle("Ce signal ne peut pas être calculé sur cette période.").length,
    ).toBe(1);
    // Monitoring columns are GONE — they answered a different question.
    expect(screen.queryByText("Volume")).toBeNull();
    expect(screen.queryByText("Transferts (e/s)")).toBeNull();
  });

  it("compliance: governed acts and ledger entries — a proven ZERO renders as 0, not a dash", async () => {
    const compliance: ComplianceLens = {
      kind: "compliance",
      rows: [
        {
          agentId: "support-client",
          governedActs: 69,
          governedRefusal: null,
          ledgerEntries: 459,
          ledgerRefusal: null,
        },
        {
          agentId: "onboarding",
          governedActs: 0,
          governedRefusal: null,
          ledgerEntries: 0,
          ledgerRefusal: null,
        },
      ],
    };
    render(
      await AgentBreakdown({
        fleet: twoAgentFleet(),
        scope: "all",
        locale: "fr",
        lens: compliance,
      }),
    );
    expect(screen.getByText("Actes gouvernés")).toBeTruthy();
    expect(screen.getByText("Entrées du journal d'audit")).toBeTruthy();
    // The fleet's own escalation fact rides along — the same per-agent fact as monitoring.
    expect(screen.getByText("Refus/escalade")).toBeTruthy();
    expect(screen.getByText("69")).toBeTruthy();
    expect(screen.getByText("459")).toBeTruthy();
    const rows = screen.getAllByRole("row");
    expect(rowAt(rows, 2).textContent).toMatch(/Onboarding/);
    // The zero row shows 0s (measured facts), never dashes.
    expect(rowAt(rows, 2).textContent).not.toMatch(/—.*—/);
    expect(screen.queryByText("Volume")).toBeNull();
  });

  it("reliability: tool errors / latency / cost — and a refused cost says why", async () => {
    const reliability: ReliabilityLens = {
      kind: "reliability",
      rows: [
        {
          agentId: "support-client",
          toolErrors: 3,
          toolTotal: 521,
          toolRefusal: null,
          totalTokens: 124,
          meanTokens: 17.7,
          costN: 7,
          costRefusal: null,
        },
        {
          agentId: "onboarding",
          toolErrors: null,
          toolTotal: null,
          toolRefusal: "not-honoured",
          totalTokens: null,
          meanTokens: null,
          costN: null,
          costRefusal: "not-honoured",
        },
      ],
    };
    render(
      await AgentBreakdown({
        fleet: twoAgentFleet(),
        scope: "all",
        locale: "fr",
        lens: reliability,
      }),
    );
    expect(screen.getByText("Erreurs outils (erreurs / appels)")).toBeTruthy();
    expect(screen.getByText("Latence")).toBeTruthy();
    expect(screen.getByText("Coût (tokens)")).toBeTruthy();
    expect(screen.getByText("3 / 521")).toBeTruthy();
    expect(screen.getByText("124")).toBeTruthy();
    // The fleet's own average latency rides along (same fact as the monitoring column).
    expect(screen.getByText("4,6 s")).toBeTruthy();
    expect(
      screen.getAllByTitle(
        "La lecture n'a pas appliqué le filtre par agent ; la valeur n'est pas affichée.",
      ).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText("Volume")).toBeNull();
  });

  it("observability: anomalies / schema conformance — and the monitoring columns are GONE", async () => {
    const observability: ObservabilityLens = {
      kind: "observability",
      rows: [
        {
          agentId: "support-client",
          anomalous: 1,
          sessions: 7,
          anomaliesRefusal: null,
          violations: 0,
          calls: 9521,
          conformanceRefusal: null,
        },
        {
          agentId: "onboarding",
          anomalous: null,
          sessions: 0,
          anomaliesRefusal: "no-sample",
          violations: null,
          calls: null,
          conformanceRefusal: "not-honoured",
        },
      ],
    };
    render(
      await AgentBreakdown({
        fleet: twoAgentFleet(),
        scope: "all",
        locale: "fr",
        lens: observability,
      }),
    );
    expect(screen.getByText("Anomalies (anormales / sessions)")).toBeTruthy();
    expect(screen.getByText("Conformité schéma (violations / appels)")).toBeTruthy();
    expect(screen.getByText("Mise en ligne")).toBeTruthy();
    expect(screen.getByText("1 / 7")).toBeTruthy();
    expect(screen.getByText("0 / 9 521")).toBeTruthy();
    // The empty window and the refused slice are BOTH dashes, but they say different things.
    expect(
      screen.getAllByTitle("Aucune donnée de cet agent pour ce signal sur la période.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByTitle(
        "La lecture n'a pas appliqué le filtre par agent ; la valeur n'est pas affichée.",
      ).length,
    ).toBe(1);
    expect(screen.queryByText("Volume")).toBeNull();
    expect(screen.queryByText("Transferts (e/s)")).toBeNull();
  });

  it("proof: the compliance columns under the proof note — the audit page names ITS question", async () => {
    render(
      await AgentBreakdown({
        fleet: twoAgentFleet(),
        scope: "all",
        locale: "fr",
        lens: {
          kind: "proof",
          rows: [
            {
              agentId: "support-client",
              governedActs: 69,
              governedRefusal: null,
              ledgerEntries: 459,
              ledgerRefusal: null,
            },
          ],
        },
      }),
    );
    expect(screen.getByText("Actes gouvernés")).toBeTruthy();
    expect(screen.getByText("Entrées du journal d'audit")).toBeTruthy();
    expect(screen.getByText(/Preuves par agent/)).toBeTruthy();
    expect(screen.queryByText(/Conformité par agent/)).toBeNull();
    expect(screen.queryByText("Volume")).toBeNull();
  });
});

describe("the quality lens answers the page's own question when nothing breaches", () => {
  it("shows fidelity / hallucination / regression / gate / eval freshness", async () => {
    const quality: QualityLens = {
      kind: "quality",
      rows: [
        {
          agentId: "support-client",
          faithfulness: 0.962,
          faithfulnessRefusal: null,
          hallucination: 0.021,
          hallucinationRefusal: null,
        },
        {
          agentId: "onboarding",
          faithfulness: null,
          faithfulnessRefusal: "unavailable",
          hallucination: null,
          hallucinationRefusal: "unavailable",
        },
      ],
    };
    render(
      // The quality lens names each agent as a client Link (the door to that agent's
      // Évaluations page), and a client Link reads the intl context — hence the provider.
      <NextIntlClientProvider locale="fr" messages={fr as unknown as AbstractIntlMessages}>
        {
          await AgentBreakdown({
            fleet: twoAgentFleet(),
            scope: "all",
            locale: "fr",
            lens: quality,
          })
        }
      </NextIntlClientProvider>,
    );
    expect(screen.getByText("Fidélité")).toBeTruthy();
    expect(screen.getByText("Hallucination")).toBeTruthy();
    expect(screen.getByText("Échecs bloquants")).toBeTruthy();
    expect(screen.getByText("Dernière évaluation")).toBeTruthy();
    expect(screen.getByText("96,2 %")).toBeTruthy();
    expect(
      screen.getAllByTitle("Ce signal ne peut pas être calculé sur cette période.").length,
    ).toBe(2);
    // The row's door: each agent name resolves to ITS evaluations page.
    const doors = screen
      .getAllByRole("link")
      .map((l) => l.getAttribute("href") ?? "")
      .filter((h) => h.includes("/evaluations"));
    expect(doors).toContain("/fr/agents/support-client/evaluations");
    expect(doors).toContain("/fr/agents/onboarding/evaluations");
  });
});
