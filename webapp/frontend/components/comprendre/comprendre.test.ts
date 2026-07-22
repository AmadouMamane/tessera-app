import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (path: string) => readFileSync(join(root, path), "utf8");
const LOCALES = ["fr", "en", "de"] as const;

const APPROVED_V2 = {
  fr: "f3da4ca862021f45a6a5d87f6cf7adaff620ecc10903d63fe3d113e019d2a4cc",
  en: "563125f8d776964aec8de18c4eada5467373e9d07326dc5555b86a4ad8d10217",
  de: "7c9141979130b122627d8b38589f28d43c1ab4849c3f17be0c78ee948597d799",
} as const;

const APPROVED_V1_SECTIONS = {
  fr: "2a30bad8deaac7b865d60fc88f95bc0ba78f6e511dd02e40abed7555a1903957",
  en: "e74a17c069bdabf90cdd222e3aa2af83ae35712a4811cb8d2aefe4d616c7c13b",
} as const;

interface Catalogue {
  comprendreV2: {
    hero: { body: string };
    diagram: {
      transition: string;
      caption: string;
      columns: unknown[];
      flows: unknown[];
    };
    journey: { steps: unknown[]; illustrative: { rows: unknown[] } };
    live: { cards: unknown[] };
    details: { items: unknown[] };
    roles: { items: unknown[] };
    difference: { items: unknown[] };
    further: { detailLink: string };
    closing: { title: string };
    fiction: string;
  };
  comprendre: {
    sections: unknown[];
    launcherOrientation: string;
    launcherLink: string;
    loginWelcome: string;
    helpUnderstand: string;
  };
  demoBadge: Record<string, string>;
}

const catalogue = (locale: (typeof LOCALES)[number]) =>
  JSON.parse(read(`messages/${locale}.json`)) as Catalogue;

describe("the closed v2 content contract", () => {
  it.each(LOCALES)("%s keeps the approved catalogue byte-for-byte", (locale) => {
    const digest = createHash("sha256")
      .update(JSON.stringify(catalogue(locale).comprendreV2))
      .digest("hex");
    expect(
      digest,
      `${locale.toUpperCase()} content is closed; return any edit to the author.`,
    ).toBe(APPROVED_V2[locale]);
  });

  it.each(LOCALES)("%s carries every repeated block with the same cardinality", (locale) => {
    const copy = catalogue(locale).comprendreV2;
    expect(copy.diagram.columns).toHaveLength(3);
    expect(copy.diagram.flows).toHaveLength(4);
    expect(copy.journey.steps).toHaveLength(4);
    expect(copy.journey.illustrative.rows).toHaveLength(4);
    expect(copy.live.cards).toHaveLength(4);
    expect(copy.details.items).toHaveLength(4);
    expect(copy.roles.items).toHaveLength(3);
    expect(copy.difference.items).toHaveLength(4);
    expect(copy.further.detailLink.length).toBeGreaterThan(8);
    expect(copy.closing.title.length).toBeGreaterThan(30);
    expect(copy.fiction.length).toBeGreaterThan(80);
  });

  it("keeps the French bank wording and excludes the forbidden claims", () => {
    const copy = JSON.stringify(catalogue("fr").comprendreV2);
    expect(copy).toContain("une banque");
    expect(copy).not.toMatch(
      /une organisation|zéro contournement|conformité assurée|sans risque|en toute confiance|infalsifiable/i,
    );
  });

  it.each(LOCALES)("%s keeps one question list and spends the closing line once", (locale) => {
    const copy = catalogue(locale).comprendreV2;
    expect(copy.hero.body).not.toMatch(/what are they doing|que font-ils|was tun sie/i);
    expect(copy.diagram.transition.length).toBeGreaterThan(20);
    expect(copy.diagram.caption.length).toBeGreaterThan(30);
    expect(copy.diagram.caption).not.toBe(copy.closing.title);
  });
});

describe("the harvested long reading remains available", () => {
  it.each(["fr", "en"] as const)("%s v1 prose remains unchanged", (locale) => {
    const digest = createHash("sha256")
      .update(JSON.stringify(catalogue(locale).comprendre.sections))
      .digest("hex");
    expect(digest).toBe(APPROVED_V1_SECTIONS[locale]);
  });

  it("the detail route reads the existing catalogue and the concise page links to it", () => {
    const detail = read("app/[locale]/comprendre/en-detail/page.tsx");
    const overview = read("components/comprendre/comprendre-v2-overview.tsx");
    expect(detail).toContain('t.raw("sections")');
    expect(overview).toContain('href="/comprendre/en-detail"');
    expect(detail).toContain("max-w-[76rem]");
    expect(overview).toContain("max-w-[76rem]");
    expect(detail).not.toContain("max-w-[46rem]");
  });

  it("does not carry the abandoned timeline navigation", () => {
    expect(existsSync(join(root, "components/comprendre-codex/timeline-nav.tsx"))).toBe(false);
    expect(existsSync(join(root, "components/comprendre/timeline-nav.tsx"))).toBe(false);
  });
});

describe("the five proof links resolve to real route entries", () => {
  const overview = read("components/comprendre/comprendre-v2-overview.tsx");

  it("uses exactly the approved routes", () => {
    expect(overview).toContain(
      'const proofRoutes = ["/agents", "/surveiller", "/eval", "/prouver"] as const;',
    );
    expect(overview).toContain('<ProofLink href="/recouvrement"');
    expect(overview.match(/data-proof-link="true"/g)).toHaveLength(1);
  });

  it.each(["agents", "surveiller", "eval", "prouver", "recouvrement"])(
    "/%s has an index page",
    (route) => {
      expect(existsSync(join(root, `app/[locale]/${route}/page.tsx`))).toBe(true);
    },
  );
});

describe("the implementation keeps content and data out of the page module", () => {
  const page = read("app/[locale]/comprendre/page.tsx");
  const overview = read("components/comprendre/comprendre-v2-overview.tsx");
  const diagram = read("components/comprendre/comprendre-v2-diagram.tsx");

  it("loads backend facts server-side and refreshes through the validated BFF", () => {
    expect(page).toContain("loadComprendreFacts()");
    expect(overview).toContain("fetchComprendreFacts()");
    expect(read("lib/server/comprendre.ts")).toContain("ComprendreResponseSchema.safeParse");
    expect(read("app/api/comprendre/route.ts")).toContain("loadComprendreFacts()");
  });

  it("reads every visible block from the locale catalogue", () => {
    expect(overview).toContain('useTranslations("comprendreV2")');
    expect(diagram).toContain('useTranslations("comprendreV2.diagram")');
    expect(overview).not.toMatch(/Tessera est le poste|Crédit Aurore est fictive/);
    expect(diagram).not.toMatch(/Espaces métier|Registre d.audit|Télémétrie/);
  });

  it("keeps the cockpit header as the only visible page title and gives each arrow one rail", () => {
    expect(overview).not.toContain('t("hero.title")');
    expect(overview).not.toContain('t("diagram.door")');
    expect(diagram).toContain("function GuardBridge");
    expect(diagram).toContain("function ExchangeBridge");
    expect(diagram).toMatch(/ArrowLeft|ArrowRight|ArrowDown/);
    expect(diagram).toContain('t("shield")');
    expect(diagram).toContain('t("door")');
    expect(diagram).toContain('t("caption")');
    expect(diagram).not.toContain('t("legend")');
    expect(overview).toContain('t("diagram.transition")');
  });

  it("frames the diagram as all of Tessera and gives AI agents a visual centre", () => {
    expect(diagram).toContain('useTranslations("app")');
    expect(diagram).not.toContain('page("closing.title")');
    expect(diagram).toContain('data-diagram-plane="business"');
    expect(diagram).toContain('data-diagram-plane="agents"');
    expect(diagram).toContain('data-diagram-plane="cockpit"');
    expect(diagram).toContain('data-agent-node="true"');
    expect(diagram).toContain("function AgentPanel");
    expect(diagram).not.toContain("cockpitCaption");
  });

  it("reserves space around the guard and keeps explanatory labels legible", () => {
    expect(diagram).toContain('data-diagram-guard="true"');
    expect(diagram).toContain('data-diagram-guard-label="true"');
    expect(diagram).toContain("xl:h-12");
    expect(diagram).toContain('data-contrast-label="door"');
    expect(overview).toContain('data-contrast-label="questions"');
    expect(overview).toContain('data-contrast-label="moment"');
  });

  it("never renders copy larger than the standard cockpit header title", () => {
    const sources = `${overview}\n${diagram}`;
    const arbitraryRemSizes = [...sources.matchAll(/text-\[(\d+(?:\.\d+)?)rem\]/g)].map(
      ([, value]) => Number(value),
    );

    expect(read("components/layout/app-header.tsx")).toContain("text-[1.45rem]");
    expect(sources).not.toMatch(/text-(?:2xl|3xl|4xl|5xl|6xl|7xl|8xl|9xl)/);
    expect(arbitraryRemSizes.every((size) => size <= 1.45)).toBe(true);
  });
});

describe("the public escape hatch stays narrowly scoped", () => {
  it("only the shared comprendre shell skips the cockpit role gate", () => {
    const files = execFileSync("grep", ["-rl", "publicAccess", "app", "components"], {
      cwd: root,
      encoding: "utf8",
    })
      .trim()
      .split("\n")
      .filter((file) => !file.endsWith(".test.ts"));

    expect(files.sort()).toEqual([
      "components/comprendre/comprendre-shell.tsx",
      "components/layout/app-shell.tsx",
    ]);
  });
});

describe("the product lexicon holds", () => {
  it.each(LOCALES)("%s demo badge copy stays product-safe", (locale) => {
    const copy = Object.values(catalogue(locale).demoBadge).join(" ");
    expect(copy).not.toMatch(/Tessera|AI Control Plane|cockpit|Cockpit/);
  });

  it.each(LOCALES)("%s keeps all three established doors", (locale) => {
    const copy = catalogue(locale).comprendre;
    expect(copy.launcherOrientation.length).toBeGreaterThan(40);
    expect(copy.launcherLink.length).toBeGreaterThan(5);
    expect(copy.loginWelcome.length).toBeGreaterThan(20);
    expect(copy.helpUnderstand.length).toBeGreaterThan(5);
  });
});
