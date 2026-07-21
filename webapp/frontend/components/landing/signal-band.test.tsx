// @vitest-environment jsdom
//
// The homepage product-pillars band (ADR 0009). These lock the HONESTY contract:
// every value is the real signal, nothing is hardcoded, "vérifiée"/"prêt" appear
// only when the source actually says so, and the meaning never rides on colour or
// icon alone. `launcherPillars` is the pure mapping; `SignalBand` is the render.
import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { SignalBand } from "@/components/landing/landing-launcher";
import { launcherPillars } from "@/lib/launcher-pillars";
import type { LauncherSignal } from "@/lib/server/launcher-signal";
import messages from "@/messages/fr.json";

function mkSignal(over: Partial<LauncherSignal> = {}): LauncherSignal {
  return {
    agentsCount: 6,
    passedAgents: 2,
    agentsWithRelease: 6,
    gateVerdict: "blocked",
    agents: [],
    integrityVerified: true,
    ...over,
  };
}

// `SignalBand` takes `t` as a prop (threaded from the launcher), so a small
// wrapper resolves it from the provider — the same `t` the page would pass.
function Band({ signal }: { signal: LauncherSignal | null }) {
  const t = useTranslations("landing");
  return <SignalBand t={t} signal={signal} />;
}

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="fr" messages={messages as unknown as AbstractIntlMessages}>
      {node}
    </NextIntlClientProvider>
  );
}

afterEach(cleanup);

describe("launcherPillars — the honest mapping", () => {
  it("is null without a signal (the band then shows one honest indisponible)", () => {
    expect(launcherPillars(null)).toBeNull();
  });

  it("names the three capabilities in order, carrying the real values", () => {
    const p = launcherPillars(mkSignal());
    expect(p?.map((x) => x.key)).toEqual(["supervise", "evaluate", "prove"]);
    expect(p?.[0]).toMatchObject({ stateKey: "signal.agentsSupervised", stateVars: { count: 6 } });
    expect(p?.[1]).toMatchObject({
      stateKey: "signal.releaseGatesReady",
      stateVars: { ready: 2, total: 6 },
    });
  });

  it("release gates: honest fallback when the gate has produced no verdict", () => {
    const p = launcherPillars(mkSignal({ agentsWithRelease: 0, passedAgents: 0 }));
    expect(p?.[1]?.stateKey).toBe("signal.evaluationsActive");
    expect(p?.[1]?.stateVars).toBeUndefined();
  });

  it("integrity: verified only when really verified, honest state otherwise", () => {
    expect(launcherPillars(mkSignal({ integrityVerified: true }))?.[2]).toMatchObject({
      stateKey: "signal.integrityVerified",
      tone: "verified",
    });
    expect(launcherPillars(mkSignal({ integrityVerified: false }))?.[2]).toMatchObject({
      stateKey: "signal.integrityUnverified",
      tone: "unverified",
    });
    expect(launcherPillars(mkSignal({ integrityVerified: null }))?.[2]).toMatchObject({
      stateKey: "signal.integrityUnavailable",
      tone: "neutral",
    });
  });
});

describe("SignalBand — the rendered pillars", () => {
  it("shows the three capabilities and never 'agents sous revue' nor a raw key", () => {
    render(wrap(<Band signal={mkSignal()} />));
    expect(screen.getByText("Supervision en temps réel")).toBeTruthy();
    expect(screen.getByText("Évaluation et sécurité continues")).toBeTruthy();
    expect(screen.getByText("Preuves à tout instant")).toBeTruthy();
    expect(screen.queryByText(/sous revue/i)).toBeNull();
    expect(screen.queryByText(/signal\./)).toBeNull();
  });

  it("the agent count is the real number, correctly pluralised", () => {
    const { rerender } = render(wrap(<Band signal={mkSignal({ agentsCount: 6 })} />));
    expect(screen.getByText("6 agents supervisés")).toBeTruthy();
    rerender(wrap(<Band signal={mkSignal({ agentsCount: 1 })} />));
    expect(screen.getByText("1 agent supervisé")).toBeTruthy();
  });

  it("the ready count is the gate's real verdict", () => {
    render(wrap(<Band signal={mkSignal({ passedAgents: 2, agentsWithRelease: 6 })} />));
    expect(screen.getByText("Release gates actifs · 2 sur 6 prêts")).toBeTruthy();
  });

  it("integrity: 'vérifiée' only when verified; honest states otherwise", () => {
    const { rerender } = render(wrap(<Band signal={mkSignal({ integrityVerified: true })} />));
    expect(screen.getByText("Chaîne d’intégrité vérifiée")).toBeTruthy();
    rerender(wrap(<Band signal={mkSignal({ integrityVerified: false })} />));
    expect(screen.getByText("Chaîne non vérifiée")).toBeTruthy();
    expect(screen.queryByText("Chaîne d’intégrité vérifiée")).toBeNull();
    rerender(wrap(<Band signal={mkSignal({ integrityVerified: null })} />));
    expect(screen.getByText("Vérification indisponible")).toBeTruthy();
  });

  it("gives each column a complete accessible label (not colour/icon alone)", () => {
    render(wrap(<Band signal={mkSignal({ agentsCount: 6 })} />));
    expect(screen.getByText("Supervision en temps réel : 6 agents supervisés")).toBeTruthy();
  });

  it("renders one honest indisponible when there is no signal at all", () => {
    render(wrap(<Band signal={null} />));
    expect(screen.getByText(messages.landing.signal.unavailable)).toBeTruthy();
    expect(screen.queryByText("Supervision en temps réel")).toBeNull();
  });
});
