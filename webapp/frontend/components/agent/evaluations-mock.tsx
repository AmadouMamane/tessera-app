"use client";

import {
  Activity,
  ArrowUpRight,
  Bell,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  FileCheck2,
  FlaskConical,
  Gauge,
  History,
  Inbox,
  KeyRound,
  type LucideIcon,
  MessageSquare,
  Play,
  Search,
  Settings,
  Shield,
  ShieldAlert,
  SlidersHorizontal,
  Terminal,
  TriangleAlert,
} from "lucide-react";

/**
 * ISOLATED, full-frame high-fidelity mock of the Évaluations page — a pixel-close
 * reproduction of `09-multi-agent-evaluations-normative-fina.png` with FICTIONAL
 * data (NON OPPOSABLE). Rendered as a `fixed inset-0` overlay so it owns the whole
 * frame (its own sidebar + thin top bar replica), independent of the app shell, to
 * allow exact visual matching. Every value comes from a single `MOCK_DATA` constant
 * shaped like the real payload — wiring real data later is a swap, no layout change.
 */

const C = {
  red: "#ff6b88",
  redText: "#ff9bb0",
  amber: "#ffce8a",
  green: "#7fe3b3",
  grey: "#6b7180",
  purple: "#b9a6ff",
} as const;

const MOCK_DATA = {
  gate: {
    label: "BLOQUÉ par le socle",
    release_badge: "RELEASE : BLOQUÉ",
    subtitle: "Cette VERSION CANDIDATE ne peut pas être promue en production.",
    base_rule: "Règle de base : SOCLE DUR RÉUSSI 100 % · DOMAINE RÉUSSI ≥ 85 %",
    families_failed: 4,
    families: ["PII-02", "PII-45", "PII-46", "SEC-03"],
    more_socle_failed: 14,
  },
  actions: ["Corriger les cas du socle", "Rejouer les tests", "Obtenir un gate PASSE"],
  details: {
    name: "Prod Safety Set v2.1",
    last_run: "15/08/2026 03:02",
    tabs: ["Résumé", "Tests (150)", "Échecs (18)", "Historique"],
    rows: [
      ["Score global", "93,6 / 100"],
      ["Réussite brute", "95,2 %"],
      ["Tests réussis", "2 450 / 2 575"],
      ["Écart cible / réalisé", "− 4,8 pts"],
      ["Durée d'exécution", "8 min 24 s"],
      ["Statut", "Échec"],
      ["Sévérité max", "Critique"],
      ["Version du jeu", "v2.1"],
    ],
    desc: "Jeu de tests de sécurité complet couvrant les types majeurs pour l'assistant.",
  },
  lifecycle: {
    stage: "CANDIDAT",
    candidate: "REL-2026.06.12+3",
    cible: "Production",
    deployed: "REL-2026.06.05+1",
    model: "Llama 3.2 3B",
    env: "Préproduction (évaluation)",
    evalset: "Prod Safety Set v2.1",
    run: "run_phase4_20260612_0752",
  },
  kpis: {
    aggregate: { value: "91,2", note: "ne neutralise pas un échec du socle" },
    selected: { value: "93,6", note: "Prod Safety Set v2.1 · 93,6 / 100" },
    coverage: { pct: 94, executed: "150 / 160 cas", not_run: "2 (1,3 %)" },
    brut: { value: "95,2 %", note: "Gate non conforme · le socle prime" },
    gate_status: { label: "BLOQUÉ", note: "socle non conforme" },
  },
  socle_cases: {
    total: 18,
    rows: [
      { id: "PII-02", family: "PII · Données personnelles", expected: "Refus / Masquage", observed: "Donnée personnelle reproduite", last: "12/06/2026 07:52" },
      { id: "PII-45", family: "Exfiltration de données", expected: "Blocage / Refus", observed: "Contenu sensible exposé", last: "12/06/2026 07:52" },
      { id: "PII-46", family: "PII / IBAN", expected: "Refus / Masquage", observed: "IBAN reproduit", last: "12/06/2026 07:52" },
      { id: "SEC-03", family: "Injection de prompt", expected: "Instruction ignorée", observed: "Instruction exécutée", last: "12/06/2026 07:52" },
    ],
  },
  categories: [
    { label: "Pertinence", score: "92,1", ok: true },
    { label: "Sécurité", score: "78,2", ok: false },
    { label: "PII / Privacy", score: "93,4", ok: true },
    { label: "Conformité", score: "91,0", ok: true },
    { label: "Robustesse", score: "94,3", ok: true },
    { label: "Exactitude", score: "90,8", ok: true },
    { label: "Utilisabilité", score: "88,9", ok: true },
  ],
  distribution: {
    total: "12 540",
    total_label: "Tests exécutés",
    segments: [
      { label: "Réussi", n: "11 670", pct: 93.1, color: C.green },
      { label: "Partiel", n: "520", pct: 4.1, color: C.amber },
      { label: "Échoué", n: "230", pct: 1.8, color: C.red },
      { label: "Non exécuté", n: "120", pct: 1.0, color: C.grey },
    ],
  },
  severity: [
    { label: "Critique", rate: 30.0 },
    { label: "Élevé", rate: 70.5 },
    { label: "Moyenne", rate: 92.1 },
    { label: "Faible", rate: 97.0 },
  ],
  evolution: [86, 88, 87, 90, 89, 91, 90, 92, 91, 93, 92, 93.6],
  config: {
    coverage: "Incomplète",
    socle_exec: "83 / 85 (97,6 %)",
    socle_not_run: "2 / 85 (2,4 %)",
    thresholds: ["Socle dur : 100 %", "Domaine : ≥ 85 %"],
    owner: "ML Engineer",
    updated: "12/06/2026",
  },
  machine: [
    ["ID de run", "run_phase4_20260612_0752"],
    ["Version du moteur", "llama.cpp 0.3.2"],
    ["Température", "0,0"],
    ["Top p", "0,9"],
    ["Exécution", "on-premise-1"],
    ["Environnement", "Préproduction"],
  ],
  links: [
    "AGIR → Release Control",
    "Politique des gates (CONFIGURER → Évaluations)",
    "Jeux d'évaluations (CONFIGURER → Évaluations)",
    "Garde-fous appliqués",
    "Connaissances utilisées",
  ],
  scopes: {
    all: "Agrège tous les jeux d'évaluation actifs de l'agent.",
    selected: "Prod Safety Set v2.1 — couverture sécurité / PII.",
  },
  grain: "Grain directeur = cas socle (× langue). Une dérogation ne lève qu'un cas hors-socle ; le socle, jamais.",
  top_failed: [
    { fam: "PII-02", echec: "Donnée personnelle reproduite", cas: "3" },
    { fam: "SEC-03", echec: "Instruction exécutée", cas: "2" },
    { fam: "PII-46", echec: "IBAN reproduit", cas: "2" },
  ],
} as const;

const PANEL = "rounded-lg border border-[#222838] bg-[#10141f]";
const M = "text-[#7b8294]";

export function EvaluationsMock() {
  const d = MOCK_DATA;
  return (
    <div className="fixed inset-0 z-[60] flex overflow-hidden bg-[#0a0d15] font-sans text-[12px] text-[#e6e8ee]">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="relative flex min-h-0 flex-1 flex-col overflow-hidden p-2.5">
          <div className="pointer-events-none absolute right-3 top-1 z-20 flex items-center gap-1.5 rounded-md border border-amber-500/50 bg-amber-500/15 px-2 py-0.5 text-[9px] font-medium text-amber-200 backdrop-blur">
            <FlaskConical className="h-3 w-3" />
            MAQUETTE — données fictives · NON OPPOSABLE
          </div>
          <div className="flex min-h-0 flex-1 gap-2.5">
            {/* Left column */}
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <VerdictHero d={d} />
              <PromoDisabled />
              <LifecycleBar lc={d.lifecycle} />
              <ScoreStrip k={d.kpis} />
              <SocleTable s={d.socle_cases} />
              <div className="grid h-[176px] shrink-0 grid-cols-4 gap-2">
                <EvolutionCard points={d.evolution} />
                <CategoryCard cats={d.categories} />
                <DistributionCard dist={d.distribution} />
                <SeverityCard sev={d.severity} />
              </div>
              <BottomStrip d={d} />
            </div>
            {/* Right column */}
            <aside className="flex w-[320px] shrink-0 flex-col gap-2 overflow-hidden">
              <DetailsCard det={d.details} />
              <ConfigCard cfg={d.config} />
              <MachineCard rows={d.machine} />
              <LinksCard links={d.links} />
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}

/* ── Chrome replicas ────────────────────────────────────────────────────── */
const NAV_AGENT: [string, LucideIcon][] = [
  ["Synthèse", Gauge],
  ["Configurations", Settings],
  ["Connaissances", BookOpen],
  ["Garde-fous", Shield],
  ["Prompts", MessageSquare],
  ["Évaluations", FlaskConical],
  ["Console", Terminal],
  ["Historique", History],
];
function Sidebar() {
  return (
    <nav className="flex w-[168px] shrink-0 flex-col border-r border-[#1b2030] bg-[#0b0e16] px-3 py-3 text-[11px]">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#6d4aed] text-[13px] font-bold text-white">
          ◈
        </div>
        <div className="leading-tight">
          <p className="text-[12px] font-semibold">TESSERA</p>
          <p className="text-[7px] uppercase tracking-wider text-[#7b8294]">AI Control Plane</p>
        </div>
      </div>
      <Group title="AGENT">
        {NAV_AGENT.map(([label, Icon]) => (
          <Item key={label} label={label} Icon={Icon} active={label === "Évaluations"} />
        ))}
        <Item label="À traiter" Icon={Inbox} badge="23" />
        <Item label="À faire" Icon={ClipboardList} badge="17" badgeTone="amber" />
      </Group>
      <Group title="GOUVERNER">
        <Item label="Surveiller" Icon={Activity} />
        <Item label="Agir" Icon={Play} />
        <Item label="Prouver" Icon={FileCheck2} />
      </Group>
      <Group title="PLATEFORME">
        <Item label="Configurer" Icon={SlidersHorizontal} />
        <Item label="Admin" Icon={KeyRound} />
      </Group>
      <div className="mt-auto flex flex-col gap-2 pt-3 text-[9px]">
        <div className="rounded-md border border-[#1b2030] p-2">
          <p className="text-[7px] uppercase tracking-wide text-[#7b8294]">Environnement actif</p>
          <p className="mt-1 flex items-center gap-1 text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Production
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#2a2150] text-[8px] font-semibold text-[#b9a6ff]">
            AD
          </div>
          <div className="leading-tight">
            <p className="text-[10px] font-medium">Amadou D.</p>
            <p className="text-[8px] text-[#7b8294]">ML Engineer</p>
          </div>
        </div>
        <p className="text-[8px] text-[#7b8294]">Tessera v1.0.0</p>
      </div>
    </nav>
  );
}
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-2">
      <p className="mb-1 text-[8px] font-semibold uppercase tracking-wider text-[#f5a623]">{title}</p>
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}
function Item({
  label,
  Icon,
  active,
  badge,
  badgeTone,
}: {
  label: string;
  Icon: LucideIcon;
  active?: boolean;
  badge?: string;
  badgeTone?: "amber";
}) {
  return (
    <div
      className={`flex items-center gap-2 rounded px-2 py-1 ${active ? "bg-[#2a2150] text-[#c9b8ff]" : "text-[#aab0be]"}`}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 opacity-80" />
      <span className="flex-1">{label}</span>
      {badge ? (
        <span
          className={`rounded px-1 text-[8px] font-semibold text-white ${badgeTone === "amber" ? "bg-amber-500" : "bg-red-500"}`}
        >
          {badge}
        </span>
      ) : null}
    </div>
  );
}

function TopBar() {
  const pill = "flex items-center gap-1 rounded-md border border-[#222838] bg-[#10141f] px-2 py-1 text-[10px]";
  return (
    <header className="flex h-11 shrink-0 items-center gap-3 border-b border-[#1b2030] bg-[#0b0e16] px-3">
      <button className="flex items-center gap-1.5 rounded-md border border-[#6d4aed]/60 bg-[#10141f] px-2 py-1 text-[11px] font-medium">
        Support client <ChevronDown className="h-3 w-3" />
      </button>
      <span className="text-[10px] text-[#7b8294] underline">Voir la flotte des agents</span>
      <div className="ml-2 flex items-center gap-1.5">
        <span className={`${pill} text-emerald-300`}>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Opérationnel
        </span>
        <span className={pill}>Tessera v1.0.0 <ChevronDown className="h-3 w-3 text-[#7b8294]" /></span>
        <span className={pill}>Prod (Crédit Aurore) <ChevronDown className="h-3 w-3 text-[#7b8294]" /></span>
        <span className={pill}>on-prem <ChevronDown className="h-3 w-3 text-[#7b8294]" /></span>
        <span className={pill}>ML Engineer <ChevronDown className="h-3 w-3 text-[#7b8294]" /></span>
      </div>
      <div className="ml-auto flex items-center gap-2 text-[#7b8294]">
        <span className="flex items-center gap-1 text-[10px]">FR <ChevronDown className="h-3 w-3" /></span>
        <span className="flex items-center gap-1 rounded-md border border-[#222838] bg-[#10141f] px-2 py-1 text-[10px]">
          <Search className="h-3 w-3" /> Rechercher… <span className="ml-2 text-[8px]">⌘K</span>
        </span>
        <span className="relative">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 flex h-3 w-3 items-center justify-center rounded-full bg-red-500 text-[7px] text-white">
            6
          </span>
        </span>
        <CircleHelp className="h-4 w-4" />
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#2a2150] text-[8px] font-semibold text-[#b9a6ff]">
          AD
        </span>
      </div>
    </header>
  );
}

/* ── Hero ───────────────────────────────────────────────────────────────── */
function VerdictHero({ d }: { d: typeof MOCK_DATA }) {
  return (
    <section className="grid shrink-0 grid-cols-12 gap-3 rounded-lg border border-[#e0566f]/50 bg-[#241019] p-2.5">
      <div className="col-span-5">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 shrink-0 text-[#ff9bb0]" />
          <span className="text-[1.05rem] font-semibold leading-none text-[#ff9bb0]">{d.gate.label}</span>
          <span className="rounded border border-[#e0566f]/60 bg-[#e0566f]/20 px-1.5 py-0.5 text-[8px] font-semibold uppercase tracking-wide text-[#ff9bb0]">
            {d.gate.release_badge}
          </span>
        </div>
        <p className="mt-1.5 text-[11px]">{d.gate.subtitle}</p>
        <p className={`mt-1 text-[10px] ${M}`}>{d.gate.base_rule}</p>
      </div>
      <div className="col-span-4">
        <p className="text-[11px] font-semibold text-[#ff9bb0]">
          {d.gate.families_failed} familles critiques en échec
        </p>
        <div className="mt-1 flex flex-wrap gap-1">
          {d.gate.families.map((f) => (
            <span key={f} className="rounded border border-[#e0566f]/50 bg-[#e0566f]/15 px-1.5 py-0.5 font-mono text-[10px] font-medium text-[#ff9bb0]">
              {f}
            </span>
          ))}
        </div>
        <p className={`mt-1 text-[10px] ${M}`}>+ {d.gate.more_socle_failed} autres cas socle échoués</p>
      </div>
      <div className="col-span-3">
        <p className={`text-[8px] uppercase tracking-wide ${M}`}>Actions requises</p>
        <ul className="mt-0.5 flex flex-col gap-0.5">
          {d.actions.map((a) => (
            <li key={a} className="flex items-start gap-1 text-[10px]">
              <span className="mt-[3px] h-1 w-1 shrink-0 rounded-full bg-[#ff9bb0]" />
              {a}
            </li>
          ))}
        </ul>
        <button className="mt-1 inline-flex items-center gap-1 rounded border border-[#e0566f]/60 bg-[#e0566f]/15 px-1.5 py-0.5 text-[10px] font-medium text-[#ff9bb0]">
          Voir dans AGIR · Release Control <ChevronRight className="h-3 w-3" />
        </button>
      </div>
    </section>
  );
}

function PromoDisabled() {
  return (
    <div className="flex shrink-0 items-center gap-2 rounded-md border border-[#e0566f]/40 bg-[#e0566f]/10 px-2.5 py-1 text-[10px] text-[#ff9bb0]">
      <TriangleAlert className="h-3 w-3" />
      <span className="font-medium">Promotion en production désactivée</span>
      <span className={M}>· Aucune release possible tant que le gate n'est pas PASSE.</span>
    </div>
  );
}

function LifecycleBar({ lc }: { lc: typeof MOCK_DATA.lifecycle }) {
  const cells: [string, string, boolean?][] = [
    ["Cycle de vie", lc.stage, true],
    ["Version candidate évaluée", lc.candidate],
    ["Cible", lc.cible],
    ["Version actuellement déployée", lc.deployed],
    ["Modèle", lc.model],
    ["Environnement du run", lc.env],
    ["Jeu d'évaluations actif", lc.evalset],
    ["Run (Phase 4)", lc.run],
  ];
  return (
    <section className={`flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 ${PANEL} px-2.5 py-1.5`}>
      {cells.map(([label, value, accent]) => (
        <div key={label} className="flex flex-col">
          <span className={`text-[8px] uppercase tracking-wide ${M}`}>{label}</span>
          <span className={`text-[11px] font-medium tabular-nums ${accent ? "text-[#b9a6ff]" : ""}`}>
            {value}
          </span>
        </div>
      ))}
    </section>
  );
}

function ScoreStrip({ k }: { k: typeof MOCK_DATA.kpis }) {
  return (
    <section className="grid shrink-0 grid-cols-5 gap-2">
      <KpiCard title="SCORE AGRÉGÉ · TOUS JEUX" value={k.aggregate.value} note={k.aggregate.note} spark />
      <KpiCard title="SCORE DU JEU SÉLECTIONNÉ" value={k.selected.value} note={k.selected.note} spark />
      <CoverageCard cov={k.coverage} />
      <KpiCard title="RÉUSSITE BRUTE" value={k.brut.value} note={k.brut.note} />
      <div className={`flex flex-col justify-center ${PANEL} px-2.5 py-2`}>
        <span className={`text-[8px] uppercase tracking-wide ${M}`}>Statut gate · INFORMATIF</span>
        <span className="text-[1.25rem] font-semibold leading-tight text-[#ff9bb0]">{k.gate_status.label}</span>
        <span className={`text-[9px] ${M}`}>{k.gate_status.note}</span>
      </div>
    </section>
  );
}
function KpiCard({ title, value, note, spark }: { title: string; value: string; note: string; spark?: boolean }) {
  return (
    <div className={`flex flex-col gap-0.5 ${PANEL} px-2.5 py-2`}>
      <span className={`text-[8px] uppercase tracking-wide ${M}`}>
        {title} <span className="opacity-70">· INFORMATIF</span>
      </span>
      <span className="text-[1.4rem] font-semibold leading-none tabular-nums">{value}</span>
      {spark ? <Spark /> : null}
      <span className={`text-[9px] leading-tight ${M}`}>{note}</span>
    </div>
  );
}
function CoverageCard({ cov }: { cov: typeof MOCK_DATA.kpis.coverage }) {
  return (
    <div className={`flex items-center gap-2 ${PANEL} px-2.5 py-2`}>
      <Ring pct={cov.pct} />
      <div className="flex flex-col">
        <span className={`text-[8px] uppercase tracking-wide ${M}`}>Couverture totale</span>
        <span className="text-[11px] font-medium">{cov.executed}</span>
        <span className="inline-flex items-center gap-1 text-[9px] text-amber-300">
          <TriangleAlert className="h-2.5 w-2.5" /> {cov.not_run} non exéc.
        </span>
      </div>
    </div>
  );
}

function SocleTable({ s }: { s: typeof MOCK_DATA.socle_cases }) {
  return (
    <section className={`shrink-0 ${PANEL} px-2.5 py-2`}>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[11px] font-semibold">
          Cas socle bloquants <span className={M}>({s.total} au total)</span>
        </span>
        <span className="text-[9px] text-[#b9a6ff]">Pourquoi ces cas bloquent ? →</span>
      </div>
      <table className="w-full text-left text-[10px]">
        <thead>
          <tr className={`text-[8px] uppercase tracking-wide ${M}`}>
            <th className="py-0.5 pr-2 font-medium">Famille</th>
            <th className="py-0.5 pr-2 font-medium">Attendu (contrat)</th>
            <th className="py-0.5 pr-2 font-medium">Obtenu (observé)</th>
            <th className="py-0.5 pr-2 font-medium">Sévérité</th>
            <th className="py-0.5 pr-2 font-medium">Statut</th>
            <th className="py-0.5 pr-2 font-medium">Dernière exéc.</th>
            <th className="py-0.5 font-medium">Trace</th>
          </tr>
        </thead>
        <tbody>
          {s.rows.map((r) => (
            <tr key={r.id} className="border-t border-[#1b2030]">
              <td className="py-1 pr-2">
                <span className="font-mono font-medium text-[#ff9bb0]">{r.id}</span>
                <span className={`block text-[8px] ${M}`}>{r.family}</span>
              </td>
              <td className="py-1 pr-2">{r.expected}</td>
              <td className="py-1 pr-2 text-[#ff9bb0]">{r.observed}</td>
              <td className="py-1 pr-2">
                <span className="rounded bg-[#e0566f]/15 px-1 py-0.5 text-[8px] font-medium text-[#ff9bb0]">Critique</span>
              </td>
              <td className="py-1 pr-2 text-[#ff9bb0]">Échec</td>
              <td className={`py-1 pr-2 tabular-nums ${M}`}>{r.last}</td>
              <td className="py-1">
                <span className="rounded border border-[#222838] px-1 py-0.5 text-[8px] text-[#b9a6ff]">XT-01</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1 text-[9px] text-[#b9a6ff]">Voir les {s.total - s.rows.length} autres cas socle bloquants →</p>
    </section>
  );
}

/* ── Charts (4 across the bottom) ───────────────────────────────────────── */
function ChartShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className={`flex min-h-0 flex-col ${PANEL} px-2.5 py-2`}>
      <span className="text-[10px] font-semibold">{title}</span>
      <div className="mt-1 min-h-0 flex-1">{children}</div>
    </section>
  );
}
function EvolutionCard({ points }: { points: readonly number[] }) {
  // Fixed Y domain (like the normative's 75–95 axis) so the line sits in the
  // upper band instead of forming a steep triangle from the data min.
  const lo = 75;
  const hi = 96;
  const w = 280;
  const h = 110;
  const step = w / (points.length - 1);
  const y = (v: number) => h - ((v - lo) / (hi - lo)) * (h - 8) - 4;
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${i * step},${y(p)}`).join(" ");
  const grid = [90, 85, 80, 75];
  const xlabels = ["01/06", "04/06", "07/06", "10/06", "12/06"];
  return (
    <ChartShell title="Évolution du score (tous jeux)">
      <div className="flex h-full flex-col">
        <div className="flex min-h-0 flex-1 gap-1">
          <div className={`flex flex-col justify-between py-0.5 text-[7px] ${M}`}>
            {grid.map((g) => (
              <span key={g}>{g}</span>
            ))}
          </div>
          <svg viewBox={`0 0 ${w} ${h}`} className="h-full flex-1" preserveAspectRatio="none">
            {grid.map((g) => (
              <line key={g} x1="0" x2={w} y1={y(g)} y2={y(g)} stroke="#1b2030" strokeWidth="1" />
            ))}
            <path d={`${line} L${w},${h} L0,${h} Z`} fill="#8b7cf0" opacity="0.08" />
            <path d={line} fill="none" stroke="#8b7cf0" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          </svg>
        </div>
        <div className={`flex justify-between pl-3 pt-0.5 text-[7px] ${M}`}>
          {xlabels.map((x) => (
            <span key={x}>{x}</span>
          ))}
        </div>
        <div className={`mt-0.5 flex items-center gap-3 text-[7px] ${M}`}>
          <span className="flex items-center gap-1">
            <span className="h-0.5 w-3 rounded bg-[#8b7cf0]" /> Score moyen
          </span>
          <span className="flex items-center gap-1">
            <span className="h-0.5 w-3 rounded bg-[#3a4055]" /> Période précédente
          </span>
        </div>
      </div>
    </ChartShell>
  );
}
function CategoryCard({ cats }: { cats: typeof MOCK_DATA.categories }) {
  return (
    <ChartShell title="Scores par catégorie · INFORMATIF">
      <div className="flex h-full flex-col justify-center gap-1">
        {cats.map((c) => (
          <div key={c.label} className="flex items-center gap-1.5 text-[9px]">
            <span className="w-16 shrink-0 truncate">{c.label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#1b2030]">
              <div className="h-full rounded-full" style={{ width: `${Number.parseFloat(c.score.replace(",", "."))}%`, background: c.ok ? C.green : C.red }} />
            </div>
            <span className="w-8 shrink-0 text-right tabular-nums">{c.score}</span>
            <span className={`w-12 shrink-0 text-right text-[8px] ${c.ok ? "text-emerald-300" : "text-[#ff9bb0]"}`}>
              {c.ok ? "OK" : "ÉCHEC"}
            </span>
          </div>
        ))}
      </div>
    </ChartShell>
  );
}
function DistributionCard({ dist }: { dist: typeof MOCK_DATA.distribution }) {
  return (
    <ChartShell title="Répartition des résultats">
      <div className="flex h-full items-center gap-2">
        <Donut segments={dist.segments} center={dist.total} caption={dist.total_label} />
        <ul className="flex flex-col gap-1 text-[9px]">
          {dist.segments.map((s) => (
            <li key={s.label} className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
              <span className="w-14">{s.label}</span>
              <span className="tabular-nums">{s.n}</span>
              <span className={`tabular-nums ${M}`}>({s.pct.toLocaleString("fr-FR")} %)</span>
            </li>
          ))}
        </ul>
      </div>
    </ChartShell>
  );
}
function SeverityCard({ sev }: { sev: typeof MOCK_DATA.severity }) {
  const tone = (r: number) => (r < 50 ? C.red : r < 85 ? C.amber : C.green);
  return (
    <ChartShell title="Taux de réussite par sévérité">
      <div className="flex h-full flex-col justify-center gap-1.5">
        {sev.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5 text-[9px]">
            <span className="w-12 shrink-0">{s.label}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#1b2030]">
              <div className="h-full rounded-full" style={{ width: `${s.rate}%`, background: tone(s.rate) }} />
            </div>
            <span className="w-10 shrink-0 text-right tabular-nums">
              {s.rate.toLocaleString("fr-FR", { minimumFractionDigits: 1 })} %
            </span>
          </div>
        ))}
      </div>
    </ChartShell>
  );
}

function BottomStrip({ d }: { d: typeof MOCK_DATA }) {
  return (
    <div className="grid min-h-0 flex-1 grid-cols-3 gap-2">
      <section className={`flex min-h-0 flex-col ${PANEL} px-2.5 py-2`}>
        <span className="text-[10px] font-semibold">Définitions des portées</span>
        <div className="mt-1 flex flex-col gap-1 text-[9px]">
          <div>
            <span className="font-medium text-[#b9a6ff]">Tous jeux</span>
            <span className={`block ${M}`}>{d.scopes.all}</span>
          </div>
          <div>
            <span className="font-medium text-[#b9a6ff]">Jeu sélectionné</span>
            <span className={`block ${M}`}>{d.scopes.selected}</span>
          </div>
        </div>
      </section>
      <section className={`flex min-h-0 flex-col ${PANEL} px-2.5 py-2`}>
        <span className="text-[10px] font-semibold">Grain directeur</span>
        <p className={`mt-1 text-[9px] leading-relaxed ${M}`}>{d.grain}</p>
      </section>
      <section className={`flex min-h-0 flex-col ${PANEL} px-2.5 py-2`}>
        <span className="text-[10px] font-semibold">Tests les plus échoués</span>
        <table className="mt-1 w-full text-left text-[9px]">
          <thead>
            <tr className={`text-[8px] uppercase ${M}`}>
              <th className="font-medium">Famille</th>
              <th className="font-medium">Échec</th>
              <th className="text-right font-medium">Cas</th>
            </tr>
          </thead>
          <tbody>
            {d.top_failed.map((r) => (
              <tr key={r.fam} className="border-t border-[#1b2030]">
                <td className="py-0.5 font-mono text-[#ff9bb0]">{r.fam}</td>
                <td className="py-0.5">{r.echec}</td>
                <td className="py-0.5 text-right tabular-nums">{r.cas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

/* ── Right column ───────────────────────────────────────────────────────── */
function DetailsCard({ det }: { det: typeof MOCK_DATA.details }) {
  return (
    <section className={`${PANEL} px-2.5 py-2`}>
      <span className="text-[11px] font-semibold">Détails de l'évaluation</span>
      <div className="mt-1 flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[10px] font-medium">
          <FlaskConical className="h-3.5 w-3.5 text-[#b9a6ff]" /> {det.name}
        </span>
        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[8px] font-medium text-emerald-300">Actif</span>
      </div>
      <p className={`mt-0.5 text-[9px] ${M}`}>Dernière exécution : {det.last_run}</p>
      <div className="mt-1 flex gap-2 border-b border-[#1b2030] text-[9px]">
        {det.tabs.map((tab, i) => (
          <span key={tab} className={`pb-1 ${i === 0 ? "border-b-2 border-[#6d4aed] text-[#e6e8ee]" : M}`}>
            {tab}
          </span>
        ))}
      </div>
      <dl className="mt-1 flex flex-col gap-0.5 text-[10px]">
        {det.rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className={M}>{label}</dt>
            <dd className={`tabular-nums ${label === "Statut" ? "text-[#ff9bb0]" : ""}`}>{value}</dd>
          </div>
        ))}
      </dl>
      <p className={`mt-1 text-[9px] leading-tight ${M}`}>{det.desc}</p>
      <p className="mt-1 text-[9px] text-[#b9a6ff]">Voir le détail →</p>
    </section>
  );
}
function ConfigCard({ cfg }: { cfg: typeof MOCK_DATA.config }) {
  return (
    <section className={`${PANEL} px-2.5 py-2`}>
      <span className="text-[11px] font-semibold">Configuration de l'évaluation</span>
      <dl className="mt-1 flex flex-col gap-0.5 text-[10px]">
        <Row label="Couverture du socle dur" value={cfg.coverage} tone="amber" />
        <Row label="Cas socle exécutés" value={cfg.socle_exec} />
        <Row label="Cas socle non exécutés" value={cfg.socle_not_run} />
        <div className="flex items-start justify-between gap-2">
          <dt className={M}>Seuils du gate</dt>
          <dd className="text-right">
            {cfg.thresholds.map((t) => (
              <span key={t} className="block tabular-nums">{t}</span>
            ))}
          </dd>
        </div>
        <Row label="Propriétaire" value={cfg.owner} />
        <Row label="Dernière mise à jour" value={cfg.updated} />
      </dl>
      <p className="mt-1 text-[9px] text-[#b9a6ff]">Voir la configuration →</p>
    </section>
  );
}
function MachineCard({ rows }: { rows: typeof MOCK_DATA.machine }) {
  return (
    <section className={`${PANEL} px-2.5 py-2`}>
      <span className="text-[11px] font-semibold">Informations techniques</span>
      <dl className="mt-1 flex flex-col gap-0.5 text-[10px]">
        {rows.map(([label, value]) => (
          <Row key={label} label={label} value={value} />
        ))}
      </dl>
    </section>
  );
}
function LinksCard({ links }: { links: typeof MOCK_DATA.links }) {
  return (
    <section className={`min-h-0 flex-1 ${PANEL} px-2.5 py-2`}>
      <span className="text-[11px] font-semibold">Liens utiles</span>
      <ul className="mt-1 flex flex-col gap-1 text-[10px]">
        {links.map((l) => (
          <li key={l} className="flex items-center justify-between gap-2">
            <span>{l}</span>
            <ArrowUpRight className="h-3 w-3 shrink-0 text-[#b9a6ff]" />
          </li>
        ))}
      </ul>
    </section>
  );
}
function Row({ label, value, tone }: { label: string; value: string; tone?: "amber" }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className={M}>{label}</dt>
      <dd className={`tabular-nums ${tone === "amber" ? "text-amber-300" : ""}`}>{value}</dd>
    </div>
  );
}

/* ── Primitives ─────────────────────────────────────────────────────────── */
function Spark() {
  return (
    <svg viewBox="0 0 80 14" className="h-3.5 w-full" preserveAspectRatio="none" aria-hidden>
      <path d="M0,11 L12,8 L24,10 L36,5 L48,7 L60,3 L72,4 L80,2" fill="none" stroke="#8b7cf0" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
function Ring({ pct }: { pct: number }) {
  const r = 16;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <svg viewBox="0 0 40 40" className="h-10 w-10 -rotate-90 shrink-0" aria-hidden>
      <circle cx="20" cy="20" r={r} fill="none" stroke="#1b2030" strokeWidth="4.5" />
      <circle cx="20" cy="20" r={r} fill="none" stroke={C.green} strokeWidth="4.5" strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round" />
      <text x="20" y="20" transform="rotate(90 20 20)" textAnchor="middle" dominantBaseline="central" className="fill-[#e6e8ee] text-[8px] font-semibold">
        {pct}%
      </text>
    </svg>
  );
}
function Donut({ segments, center, caption }: { segments: readonly { pct: number; color: string }[]; center: string; caption: string }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  let acc = 0;
  return (
    <svg viewBox="0 0 78 78" className="h-[78px] w-[78px] -rotate-90 shrink-0" aria-hidden>
      <circle cx="39" cy="39" r={r} fill="none" stroke="#1b2030" strokeWidth="9" />
      {segments.map((s) => {
        const len = (s.pct / 100) * c;
        const el = (
          <circle key={s.color + acc} cx="39" cy="39" r={r} fill="none" stroke={s.color} strokeWidth="9" strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-acc} />
        );
        acc += len;
        return el;
      })}
      <text x="39" y="36" transform="rotate(90 39 39)" textAnchor="middle" className="fill-[#e6e8ee] text-[10px] font-semibold">
        {center}
      </text>
      <text x="39" y="46" transform="rotate(90 39 39)" textAnchor="middle" className="fill-[#7b8294] text-[5px]">
        {caption}
      </text>
    </svg>
  );
}
