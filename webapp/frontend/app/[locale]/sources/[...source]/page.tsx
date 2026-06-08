import { ArrowLeft, BookOpen, FileText, ShieldCheck } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AppShell } from "@/components/layout/app-shell";
import type { Locale } from "@/i18n/routing";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

export const dynamic = "force-dynamic";

interface SourcePageProps {
  params: Promise<{ locale: Locale; source: string[] }>;
}

interface SourceDocument {
  source: string;
  locator: string;
  language: Locale;
  corpus: string;
  category: string;
  text: string;
  metadata: Record<string, string>;
}

function encodedSourcePath(segments: string[]): string {
  return segments.map((segment) => encodeURIComponent(segment)).join("/");
}

async function fetchSourceDocument(
  locale: Locale,
  segments: string[],
): Promise<SourceDocument | null> {
  if (segments.length === 0) return null;
  const url = `${backendUrl()}/sources/${encodedSourcePath(segments)}?language=${locale}`;
  const response = await fetch(url, {
    headers: backendHeaders({ Accept: "application/json" }),
    cache: "no-store",
  });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`source lookup failed with ${response.status}`);
  }
  return (await response.json()) as SourceDocument;
}

export async function generateMetadata({ params }: SourcePageProps) {
  const { locale, source } = await params;
  const t = await getTranslations({ locale, namespace: "source" });
  const document = await fetchSourceDocument(locale, source);
  return { title: document?.locator ?? t("title") };
}

export default async function SourcePage({ params }: SourcePageProps) {
  const { locale, source } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "source" });
  const document = await fetchSourceDocument(locale, source);
  if (document === null) notFound();

  const metadataRows = [
    [t("sourceId"), document.source],
    [t("corpus"), document.corpus],
    [t("category"), document.category],
    [t("language"), document.language.toUpperCase()],
  ];

  return (
    <AppShell title={t("title")} description={document.source}>
      <div className="flex min-h-0 flex-1 flex-col gap-5">
        <Link
          href={`/${locale}/chat`}
          className="inline-flex w-fit items-center gap-1 text-sm font-medium text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
        >
          <ArrowLeft className="h-4 w-4" />
          {t("back")}
        </Link>

        <header className="border-b border-[var(--border)] pb-5">
          <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)]">
            <span className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--muted)]/30 px-2 py-1">
              <ShieldCheck className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
              {t("verified")}
            </span>
            <span className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] bg-[var(--muted)]/30 px-2 py-1">
              <BookOpen className="h-3.5 w-3.5 text-gold-600 dark:text-gold-400" />
              {document.corpus}
            </span>
          </div>
          <h1 className="mt-4 max-w-4xl text-2xl font-semibold text-[var(--foreground)]">
            {document.locator}
          </h1>
          <p className="mt-2 max-w-4xl font-mono text-xs text-[var(--muted-foreground)]">
            {document.source}
          </p>
        </header>

        <section className="grid gap-3 md:grid-cols-[16rem_minmax(0,1fr)]">
          <dl className="space-y-2 border-r border-transparent text-sm md:border-[var(--border)] md:pr-5">
            {metadataRows.map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs font-medium text-[var(--muted-foreground)]">{label}</dt>
                <dd className="mt-0.5 break-words text-[var(--foreground)]">{value}</dd>
              </div>
            ))}
          </dl>

          <article className="min-w-0 rounded-md border border-[var(--border)] bg-[var(--background)] p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
              <FileText className="h-4 w-4 text-gold-600 dark:text-gold-400" />
              {t("document")}
            </div>
            <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--foreground)]">
              {document.text}
            </p>
          </article>
        </section>
      </div>
    </AppShell>
  );
}
