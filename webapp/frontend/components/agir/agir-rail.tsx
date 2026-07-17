"use client";

import { CircleDot, History, Undo2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { cn } from "@/lib/cn";

/**
 * AGIR temporal rail (registre des rails temporels §6): **As-of** (read the
 * state at T, C1 fold) + **Live** (act now). This is NOT the SURVEILLER signal
 * scrubber: no baseline, no period comparison, no replay — and no rail code on
 * screen. The active mode is always displayed and derives from the URL
 * (`?asof=<ISO>`), never from local state, so an As-of reading is deep-linkable
 * and shareable. While As-of, the page's mutations are disabled by the caller —
 * one does not act in the past.
 */

/** The page's As-of instant from the URL, or null in Live. */
export function useAsOf(): string | null {
  return useSearchParams().get("asof");
}

export function AgirRail() {
  const t = useTranslations("agirRail");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const asof = searchParams.get("asof");

  // datetime-local speaks LOCAL wall-clock; the URL speaks UTC ISO. Convert
  // explicitly both ways — slicing the ISO would silently shift the display.
  const toLocalInput = (iso: string) => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

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

  return (
    <section
      data-testid="agir-rail"
      className="flex min-h-[44px] shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-1.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
    >
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[0.66rem] font-medium",
          asof
            ? "border-amber-500/40 bg-amber-500/15 text-amber-300"
            : "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
        )}
      >
        {asof ? <History className="h-3 w-3" /> : <CircleDot className="h-3 w-3" />}
        {asof ? t("asofBadge") : t("liveBadge")}
      </span>
      {asof ? (
        <>
          <span className="min-w-0 truncate text-[0.68rem] text-[var(--tessera-text)]">
            {t("asofReading", { t: new Date(asof).toLocaleString() })}
          </span>
          <button
            type="button"
            onClick={() => setAsof(null)}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.66rem] font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)]"
          >
            <Undo2 className="h-3 w-3" /> {t("backToLive")}
          </button>
        </>
      ) : (
        <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("liveNote")}</span>
      )}
      <label className="ml-auto inline-flex items-center gap-1.5 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {t("pickLabel")}
        <input
          type="datetime-local"
          aria-label={t("pickLabel")}
          value={asof ? toLocalInput(asof) : ""}
          onChange={(e) => {
            const v = e.target.value;
            setAsof(v ? new Date(v).toISOString() : null);
          }}
          className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.64rem] text-[var(--tessera-text)]"
        />
      </label>
    </section>
  );
}
