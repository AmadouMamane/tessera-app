import { cn } from "@/lib/cn";

/**
 * The wave band that closes the public surfaces (`/select-space`, `/espaces`, `/login`).
 *
 * WHY IT IS A COMPONENT NOW. It was declared THREE times — the same eight style
 * properties pasted into `landing-launcher.tsx`, `espaces/page.tsx` and
 * `login/page.tsx` — and the copies had already drifted: three different mask stops
 * (60 %, 55 %, 48 %) for no reason anyone wrote down, and one of the three at 0.7
 * strength for a reason that WAS written down. A decoration that must be fixed in
 * three places gets fixed in one. The variation that is deliberate is now a named
 * argument; the variation that was drift is now gone.
 *
 * WHY IT MOVED. It used to be `absolute bottom-0` against the PAGE, so when
 * `LauncherFooter` arrived on 2026-08-02 the footer landed inside it: measured on the
 * deployed build, the band spanned y 600→900 and the footer 773→900 — the whole footer,
 * every pixel of it, sitting on the artwork. On the dark themes the gold and cyan
 * strands ran straight behind "Cockpit de gouvernance", and the footer's scrim cut a
 * hard horizontal seam across the middle of the picture. That is the collision Amadou
 * reported ("le footer collisionne avec les vagues en mode bleu nuit"), and a scrim
 * treats its symptom.
 *
 * So the band is anchored to the bottom of `<main>` instead — which means it ends
 * exactly at the footer's top rule WHATEVER the footer's height, and the footer wraps
 * to two rows on a phone. The rule becomes the horizon the waves rest on: content,
 * then waves, then a line, then the foot of the page. Nothing overlaps anything.
 *
 * Its opacity is a token (`--launcher-waves-opacity`), pinned to 0 under "Clair":
 * `tessera-waves-band.png` is 8-bit RGB with no alpha, so dimming it composites the
 * whole navy plate rather than revealing the page underneath. See
 * `launcher-surface-contrast.test.ts` for that one.
 *
 * WHERE IT GOES is the one thing the caller must get right, and it is a fact about the
 * PAGE, not a taste — which is why it is `anchor` and not a z-index the caller passes:
 *
 *   · `anchor="content"` (default) — first child of a `relative` <main>, on a page that
 *     has a footer. `-z-10` puts it behind main's in-flow content while staying above
 *     the page backdrop, and `inset-x-0` resolves against main's PADDING box, so it
 *     stays full-bleed despite main's `px-6`.
 *   · `anchor="page"` — direct child of the page wrapper, on a page with NO footer
 *     (`/login`). There it is a SIBLING of the backdrop rather than a descendant of
 *     something painted above it, so `-z-10` would put it *behind* that backdrop and
 *     it would disappear. `z-0` is the same layer, ordered after it.
 */
export function LauncherWaves({
  anchor = "content",
  /** Multiplier on the theme's own allowance — `/login` runs the artwork at 0.7 so the
   *  sign-in card stays the loudest thing on a page that has nothing else. */
  strength = 1,
  /** Where the top fade starts. Lower = the artwork reaches further up the page. */
  fadeFrom = "60%",
}: {
  anchor?: "content" | "page";
  strength?: number;
  fadeFrom?: string;
}) {
  const mask = `linear-gradient(to top, #000 ${fadeFrom}, transparent 100%)`;
  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-x-0 bottom-0 h-[300px]",
        anchor === "content" ? "-z-10" : "z-0",
      )}
      style={{
        backgroundImage: "url('/assets/tessera-waves-band.png')",
        backgroundRepeat: "no-repeat",
        backgroundPosition: "center bottom",
        backgroundSize: "100% 100%",
        opacity:
          strength === 1
            ? "var(--launcher-waves-opacity)"
            : `calc(var(--launcher-waves-opacity) * ${strength})`,
        maskImage: mask,
        WebkitMaskImage: mask,
      }}
    />
  );
}
