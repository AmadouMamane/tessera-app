import { execSync } from "node:child_process";
// Glossary relabel engine — rewrites façade English/jargon to business FR/DE
// inside the VALUES of one top-level message namespace, then builds an isolated
// `HEAD + edits` blob per locale (scratchpad) for clean staging (the repo has
// unrelated WIP in messages/*.json, so we never `git add` the whole file).
//
//   node scripts/relabel-glossary.mjs <namespace> [namespace2 ...]
import fs from "node:fs";

const SP =
  "/private/tmp/claude-501/-Users-amadou-local-apps-codex-tessera/8b6f94b3-17da-4159-8859-d18e146851c0/scratchpad";
const namespaces = process.argv.slice(2);
if (namespaces.length === 0) {
  console.error("usage: relabel-glossary.mjs <ns> ...");
  process.exit(1);
}
const SENT = ""; // placeholder sentinel — never appears in messages

function cased(src, repl) {
  if (src === src.toUpperCase() && src !== src.toLowerCase()) return repl.toUpperCase();
  if (src[0] === src[0].toUpperCase()) return repl[0].toUpperCase() + repl.slice(1);
  return repl;
}

// Ordered longest-first. Each: [regex, frRepl, deRepl].
const TERMS = [
  ["evidence pack", "dossier de preuves", "Beweismappe"],
  ["quality gate", "gate qualité", "Qualitäts-Gate"],
  ["rate[- ]?limit", "limite de débit", "Ratenbegrenzung"],
  ["coverage", "couverture", "Abdeckung"],
  ["baseline", "référence", "Referenz"],
  ["snapshot", "instantané", "Momentaufnahme"],
  ["rollback", "retour arrière", "Rückabwicklung"],
  ["staging", "préproduction", "Vorproduktion"],
  ["timeout", "délai d'expiration", "Zeitüberschreitung"],
  ["canary", "canari", "Canary"],
  ["chunk", "fragment", "Fragment"],
  ["draft", "brouillon", "Entwurf"],
  ["owner", "responsable", "Verantwortlicher"],
  ["scope", "portée", "Geltungsbereich"],
  ["retry", "relance", "Wiederholung"],
  ["shadow[- ]?judge", "juge fantôme", "Schatten-Richter"],
  ["shadow traffic", "trafic fantôme", "Schattenverkehr"],
  ["time travel", "navigation temporelle", "Zeitreise"],
  ["red[- ]?team", "test d'intrusion", "Angriffstest"],
  ["burn[- ]?rate", "vitesse de consommation", "Verbrauchsrate"],
  ["faithfulness", "fidélité", "Treue"],
  ["grounding", "ancrage", "Verankerung"],
  ["jailbreak", "contournement", "Umgehung"],
  ["playbooks", "procédures", "Verfahren"],
  ["playbook", "procédure", "Verfahren"],
  ["funnel", "entonnoir", "Trichter"],
  ["backlog", "file d'attente", "Rückstand"],
  ["throughput", "débit", "Durchsatz"],
  ["bundles", "lots", "Pakete"],
  ["bundle", "lot", "Paket"],
  ["drift", "dérive", "Abweichung"],
  ["shadow", "trafic fantôme", "Schattenverkehr"],
  ["replay", "rejeu", "Wiedergabe"],
];
const GLOSS = [
  "faithfulness",
  "grounding",
  "shadow",
  "red-team",
  "red team",
  "jailbreak",
  "playbook",
  "evidence pack",
  "drift",
];

function applyOne(val, locale) {
  let out = val;
  // 0) protect ICU placeholders {var} / {var, plural, ...} — names are code.
  const ph = [];
  out = out.replace(/\{[^{}]*\}/g, (m) => {
    ph.push(m);
    return SENT + (ph.length - 1) + SENT;
  });
  // 1) strip "(englishGloss)" parentheticals
  for (const g of GLOSS) out = out.replace(new RegExp(`\\s*\\((?:${g})\\)`, "gi"), "");
  // 2) term substitutions (smart-cased)
  for (const [pat, fr, de] of TERMS) {
    const repl = locale === "de" ? de : fr;
    out = out.replace(new RegExp(`\\b${pat}\\b`, "gi"), (m) => cased(m, repl));
  }
  // 3) collapse "<word> / <word>" duplicate glosses → keep first
  out = out.replace(/\b([\p{L}]+)\s*\/\s*\1\b/giu, "$1");
  // 4) FR determiner agreement for feminine replacements ("le playbook"→"la procédure")
  if (locale === "fr") {
    const FEM = [
      "procédures?",
      "fidélité",
      "dérive",
      "file d'attente",
      "référence",
      "portée",
      "relance",
      "préproduction",
      "limite de débit",
    ];
    for (const t of FEM) {
      out = out.replace(new RegExp(`\\b(l)e (${t})\\b`, "g"), "$1a $2");
      out = out.replace(new RegExp(`\\b(L)e (${t})\\b`, "g"), "$1a $2");
      out = out.replace(new RegExp(`\\b(u)n (${t})\\b`, "g"), "$1ne $2");
      out = out.replace(new RegExp(`\\b(U)n (${t})\\b`, "g"), "$1ne $2");
      out = out.replace(new RegExp(`\\b(c)e (${t})\\b`, "g"), "$1ette $2");
      out = out.replace(new RegExp(`\\b(C)e (${t})\\b`, "g"), "$1ette $2");
      out = out.replace(new RegExp(`\\bdu (${t})\\b`, "g"), "de la $1");
      out = out.replace(new RegExp(`\\bau (${t})\\b`, "g"), "à la $1");
    }
    // 5) elision "le ancrage" → "l'ancrage"
    out = out.replace(/\b([Ll])e (ancrage|entonnoir|anomalie)/g, "$1'$2");
  }
  // 6) restore placeholders, collapse doubled spaces
  out = out.replace(new RegExp(`${SENT}(\\d+)${SENT}`, "g"), (m, i) => ph[+i] ?? m);
  out = out.replace(/ {2,}/g, " ").replace(/^ | $/g, "");
  return out;
}

function flat(o, p = "", out = {}) {
  if (o && typeof o === "object")
    for (const k of Object.keys(o)) flat(o[k], p ? `${p}.${k}` : k, out);
  else out[p] = o;
  return out;
}
function setPath(o, dotted, val) {
  const parts = dotted.split(".");
  let cur = o;
  for (const k of parts.slice(0, -1)) cur = cur[k];
  cur[parts[parts.length - 1]] = val;
}
function walkApply(obj, locale) {
  let n = 0;
  const rec = (o) => {
    for (const k of Object.keys(o)) {
      const v = o[k];
      if (v && typeof v === "object") rec(v);
      else if (typeof v === "string") {
        const nv = applyOne(v, locale);
        if (nv !== v) {
          o[k] = nv;
          n++;
        }
      }
    }
  };
  rec(obj);
  return n;
}

for (const locale of ["fr", "de"]) {
  const path = `messages/${locale}.json`;
  const head = JSON.parse(execSync(`git show HEAD:webapp/frontend/${path}`).toString());
  const before = flat(JSON.parse(JSON.stringify(head)));
  let n = 0;
  for (const ns of namespaces) if (head[ns]) n += walkApply(head[ns], locale);
  fs.writeFileSync(`${SP}/${locale}.relabel.json`, `${JSON.stringify(head, null, 2)}\n`);
  // working tree: apply ONLY keys my relabel changed, preserving unrelated WIP
  const after = flat(head);
  const wt = JSON.parse(fs.readFileSync(path, "utf8"));
  for (const k of Object.keys(after)) if (after[k] !== before[k]) setPath(wt, k, after[k]);
  fs.writeFileSync(path, `${JSON.stringify(wt, null, 2)}\n`);
  console.log(`${locale}: ${n} valeur(s) relabellée(s) dans [${namespaces.join(", ")}]`);
}
