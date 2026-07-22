"use client";

import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Bot,
  Building2,
  Gauge,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
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
const flowIcons = [ArrowLeft, ArrowRight, ArrowLeft, ArrowDown] as const;

/** The approved E architecture map: three spaces, one online guard and a separate ledger. */
export function ComprendreV2Diagram() {
  const t = useTranslations("comprendreV2.diagram");
  const columns = t.raw("columns") as DiagramColumn[];
  const flows = t.raw("flows") as DiagramFlow[];

  return (
    <figure className="relative overflow-hidden rounded-3xl border border-[var(--tessera-border-strong)] bg-[linear-gradient(145deg,var(--tessera-surface-elevated),var(--tessera-surface))] p-5 shadow-[var(--shadow-card-elevated)] sm:p-8">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/3 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(0,200,120,0.11),transparent_68%)] blur-3xl"
      />

      <div className="relative grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
        {columns.map((column, index) => {
          const Icon = columnIcons[index] ?? Gauge;
          return (
            <div key={column.title} className="contents">
              <section className="relative rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] p-5">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-xl border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] text-[var(--tessera-green)]">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <h3 className="font-semibold text-[var(--tessera-text)]">{column.title}</h3>
                </div>
                <ul className="mt-5 space-y-2">
                  {column.items.map((item) => (
                    <li
                      key={item}
                      className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2.5 text-sm text-[var(--tessera-text)]"
                    >
                      {item}
                    </li>
                  ))}
                </ul>
                {column.caption ? (
                  <p className="mt-4 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
                    {column.caption}
                  </p>
                ) : null}
              </section>

              {index === 0 ? (
                <div className="flex items-center justify-center lg:pointer-events-none lg:absolute lg:top-1/2 lg:left-1/3 lg:z-10 lg:-translate-x-1/2 lg:-translate-y-1/2">
                  <div className="flex max-w-xs items-center gap-3 rounded-2xl border border-[rgba(0,200,120,0.35)] bg-[color-mix(in_srgb,var(--tessera-surface-elevated)_90%,transparent)] px-4 py-3 shadow-lg backdrop-blur">
                    <ShieldCheck
                      className="size-6 shrink-0 text-[var(--tessera-green)]"
                      aria-hidden="true"
                    />
                    <span className="text-xs leading-relaxed font-semibold text-[var(--tessera-text)]">
                      {t("shield")}
                    </span>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="hidden lg:block" />
        <section className="rounded-2xl border border-[#8bb7ff]/30 bg-[#8bb7ff]/[0.06] p-5">
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
        <div className="hidden lg:block" />
      </div>

      <p className="mt-6 rounded-2xl border border-dashed border-[var(--tessera-border-strong)] bg-[var(--tessera-bg-soft)] px-5 py-4 text-sm leading-relaxed font-medium text-[var(--tessera-text)]">
        {t("door")}
      </p>

      <div className="mt-6 border-[var(--tessera-border)] border-t pt-5">
        <p className="font-mono text-[0.62rem] tracking-[0.13em] text-[var(--tessera-text-subtle)] uppercase">
          {t("legend")}
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {flows.map((flow, index) => {
            const Icon = flowIcons[index] ?? ArrowRight;
            return (
              <div key={flow.label} className="flex items-start gap-3 text-xs">
                <Icon className="mt-0.5 size-4 shrink-0 text-[var(--tessera-green)]" aria-hidden />
                <span>
                  <strong className="block font-semibold text-[var(--tessera-text)]">
                    {flow.label}
                  </strong>
                  <span className="mt-1 block leading-relaxed text-[var(--tessera-text-muted)]">
                    {flow.detail}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </figure>
  );
}
