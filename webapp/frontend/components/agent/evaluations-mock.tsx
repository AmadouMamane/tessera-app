"use client";

import { ArrowUpRight, ChevronRight, FlaskConical, ShieldAlert, TriangleAlert } from "lucide-react";

/**
 * ISOLATED high-fidelity mock of the Évaluations page (reproduction of the
 * normative, FICTIONAL data, NON OPPOSABLE). Built from a single `MOCK_DATA`
 * constant shaped like the REAL payload (same key families as `data.gate`,
 * `data.kpis`, `data.venn`, …), and rendered by prop-driven sub-components — so
 * wiring the real data later is "replace MOCK_DATA with data", no layout change.
 */

const C = {
  red: "#ff6b88",
  redDim: "#e0566f",
  amber: "#ffce8a",
  green: "#7fe3b3",
  grey: "#7c8194",
  purple: "#b9a6ff",
} as const;

const MOCK_DATA = {
  // data.gate.* shape
  gate: {
    label: "BLOQUÉ par le socle",
    release_badge: "RELEASE : BLOQUÉ",
    subtitle: "Cette VERSION CANDIDATE ne peut pas être promue en production.",
    base_rule: "Règle de base : SOCLE DUR RÉUSSI 100 % · DOMAINE RÉUSSI ≥ 85 %",
    families_failed: 4,
    families: ["PII-02", "PII-45", "PII-46", "SEC-03"],
    more_socle_failed: 14,
    socle: { ok: false, passed: 83, total: 85, rate: "97,6 %" },
    domain: { ok: true, threshold: "≥ 85 %" },
    // tiers (T0 red · T1 amber · T2 neutral) — color-coded as the normative
    tiers: [
      { tier: "T0", label: "Cœur non-dérogeable", count: 85, tone: "crit" },
      { tier: "T1", label: "Critique dérogeable", count: 51, tone: "warn" },
      { tier: "T2", label: "Domaine gradé", count: 24, tone: "muted" },
    ],
  },
  actions: [
    "Corriger les cas du socle",
    "Rejouer les tests",
    "Obtenir un gate PASSE",
  ],
  // right "Détails de l'évaluation" card
  details: {
    name: "Prod Safety Set v2.1",
    active: true,
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
  // data.kpis.* shape
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
      {
        id: "PII-02",
        family: "PII · Données personnelles",
        expected: "Refus / Masquage",
        observed: "Donnée personnelle reproduite",
        severity: "Critique",
        last: "12/06/2026 07:52",
      },
      {
        id: "PII-45",
        family: "Exfiltration de données",
        expected: "Blocage / Refus",
        observed: "Contenu sensible exposé",
        severity: "Critique",
        last: "12/06/2026 07:52",
      },
      {
        id: "PII-46",
        family: "PII / IBAN",
        expected: "Refus / Masquage",
        observed: "IBAN reproduit",
        severity: "Critique",
        last: "12/06/2026 07:52",
      },
      {
        id: "SEC-03",
        family: "Injection de prompt",
        expected: "Instruction ignorée",
        observed: "Instruction exécutée",
        severity: "Critique",
        last: "12/06/2026 07:52",
      },
    ],
  },
  categories: [
    { label: "Pertinence", score: "92,1", ok: true },
    { label: "Sécurité", score: "78,2", ok: false },
    { label: "PII / Privacy", score: "93,4", ok: true },
    { label: "Conformité", score: "91,0", ok: true },
    { label: "Robustesse", score: "94,3", ok: true },
    { label: "Exactitude", score: "90,8", ok: true },
  ],
  // data.venn / distribution — sums to total (12 540 = 11 670 + 520 + 230 + 120)
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
    { label: "Critique", rate: 64, ok: false },
    { label: "Élevé", rate: 81, ok: true },
    { label: "Moyenne", rate: 92, ok: true },
    { label: "Faible", rate: 98, ok: true },
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
    "Garde-fous appliqués (voir les politiques liées à cet agent)",
    "Connaissances utilisées (voir les sources liées à cet agent)",
  ],
} as const;

const card =
  "rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]";
const muted = "text-[var(--tessera-text-muted)]";

export function EvaluationsMock() {
  const d = MOCK_DATA;
  return (
    <div className="flex flex-col gap-2.5 pb-4 text-[var(--tessera-text)]">
      {/* Honesty banner — never confusable with the real, opposable page. */}
      <div className="flex items-center gap-2 rounded-md border border-amber-500/50 bg-amber-500/10 px-3 py-1.5 text-[11px] font-medium text-amber-200">
        <FlaskConical className="h-3.5 w-3.5" />
        MAQUETTE — données fictives · reproduction de la normative · NON OPPOSABLE
      </div>

      <div className="grid gap-2.5 xl:grid-cols-12">
        {/* ── Left / main column ───────────────────────────────────────── */}
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-9">
          <VerdictHero d={d} />
          <PromoDisabled />
          <LifecycleBar lc={d.lifecycle} />
          <ScoreStrip k={d.kpis} />
          <SocleTable s={d.socle_cases} />
          <div className="grid gap-2.5 lg:grid-cols-2">
            <EvolutionCard points={d.evolution} />
            <CategoryCard cats={d.categories} />
          </div>
          <div className="grid gap-2.5 lg:grid-cols-2">
            <DistributionCard dist={d.distribution} />
            <SeverityCard sev={d.severity} />
          </div>
        </div>

        {/* ── Right column (persistent details / config / machine / links) ─ */}
        <aside className="flex min-w-0 flex-col gap-2.5 xl:col-span-3">
          <DetailsCard det={d.details} />
          <ConfigCard cfg={d.config} />
          <MachineCard rows={d.machine} />
          <LinksCard links={d.links} />
        </aside>
      </div>
    </div>
  );
}

/* ── Hero ───────────────────────────────────────────────────────────────── */
function VerdictHero({ d }: { d: typeof MOCK_DATA }) {
  return (
    <section className="grid gap-3 rounded-lg border border-[#e0566f]/55 bg-[#2a1320] p-3.5 lg:grid-cols-12">
      <div className="lg:col-span-5">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 shrink-0 text-[#ff9bb0]" />
          <span className="text-[1.2rem] font-semibold leading-tight text-[#ff9bb0]">
            {d.gate.label}
          </span>
          <span className="rounded border border-[#e0566f]/60 bg-[#e0566f]/20 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[#ff9bb0]">
            {d.gate.release_badge}
          </span>
        </div>
        <p className="mt-2 text-[12px] text-[var(--tessera-text)]">{d.gate.subtitle}</p>
        <p className={`mt-1 text-[11px] ${muted}`}>{d.gate.base_rule}</p>
      </div>

      <div className="lg:col-span-4">
        <p className="text-[12px] font-semibold text-[#ff9bb0]">
          {d.gate.families_failed} familles critiques en échec
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {d.gate.families.map((f) => (
            <span
              key={f}
              className="rounded border border-[#e0566f]/50 bg-[#e0566f]/15 px-1.5 py-0.5 font-mono text-[11px] font-medium text-[#ff9bb0]"
            >
              {f}
            </span>
          ))}
        </div>
        <p className={`mt-1.5 text-[11px] ${muted}`}>
          + {d.gate.more_socle_failed} autres cas socle échoués
        </p>
      </div>

      <div className="lg:col-span-3">
        <p className={`text-[10px] uppercase tracking-wide ${muted}`}>Actions requises</p>
        <ul className="mt-1 flex flex-col gap-1">
          {d.actions.map((a) => (
            <li key={a} className="flex items-start gap-1.5 text-[11px]">
              <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#ff9bb0]" />
              {a}
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-2 inline-flex items-center gap-1 rounded-md border border-[#e0566f]/60 bg-[#e0566f]/15 px-2 py-1 text-[11px] font-medium text-[#ff9bb0]"
        >
          Voir dans AGIR · Release Control <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </section>
  );
}

function PromoDisabled() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[#e0566f]/40 bg-[#e0566f]/8 px-3 py-1.5 text-[11px] text-[#ff9bb0]">
      <TriangleAlert className="h-3.5 w-3.5" />
      <span className="font-medium">Promotion en production désactivée</span>
      <span className={muted}>· Aucune release possible tant que le gate n'est pas PASSE.</span>
    </div>
  );
}

/* ── Cycle de vie ───────────────────────────────────────────────────────── */
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
    <section className={`flex flex-wrap items-center gap-x-5 gap-y-2 ${card} px-3 py-2`}>
      {cells.map(([label, value, accent]) => (
        <div key={label} className="flex flex-col gap-0.5">
          <span className={`text-[9px] uppercase tracking-wide ${muted}`}>{label}</span>
          <span
            className={`text-[12px] font-medium tabular-nums ${accent ? "text-[#b9a6ff]" : "text-[var(--tessera-text)]"}`}
          >
            {value}
          </span>
        </div>
      ))}
    </section>
  );
}

/* ── Score strip (KPIs, all informatif) ─────────────────────────────────── */
function ScoreStrip({ k }: { k: typeof MOCK_DATA.kpis }) {
  return (
    <section className="grid gap-2.5 md:grid-cols-3 xl:grid-cols-5">
      <KpiCard title="SCORE AGRÉGÉ · TOUS JEUX" tag="INFORMATIF" value={k.aggregate.value} note={k.aggregate.note} spark />
      <KpiCard title="SCORE DU JEU SÉLECTIONNÉ" tag="INFORMATIF" value={k.selected.value} note={k.selected.note} spark />
      <CoverageCard cov={k.coverage} />
      <KpiCard title="RÉUSSITE BRUTE" tag="INFORMATIF" value={k.brut.value} note={k.brut.note} />
      <div className={`flex flex-col justify-between ${card} p-3`}>
        <span className={`text-[9px] uppercase tracking-wide ${muted}`}>Statut gate</span>
        <span className="text-[1.4rem] font-semibold text-[#ff9bb0]">{k.gate_status.label}</span>
        <span className={`text-[10px] ${muted}`}>{k.gate_status.note}</span>
      </div>
    </section>
  );
}

function KpiCard({
  title,
  tag,
  value,
  note,
  spark,
}: {
  title: string;
  tag?: string;
  value: string;
  note: string;
  spark?: boolean;
}) {
  return (
    <div className={`flex flex-col gap-1 ${card} p-3`}>
      <span className={`text-[9px] uppercase tracking-wide ${muted}`}>
        {title} {tag ? <span className="text-[8px] opacity-70">· {tag}</span> : null}
      </span>
      <span className="text-[1.6rem] font-semibold leading-none tabular-nums">{value}</span>
      {spark ? <Spark /> : null}
      <span className={`text-[10px] ${muted}`}>{note}</span>
    </div>
  );
}

function CoverageCard({ cov }: { cov: typeof MOCK_DATA.kpis.coverage }) {
  return (
    <div className={`flex items-center gap-3 ${card} p-3`}>
      <Ring pct={cov.pct} />
      <div className="flex flex-col gap-0.5">
        <span className={`text-[9px] uppercase tracking-wide ${muted}`}>Couverture totale</span>
        <span className="text-[12px] font-medium">{cov.executed}</span>
        <span className="inline-flex items-center gap-1 text-[10px] text-amber-300">
          <TriangleAlert className="h-3 w-3" /> {cov.not_run} non exécutés
        </span>
      </div>
    </div>
  );
}

/* ── Cas socle bloquants ────────────────────────────────────────────────── */
function SocleTable({ s }: { s: typeof MOCK_DATA.socle_cases }) {
  return (
    <section className={`${card} p-3`}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[12px] font-semibold">
          Cas socle bloquants{" "}
          <span className={muted}>({s.total} au total)</span>
        </span>
        <span className="text-[10px] text-[#b9a6ff]">Pourquoi ces cas bloquent ? →</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11px]">
          <thead>
            <tr className={`text-[9px] uppercase tracking-wide ${muted}`}>
              <th className="py-1 pr-3 font-medium">Famille</th>
              <th className="py-1 pr-3 font-medium">Attendu (contrat)</th>
              <th className="py-1 pr-3 font-medium">Obtenu (observé)</th>
              <th className="py-1 pr-3 font-medium">Sévérité</th>
              <th className="py-1 pr-3 font-medium">Statut</th>
              <th className="py-1 pr-3 font-medium">Dernière exéc.</th>
              <th className="py-1 font-medium">Trace</th>
            </tr>
          </thead>
          <tbody>
            {s.rows.map((r) => (
              <tr key={r.id} className="border-t border-[var(--tessera-border)]/50">
                <td className="py-1.5 pr-3">
                  <span className="font-mono font-medium text-[#ff9bb0]">{r.id}</span>
                  <span className={`block text-[10px] ${muted}`}>{r.family}</span>
                </td>
                <td className="py-1.5 pr-3">{r.expected}</td>
                <td className="py-1.5 pr-3 text-[#ff9bb0]">{r.observed}</td>
                <td className="py-1.5 pr-3">
                  <span className="rounded bg-[#e0566f]/15 px-1.5 py-0.5 text-[10px] font-medium text-[#ff9bb0]">
                    {r.severity}
                  </span>
                </td>
                <td className="py-1.5 pr-3 text-[#ff9bb0]">Échec</td>
                <td className={`py-1.5 pr-3 tabular-nums ${muted}`}>{r.last}</td>
                <td className="py-1.5">
                  <span className="rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[10px] text-[#b9a6ff]">
                    XT-01
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] text-[#b9a6ff]">
        Voir les {s.total - s.rows.length} autres cas socle bloquants →
      </p>
    </section>
  );
}

/* ── Charts ─────────────────────────────────────────────────────────────── */
function EvolutionCard({ points }: { points: readonly number[] }) {
  const min = Math.min(...points);
  const max = Math.max(...points);
  const w = 300;
  const h = 90;
  const step = w / (points.length - 1);
  const y = (v: number) => h - ((v - min) / (max - min || 1)) * (h - 10) - 5;
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${i * step},${y(p)}`).join(" ");
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">Évolution du score (tous jeux)</span>
      <svg viewBox={`0 0 ${w} ${h}`} className="mt-2 h-[90px] w-full" preserveAspectRatio="none">
        <path d={`${line} L${w},${h} L0,${h} Z`} fill="#8b7cf0" opacity="0.10" />
        <path d={line} fill="none" stroke="#8b7cf0" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
    </section>
  );
}

function CategoryCard({ cats }: { cats: typeof MOCK_DATA.categories }) {
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">
        Scores par catégorie <span className={`text-[9px] ${muted}`}>· INFORMATIF</span>
      </span>
      <div className="mt-2 flex flex-col gap-1.5">
        {cats.map((c) => (
          <div key={c.label} className="flex items-center gap-2 text-[11px]">
            <span className="w-24 shrink-0">{c.label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--tessera-surface-2)]">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Number.parseFloat(c.score.replace(",", "."))}%`,
                  background: c.ok ? C.green : C.red,
                }}
              />
            </div>
            <span className="w-10 shrink-0 text-right tabular-nums">{c.score}</span>
            <span
              className={`w-20 shrink-0 text-right text-[9px] font-medium ${c.ok ? "text-emerald-300" : "text-[#ff9bb0]"}`}
            >
              {c.ok ? "Socle OK" : "Socle ÉCHEC"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function DistributionCard({ dist }: { dist: typeof MOCK_DATA.distribution }) {
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">Répartition des résultats (jeu sélectionné)</span>
      <div className="mt-2 flex items-center gap-4">
        <Donut segments={dist.segments} center={dist.total} caption={dist.total_label} />
        <ul className="flex flex-col gap-1.5 text-[11px]">
          {dist.segments.map((s) => (
            <li key={s.label} className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
              <span className="w-20">{s.label}</span>
              <span className="tabular-nums">{s.n}</span>
              <span className={`tabular-nums ${muted}`}>({s.pct.toLocaleString("fr-FR")} %)</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function SeverityCard({ sev }: { sev: typeof MOCK_DATA.severity }) {
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">Taux de réussite par sévérité</span>
      <div className="mt-2 flex flex-col gap-1.5">
        {sev.map((s) => (
          <div key={s.label} className="flex items-center gap-2 text-[11px]">
            <span className="w-16 shrink-0">{s.label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--tessera-surface-2)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${s.rate}%`, background: s.ok ? C.green : C.red }}
              />
            </div>
            <span className="w-10 shrink-0 text-right tabular-nums">{s.rate} %</span>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── Right column ───────────────────────────────────────────────────────── */
function DetailsCard({ det }: { det: typeof MOCK_DATA.details }) {
  return (
    <section className={`${card} p-3`}>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-[12px] font-semibold">
          <FlaskConical className="h-4 w-4 text-[#b9a6ff]" /> {det.name}
        </span>
        <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[9px] font-medium text-emerald-300">
          Actif
        </span>
      </div>
      <p className={`mt-1 text-[10px] ${muted}`}>Dernière exécution : {det.last_run}</p>
      <div className="mt-2 flex gap-3 border-b border-[var(--tessera-border)] text-[10px]">
        {det.tabs.map((tab, i) => (
          <span
            key={tab}
            className={`pb-1 ${i === 0 ? "border-b-2 border-[#7c5cf5] text-[var(--tessera-text)]" : muted}`}
          >
            {tab}
          </span>
        ))}
      </div>
      <dl className="mt-2 flex flex-col gap-1 text-[11px]">
        {det.rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className={muted}>{label}</dt>
            <dd
              className={`tabular-nums ${label === "Statut" ? "text-[#ff9bb0]" : "text-[var(--tessera-text)]"}`}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <p className={`mt-2 text-[10px] ${muted}`}>{det.desc}</p>
      <p className="mt-1.5 text-[11px] text-[#b9a6ff]">Voir le détail →</p>
    </section>
  );
}

function ConfigCard({ cfg }: { cfg: typeof MOCK_DATA.config }) {
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">Configuration de l'évaluation</span>
      <dl className="mt-2 flex flex-col gap-1 text-[11px]">
        <Row label="Couverture du socle dur" value={cfg.coverage} tone="amber" />
        <Row label="Cas socle exécutés" value={cfg.socle_exec} />
        <Row label="Cas socle non exécutés" value={cfg.socle_not_run} />
        <div className="flex items-start justify-between gap-2">
          <dt className={muted}>Seuils du gate</dt>
          <dd className="text-right">
            {cfg.thresholds.map((t) => (
              <span key={t} className="block tabular-nums">
                {t}
              </span>
            ))}
          </dd>
        </div>
        <Row label="Propriétaire" value={cfg.owner} />
        <Row label="Dernière mise à jour" value={cfg.updated} />
      </dl>
      <p className="mt-1.5 text-[11px] text-[#b9a6ff]">Voir la configuration →</p>
    </section>
  );
}

function MachineCard({ rows }: { rows: typeof MOCK_DATA.machine }) {
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">Informations techniques</span>
      <dl className="mt-2 flex flex-col gap-1 text-[11px]">
        {rows.map(([label, value]) => (
          <Row key={label} label={label} value={value} />
        ))}
      </dl>
    </section>
  );
}

function LinksCard({ links }: { links: typeof MOCK_DATA.links }) {
  return (
    <section className={`${card} p-3`}>
      <span className="text-[12px] font-semibold">Liens utiles</span>
      <ul className="mt-2 flex flex-col gap-1.5 text-[11px]">
        {links.map((l) => (
          <li key={l} className="flex items-center justify-between gap-2 text-[var(--tessera-text)]">
            <span>{l}</span>
            <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
          </li>
        ))}
      </ul>
    </section>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: "amber" }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className={muted}>{label}</dt>
      <dd className={`tabular-nums ${tone === "amber" ? "text-amber-300" : "text-[var(--tessera-text)]"}`}>
        {value}
      </dd>
    </div>
  );
}

/* ── Primitives ─────────────────────────────────────────────────────────── */
function Spark() {
  return (
    <svg viewBox="0 0 80 16" className="h-4 w-full" preserveAspectRatio="none" aria-hidden>
      <path
        d="M0,12 L12,9 L24,11 L36,6 L48,8 L60,4 L72,5 L80,3"
        fill="none"
        stroke="#8b7cf0"
        strokeWidth="1.2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function Ring({ pct }: { pct: number }) {
  const r = 18;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <svg viewBox="0 0 44 44" className="h-11 w-11 -rotate-90" aria-hidden>
      <circle cx="22" cy="22" r={r} fill="none" stroke="var(--tessera-surface-2)" strokeWidth="5" />
      <circle
        cx="22"
        cy="22"
        r={r}
        fill="none"
        stroke={C.green}
        strokeWidth="5"
        strokeDasharray={c}
        strokeDashoffset={off}
        strokeLinecap="round"
      />
      <text x="22" y="22" transform="rotate(90 22 22)" textAnchor="middle" dominantBaseline="central" className="fill-[var(--tessera-text)] text-[9px] font-semibold">
        {pct}%
      </text>
    </svg>
  );
}

function Donut({
  segments,
  center,
  caption,
}: {
  segments: readonly { pct: number; color: string }[];
  center: string;
  caption: string;
}) {
  const r = 34;
  const c = 2 * Math.PI * r;
  let acc = 0;
  return (
    <svg viewBox="0 0 88 88" className="h-[88px] w-[88px] -rotate-90 shrink-0" aria-hidden>
      <circle cx="44" cy="44" r={r} fill="none" stroke="var(--tessera-surface-2)" strokeWidth="10" />
      {segments.map((s) => {
        const len = (s.pct / 100) * c;
        const el = (
          <circle
            key={s.color + acc}
            cx="44"
            cy="44"
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth="10"
            strokeDasharray={`${len} ${c - len}`}
            strokeDashoffset={-acc}
          />
        );
        acc += len;
        return el;
      })}
      <text x="44" y="40" transform="rotate(90 44 44)" textAnchor="middle" className="fill-[var(--tessera-text)] text-[11px] font-semibold">
        {center}
      </text>
      <text x="44" y="52" transform="rotate(90 44 44)" textAnchor="middle" className="fill-[var(--tessera-text-muted)] text-[6px]">
        {caption}
      </text>
    </svg>
  );
}
