import { FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";

import { isSynthetic } from "@/lib/signal-registry";

/**
 * An honest, registry-driven banner marking a card as a deterministic fixture (ADR 0015 §E).
 *
 * Fixture composites and deterministic assistant fallbacks have no real per-agent substrate.
 * Rather than let them read as live data, this banner names them what they are — sourced from
 * the *same* `isSynthetic(signalId)` flag that drives the registry, so the label cannot drift
 * from the declaration. Renders nothing for a non-synthetic signal.
 */
export function SyntheticNotice({
  signalId,
  compact = false,
}: { signalId: string; compact?: boolean }) {
  const t = useTranslations("synthetic");
  if (!isSynthetic(signalId)) return null;
  return (
    <div
      role="note"
      className={
        compact
          ? "mb-2 flex shrink-0 items-center gap-1.5 rounded-md border border-amber-500/25 bg-amber-500/10 px-2 py-1 text-[0.62rem] text-[var(--tessera-fg-warning)]/90"
          : "flex shrink-0 items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[0.72rem] text-[var(--tessera-fg-warning)]/90"
      }
    >
      <FlaskConical
        className={
          compact
            ? "h-3 w-3 shrink-0 text-[var(--tessera-fg-warning)]"
            : "h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-warning)]"
        }
      />
      <span className="min-w-0 truncate">
        <span className="font-semibold">{t("title")}</span>
        <span className="text-[var(--tessera-fg-warning)]/70"> — {t("detail")}</span>
      </span>
    </div>
  );
}
