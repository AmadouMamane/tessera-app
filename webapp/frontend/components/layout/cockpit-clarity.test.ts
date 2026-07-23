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

  it("preserves every fleet reconciliation value in all three languages", () => {
    for (const catalogue of [fr, en, de]) {
      expect(catalogue.agentScope.dedupExplain).toContain("{naive}");
      expect(catalogue.agentScope.dedupExplain).toContain("{saved}");
      expect(catalogue.agentScope.dedupExplain).toContain("{shared}");
      expect(catalogue.agentScope.dedupExplainNone).toContain("{naive}");
      expect(catalogue.agentScope.dedupExplainNone).not.toMatch(/\{shared\}|\{saved\}/u);
      expect(catalogue.agentScope.handoffGap).toContain("{events}");
      expect(catalogue.agentScope.handoffGap).toContain("{attested}");
      expect(catalogue.agentScope.handoffGap).toContain("{seen}");
    }
  });

  it("uses a natural zero-state for fleet reconciliation in every language", () => {
    expect(fr.agentScope.dedupExplainNone).toMatch(/Aucune conversation.*total reste/u);
    expect(en.agentScope.dedupExplainNone).toMatch(/No conversation.*total stays/u);
    expect(de.agentScope.dedupExplainNone).toMatch(/Keine Konversation.*Gesamtzahl bleibt/u);
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
    mutant.agentScope.dedupExplain =
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

  it("does not insert a large margin between a signal banner and its temporal controls", () => {
    expect(excessiveAlertGap(qualityPage)).toEqual([]);
    expect(excessiveAlertGap(overviewPage)).toEqual([]);
  });

  it("keeps the sticky background fill shallow enough for the compact gap", () => {
    expect(oversizedUpwardShadow(qualityDashboard)).toEqual([]);
    expect(oversizedUpwardShadow(overviewDashboard)).toEqual([]);
  });

  it("has teeth: the former spacing and shadow are rejected", () => {
    const marginMutation = '<div className="mb-6"><SignalBreachHero /></div>';
    const shadowMutation =
      '<div className="shadow-[0_-20px_0_0_var(--tessera-bg)]">temporal controls</div>';
    expect(excessiveAlertGap(marginMutation)).toEqual([6]);
    expect(oversizedUpwardShadow(shadowMutation)).toEqual([20]);
  });
});
