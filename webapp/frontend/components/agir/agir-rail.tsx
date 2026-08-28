"use client";

import { Activity, History, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AsOfPickerChip } from "@/components/cockpit/asof-picker-chip";
import { LiveBeacon } from "@/components/cockpit/live-beacon";
import { CHIP_ACTIVE, CHIP_BASE } from "@/components/cockpit/rail-chip";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/**
 * AGIR temporal rail (registre des rails temporels §6): **As-of** (read the
 * state at T, C1 fold) + **Live** (act now). This is NOT the SURVEILLER signal
 * scrubber: no baseline, no period comparison, no replay — and no rail code on
 * screen. The active mode is always displayed and derives from the URL
 * (`?asof=<ISO>`), never from local state, so an As-of reading is deep-linkable
 * and shareable. While As-of, the page's mutations are disabled by the caller —
 * one does not act in the past.
 *
 * The rail wears the SR-01 command-bar grammar (chips on the lacquered strip +
 * a contextual micro-line): a Lecture chip naming the reading, the premium
 * "Voir à date / État au" picker (shared CalendarPopover — never the OS-drawn
 * datetime panel), and the single outline "Revenir au direct".
 */

/** The page's As-of instant from the URL, or null in Live. */
export function useAsOf(): string | null {
  return useSearchParams().get("asof");
}

export function AgirRail({
  liveNote,
  asofNote,
}: {
  /** Page-scoped Live wording (default: the AGIR "you act on the present"). */
  liveNote?: string;
  /**
   * What the As-of reading actually covers on THIS page (e.g. Paramètres: only
   * the governed overrides are refolded at T — the process posture stays live).
   * A reading that claims more than the backend re-reads is the cosmetic mode
   * purged in registre v1.5; this note is how a page keeps the claim exact.
   */
  asofNote?: string;
} = {}) {
  const t = useTranslations("agirRail");
  const to = useTranslations("overview.time");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const asof = searchParams.get("asof");

  const setAsof = (value: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("asof", value);
    } else {
      params.delete("asof");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };

  const ReadingIcon = asof ? History : Activity;
  return (
    <section
      data-testid="agir-rail"
      // Instrument surface (sr01-strip): every temporal rail wears the same
      // lacquered chrome, visually distinct from the page's content cards.
      className="sr01-strip shrink-0 rounded-2xl backdrop-blur-md"
    >
      <div className="sr01-command-row flex flex-wrap items-center gap-2 px-3 py-2">
        {/* Lecture — the reading, always visible. An indicator chip (champagne,
            like SR-01's primary reading control), not a second way to switch:
            picking a date and "Revenir au direct" are the single entries. */}
        <span className={cn(CHIP_BASE, CHIP_ACTIVE, "cursor-default")}>
          <ReadingIcon className="h-3.5 w-3.5 shrink-0 text-gold-600 dark:text-gold-400" />
          {to("reading")}
          <span className="font-semibold text-[var(--tessera-text)]">
            {asof ? t("asofBadge") : t("liveBadge")}
          </span>
          {/* The heartbeat: Live here is URL-derived (no ?asof), true by
              construction — the one place the beacon may beat (live-beacon). */}
          {asof ? null : <LiveBeacon />}
        </span>
        <AsOfPickerChip value={asof} onChange={setAsof} />
      </div>

      {/* Contextual micro-line — describes ONLY the active reading, and carries
          the single "Revenir au direct" (outline, discreet — SR-01 grammar). */}
      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 border-t border-[rgba(96,194,242,0.1)] px-3 py-1.5 text-xs text-[var(--tessera-text-muted)]">
        {asof ? (
          <span className="min-w-0">
            <span className="font-medium text-[var(--tessera-text)]">
              {t("asofReading", { t: new Date(asof).toLocaleString() })}
            </span>
            {asofNote ? <span> · {asofNote}</span> : null}
          </span>
        ) : (
          <span className="font-medium text-[var(--tessera-text)]">
            {liveNote ?? t("liveNote")}
          </span>
        )}
        {asof ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto h-7 gap-1.5 px-2.5 text-xs"
            onClick={() => setAsof(null)}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            {t("backToLive")}
          </Button>
        ) : null}
      </div>
    </section>
  );
}
