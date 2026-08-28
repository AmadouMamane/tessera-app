import { ExternalLink, Layers, ShieldCheck, SlidersHorizontal } from "lucide-react";
import type { Route } from "next";

import { Link } from "@/i18n/navigation";

/** The read-only catalogue definition an agent binds to (shared shape across the
 *  Configurations and Prompts payloads). */
export type DefinitionData = {
  title: string;
  subtitle: string;
  link: { label: string; href: string };
  rows: { label: string; value: string }[];
};

/** Shared "1. Définition (catalogue, lecture seule) / 2. Configuration pour cet
 *  agent (instance)" framing (define / choose / govern). Used by Configurations
 *  and Prompts so the two pages tell the same governed story with one component.
 *  Every value is real — the definition rows come from the governed registry /
 *  catalogue, never free-text. */
export function DefineInstanceBanner({
  definition,
  governanceBanner,
  instanceLabel,
  instanceHint,
}: {
  definition?: DefinitionData;
  governanceBanner?: string;
  instanceLabel: string;
  instanceHint?: string;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      {definition ? (
        <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 className="flex items-center gap-2 text-[0.82rem] font-semibold text-[var(--tessera-text)]">
              <span className="grid h-5 w-5 place-items-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-xs font-bold text-[var(--tessera-fg-accent)]">
                1
              </span>
              <Layers className="h-4 w-4 text-[var(--tessera-fg-accent)]" />
              {definition.title}
              <span className="rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {definition.subtitle}
              </span>
            </h2>
            <Link
              href={definition.link.href as Route}
              className="flex items-center gap-1 text-xs text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
            >
              {definition.link.label} <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs md:grid-cols-3">
            {definition.rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between gap-2">
                <dt className="text-[var(--tessera-text-muted)]">{r.label}</dt>
                <dd className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
                  {r.value}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {/* 2 · Configuration pour cet agent (instance) — introduces the editable
          sections below; the actual controls remain each page's own. */}
      <div className="flex items-center gap-2 px-0.5">
        <span className="grid h-5 w-5 place-items-center rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-xs font-bold text-[var(--tessera-fg-success)]">
          2
        </span>
        <SlidersHorizontal className="h-4 w-4 text-[var(--tessera-fg-success)]" />
        <span className="text-[0.78rem] font-semibold text-[var(--tessera-text)]">
          {instanceLabel}
        </span>
        {instanceHint ? (
          <span className="text-xs text-[var(--tessera-text-muted)]">· {instanceHint}</span>
        ) : null}
      </div>

      {governanceBanner ? (
        <div className="flex items-start gap-2 rounded-lg border border-[#1f3a5f]/60 bg-[#0e1f33]/40 px-3 py-2.5 text-xs text-[var(--tessera-text-muted)]">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--tessera-fg-info)]" />
          <span>{governanceBanner}</span>
        </div>
      ) : null}
    </div>
  );
}
