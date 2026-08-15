import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A Server Component may RENDER a client export. It may never CALL one.
 *
 * This is the fault class `tsc` structurally cannot see, and it has now hit the same page twice:
 *
 *  · 2026-08-07 — the launch verdict ribbon handed `AlertRibbon` (a Client Component) an `icon`
 *    FUNCTION. Types agreed on both sides; every request rendered the error boundary.
 *  · 2026-08-14 — `lib/format-number.ts` carried `"use client"` while exporting `formatInt`,
 *    whose own docstring announced it as "the server twin, for Server Components".
 *    `components/eval/compare-tab.tsx` imported it exactly as documented and threw on every
 *    render: *Attempted to call formatInt() from the server but formatInt is on the client.*
 *    The Comparaison tab of Qualité IA was dead for a day.
 *
 * Both are invisible to the type-checker because `"use client"` is a STRING, not a type: the
 * module's signature is identical on both sides of the boundary and only the runtime disagrees.
 * `biome` does not model it either. So the boundary needs its own witness, and it belongs in the
 * gate — the e2e suite is not in the gate, and on this repo it runs only when someone remembers.
 *
 * The rule, stated as the compiler would if it could:
 *
 *     a module WITHOUT `"use client"` may import a binding from a module WITH it — that is how
 *     every page mounts its client components — but it may not INVOKE that binding.
 *
 * Invocation is what `foo(` catches and `<Foo />` does not, which is precisely the line between
 * the legal case and the fatal one.
 */

const ROOT = process.cwd();
const DIRS = ["app", "components", "lib"];

/** `"use client"` must be the module's first statement, so looking at the head is enough. */
function isClientModule(text: string): boolean {
  for (const raw of text.split("\n", 12)) {
    const line = raw.trim();
    if (line === "" || line.startsWith("//") || line.startsWith("*") || line.startsWith("/*"))
      continue;
    return /^["']use client["'];?$/.test(line);
  }
  return false;
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

/** `@/lib/x` → the file that actually answers it, or null when it resolves outside the scan. */
function resolveAlias(spec: string, known: Set<string>): string | null {
  if (!spec.startsWith("@/")) return null;
  const base = spec.slice(2);
  for (const candidate of [`${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`]) {
    if (known.has(candidate)) return candidate;
  }
  return null;
}

const IMPORT = /import\s+(type\s+)?\{([^}]*)\}\s+from\s+["']([^"']+)["']/g;

interface Offence {
  file: string;
  binding: string;
  from: string;
}

function findServerCallsIntoClientModules(files: Map<string, string>): Offence[] {
  const known = new Set(files.keys());
  const clientModules = new Set(
    [...files].filter(([, text]) => isClientModule(text)).map(([rel]) => rel),
  );

  const offences: Offence[] = [];
  for (const [rel, text] of files) {
    if (clientModules.has(rel)) continue; // both sides client: nothing crosses.
    for (const match of text.matchAll(IMPORT)) {
      const [, typeOnly, names = "", spec = ""] = match;
      if (typeOnly) continue; // erased at compile time — it never reaches the runtime boundary.
      const target = resolveAlias(spec, known);
      if (!target || !clientModules.has(target)) continue;
      for (const raw of names.split(",")) {
        const piece = raw.trim();
        if (piece === "" || piece.startsWith("type ")) continue;
        // `a as b` — the LOCAL name is what the file calls.
        const binding = (piece.includes(" as ") ? (piece.split(" as ")[1] ?? "") : piece).trim();
        if (!/^[A-Za-z_$][\w$]*$/.test(binding)) continue;
        if (new RegExp(`\\b${binding}\\s*\\(`).test(text)) {
          offences.push({ file: rel, binding, from: target });
        }
      }
    }
  }
  return offences;
}

function readAll(): Map<string, string> {
  const files = new Map<string, string>();
  for (const dir of DIRS) {
    for (const abs of walk(join(ROOT, dir))) {
      const rel = abs.slice(ROOT.length + 1);
      if (rel.includes(".test.")) continue;
      files.set(rel, readFileSync(abs, "utf8"));
    }
  }
  return files;
}

describe("the server/client boundary", () => {
  const files = readAll();
  const offences = findServerCallsIntoClientModules(files);

  it("can still see — the positive control", () => {
    // A moved directory or a renamed alias would empty the scan and read as a clean sweep.
    expect(files.size).toBeGreaterThan(300);
    expect([...files].filter(([, t]) => isClientModule(t)).length).toBeGreaterThan(100);
  });

  it("detects the fault it was written for — the negative control", () => {
    // Verbatim shape of the 2026-08-14 regression, replayed on a synthetic tree. Without this,
    // a typo in the import regex would leave the list permanently empty and permanently green.
    const synthetic = new Map([
      ["lib/format-number.ts", '"use client";\nexport function formatInt() {}\n'],
      [
        "components/eval/compare-tab.tsx",
        'import { formatInt } from "@/lib/format-number";\nconst s = formatInt(locale, 1);\n',
      ],
    ]);
    expect(findServerCallsIntoClientModules(synthetic)).toEqual([
      {
        file: "components/eval/compare-tab.tsx",
        binding: "formatInt",
        from: "lib/format-number.ts",
      },
    ]);
  });

  it("would catch the 2026-08-14 regression on the REAL tree, not a toy one", () => {
    // The synthetic control above proves the regexes work on two files I wrote. This one proves
    // they work on the repository as it actually is: put the directive back on the real
    // `lib/format-number.ts` — in memory, nothing on disk moves — and the real
    // `components/eval/compare-tab.tsx`, unedited, must be named.
    //
    // It is also what keeps the fix from being undone silently: the day someone reintroduces
    // `"use client"` there, the suite goes red on the test above; the day compare-tab stops
    // calling `formatInt`, it goes red here and this control must be re-aimed rather than
    // deleted.
    const replayed = new Map(files);
    const real = replayed.get("lib/format-number.ts");
    expect(real, "the module that owns the server twin still exists").toBeTruthy();
    replayed.set("lib/format-number.ts", `"use client";\n${real}`);
    expect(findServerCallsIntoClientModules(replayed)).toContainEqual({
      file: "components/eval/compare-tab.tsx",
      binding: "formatInt",
      from: "lib/format-number.ts",
    });
  });

  it("leaves the LEGAL crossing alone — a server page rendering a client component", () => {
    const synthetic = new Map([
      ["components/ui/ribbon.tsx", '"use client";\nexport function AlertRibbon() {}\n'],
      [
        "app/page.tsx",
        'import { AlertRibbon } from "@/components/ui/ribbon";\nexport default () => <AlertRibbon title="x" />;\n',
      ],
    ]);
    expect(findServerCallsIntoClientModules(synthetic)).toEqual([]);
  });

  it("has no server module calling into a client one", () => {
    // Not frozen, deliberately. Each occurrence is a page that renders the error boundary in
    // production for every request — there is no such thing as an acceptable one to keep.
    expect(offences).toEqual([]);
  });
});
