// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TooltipProvider } from "@/components/ui/tooltip";
import messages from "@/messages/fr.json";

import { type EmbeddingSkewQueryState, RunsKpis, embeddingSkewTone } from "./runs-datasets";

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
