import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * `/comprendre` carries validated content, not code.
 *
 * The French (§3 of the source brief) and the English (§5 bis) were approved word for word,
 * and the instruction was explicit: any rewording goes back to the author. Prose in a JSON
 * catalogue is the easiest thing in this repository to "improve" by accident — one tidied
 * comma during a merge and the approval no longer covers what ships.
 *
 * Hence the fingerprints below. They cannot check the text against the source document (it
 * lives outside the repository, and a test that skipped itself when the file was missing
 * would be a vacuous green). What they can do is make an edit *loud*: change one character of
 * validated prose and this file turns red, naming the person who has to agree to it.
 */

const root = process.cwd();
const read = (path: string) => readFileSync(join(root, path), "utf8");

/**
 * sha256 of the validated sections, verbatim as approved on 2026-07-10.
 *
 * Re-run the printed digest and update these ONLY once the rewording is approved. A failure
 * here is not a broken test — it is the guard doing the one job it has.
 */
const APPROVED_SECTIONS = {
  fr: "a815b549c52ce375d45a2c34a5aec09a1a83a95a00dbf8cdd2bf8d9aab3125b1",
  en: "f76d02db77de0fa3c13a1e970ad64bb3dcfe31c6de4384be6ec239a6d71a7952",
} as const;

interface Section {
  heading: string;
  body: string[];
  proof?: { text: string; href: string };
}

const LOCALES = ["fr", "en", "de"] as const;

const catalogue = (locale: string) =>
  JSON.parse(read(`messages/${locale}.json`)) as {
    comprendre: {
      pageTitle: string;
      sections: Section[];
      launcherOrientation: string;
      launcherLink: string;
      loginWelcome: string;
      helpUnderstand: string;
    };
    demoBadge: Record<string, string>;
  };

describe("the page exists in three languages, with the same eight sections", () => {
  it.each(LOCALES)("%s carries the eight sections and their prose", (locale) => {
    const { sections } = catalogue(locale).comprendre;
    expect(sections).toHaveLength(8);
    for (const section of sections) {
      expect(section.heading.length).toBeGreaterThan(3);
      expect(section.body.length).toBeGreaterThan(0);
      for (const paragraph of section.body) {
        // Full sentences, not telegraphic style: the register is binding.
        expect(paragraph.length).toBeGreaterThan(40);
      }
    }
  });

  it.each(LOCALES)("%s names the three doors", (locale) => {
    const c = catalogue(locale).comprendre;
    expect(c.launcherOrientation.length).toBeGreaterThan(40);
    expect(c.launcherLink.length).toBeGreaterThan(5);
    expect(c.loginWelcome.length).toBeGreaterThan(20);
    expect(c.helpUnderstand.length).toBeGreaterThan(5);
  });

  it.each(["fr", "en"] as const)(
    "%s prose is byte-for-byte the text that was approved",
    (locale) => {
      const blob = JSON.stringify(catalogue(locale).comprendre.sections);
      const digest = createHash("sha256").update(blob).digest("hex");
      const why = `${locale.toUpperCase()} is validated content: any rewording goes back to Amadou first. If the change is approved, replace the digest in APPROVED_SECTIONS.`;
      expect(digest, why).toBe(APPROVED_SECTIONS[locale]);
    },
  );

  it("the three locales agree on where every proof link points", () => {
    const hrefs = LOCALES.map((locale) =>
      catalogue(locale)
        .comprendre.sections.map((s) => s.proof?.href ?? null)
        .join("|"),
    );
    expect(new Set(hrefs).size).toBe(1);
  });
});

describe("every proof link reaches a live page", () => {
  const { sections } = catalogue("fr").comprendre;
  const proofs = sections.flatMap((s) => (s.proof ? [s.proof.href] : []));

  it("there are exactly three, as the content declares", () => {
    expect(proofs).toEqual(["/agents", "/agents/duplex-agent/console", "/prouver/etat-a-date"]);
  });

  it.each(["app/[locale]/agents/page.tsx", "app/[locale]/prouver/etat-a-date/page.tsx"])(
    "%s exists",
    (page) => {
      expect(() => read(page)).not.toThrow();
    },
  );

  it("the duplex console route is the generic agent console, which exists", () => {
    expect(() => read("app/[locale]/agents/[agentId]/console/page.tsx")).not.toThrow();
  });
});

describe("the product lexicon holds: the pill's card never names the platform", () => {
  it.each(LOCALES)("%s demo badge copy stays product-safe", (locale) => {
    const copy = Object.values(catalogue(locale).demoBadge).join(" ");
    // The change of world happens on the click, never in the text.
    expect(copy).not.toMatch(/Tessera|AI Control Plane|cockpit|Cockpit/);
  });

  it("the card carries a body and a way out", () => {
    for (const locale of LOCALES) {
      const badge = catalogue(locale).demoBadge;
      expect(badge.sheetBody, `${locale}: the pill's card has no body`).toBeDefined();
      expect(badge.sheetCta, `${locale}: the pill's card offers no way out`).toBeDefined();
      expect((badge.sheetBody ?? "").length).toBeGreaterThan(40);
      expect((badge.sheetCta ?? "").length).toBeGreaterThan(10);
    }
  });
});

describe("the public escape hatch stays a hatch", () => {
  it("exactly one page skips the cockpit role gate, and it is this one", () => {
    // `publicAccess` exists because an explanation nobody can read explains nothing. It is
    // also the one prop in this codebase that can silently un-gate a page holding real facts.
    const pages = execFileSync("grep", ["-rl", "publicAccess", "app", "components"], {
      cwd: root,
      encoding: "utf8",
    })
      .trim()
      .split("\n")
      .filter((p) => !p.endsWith(".test.ts"));

    expect(pages.sort()).toEqual([
      "app/[locale]/comprendre/page.tsx",
      "components/layout/app-shell.tsx",
    ]);
  });
});

describe("nothing on the page is hardcoded", () => {
  const page = read("app/[locale]/comprendre/page.tsx");
  const diagram = read("components/comprendre/two-worlds-diagram.tsx");

  it("the page reads its sections from the catalogue", () => {
    expect(page).toContain('t.raw("sections")');
    // A French sentence in the TSX would mean the other two locales silently lost it.
    expect(page).not.toMatch(/Tessera est un poste de pilotage/);
  });

  it("the diagram carries only the eight words of the brief, all translated", () => {
    for (const key of [
      "bank",
      "cockpit",
      "door",
      "agents",
      "publishes",
      "testMessage",
      "measures",
      "ledger",
    ]) {
      expect(diagram).toContain(`t("${key}")`);
    }
    // No technical term reaches the drawing.
    expect(diagram).not.toMatch(/OTLP|Prometheus|manifest|binding|telemetry/i);
  });
});
