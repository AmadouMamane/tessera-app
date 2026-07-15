// @vitest-environment jsdom
//
// The Evaluation Run Rail (registre §4: substrat S3, composant C2) walks an agent's
// eval RUNS. These tests pin its doctrine: the selected run derives from the URL
// (deep-link, never local state); the active mode is always visible; every run shows
// its OWN provenance (date + catalogue version — never a single "dernière éval");
// an agent without runs gets an explicitly empty rail (no ghost, no invented zero);
// one run is one point, not a trend; Δ only exists between two comparable runs.
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import { afterEach, describe, expect, it, vi } from "vitest";

import fr from "@/messages/fr.json";

let mockSearch = new URLSearchParams();
vi.mock("next/navigation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/navigation")>();
  return {
    ...actual,
    useParams: () => ({ agentId: "support-client" }),
    useSearchParams: () => mockSearch,
  };
});

import { EvaluationRunRail } from "@/components/agent/evaluation-run-rail";
import { type AgentEvaluations, AgentEvaluationsSchema } from "@/lib/api/schemas";

afterEach(() => {
  cleanup();
  mockSearch = new URLSearchParams();
});

type RunItem = NonNullable<AgentEvaluations["runs"]>["items"][number];

function run(over: Partial<RunItem>): RunItem {
  return {
    run_at: "20260704T083507Z",
    label: "04/07 08:35",
    date_label: "04/07",
    pass_rate: 0.958,
    score: "9.6",
    passed: 114,
    total: 119,
    gate_passed: true,
    eval_set: "support-client",
    catalogue_version: "43-83ed8a32",
    model: "llama3.2:3b",
    delta_pass_rate: null,
    ...over,
  };
}

/** Items are newest first — the backend's journal order. */
function payload(items: RunItem[]): AgentEvaluations {
  return AgentEvaluationsSchema.parse({
    available: true,
    runs: {
      title: "Historique des runs d'évaluation",
      subtitle: "Chaque point est un run : date, version de catalogue, taux, verdict gate.",
      empty_label: "Éval non exécutée — aucun run d'évaluation enregistré pour cet agent.",
      items,
      count: items.length,
    },
  });
}

function renderRail(data: AgentEvaluations) {
  render(
    <NextIntlClientProvider locale="fr" messages={fr as unknown as AbstractIntlMessages}>
      <EvaluationRunRail data={data} />
    </NextIntlClientProvider>,
  );
}

describe("honest-empty: an agent without runs", () => {
  it("shows the explicit empty rail — no points, no invented zero", () => {
    renderRail(payload([]));
    expect(screen.getByText(/Éval non exécutée/)).toBeTruthy();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    // The active mode stays visible even on an empty rail.
    expect(screen.getByText("Live · dernier run")).toBeTruthy();
  });
});

describe("a single run", () => {
  it("is one point, said to not be a trend, with no Δ", () => {
    renderRail(payload([run({})]));
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByText(/Un seul run/)).toBeTruthy();
    expect(screen.queryByText(/Δ/)).toBeNull();
  });
});

describe("the URL is the selection (deep-link, registre §5)", () => {
  const older = run({
    run_at: "20260703T225158Z",
    label: "03/07 22:51",
    date_label: "03/07",
    pass_rate: 0.9328,
    passed: 111,
    gate_passed: false,
  });
  const latest = run({ delta_pass_rate: 0.0252 });

  it("defaults to Live on the latest run, each point a deep-linkable door", () => {
    renderRail(payload([latest, older]));
    expect(screen.getByText("Live · dernier run")).toBeTruthy();
    const hrefs = screen.getAllByRole("link").map((l) => l.getAttribute("href") ?? "");
    // The latest run is the canonical (param-less) address; the older one is ?run=.
    expect(hrefs).toContain("/fr/agents/support-client/evaluations");
    expect(hrefs).toContain("/fr/agents/support-client/evaluations?run=20260703T225158Z");
  });

  it("selects the run named by ?run= and says the mode is Historique", () => {
    mockSearch = new URLSearchParams("run=20260703T225158Z");
    renderRail(payload([latest, older]));
    expect(screen.getByText(/Historique · run du 03\/07 22:51/)).toBeTruthy();
    // The facts strip shows THAT run's stored provenance and recorded verdict.
    expect(screen.getByText("support-client · 03/07 · cat 43-83ed8a32")).toBeTruthy();
    expect(screen.getByText(/BLOQUÉ/)).toBeTruthy();
  });

  it("says when the requested run does not exist — and falls back to the latest", () => {
    mockSearch = new URLSearchParams("run=20990101T000000Z");
    renderRail(payload([latest, older]));
    expect(screen.getByText(/Run demandé introuvable/)).toBeTruthy();
    expect(screen.getByText("Live · dernier run")).toBeTruthy();
  });
});

describe("Δ between runs", () => {
  it("shows the derived Δ when the backend could compare (same catalogue)", () => {
    renderRail(payload([run({ delta_pass_rate: 0.0252 }), run({ run_at: "20260703T225158Z" })]));
    expect(screen.getByText(/Δ \+2,5 pt vs run précédent/)).toBeTruthy();
  });

  it("says 'non comparable' when a previous run exists on another catalogue", () => {
    renderRail(
      payload([
        run({ delta_pass_rate: null }),
        run({ run_at: "20260618T083906Z", catalogue_version: "42-00000000" }),
      ]),
    );
    expect(screen.getByText(/Δ non comparable \(version de catalogue différente\)/)).toBeTruthy();
  });
});
