import {
  BookOpenCheck,
  ClipboardCheck,
  Eye,
  FileCheck2,
  FlaskConical,
  type LucideIcon,
  TriangleAlert,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { type SignalProvenance, provenanceFor } from "@/lib/signal-registry";

type NonLiveProvenance = Exclude<SignalProvenance, "live">;

const ICONS: Record<NonLiveProvenance, LucideIcon> = {
  reference: BookOpenCheck,
  evaluation: ClipboardCheck,
  simulation: FlaskConical,
  preview: Eye,
  fallback: TriangleAlert,
  declaration: FileCheck2,
};

const TONES: Record<NonLiveProvenance, string> = {
  reference: "border-sky-500/25 bg-sky-500/10 text-[var(--tessera-fg-info)]",
  evaluation: "border-indigo-500/25 bg-indigo-500/10 text-[var(--tessera-fg-info)]",
  simulation: "border-amber-500/25 bg-amber-500/10 text-[var(--tessera-fg-warning)]",
  preview: "border-violet-500/25 bg-violet-500/10 text-[var(--tessera-fg-info)]",
  fallback: "border-amber-500/30 bg-amber-500/10 text-[var(--tessera-fg-warning)]",
  declaration: "border-slate-500/25 bg-slate-500/10 text-[var(--tessera-text-muted)]",
};

/**
 * Contextual provenance for material that is not live telemetry.
 *
 * The signal registry owns the category, the locale catalogue owns the explanation, and this
 * component owns the visual grammar. Live or undeclared signals render nothing. Keeping these
 * three responsibilities separate prevents one generic "demo data" warning from smearing a
 * versioned reference, an evaluation set, a simulation and a local fallback as the same thing.
 */
export function ProvenanceNotice({
  signalId,
  compact = false,
}: { signalId: string; compact?: boolean }) {
  const t = useTranslations("dataProvenance");
  const provenance = provenanceFor(signalId);
  if (provenance === undefined || provenance === "live") return null;

  const Icon = ICONS[provenance];
  return (
    <div
      role="note"
      data-provenance={provenance}
      className={`${TONES[provenance]} flex shrink-0 items-center rounded-md border ${
        compact ? "mb-2 gap-1.5 px-2.5 py-1.5 text-xs" : "gap-2 px-3 py-2.5 text-xs"
      }`}
    >
      <Icon className={compact ? "h-3.5 w-3.5 shrink-0" : "h-4 w-4 shrink-0"} />
      <span className="min-w-0 leading-relaxed">
        <span className="font-semibold">{t(`${provenance}.title`)}</span>
        <span className="opacity-75"> — {t(`${provenance}.detail`)}</span>
      </span>
    </div>
  );
}
