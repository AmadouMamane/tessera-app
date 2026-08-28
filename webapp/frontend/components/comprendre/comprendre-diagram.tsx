import { useTranslations } from "next-intl";

/**
 * The one image at the top of /comprendre.
 *
 * A map, not a mood board: the agents sit inside the bank panel, the two records sit inside
 * the cockpit panel, and every arrow starts on one panel and ends on the other. Two plain
 * arrows carry the data (the agent publishes, the cockpit sends a trial message); one dashed
 * line below carries the only passage between the spaces, and its arrowhead shows the single
 * direction. The words are the eight in the brief and nothing else: the bank, the cockpit,
 * the agents, publishes, trial message, the measurements, the audit ledger, the door.
 *
 * Plain HTML and CSS, not an SVG: it reflows on a phone (the panels stack and the arrows
 * turn into glyphs), it inherits the theme's colours, and a screen reader walks it as the
 * text it is.
 */
export function ComprendreDiagram() {
  const t = useTranslations("comprendre.diagram");

  return (
    <figure className="my-8 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 sm:p-7">
      <div className="grid gap-3 sm:grid-cols-[1fr_minmax(11rem,1.15fr)_1fr] sm:gap-0">
        {/* The bank, with its agents inside it. */}
        <section className="flex flex-col rounded-xl border border-sky-500/35 bg-sky-500/[0.06]">
          <p className="border-sky-500/25 border-b px-4 py-2.5 text-center font-semibold text-[0.9rem] text-[var(--tessera-fg-info)]">
            {t("bank")}
          </p>
          <div className="flex flex-1 items-center justify-center px-4 py-6">
            <p className="w-full rounded-lg border border-sky-300/25 bg-[var(--tessera-surface-2)] px-4 py-3 text-center font-medium text-[0.82rem] text-[var(--tessera-text)]">
              {t("agents")}
            </p>
          </div>
        </section>

        {/* Desktop: the two data flows, each drawn from one panel to the other. */}
        <div className="hidden flex-col justify-center gap-7 px-3 sm:flex">
          <FlowAcross direction="right" label={t("publishes")} />
          <FlowAcross direction="left" label={t("testMessage")} />
        </div>

        {/* Phone: the same two flows as stacked rows between the panels. */}
        <div className="flex flex-col gap-2 sm:hidden">
          <FlowStacked glyph="↓" label={t("publishes")} />
          <FlowStacked glyph="↑" label={t("testMessage")} />
        </div>

        {/* The cockpit, with the two records inside it. */}
        <section className="flex flex-col rounded-xl border border-[#7c5cf5]/40 bg-[#7c5cf5]/[0.07]">
          <p className="border-[#7c5cf5]/30 border-b px-4 py-2.5 text-center font-semibold text-[var(--tessera-fg-accent)] text-[0.9rem]">
            {t("cockpit")}
          </p>
          <div className="flex flex-1 flex-col justify-center gap-2.5 px-4 py-5">
            <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-4 py-3 text-center text-[0.8rem] text-[var(--tessera-text)]">
              {t("measures")}
            </p>
            <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-4 py-3 text-center text-[0.8rem] text-[var(--tessera-text)]">
              {t("ledger")}
            </p>
          </div>
        </section>
      </div>

      {/* The single door, cockpit → bank. Dashed on purpose: people pass here, not data. */}
      <div className="relative mt-6 hidden h-4 sm:block">
        <span
          aria-hidden
          className="absolute inset-x-[14%] top-1/2 border-[var(--tessera-border)] border-t border-dashed"
        />
        <span
          aria-hidden
          className="absolute left-[14%] top-1/2 h-0 w-0 -translate-x-full -translate-y-1/2 border-y-4 border-y-transparent border-r-[7px] border-r-[var(--tessera-text-muted)]"
        />
        <p className="-translate-y-1/2 absolute top-1/2 right-0 left-0 mx-auto w-fit bg-[var(--tessera-surface)] px-3 text-center text-xs text-[var(--tessera-text-muted)]">
          {t("door")}
        </p>
      </div>
      <div className="mt-2 sm:hidden">
        <FlowStacked glyph="↑" label={t("door")} dashed />
      </div>

      <figcaption className="mt-4 text-center text-xs text-[var(--tessera-text-muted)]">
        {t("caption")}
      </figcaption>
    </figure>
  );
}

/** One horizontal arrow spanning the whole gutter, its head touching the panel it enters. */
function FlowAcross({ direction, label }: { direction: "left" | "right"; label: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span aria-hidden className="flex w-full items-center">
        {direction === "left" ? (
          <span className="h-0 w-0 border-y-4 border-y-transparent border-r-[7px] border-r-[var(--tessera-text-muted)]" />
        ) : null}
        <span className="h-px flex-1 bg-[var(--tessera-text-muted)]/55" />
        {direction === "right" ? (
          <span className="h-0 w-0 border-y-4 border-y-transparent border-l-[7px] border-l-[var(--tessera-text-muted)]" />
        ) : null}
      </span>
      <span className="text-center text-xs text-[var(--tessera-text-muted)] leading-tight">
        {label}
      </span>
    </div>
  );
}

/** The phone rendering of a flow: a glyph and its label, stacked between the panels. */
function FlowStacked({
  glyph,
  label,
  dashed = false,
}: {
  glyph: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <p
      className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-xs text-[var(--tessera-text-muted)] ${
        dashed
          ? "border border-[var(--tessera-border)] border-dashed"
          : "bg-[var(--tessera-surface-2)]"
      }`}
    >
      <span
        aria-hidden
        className="font-semibold text-[1rem] text-[var(--tessera-text)] leading-none"
      >
        {glyph}
      </span>
      <span>{label}</span>
    </p>
  );
}
