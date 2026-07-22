import { getTranslations, setRequestLocale } from "next-intl/server";

import { ComprendreDiagram } from "@/components/comprendre/comprendre-diagram";
import { ComprendreShell } from "@/components/comprendre/comprendre-shell";
import { Link } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

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

/** The original approved long-form explanation, moved without changing its catalogue. */
export default async function ComprendreDetailPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "comprendre" });
  const sections = t.raw("sections") as Section[];

  return (
    <ComprendreShell title={t("pageTitle")} description={t("pageLead")}>
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
                {t("proofSeparator")}
                {section.proof.text}
              </p>
            ) : null}
          </section>
        ))}
      </article>
    </ComprendreShell>
  );
}
