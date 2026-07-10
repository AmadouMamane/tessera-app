import { useTranslations } from "next-intl";

/**
 * The one image at the top of /comprendre.
 *
 * Two columns, one one-way door between them, the agents below with an arrow each way, and
 * the two memories at the bottom. The words are the eight in the brief and nothing else:
 * the bank, the cockpit, the agent publishes, trial message, the measurements, the audit
 * ledger. No technical term reaches this drawing, which is why it is drawn rather than
 * labelled — a caption that needed a glossary would defeat it.
 *
 * Plain HTML and CSS, not an SVG: it reflows on a phone, it inherits the theme's colours,
 * and a screen reader walks it as the text it is.
 */
export function TwoWorldsDiagram() {
  const t = useTranslations("comprendre.diagram");

  return (
    <figure className="my-8 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 sm:p-7">
      <div className="flex flex-col gap-4">
        {/* The two worlds, side by side, with the single door between them. */}
        <div className="grid items-stretch gap-3 sm:grid-cols-[1fr_auto_1fr]">
          <World name={t("bank")} tone="bank" />
          <div className="flex flex-col items-center justify-center gap-1.5 px-1 py-2 sm:py-0">
            <span
              aria-hidden
              className="font-semibold text-[1.25rem] text-[var(--tessera-text-muted)] leading-none"
            >
              ←
            </span>
            <span className="max-w-[9rem] text-center text-[0.66rem] text-[var(--tessera-text-muted)] leading-tight">
              {t("door")}
            </span>
          </div>
          <World name={t("cockpit")} tone="cockpit" />
        </div>

        {/* The agents below, with one arrow up and one arrow down. */}
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_1fr]">
          <Flow arrow="↑" text={t("publishes")} />
          <div className="flex items-center justify-center rounded-lg border border-[var(--tessera-border)] border-dashed px-4 py-3 text-center font-medium text-[0.8rem] text-[var(--tessera-text)]">
            {t("agents")}
          </div>
          <Flow arrow="↓" text={t("testMessage")} />
        </div>

        {/* The two memories. */}
        <div className="grid gap-3 sm:grid-cols-2">
          <Memory name={t("measures")} />
          <Memory name={t("ledger")} />
        </div>
      </div>
      <figcaption className="mt-4 text-center text-[0.72rem] text-[var(--tessera-text-muted)]">
        {t("caption")}
      </figcaption>
    </figure>
  );
}

function World({ name, tone }: { name: string; tone: "bank" | "cockpit" }) {
  return (
    <div
      className={
        tone === "bank"
          ? "rounded-lg border border-sky-500/35 bg-sky-500/[0.07] px-4 py-6 text-center font-semibold text-[0.95rem] text-sky-200"
          : "rounded-lg border border-[#7c5cf5]/40 bg-[#7c5cf5]/[0.09] px-4 py-6 text-center font-semibold text-[#c9b8ff] text-[0.95rem]"
      }
    >
      {name}
    </div>
  );
}

function Flow({ arrow, text }: { arrow: string; text: string }) {
  return (
    <p className="flex items-center gap-2 rounded-lg bg-[var(--tessera-surface-2)] px-3 py-3 text-[0.72rem] text-[var(--tessera-text-muted)]">
      <span
        aria-hidden
        className="font-semibold text-[1rem] text-[var(--tessera-text)] leading-none"
      >
        {arrow}
      </span>
      <span>{text}</span>
    </p>
  );
}

function Memory({ name }: { name: string }) {
  return (
    <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-4 py-3 text-center text-[0.78rem] text-[var(--tessera-text)]">
      {name}
    </p>
  );
}
