import { setRequestLocale } from "next-intl/server";

import { EvaluationsMock } from "@/components/agent/evaluations-mock";

interface PageProps {
  params: Promise<{ locale: string; agentId: string }>;
}

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return { title: "Évaluations — Maquette (réf.)" };
}

/**
 * ISOLATED high-fidelity mock of the Évaluations page, reproducing the normative
 * `09-multi-agent-evaluations-normative-fina.png` pixel-close with **fictional**
 * data. It is NOT the real, opposable Évaluations page (that lives at
 * `../` and is wired to the live payload): this route exists only to prove visual
 * fidelity is reachable without the real-data constraint. Every value is hard-coded
 * in `MOCK_DATA` and clearly labelled NON OPPOSABLE — see the banner.
 */
export default async function EvaluationsMockPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <EvaluationsMock />;
}
