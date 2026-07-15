// @vitest-environment jsdom
//
// Release Control is the page where the operator decides who ships. Until 2026-07-15 it
// could say BLOQUÉ but never WHY: the zod release block stripped `floor_block` (the ADR
// 0021 Rule 1 certificate), `verdict_stale` and the pass counts before any reader. These
// tests pin the reason chain end to end: a wire-shaped payload parsed through the REAL
// schema must surface the floor's own words on the blocked card — and ONLY there.
import { cleanup, render, screen } from "@testing-library/react";
import { NextIntlClientProvider, createTranslator } from "next-intl";
import type { ComponentProps, ReactNode } from "react";
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

vi.mock("@/i18n/navigation", () => ({
  Link: ({ href, children, ...rest }: { href: unknown; children: ReactNode }) => (
    <a href={String(href)} {...rest}>
      {children}
    </a>
  ),
}));

import { ReleaseControlView } from "@/components/agir/release-control-view";
import { ReleaseControlSchema } from "@/lib/api/schemas";

afterEach(cleanup);

const FLOOR_BLOCK =
  "the model is CERTIFIED worse than silence on 1 run(s) this agent executes " +
  "(56_policy_violation_disparage_bank|de) — measured over 15 full passes.";

/** Wire-shaped rows parsed through the REAL schema — never a hand-typed lens object. */
function payload() {
  return ReleaseControlSchema.parse({
    available: true,
    summary: { total: 3, passing: 1, blocked: 1, not_run: 1 },
    agents: [
      {
        agent_id: "support-client",
        name: "Support Client",
        owner: "ops",
        state: "Publiable",
        state_tone: "good",
        last_phase: "registered",
        flow: ["proposed", "reviewed", "approved", "live"],
        history: [],
        release: {
          agent_id: "support-client",
          available: true,
          passed: true,
          verdict_label: "PASSE",
          verdict_tone: "good",
          candidate_version: "20260704T083507Z",
          eval_set: "support-client",
          executions: 119,
          socle_ok: true,
          blocking_socle: 0,
          blocking_t1: 0,
          waived_active: 0,
          run_at: "20260704T083507Z",
          catalogue_version: "43-83ed8a32",
          current_catalogue_version: "43-83ed8a32",
          verdict_stale: false,
          summary_passed: 114,
          summary_total: 119,
          socle_passed: 18,
          socle_total: 18,
          floor_ok: true,
          floor_block: null,
        },
      },
      {
        agent_id: "recouvrement",
        name: "Recouvrement",
        owner: "ops",
        state: "Bloqué (pire que sans modèle)",
        state_tone: "bad",
        last_phase: "registered",
        flow: ["proposed", "reviewed", "approved", "live"],
        history: [],
        release: {
          agent_id: "recouvrement",
          available: true,
          passed: false,
          verdict_label: "BLOQUÉ (règle 1)",
          verdict_tone: "crit",
          candidate_version: "20260704T082820Z",
          eval_set: "recouvrement",
          executions: 80,
          socle_ok: true,
          blocking_socle: 0,
          blocking_t1: 0,
          waived_active: 0,
          run_at: "20260704T082820Z",
          // Scored against a SUPERSEDED catalogue → the stale badge must render too.
          catalogue_version: "28-990f1447",
          current_catalogue_version: "29-aaaa0000",
          verdict_stale: true,
          summary_passed: 76,
          summary_total: 80,
          socle_passed: 18,
          socle_total: 18,
          floor_ok: false,
          floor_block: FLOOR_BLOCK,
        },
      },
      {
        agent_id: "hello-agent",
        name: "Hello Agent",
        owner: "plateforme",
        state: "En attente",
        state_tone: "warn",
        last_phase: "registered",
        flow: ["proposed", "reviewed", "approved", "live"],
        history: [],
        release: {
          agent_id: "hello-agent",
          available: false,
          passed: false,
          verdict_label: "Éval non exécutée",
          verdict_tone: "muted",
          candidate_version: "",
          eval_set: "",
          executions: 0,
          socle_ok: false,
          blocking_socle: 0,
          blocking_t1: 0,
          waived_active: 0,
        },
      },
    ],
  });
}

async function renderView(locale: "fr" | "de" | "en" = "fr") {
  const props: ComponentProps<typeof ReleaseControlView> = { data: payload(), locale };
  // MetricInfo (the ⓘ affordance) is a client component reading its own namespace, so the
  // rendered server tree needs the client provider around it.
  render(
    <NextIntlClientProvider locale={locale} messages={MESSAGES[locale] as never}>
      {await ReleaseControlView(props)}
    </NextIntlClientProvider>,
  );
}

describe("the blocked card names its reason (qui est BLOQUÉ, et POURQUOI)", () => {
  it("renders the floor certificate verbatim under the localized label — on the blocked card only", async () => {
    await renderView();
    expect(screen.getByText("Motif du blocage (règle 1)")).toBeDefined();
    expect(screen.getByText(/56_policy_violation_disparage_bank\|de/)).toBeDefined();
    // One reason block for one blocked agent: the passing card carries none.
    expect(screen.getAllByText("Motif du blocage (règle 1)")).toHaveLength(1);
    expect(screen.getByText("PASSE")).toBeDefined();
    expect(screen.getByText("BLOQUÉ (règle 1)")).toBeDefined();
  });

  it("renders the pass counts the operator weighs: cas passés and socle counted", async () => {
    await renderView();
    expect(screen.getByText("76/80")).toBeDefined();
    expect(screen.getByText("114/119")).toBeDefined();
    // The socle cell shows the counted floor set for both evaluated agents.
    expect(screen.getAllByText("18/18")).toHaveLength(2);
  });

  it("flags a verdict scored against a superseded catalogue — on that card only", async () => {
    await renderView();
    const stale = screen.getAllByText("Verdict périmé");
    expect(stale).toHaveLength(1);
    expect(stale[0]?.getAttribute("title")).toContain("28-990f1447");
    expect(stale[0]?.getAttribute("title")).toContain("29-aaaa0000");
  });

  it("keeps the honest empty state for an agent with no run", async () => {
    await renderView();
    expect(screen.getByText("Évaluation non exécutée")).toBeDefined();
  });

  it("localizes the reason label (de)", async () => {
    await renderView("de");
    expect(screen.getByText("Blockierungsgrund (Regel 1)")).toBeDefined();
    expect(screen.getByText("Verdikt veraltet")).toBeDefined();
  });
});
