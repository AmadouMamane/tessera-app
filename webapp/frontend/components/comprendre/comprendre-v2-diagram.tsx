"use client";

import { Bot, Building2, CircleDot, Gauge, ScrollText, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";

interface DiagramColumn {
  title: string;
  items: string[];
  caption?: string;
}

interface DiagramFlow {
  label: string;
  detail: string;
}

const columnIcons = [Building2, Bot, Gauge] as const;

/** The approved E architecture map: three spaces, one online guard and a separate ledger. */
export function ComprendreV2Diagram() {
  const t = useTranslations("comprendreV2.diagram");
  const columns = t.raw("columns") as DiagramColumn[];
  const flows = t.raw("flows") as DiagramFlow[];

  return (
    <figure className="relative overflow-hidden rounded-2xl border border-[var(--tessera-border-strong)] bg-[linear-gradient(145deg,var(--tessera-surface-elevated),var(--tessera-surface))] p-5 shadow-[var(--shadow-card)] sm:p-7">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/3 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(0,200,120,0.11),transparent_68%)] blur-3xl"
      />

      <div className="relative flex items-center gap-3 rounded-xl border border-[rgba(0,200,120,0.28)] bg-[rgba(0,200,120,0.06)] px-4 py-3">
        <ShieldCheck className="size-5 shrink-0 text-[var(--tessera-green)]" aria-hidden="true" />
        <p className="text-sm leading-6 font-medium text-[var(--tessera-text)]">{t("shield")}</p>
      </div>

      <div className="relative mt-5 grid gap-4 lg:grid-cols-3">
        {columns.map((column, index) => {
          const Icon = columnIcons[index] ?? Gauge;
          return (
            <section
              key={column.title}
              className="relative rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] p-5"
            >
              <div className="flex items-center gap-3">
                <span className="grid size-9 place-items-center rounded-lg border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] text-[var(--tessera-green)]">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <h3 className="text-sm font-semibold text-[var(--tessera-text)]">{column.title}</h3>
              </div>
              <ul className="mt-4 space-y-2">
                {column.items.map((item) => (
                  <li
                    key={item}
                    className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2.5 text-sm text-[var(--tessera-text)]"
                  >
                    {item}
                  </li>
                ))}
              </ul>
              {column.caption ? (
                <p className="mt-4 text-xs leading-6 text-[var(--tessera-text-muted)]">
                  {column.caption}
                </p>
              ) : null}
            </section>
          );
        })}
      </div>

      <div className="relative mt-4">
        <section className="rounded-xl border border-[#8bb7ff]/30 bg-[#8bb7ff]/[0.06] p-5">
          <div className="flex items-start gap-3">
            <ScrollText className="mt-0.5 size-5 shrink-0 text-[#8bb7ff]" aria-hidden="true" />
            <div>
              <h3 className="font-semibold text-[var(--tessera-text)]">{t("audit.title")}</h3>
              <p className="mt-2 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
                {t("audit.body")}
              </p>
            </div>
          </div>
        </section>
      </div>

      <figcaption className="relative mt-5 border-[var(--tessera-border)] border-t pt-5">
        <p className="font-mono text-[0.62rem] tracking-[0.13em] text-[var(--tessera-text-subtle)] uppercase">
          {t("legend")}
        </p>
        <div className="mt-3 grid gap-x-6 gap-y-4 sm:grid-cols-2">
          {flows.map((flow) => (
            <div key={flow.label} className="flex items-start gap-3 text-xs">
              <CircleDot
                className="mt-0.5 size-4 shrink-0 text-[var(--tessera-green)]"
                aria-hidden
              />
              <span>
                <strong className="block font-semibold text-[var(--tessera-text)]">
                  {flow.label}
                </strong>
                <span className="mt-1 block leading-6 text-[var(--tessera-text-muted)]">
                  {flow.detail}
                </span>
              </span>
            </div>
          ))}
        </div>
      </figcaption>
    </figure>
  );
}
