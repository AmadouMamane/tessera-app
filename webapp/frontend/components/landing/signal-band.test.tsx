// @vitest-environment jsdom
//
// The homepage product-pillars band (ADR 0009). These lock the HONESTY contract:
// every value is the real signal, nothing is hardcoded, "vérifiée"/"prêt" appear
// only when the source actually says so, and the meaning never rides on colour or
// icon alone. Four pillars because the two gates are different things (the online
// guard counts messages; the release gate judges agents) — fusing them was the
// dishonest line this band replaced. `launcherPillars` is the pure mapping;
// `SignalBand` is the render (polling disabled here via pollMs={0}).
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
    evaluationBuckets: { ready: 2, review: 4 },
    gateVerdict: "blocked",
    agents: [],
    integrityVerified: true,
    opposabilityBadge: "scelle_opposable",
    guardActivity: { checkedToday: 214, blockedToday: 2 },
    generatedAt: "2026-07-21T12:00:00.000Z",
    ...over,
  };
}

// `SignalBand` takes `t` as a prop (threaded from the launcher), so a small
// wrapper resolves it from the provider — the same `t` the page would pass.
// Polling is off: these tests judge the mapping and the render, not the timer.
function Band({ signal }: { signal: LauncherSignal | null }) {
  const t = useTranslations("landing");
  return <SignalBand t={t} signal={signal} pollMs={0} />;
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

  it("names the four capabilities in order, carrying the real values", () => {
    const p = launcherPillars(mkSignal());
    expect(p?.map((x) => x.key)).toEqual(["supervise", "secure", "evaluate", "prove"]);
    expect(p?.[0]).toMatchObject({ stateKey: "signal.agentsSupervised", stateVars: { count: 6 } });
    expect(p?.[1]).toMatchObject({
      stateKey: "signal.messagesChecked",
      stateVars: { checked: 214, blocked: 2 },
    });
    expect(p?.[2]).toMatchObject({
      stateKey: "signal.evaluateBuckets",
      stateVars: { ready: 2, review: 4 },
    });
  });

  it("guard activity: honest states when the counters are missing or quiet", () => {
    expect(launcherPillars(mkSignal({ guardActivity: null }))?.[1]).toMatchObject({
      stateKey: "signal.activityUnavailable",
      tone: "neutral",
    });
    expect(
      launcherPillars(mkSignal({ guardActivity: { checkedToday: 0, blockedToday: 0 } }))?.[1],
    ).toMatchObject({ stateKey: "signal.noMessagesToday" });
  });

  it("release gate: honest fallback when the gate has produced no verdict", () => {
    const p = launcherPillars(mkSignal({ evaluationBuckets: null }));
    expect(p?.[2]?.stateKey).toBe("signal.evaluationsActive");
    expect(p?.[2]?.stateVars).toBeUndefined();
  });

  it("release gate: the review bucket puts the column back in play", () => {
    const p = launcherPillars(mkSignal({ evaluationBuckets: { ready: 2, review: 1 } }));
    expect(p?.[2]).toMatchObject({ stateKey: "signal.evaluateBuckets", tone: "stale" });
  });

  it("release gate: ignores the legacy frontend rollup and uses the shared endpoint buckets", () => {
    const p = launcherPillars(
      mkSignal({
        passedAgents: 99,
        agentsWithRelease: 99,
        evaluationBuckets: { ready: 2, review: 4 },
      }),
    );
    expect(p?.[2]?.stateVars).toEqual({ ready: 2, review: 4 });
  });

  it("proof: infalsifiable only when the qualified external seal earns it", () => {
    expect(
      launcherPillars(
        mkSignal({ integrityVerified: true, opposabilityBadge: "scelle_opposable" }),
      )?.[3],
    ).toMatchObject({
      stateKey: "signal.ledgerInfalsifiable",
      tone: "verified",
    });
    expect(
      launcherPillars(
        mkSignal({ integrityVerified: true, opposabilityBadge: "integrite_partielle" }),
      )?.[3],
    ).toMatchObject({ stateKey: "signal.integrityVerifiedSealPending", tone: "stale" });
    expect(
      launcherPillars(mkSignal({ integrityVerified: false, opposabilityBadge: "non_scelle" }))?.[3],
    ).toMatchObject({
      stateKey: "signal.integrityUnverified",
      tone: "unverified",
    });
    expect(
      launcherPillars(mkSignal({ integrityVerified: null, opposabilityBadge: null }))?.[3],
    ).toMatchObject({
      stateKey: "signal.integrityUnavailable",
      tone: "neutral",
    });
  });
});

describe("SignalBand — the rendered pillars", () => {
  it("shows the four capabilities and never a raw key", () => {
    render(wrap(<Band signal={mkSignal()} />));
    expect(screen.getByText("Supervision en temps réel")).toBeTruthy();
    expect(screen.getByText("Sécurité à chaque message")).toBeTruthy();
    expect(screen.getByText("Évaluation avant production")).toBeTruthy();
    expect(screen.getByText("Preuves à tout instant")).toBeTruthy();
    expect(screen.queryByText(/signal\./)).toBeNull();
  });

  it("the agent count is the real number, correctly pluralised, observed not touched", () => {
    const { rerender } = render(wrap(<Band signal={mkSignal({ agentsCount: 6 })} />));
    expect(screen.getAllByText(/6 agents observés/).length).toBeGreaterThan(0);
    rerender(wrap(<Band signal={mkSignal({ agentsCount: 1 })} />));
    expect(screen.getAllByText(/1 agent observé/).length).toBeGreaterThan(0);
  });

  it("the guard counters are the real numbers, with the day's blocks", () => {
    render(wrap(<Band signal={mkSignal()} />));
    expect(
      screen.getAllByText(/214 messages contrôlés · 2 bloqués aujourd’hui/).length,
    ).toBeGreaterThan(0);
  });

  it("a quiet day renders a real 'aucun blocage', never a fabricated count", () => {
    render(
      wrap(<Band signal={mkSignal({ guardActivity: { checkedToday: 9, blockedToday: 0 } })} />),
    );
    expect(screen.getAllByText(/9 messages contrôlés · aucun blocage/).length).toBeGreaterThan(0);
  });

  it("the ready count is the gate's real verdict", () => {
    render(wrap(<Band signal={mkSignal({ evaluationBuckets: { ready: 2, review: 4 } })} />));
    expect(screen.getAllByText(/2 agents prêts · 4 à évaluer ou réévaluer/).length).toBeGreaterThan(
      0,
    );
  });

  it("proof: the infalsifiable label follows the qualified live verdict", () => {
    const { rerender } = render(
      wrap(
        <Band
          signal={mkSignal({
            integrityVerified: true,
            opposabilityBadge: "scelle_opposable",
          })}
        />,
      ),
    );
    expect(screen.getAllByText(/Registre infalsifiable/).length).toBeGreaterThan(0);
    rerender(
      wrap(
        <Band
          signal={mkSignal({
            integrityVerified: true,
            opposabilityBadge: "integrite_partielle",
          })}
        />,
      ),
    );
    expect(
      screen.getAllByText(/Chaîne vérifiée · scellement qualifié attendu/).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/Registre infalsifiable/)).toBeNull();
    rerender(
      wrap(
        <Band signal={mkSignal({ integrityVerified: false, opposabilityBadge: "non_scelle" })} />,
      ),
    );
    expect(screen.getAllByText(/Chaîne non vérifiée/).length).toBeGreaterThan(0);
    rerender(
      wrap(<Band signal={mkSignal({ integrityVerified: null, opposabilityBadge: null })} />),
    );
    expect(screen.getAllByText(/Vérification indisponible/).length).toBeGreaterThan(0);
  });

  it("the temporal pillars carry a freshness stamp — 'temps réel' is witnessed, not asserted", () => {
    render(wrap(<Band signal={mkSignal({ agentsCount: 6 })} />));
    expect(
      screen.getByText("Supervision en temps réel : 6 agents observés · à l’instant"),
    ).toBeTruthy();
    // The two non-temporal pillars carry no stamp.
    expect(screen.getByText(/^Sécurité à chaque message : 214 messages contrôlés/)).toBeTruthy();
  });

  it("each pillar offers its ⓘ explanation (the only buttons in the band)", () => {
    render(wrap(<Band signal={mkSignal()} />));
    expect(screen.getAllByRole("button").length).toBe(4);
  });

  it("renders one honest indisponible when there is no signal at all", () => {
    render(wrap(<Band signal={null} />));
    expect(screen.getByText(messages.landing.signal.unavailable)).toBeTruthy();
    expect(screen.queryByText("Supervision en temps réel")).toBeNull();
  });
});
