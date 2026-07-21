import { getTranslations, setRequestLocale } from "next-intl/server";

import { ComprendreDiagram } from "@/components/comprendre/comprendre-diagram";
import { AppShell } from "@/components/layout/app-shell";
import { Link } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

/** One section of the page, as the locale catalogue carries it. */
interface Section {
  heading: string;
  body: string[];
  proof?: { text: string; href: string };
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "comprendre" });
  return { title: t("pageTitle") };
}

/**
 * `/comprendre` — three minutes for a visitor who knows nothing about any of this.
 *
 * The prose is validated content, held in the locale catalogues and reproduced verbatim
 * (`comprendre.test.ts` checks the French against the source document, paragraph by
 * paragraph). Nothing here rewrites it, and nothing here is hardcoded: eight sections and a
 * diagram, all read from `messages/<locale>.json`.
 *
 * Each "See for yourself" link points at a live page that shows what the paragraph above it
 * just claimed. That is the page's whole signature — an assertion with a runnable example
 * beside it — and it is why the links are part of the content, not decoration.
 */
export default async function ComprendrePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "comprendre" });
  const sections = t.raw("sections") as Section[];

  return (
    // Public on purpose: the launcher offers this page to a visitor who has not logged in,
    // and an explanation nobody can read explains nothing. It renders no fact and reads no
    // store — see `AppShell.publicAccess`, which exactly one page sets.
    <AppShell title={t("pageTitle")} description={t("pageLead")} publicAccess>
      <article className="mx-auto max-w-[46rem] pb-12">
        <ComprendreDiagram />

        {sections.map((section) => (
          <section key={section.heading} className="mt-10 first:mt-0">
            <h2 className="font-semibold text-[1.05rem] text-[var(--tessera-text)]">
              {section.heading}
            </h2>
            {section.body.map((paragraph) => (
              <p
                key={paragraph.slice(0, 48)}
                className="mt-3 text-[0.9rem] text-[var(--tessera-text-muted)] leading-relaxed"
              >
                {paragraph}
              </p>
            ))}
            {section.proof ? (
              <p className="mt-4 border-[#7c5cf5]/50 border-l-2 pl-3 text-[0.82rem] text-[var(--tessera-text-muted)] italic">
                <Link
                  href={section.proof.href}
                  className="font-medium text-[#b9a6ff] not-italic hover:text-white"
                >
                  {t("proofLabel")}
                </Link>
                {" : "}
                {section.proof.text}
              </p>
            ) : null}
          </section>
        ))}
      </article>
    </AppShell>
  );
}
