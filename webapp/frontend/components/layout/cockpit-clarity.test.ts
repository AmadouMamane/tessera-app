import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

type Catalogue = typeof fr | typeof en | typeof de;

const PAGE_ENTRY_NAMESPACES = [
  "fleet",
  "overview",
  "quality",
  "signalCatalogue",
  "security",
  "policies",
  "compliance",
  "health",
  "agentConsole",
  "agentPrompts",
  "proofs",
  "curation",
  "releaseControl",
  "replay",
  "sources",
] as const;

const OPAQUE_FLEET_COPY = {
  fr: /Somme naïve|total org|dédoublonn|org-wide|eval-gate|run de référence|\bKPI(?:s)?\b/iu,
  en: /naive sum|org total|deduplicat(?:e|ed|ion)|org-wide|eval-gate/iu,
  de: /naive Summe|Org-Gesamt|dedupl|org-weit|Eval-Gate/iu,
} as const;

const OPAQUE_FRENCH_PAGE_ENTRY =
  /\b(?:run|runs|dataset|datasets|release|runtime|baseline|eval-gate|pipeline)\b/iu;

const OPAQUE_PRIMARY_QUALITY_COPY = {
  fr: /\b(?:SLO|Burn|runs?|datasets?|gate|release)\b/iu,
  en: /\b(?:SLO|Burn|runs?|datasets?|gate|release)\b/iu,
  de: /\b(?:SLO|Burn|Runs?|Datasets?|Gate|Release)\b/iu,
} as const;

const OPAQUE_NAV_COPY = {
  fr: /Release Control|Signal Catalog|Curation eval set|Evidence store|Sécurité & Privacy|Policies/iu,
  en: /Release Control|Signal Catalog|Eval.set curation|Evidence store|Security & Privacy/u,
  de: /Release.Control|Signal Catalog|Eval.Set|Evidence.Speicher|Policies|Prompts/iu,
} as const;

const OPAQUE_SECONDARY_QUALITY_COPY = {
  fr: /\b(?:run|runs|dataset|datasets|releases?|RAG|Operator)\b|Pass-rate|Signal Catalog|Calibration juge|Accord juge|Dual control|regression-set/iu,
  en: /\b(?:run|runs|dataset|datasets|releases?|RAG)\b|Pass-rate|Judge calibration|Dual control/iu,
  de: /\b(?:Run|Runs|Dataset|Datasets|Releases?|RAG)\b|Pass-Rate|Judge|Dual Control|Signal Catalog/iu,
} as const;

const OPAQUE_INCIDENT_COPY = {
  fr: /\b(?:MTTA|MTTR|SLA|playbook|triage|post-mortem|automation|PII|RAG|release)\b|Evidence pack|Prompt injection|Dry-run/iu,
  en: /\b(?:MTTA|MTTR|SLA|playbook|triage|post-mortem|automation|PII|RAG|release)\b|Evidence pack|Prompt injection|Dry-run/iu,
  de: /\b(?:MTTA|MTTR|SLA|Playbook|Triage|Post-Mortem|Automation|PII|RAG|Release)\b|Evidence-Pack|Prompt-Injection|Dry-run/iu,
} as const;

const OPAQUE_CURATION_COPY = {
  fr: /\b(?:curation|curer|gaps?|promouvable|intent|workflow|release|datasets?|readiness|pass-rate|dual-control|PII|RAG)\b|dédoubl|cross-tenant|Owners/iu,
  en: /\b(?:curation|gaps?|promotable|intent|workflow|release|datasets?|readiness|pass-rate|dual-control|PII|RAG)\b|dedup|cross-tenant|evidence pack/iu,
  de: /\b(?:Kuration|Gaps?|beförderbar|Intent|Workflow|Release|Datasets?|Readiness|Pass-Rate|Dual-Control|PII|RAG)\b|Dedupl|Cross-Tenant|Evidence-Pack/iu,
} as const;

const OPAQUE_RELEASE_COPY = {
  fr: /\b(?:promouvoir|run|eval|socle|T0|T1|dérogé|release|live|gate|waiver|pipeline)\b/iu,
  en: /\b(?:promote|run|eval|socle|T0|T1|waiver|release|live|gate|pipeline)\b/iu,
  de: /\b(?:Promotion|Lauf|Eval|Sockel|T0|T1|Waiver|Release|Live|Gate|Pipeline)\b/iu,
} as const;

const OPAQUE_AUTOMATION_COPY = {
  fr: /\b(?:automations?|orchestration|pipeline|MTTR|run|release|gate|PII|policy|backlog|curation)\b|dual[- ]control|evidence pack/iu,
  en: /\b(?:automation|orchestrate|pipeline|MTTR|release|gate|PII|policy|backlog|curation)\b|dual control|evidence pack|guardrail/iu,
  de: /\b(?:Automatisierung|Orchestrierung|Pipeline|MTTR|Lauf|Release|Gate|PII|Policy|Backlog|Kuration)\b|Dual.Control|Evidence.Pack/iu,
} as const;

const OPAQUE_PROOF_COPY = {
  fr: /Evidence packs?|Exporteurs?|Pipeline de preuve|Pack courant|Artefacts?|Bundles?|Manifest|Dernier push|Case ID/iu,
  en: /Evidence packs?|Exporters?|Proof pipeline|Current pack|Artifacts?|Replay bundles?|Manifest|Last push|Case ID\b/iu,
  de: /Evidence.Packs?|Exporteure?|Nachweis.Pipeline|Aktuelles Pack|Artefakte?|Replay.Bundles?|Manifest|Letzter Push|Case.ID/iu,
} as const;

const OPAQUE_QUEUE_COPY = {
  fr: /\bLive\b|Relire file à T|\bSLA\b|File réelle|Run d'évaluation|Timeline événements/iu,
  en: /\bLive\b|Replay queue at T|\bSLA\b|Real queue|Evaluation run|Event timeline/iu,
  de: /\bLive\b|Queue bei T|\bSLA\b|Echte Warteschlange|Evaluierungslauf|Ereignis.Timeline/iu,
} as const;

const OPAQUE_SIGNAL_COPY = {
  fr: /\bCritical\b|\bActif\b|En évaluation|Qualité \(30j\)|Propriétaire|Performance réelle|Composition de la garde/iu,
  en: /\bActive\b|In evaluation|Quality \(30d\)|Real performance|Guard composition/iu,
  de: /\bCritical\b|\bAktiv\b|In Bewertung|Qualität \(30T\)|\bOwner\b|Reale Leistung|Guard.Zusammensetzung/iu,
} as const;

const OPAQUE_SHARED_COPY = {
  fr: /org-wide|Dual control|Admin\+|Relire à T|Ops Admin/iu,
  en: /org-wide|Dual control|Admin\+|Replay at T|Ops Admin/iu,
  de: /org-weit|Dual Control|Admin\+|(?:Wiedergabe|Stand) (?:bei|zu) T|Ops Admin/iu,
} as const;

const OPAQUE_OVERVIEW_COPY = {
  fr: /\b(?:SLO|SLA|playbooks?|RAG|Privacy|Guard|gates?|releases?|roadmap|bucket)\b|vitesse de consommation|Comparer au Live|sonde live/iu,
  en: /\b(?:SLO|SLA|playbooks?|RAG|PII|gates?|releases?|roadmap|bucket|burn-rate)\b|Compare to Live|live probe/iu,
  de: /\b(?:SLO|SLA|Playbooks?|RAG|PII|Gates?|Releases?|Roadmap|Bucket)\b|Mit Live vergleichen|Live-Sonde/iu,
} as const;

function stringValues(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(stringValues);
  if (value && typeof value === "object") return Object.values(value).flatMap(stringValues);
  return [];
}

function visibleFleetCopy(catalogue: Catalogue): string {
  return stringValues({ fleet: catalogue.fleet, agentScope: catalogue.agentScope }).join("\n");
}

function pageEntryCopy(catalogue: Catalogue): string[] {
  return PAGE_ENTRY_NAMESPACES.flatMap((namespace) => {
    const copy = catalogue[namespace] as {
      title?: string;
      subtitle?: string;
      description?: string;
    };
    return [copy.title, copy.subtitle, copy.description].filter(
      (value): value is string => !!value,
    );
  });
}

function primaryQualityCopy(catalogue: Catalogue): string {
  return stringValues({
    tabs: catalogue.quality.tabs,
    cta: catalogue.quality.cta,
    views: catalogue.quality.views,
    signalHero: catalogue.signalHero,
  }).join("\n");
}

function primaryNavCopy(catalogue: Catalogue): string {
  const { nav } = catalogue;
  return [
    nav.security,
    nav.replay,
    nav.curation,
    nav.release,
    nav.proofExporters,
    nav.signalCatalog,
    nav.policies,
    nav.item.prompts,
    nav.item.securitePrivacy,
    nav.item.replayShadow,
    nav.item.curationEvalSet,
    nav.item.releaseControl,
    nav.item.evidenceStore,
    nav.item.signalCatalog,
  ].join("\n");
}

function secondaryQualityCopy(catalogue: Catalogue): string {
  const { quality } = catalogue;
  return stringValues({
    reco: quality.reco,
    rr: quality.rr,
    statusbar: quality.statusbar,
    rail: quality.rail,
    kpi: quality.kpi,
    charts: quality.charts,
    release: quality.release,
    exec: quality.exec,
    signalsTable: quality.signalsTable,
  }).join("\n");
}

function incidentCopy(catalogue: Catalogue): string {
  return stringValues(catalogue.incidents).join("\n");
}

function primaryCurationCopy(catalogue: Catalogue): string {
  const { curation } = catalogue;
  return stringValues({
    tabs: curation.tabs,
    actions: curation.actions,
    zone: curation.zone,
    kpi: curation.kpi,
    panel: curation.panel,
    col: curation.col,
    source: curation.source,
    category: curation.category,
    dist: curation.dist,
    cov: curation.cov,
    signal: curation.signal,
    dsCol: curation.dsCol,
    action: curation.action,
    actCtrl: curation.actCtrl,
    quick: curation.quick,
    release: curation.release,
    evidence: curation.evidence,
    backlogLegend: curation.backlogLegend,
    balanceLegend: curation.balanceLegend,
    impact: curation.impact,
    viewAll: curation.viewAll,
    footer: curation.footer,
    decide: curation.decide,
    tabview: curation.tabview,
  }).join("\n");
}

function primaryReleaseCopy(catalogue: Catalogue): string {
  const { releaseControl } = catalogue;
  return stringValues({
    viewFleet: releaseControl.viewFleet,
    viewAgent: releaseControl.viewAgent,
    summaryCases: releaseControl.summaryCases,
    floorReason: releaseControl.floorReason,
    floorSummary: releaseControl.floorSummary,
    floorSummaryGeneric: releaseControl.floorSummaryGeneric,
    floorTechnicalDetail: releaseControl.floorTechnicalDetail,
    stale: releaseControl.stale,
    staleTitle: releaseControl.staleTitle,
    title: releaseControl.title,
    subtitle: releaseControl.subtitle,
    total: releaseControl.total,
    passing: releaseControl.passing,
    blocked: releaseControl.blocked,
    notRun: releaseControl.notRun,
    evalNotRun: releaseControl.evalNotRun,
    evalSet: releaseControl.evalSet,
    executions: releaseControl.executions,
    socle: releaseControl.socle,
    socleOk: releaseControl.socleOk,
    socleFail: releaseControl.socleFail,
    blockingSocle: releaseControl.blockingSocle,
    blockingT1: releaseControl.blockingT1,
    waived: releaseControl.waived,
    lastEvent: releaseControl.lastEvent,
    empty: releaseControl.empty,
    flow: releaseControl.flow,
  }).join("\n");
}

function primaryAutomationCopy(catalogue: Catalogue): string {
  const { automations } = catalogue;
  return stringValues({
    title: automations.title,
    subtitle: automations.subtitle,
    tabs: automations.tabs,
    actions: automations.actions,
    zone: automations.zone,
    kpi: automations.kpi,
    panel: automations.panel,
    col: automations.col,
    mode: automations.mode,
    status: automations.status,
    pipeline: automations.pipeline,
    type: automations.type,
    env: automations.env,
    jCol: automations.jCol,
    result: automations.result,
    approve: automations.approve,
    gr: automations.gr,
    perf: automations.perf,
    savings: automations.savings,
    ctx: automations.ctx,
    gov: automations.gov,
    quick: automations.quick,
    viewAll: automations.viewAll,
    footer: automations.footer,
    tabx: automations.tabx,
  }).join("\n");
}

function primaryProofCopy(catalogue: Catalogue): string {
  const { proofs } = catalogue;
  return stringValues({
    title: proofs.title,
    tabs: proofs.tabs,
    rail: proofs.rail,
    zone: proofs.zone,
    kpi: proofs.kpi,
    pipeline: proofs.pipeline,
    pack: proofs.pack,
    content: proofs.content,
    packCol: proofs.packCol,
    art: proofs.art,
    expCol: proofs.expCol,
    ccCol: proofs.ccCol,
    quick: proofs.quick,
    viewAll: proofs.viewAll,
  }).join("\n");
}

function primaryQueueCopy(catalogue: Catalogue): string {
  return stringValues({
    inbox: {
      rail: catalogue.inbox.rail,
      kpi: catalogue.inbox.kpi,
      col: catalogue.inbox.col,
      zone: catalogue.inbox.zone,
      sla: catalogue.inbox.sla,
      actions: catalogue.inbox.actions,
    },
    aFaire: {
      title: catalogue.agentAFaire.title,
      subtitle: catalogue.agentAFaire.subtitle,
    },
  }).join("\n");
}

function primarySignalCopy(catalogue: Catalogue): string {
  const { signalCatalogue } = catalogue;
  return stringValues({
    name: signalCatalogue.name,
    sourceValue: signalCatalogue.sourceValue,
    ownerValue: signalCatalogue.ownerValue,
    kpi: signalCatalogue.kpi,
    col: signalCatalogue.col,
    severity: signalCatalogue.severity,
    status: signalCatalogue.status,
    performance: signalCatalogue.detail.secPerformance,
    controls: signalCatalogue.detail.secGuard,
  }).join("\n");
}

function sharedFirstReadingCopy(catalogue: Catalogue): string {
  return stringValues({
    signalScope: catalogue.quality.signalsRail.byAgent_no,
    signalApproval: catalogue.quality.signalsRail.dualControl,
    securityApproval: catalogue.security.dualControl,
    sensitivePolicy: catalogue.policies.sensitive.reservedOps,
    userScope: catalogue.users.phaseNote,
    assistantDate: catalogue.assistant.replayAt,
    qualityDate: catalogue.quality.temporal.replay,
    agentDate: catalogue.agentSynthese.cmd.replay,
  }).join("\n");
}

function overviewFirstReadingCopy(catalogue: Catalogue): string {
  const { overview } = catalogue;
  return stringValues({
    quality: overview.kpi.quality,
    qualityDelta: overview.kpi.qualityDelta,
    cases: overview.explain.cases,
    procedures: overview.explain.controlCases,
    incidents: overview.explain.rightIncidents,
    goLive: overview.explain.rightRelease,
    scores: overview.explain.analyticsScores,
    improvement: overview.explain.governanceSection,
    improvementTitle: overview.governance.title,
    uncataloguedMeasurement: overview.criticalControls.liveProbe,
    signals: overview.signals,
    impact: overview.impact,
    controlCases: overview.controlCases,
    rightColumn: overview.rightColumn,
    pauseGoLives: {
      action: overview.quick.freezeReleases,
      paused: overview.quick.frozen,
      resumed: overview.quick.unfrozen,
      compare: overview.quick.compareLive,
    },
  }).join("\n");
}

function excessiveAlertGap(source: string): number[] {
  return [...source.matchAll(/className="mb-(\d+)"[^>]*>[\s\S]{0,160}<SignalBreachHero/g)].flatMap(
    (match) => {
      const spacing = Number(match[1]);
      return spacing > 3 ? [spacing] : [];
    },
  );
}

function oversizedUpwardShadow(source: string): number[] {
  return [...source.matchAll(/shadow-\[0_-(\d+)px_0_0_var\(--tessera-bg\)\]/g)].flatMap((match) => {
    const depth = Number(match[1]);
    return depth > 8 ? [depth] : [];
  });
}

function overviewStackGap(source: string): number | undefined {
  const match = source.match(/flex w-full flex-col gap-(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : undefined;
}

function commandRowPadding(source: string): number | undefined {
  const match = source.match(/sr01-command-row[^"]* py-(\d+(?:\.\d+)?)/);
  return match ? Number(match[1]) : undefined;
}

function timelineTopGap(source: string): number | undefined {
  const match = source.match(
    /className="relative mt-(\d+(?:\.\d+)?)[^"]*cursor-pointer select-none"/,
  );
  return match ? Number(match[1]) : undefined;
}

describe("cockpit language stays human at the first reading level", () => {
  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)(
    "%s explains fleet totals without internal aggregation jargon",
    (locale, catalogue) => {
      expect(visibleFleetCopy(catalogue)).not.toMatch(OPAQUE_FLEET_COPY[locale]);
    },
  );

  it("keeps technical project vocabulary out of French page introductions", () => {
    expect(pageEntryCopy(fr).filter((copy) => OPAQUE_FRENCH_PAGE_ENTRY.test(copy))).toEqual([]);
  });

  it("preserves the facts needed by every fleet reconciliation state in all three languages", () => {
    for (const catalogue of [fr, en, de]) {
      expect(catalogue.agentScope.noHandoffSummary).toContain("{total}");
      expect(catalogue.agentScope.handoffSummary.one).toContain("{total}");
      expect(catalogue.agentScope.handoffSummary.many).toContain("{attested}");
      expect(catalogue.agentScope.handoffSummary.many).toContain("{total}");
      expect(catalogue.agentScope.handoffGap).toContain("{events}");
      expect(catalogue.agentScope.handoffGap).toContain("{attested}");
      expect(catalogue.agentScope.handoffGap).toContain("{seen}");
      expect(catalogue.agentScope).not.toHaveProperty("breakdownNote");
    }
  });

  it("uses a natural zero-state for fleet reconciliation in every language", () => {
    expect(fr.agentScope.noHandoffSummary).toMatch(/aucun transfert.*total de la flotte/u);
    expect(en.agentScope.noHandoffSummary).toMatch(/No handoff.*fleet total/u);
    expect(de.agentScope.noHandoffSummary).toMatch(/keine Übergabe.*Flottensumme/u);
  });

  it("explains verified transfers in ordinary language in every language", () => {
    expect(fr.agentScope.handoffSummary.many).toMatch(/deux agents concernés.*une fois/u);
    expect(en.agentScope.handoffSummary.many).toMatch(/both agents.*only once/u);
    expect(de.agentScope.handoffSummary.many).toMatch(/beider beteiligten Agenten.*einmal/u);
  });

  it("explains why a transferred conversation can be counted under two agents", () => {
    expect(fr.agentScope.handoffGap).toMatch(/agent de départ.*agent d'arrivée/u);
    expect(en.agentScope.handoffGap).toMatch(/sending.*receiving agent/u);
    expect(de.agentScope.handoffGap).toMatch(/abgebenden.*übernehmenden Agenten/u);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)(
    "%s keeps the quality landing view and main navigation jargon-free",
    (locale, catalogue) => {
      expect(primaryQualityCopy(catalogue)).not.toMatch(OPAQUE_PRIMARY_QUALITY_COPY[locale]);
      expect(secondaryQualityCopy(catalogue)).not.toMatch(OPAQUE_SECONDARY_QUALITY_COPY[locale]);
      expect(primaryNavCopy(catalogue)).not.toMatch(OPAQUE_NAV_COPY[locale]);
    },
  );

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s explains incident handling without internal shorthand", (locale, catalogue) => {
    expect(incidentCopy(catalogue)).not.toMatch(OPAQUE_INCIDENT_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s explains evaluation-set work without internal shorthand", (locale, catalogue) => {
    expect(primaryCurationCopy(catalogue)).not.toMatch(OPAQUE_CURATION_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s explains launch readiness without internal shorthand", (locale, catalogue) => {
    expect(primaryReleaseCopy(catalogue)).not.toMatch(OPAQUE_RELEASE_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s explains automatic rules without internal shorthand", (locale, catalogue) => {
    expect(primaryAutomationCopy(catalogue)).not.toMatch(OPAQUE_AUTOMATION_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s names evidence objects in operator language", (locale, catalogue) => {
    expect(primaryProofCopy(catalogue)).not.toMatch(OPAQUE_PROOF_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s explains work queues without delivery shorthand", (locale, catalogue) => {
    expect(primaryQueueCopy(catalogue)).not.toMatch(OPAQUE_QUEUE_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s gives monitored signals human display names", (locale, catalogue) => {
    expect(primarySignalCopy(catalogue)).not.toMatch(OPAQUE_SIGNAL_COPY[locale]);
    expect(Object.keys(catalogue.signalCatalogue.name)).toHaveLength(10);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s keeps shared scope, authority and date controls human", (locale, catalogue) => {
    expect(sharedFirstReadingCopy(catalogue)).not.toMatch(OPAQUE_SHARED_COPY[locale]);
  });

  it.each([
    ["fr", fr],
    ["en", en],
    ["de", de],
  ] as const)("%s keeps the overview readable without delivery shorthand", (locale, catalogue) => {
    expect(overviewFirstReadingCopy(catalogue)).not.toMatch(OPAQUE_OVERVIEW_COPY[locale]);
  });

  it("explains every shared authority level without changing its technical token", () => {
    expect(stringValues(fr.authority).join("\n")).not.toMatch(/Admin\+|Operator\+|Compliance\+/u);
    expect(fr.authority.technical).toContain("{role}");
  });

  it("has teeth: restoring the original fleet sentence turns the ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.agentScope.noHandoffSummary =
      "Somme naïve {naive} · {saved} dédoublonnées · {shared} conversations partagées";
    expect(visibleFleetCopy(mutant)).toMatch(OPAQUE_FLEET_COPY.fr);
  });

  it("has teeth: restoring SLO and Runs & datasets turns the primary-copy ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.quality.tabs.runs = "Runs & datasets";
    mutant.signalHero.title = "Signal franchi (SLO)";
    expect(primaryQualityCopy(mutant)).toMatch(OPAQUE_PRIMARY_QUALITY_COPY.fr);
  });

  it("has teeth: restoring triage and MTTR turns the incident-copy ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.incidents.zone.triage = "B · Diagnostic / triage";
    mutant.incidents.kpi.mttr = "MTTR (moy. 7 j)";
    expect(incidentCopy(mutant)).toMatch(OPAQUE_INCIDENT_COPY.fr);
  });

  it("has teeth: restoring curation and dataset jargon turns its ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.curation.tabs.curate = "À curer";
    mutant.curation.panel.linkedDatasets = "Datasets liés";
    expect(primaryCurationCopy(mutant)).toMatch(OPAQUE_CURATION_COPY.fr);
  });

  it("has teeth: restoring run and socle labels turns the launch ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.releaseControl.notRun = "Sans run";
    mutant.releaseControl.socle = "Socle (T0)";
    expect(primaryReleaseCopy(mutant)).toMatch(OPAQUE_RELEASE_COPY.fr);
  });

  it("has teeth: restoring automation pipeline jargon turns its ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.automations.title = "Automations";
    mutant.automations.zone.pipeline = "Pipeline d'exécution";
    expect(primaryAutomationCopy(mutant)).toMatch(OPAQUE_AUTOMATION_COPY.fr);
  });

  it("has teeth: restoring evidence-pack jargon turns the proof ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.proofs.tabs.evidencePacks = "Evidence packs";
    mutant.proofs.zone.pipeline = "Pipeline de preuve";
    expect(primaryProofCopy(mutant)).toMatch(OPAQUE_PROOF_COPY.fr);
  });

  it("has teeth: restoring SLA and Live turns the queue ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.inbox.rail.live = "Live";
    mutant.inbox.kpi.sla_2h = "SLA < 2h";
    expect(primaryQueueCopy(mutant)).toMatch(OPAQUE_QUEUE_COPY.fr);
  });

  it("has teeth: restoring raw signal labels turns the signal ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.signalCatalogue.kpi.critical = "Critical";
    mutant.signalCatalogue.col.owner = "Propriétaire";
    expect(primarySignalCopy(mutant)).toMatch(OPAQUE_SIGNAL_COPY.fr);
  });

  it("has teeth: restoring org-wide and Replay at T turns the shared ratchet red", () => {
    const mutant = structuredClone(en);
    mutant.quality.signalsRail.byAgent_no = "No — org-wide by construction";
    mutant.quality.temporal.replay = "Replay at T";
    expect(sharedFirstReadingCopy(mutant)).toMatch(OPAQUE_SHARED_COPY.en);
  });

  it("has teeth: restoring release gates turns the overview ratchet red", () => {
    const mutant = structuredClone(fr);
    mutant.overview.rightColumn.release = "Release / changements";
    mutant.overview.rightColumn.gates.quality = "Gate qualité";
    expect(overviewFirstReadingCopy(mutant)).toMatch(OPAQUE_OVERVIEW_COPY.fr);
  });
});

describe("alert-to-rail spacing stays compact", () => {
  const root = process.cwd();
  const qualityPage = readFileSync(
    join(root, "app/[locale]/surveiller/qualite-ia/page.tsx"),
    "utf8",
  );
  const overviewPage = readFileSync(
    join(root, "app/[locale]/surveiller/vue-ensemble/page.tsx"),
    "utf8",
  );
  const qualityDashboard = readFileSync(
    join(root, "components/observability/observability-dashboard.tsx"),
    "utf8",
  );
  const overviewDashboard = readFileSync(
    join(root, "components/overview/overview-dashboard.tsx"),
    "utf8",
  );
  const signalCommandBar = readFileSync(
    join(root, "components/surveiller/signal-command-bar.tsx"),
    "utf8",
  );
  const temporalRail = readFileSync(join(root, "components/overview/temporal-rail.tsx"), "utf8");

  it("does not insert a large margin between a signal banner and its temporal controls", () => {
    expect(excessiveAlertGap(qualityPage)).toEqual([]);
    expect(excessiveAlertGap(overviewPage)).toEqual([]);
  });

  it("keeps the sticky background fill shallow enough for the compact gap", () => {
    expect(oversizedUpwardShadow(qualityDashboard)).toEqual([]);
    expect(oversizedUpwardShadow(overviewDashboard)).toEqual([]);
  });

  it("pins the overview rail against the header instead of exposing scrolling content", () => {
    expect(overviewDashboard).toContain('className="sticky -top-5 z-40');
    expect(overviewDashboard).not.toContain('className="sticky top-0 z-40');

    const transparentGapMutation = overviewDashboard.replace("sticky -top-5", "sticky top-0");
    expect(transparentGapMutation).toContain('className="sticky top-0 z-40');
  });

  it("keeps the overview opening band and expanded rail vertically compact", () => {
    expect(overviewStackGap(overviewDashboard)).toBe(2.5);
    expect(commandRowPadding(signalCommandBar)).toBeLessThanOrEqual(1.5);
    expect(timelineTopGap(temporalRail)).toBeLessThanOrEqual(3);
  });

  it("uses a ten-pixel rhythm between sibling surfaces on the overview", () => {
    for (const layoutClass of [
      "grid gap-2.5 2xl:grid-cols-[minmax(0,1fr)_auto] 2xl:items-center",
      "grid gap-2.5 md:grid-cols-2 xl:grid-cols-6",
      "grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_320px] 2xl:grid-cols-[minmax(0,1fr)_340px]",
      "flex min-w-0 flex-col gap-2.5",
      "grid gap-2.5 xl:grid-cols-3",
    ]) {
      expect(overviewDashboard).toContain(layoutClass);
    }
  });

  it("has teeth: the former spacing and shadow are rejected", () => {
    const marginMutation = '<div className="mb-6"><SignalBreachHero /></div>';
    const shadowMutation =
      '<div className="shadow-[0_-20px_0_0_var(--tessera-bg)]">temporal controls</div>';
    const stackMutation = '<div className="flex w-full flex-col gap-4 pb-8">';
    const commandMutation = '<div className="sr01-command-row flex py-3">';
    const timelineMutation = '<div className="relative mt-6 h-14 cursor-pointer select-none">';
    expect(excessiveAlertGap(marginMutation)).toEqual([6]);
    expect(oversizedUpwardShadow(shadowMutation)).toEqual([20]);
    expect(overviewStackGap(stackMutation)).toBeGreaterThan(2.5);
    expect(commandRowPadding(commandMutation)).toBeGreaterThan(1.5);
    expect(timelineTopGap(timelineMutation)).toBeGreaterThan(3);
  });
});

describe("cockpit surfaces keep one ten-pixel rhythm", () => {
  const root = process.cwd();
  const shellFrame = readFileSync(join(root, "components/layout/shell-frame.tsx"), "utf8");
  const card = readFileSync(join(root, "components/ui/card.tsx"), "utf8");
  const globals = readFileSync(join(root, "app/globals.css"), "utf8");
  const security = readFileSync(join(root, "components/security/security-dashboard.tsx"), "utf8");
  const qualityViewSwitch = readFileSync(
    join(root, "components/surveiller/quality-view-switch.tsx"),
    "utf8",
  );

  const pageRoots = [
    "components/incidents/incidents-overview.tsx",
    "components/curation/curation-overview.tsx",
    "components/replay/replay-overview.tsx",
    "components/system/system-profile.tsx",
    "components/parameters/parameters-overview.tsx",
    "components/proofs/proofs-overview.tsx",
    "components/policies/policies-overview.tsx",
    "components/automations/automations-overview.tsx",
    "components/inbox/inbox-overview.tsx",
    "components/connectors/connectors-overview.tsx",
    "components/integrations/integrations-overview.tsx",
    "components/signals/signal-catalogue.tsx",
    "components/access/access-overview.tsx",
    "components/users/users-overview.tsx",
    "components/agent/agent-configurations.tsx",
    "components/agent/agent-prompts.tsx",
    "components/agent/agent-historique.tsx",
    "components/agent/agent-a-faire.tsx",
    "components/agent/agent-garde-fous.tsx",
    "components/agent/agent-connaissances.tsx",
    "components/agent/fleet-explorer.tsx",
    "components/sources/sources-overview.tsx",
    "components/configurer/guardrail-catalogue.tsx",
    "components/configurer/model-catalogue.tsx",
    "components/agent/gov-scope-section.tsx",
    "components/health/health-dashboard.tsx",
    "components/agir/release-control-view.tsx",
    "components/reliability/reliability-dashboard.tsx",
    "components/improvement/improvement-dashboard.tsx",
    "components/compliance/compliance-dashboard.tsx",
    "components/observability/observability-dashboard.tsx",
    "components/proofs/etat-a-date.tsx",
    "components/agent/agent-subtab-shared.tsx",
    "components/agent/agent-console.tsx",
    "app/[locale]/agents/page.tsx",
    "app/[locale]/agents/[agentId]/historique/[sessionId]/page.tsx",
  ] as const;
  const customSurfaceSources = [
    "components/incidents/incidents-overview.tsx",
    "components/automations/automations-overview.tsx",
    "components/curation/curation-overview.tsx",
    "components/proofs/proofs-overview.tsx",
    "components/replay/replay-overview.tsx",
    "components/replay/replay-cassette.tsx",
    "components/compliance/compliance-dashboard.tsx",
    "components/observability/observability-dashboard.tsx",
    "components/proofs/etat-a-date.tsx",
    "components/policies/policies-overview.tsx",
    "components/access/access-overview.tsx",
    "components/integrations/integrations-overview.tsx",
    "components/system/system-profile.tsx",
    "components/sources/sources-overview.tsx",
    "components/inbox/inbox-overview.tsx",
    "components/parameters/parameters-overview.tsx",
    "components/configurer/model-catalogue.tsx",
    "components/configurer/guardrail-catalogue.tsx",
  ] as const;

  it("sets the shell and every sibling Card collection to ten pixels", () => {
    // `min-h-full`, not `h-full`: this assertion is about the ten-pixel RHYTHM, and it was
    // pinning the height keyword alongside it. A fixed 100% height made the content box exactly
    // the viewport and let its children overflow it, so the scroll container's padding-bottom
    // never reached the end of a long page (the last card sat on the footer, 2026-08-07).
    expect(shellFrame).toContain("mx-auto flex min-h-full w-full flex-col gap-2.5");
    expect(card).toContain('data-slot="card"');
    expect(globals).toContain(
      ':where(.flex, .grid):has(> [data-slot="card"] ~ [data-slot="card"])',
    );
    expect(globals).toContain("gap: 0.625rem !important");
  });

  it("keeps custom page stacks on the same ten-pixel rhythm", () => {
    for (const path of pageRoots) {
      expect(readFileSync(join(root, path), "utf8"), path).toMatch(
        /flex[^"]*flex-col gap-2\.5(?:\s|")/,
      );
    }
  });

  it("marks legacy panels as surfaces so their flex and grid parents inherit ten pixels", () => {
    for (const path of customSurfaceSources) {
      expect(readFileSync(join(root, path), "utf8"), path).toContain('data-slot="card"');
    }
  });

  it("keeps the quality view doors ten pixels apart without an extra bottom margin", () => {
    expect(qualityViewSwitch).toContain('className="grid grid-cols-1 gap-2.5 sm:grid-cols-2"');
    expect(qualityViewSwitch).not.toMatch(/<nav[^>]*className="[^"]*mb-/u);
  });

  it("removes the security page's former eight-pixel and negative-gap exceptions", () => {
    expect(security).toContain('className="grid gap-2.5 lg:grid-cols-[minmax(0,1fr)_340px]"');
    expect(security).toContain('className="flex min-w-0 flex-col gap-2.5"');
    expect(security).not.toContain('className="-mt-0.5"');
    expect(security).not.toContain(
      'className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t',
    );
  });

  it("has teeth: widening the shell or sibling-card gutter turns the ratchet red", () => {
    const shellMutation = shellFrame.replace("flex-col gap-2.5", "flex-col gap-4");
    const cssMutation = globals.replace("gap: 0.625rem !important", "gap: 1rem !important");
    expect(shellMutation).not.toContain("mx-auto flex h-full w-full flex-col gap-2.5");
    expect(cssMutation).not.toContain("gap: 0.625rem !important");
  });
});
