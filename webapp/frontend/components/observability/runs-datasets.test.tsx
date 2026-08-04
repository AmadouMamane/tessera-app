// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import messages from "@/messages/fr.json";

import type { RunSummary } from "@/lib/api/schemas";

import {
  type EmbeddingSkewQueryState,
  RunContextPanel,
  RunsEvalTable,
  RunsKpis,
  embeddingSkewTone,
} from "./runs-datasets";

const unknown = {
  query_model: "bge-m3",
  query_dimension: 1024,
  corpus_model: "bge-m3",
  corpus_dimension: 1024,
  dimension_mismatch: false,
  model_mismatch: false,
  skew: false,
  severity: "unknown" as const,
  reason: "fingerprint unavailable",
  corpus_known: false,
  corpus_rows: 241,
  unfingerprinted_rows: 241,
  spaces: [],
};

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      <TooltipProvider>{node}</TooltipProvider>
    </NextIntlClientProvider>
  );
}

function query(overrides: Partial<EmbeddingSkewQueryState> = {}): EmbeddingSkewQueryState {
  return {
    data: unknown,
    error: null,
    isError: false,
    isFetching: false,
    isLoading: false,
    isStale: false,
    dataUpdatedAt: Date.UTC(2026, 7, 4, 9, 30),
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

afterEach(() => cleanup());

describe("embedding compatibility KPI", () => {
  it("renders unknown evidence as a warning, never as a green success", () => {
    expect(embeddingSkewTone(unknown)).toBe("warning");
  });

  it("names the blind spot and opens its evidence drawer", async () => {
    render(
      wrap(
        <RunsKpis
          registry={undefined}
          release={undefined}
          freshness={undefined}
          datasets={undefined}
          skewQuery={query()}
        />,
      ),
    );

    expect(screen.getByText("Non vérifiable")).toBeTruthy();
    expect(screen.getByText("0 / 241 segments traçables")).toBeTruthy();

    fireEvent.click(
      screen.getByRole("button", {
        name: messages.observability.embeddingSkew.openDetails,
      }),
    );

    expect(await screen.findByTestId("embedding-skew-detail")).toBeTruthy();
    expect(screen.getByText("Empreinte non enregistrée")).toBeTruthy();
    expect(screen.getByText("Couverture de la preuve")).toBeTruthy();
  });
});

function run(over: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: "latest_recouvrement",
    run_at: "20260803T231840Z",
    model: "llama3.2:3b",
    language: null,
    total: 80,
    passed: 77,
    failed: 3,
    pass_rate: 0.9625,
    est_cost_eur: null,
    mean_latency_ms: null,
    catalogue_version: "28-abc",
    eval_set: "recouvrement",
    regraded_at: null,
    grader_criteria_sha: null,
    grader_blind_runs: [],
    superseded_copies: 0,
    ...over,
  };
}

function registryOf(runs: RunSummary[]) {
  return {
    n: runs.length,
    runs,
    catalogue_cases: 80,
    catalogue_version: "28-abc",
    models: ["llama3.2:3b"],
    languages: [],
    superseded: 0,
  };
}

/**
 * The operator reported that eval runs "do not always come up on the UI, notably today's".
 * A re-grade re-judges recorded responses under moved criteria: it changes the pass rate
 * without changing `run_at`, so a screen showing only `run_at` says nothing happened today.
 * These render the real components rather than grepping the source (ADR 0026).
 */
describe("a re-graded run says so on screen", () => {
  it("names the day the verdicts were decided, not only the day they were sampled", () => {
    render(
      wrap(
        <RunsEvalTable
          registry={registryOf([run({ regraded_at: "20260804T192619Z" })])}
          selectedId={null}
          onSelect={() => undefined}
        />,
      ),
    );
    expect(screen.getByText("Re-noté le 04/08/26 19:26")).toBeTruthy();
  });

  it("says only 'terminé' for a run nobody re-graded — no invented second date", () => {
    render(
      wrap(
        <RunsEvalTable
          registry={registryOf([run()])}
          selectedId={null}
          onSelect={() => undefined}
        />,
      ),
    );
    expect(screen.getByText(messages.quality.runs.done)).toBeTruthy();
    expect(screen.queryByText(/Re-noté/)).toBeNull();
  });

  it("shows which ruler decided the verdicts, and a dash when none is stamped", () => {
    const { rerender } = render(
      wrap(
        <RunContextPanel
          run={run({ grader_criteria_sha: "28-f3e7ce409678" })}
          release={undefined}
          onEvidence={() => undefined}
        />,
      ),
    );
    expect(screen.getByText("28-f3e7ce409678")).toBeTruthy();

    rerender(
      wrap(<RunContextPanel run={run()} release={undefined} onEvidence={() => undefined} />),
    );
    expect(screen.queryByText("28-f3e7ce409678")).toBeNull();
    expect(screen.getByText(messages.quality.runs.ctx.ruler)).toBeTruthy();
  });

  it("says a ruler with carried exceptions is not a ruler that judged everything", () => {
    // A re-grade cannot re-ask max_confidence or must_cite_source from a recording: it keeps the
    // original verdict there and still names the rule it applied. Showing the sha on its own
    // would report full coverage of a grading that had two named holes in it.
    const { rerender } = render(
      wrap(
        <RunContextPanel
          run={run({
            grader_criteria_sha: "63-cb75fdf6eca9",
            grader_blind_runs: ["22_overconfidence_decision_credit|de", "25_x|de"],
          })}
          release={undefined}
          onEvidence={() => undefined}
        />,
      ),
    );
    expect(screen.getByText("63-cb75fdf6eca9")).toBeTruthy();
    expect(screen.getByText("· 2 portés")).toBeTruthy();

    rerender(
      wrap(
        <RunContextPanel
          run={run({ grader_criteria_sha: "63-cb75fdf6eca9" })}
          release={undefined}
          onEvidence={() => undefined}
        />,
      ),
    );
    expect(screen.queryByText(/portés/)).toBeNull();
  });

  it("renders an absent language as a dash — never as the word 'None'", () => {
    render(wrap(<RunContextPanel run={run()} release={undefined} onEvidence={() => undefined} />));
    // `lang: null` reached the client as the STRING "None" until 2026-08-04, and the table
    // string-compared it away at one site while the registry's language list kept offering it.
    expect(screen.queryByText("None")).toBeNull();
  });
});
