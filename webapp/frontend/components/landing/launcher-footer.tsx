import { useTranslations } from "next-intl";

import { TesseraLogo } from "@/components/brand/tessera-logo";
import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

/**
 * The foot of the public surfaces (`/select-space`, `/espaces`).
 *
 * Those pages used to end on 300 px of decorative wave band and nothing else. On the dark
 * themes that band is night-blue artwork and it reads; under "Clair" it is an OPAQUE navy
 * rectangle composited at 12 %, i.e. a uniform grey slab with two coloured smudges — which
 * is what "le bas de la page ne ressemble plus à rien" was pointing at (2026-08-02). The
 * band is now withheld under "Clair" (`--launcher-waves-opacity: 0`), and this footer gives
 * the bottom of the page something to BE instead of something to hide.
 *
 * Everything it states is real: three routes that exist, and the same demonstration framing
 * the DEMO badge already carries at the top. No fabricated metric, no invented link.
 */
export function LauncherFooter({ width = "wide" }: { width?: "wide" | "narrow" }) {
  const t = useTranslations("landing.footer");
  // The two pages cap their content differently (the launcher at 1220, the directory at
  // 1040). A footer that keeps its own cap starts one gutter off the column above it, and a
  // page whose two columns *nearly* line up reads worse than one that plainly does not.
  // Whole literals, not an assembled string — a constructed Tailwind class emits no CSS.
  const cap = width === "narrow" ? "max-w-[1040px]" : "max-w-[1220px]";
  const links: Array<{
    href: "/comprendre" | "/espaces" | "/surveiller/vue-ensemble";
    key: string;
  }> = [
    { href: "/comprendre", key: "understand" },
    { href: "/espaces", key: "spaces" },
    { href: "/surveiller/vue-ensemble", key: "cockpit" },
  ];
  return (
    // `px-6` on the OUTER box and the cap on the inner one — the same nesting `<main>` uses,
    // so the footer's first character sits on the same vertical as the cards above it. The
    // other way round (cap outside, padding inside) insets the text by one gutter and the
    // page reads as two columns that nearly line up, which is worse than either.
    <footer
      // NO SCRIM ANY MORE, and its removal is the actual fix. A wash of the page colour
      // plus `backdrop-blur` was what stood between these words and the wave band running
      // underneath them — it made the text readable and left the collision in place, which
      // is why it still read as a seam cut across the artwork. The band now stops at this
      // element's top rule (`LauncherWaves`), so there is nothing behind the footer to
      // hide, and it sits on the page ground like every other region of the page.
      className="relative z-10 mt-auto w-full border-[var(--border-subtle)] border-t px-6"
    >
      <div
        className={cn(
          "mx-auto flex w-full flex-col gap-[18px] pt-[26px] pb-[10px] sm:flex-row sm:items-center sm:justify-between",
          cap,
        )}
      >
        {/* `items-start`: the lockup is an <img> with `w-auto object-contain`, so a stretched
            flex item centres its own artwork inside the full row width. */}
        <div className="flex flex-col items-start gap-[8px]">
          <TesseraLogo className="h-[24px]" />
          <p className="max-w-[34rem] text-[11.5px] leading-[1.5] text-[var(--text-secondary)]">
            {t("tagline")}
          </p>
        </div>
        <nav
          aria-label={t("navLabel")}
          className="flex flex-wrap items-center gap-x-[20px] gap-y-[8px]"
        >
          {links.map((link) => (
            <Link
              key={link.key}
              href={link.href}
              className="rounded-sm text-[12px] text-[var(--text-secondary)] outline-none transition-colors hover:text-[var(--text-primary)] focus-visible:ring-2 focus-visible:ring-[color-mix(in_srgb,var(--text-primary)_60%,transparent)]"
            >
              {t(`links.${link.key}` as "links.understand")}
            </Link>
          ))}
        </nav>
      </div>
      <div className={cn("mx-auto w-full pb-[24px]", cap)}>
        <p className="text-[11px] leading-[1.5] text-[color-mix(in_srgb,var(--text-secondary)_78%,transparent)]">
          {t("note")}
        </p>
      </div>
    </footer>
  );
}
