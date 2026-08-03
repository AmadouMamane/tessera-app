/**
 * The wave band that closes the public surfaces (`/select-space`, `/espaces`).
 *
 * WHY IT IS A COMPONENT NOW. It was declared TWICE — the same eight style properties
 * pasted into `landing-launcher.tsx` and `espaces/page.tsx` — and the two copies had
 * already drifted (one masked at 60 %, the other at 55 %, for no reason anyone wrote
 * down). A decoration that must be fixed in two places gets fixed in one.
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
 * USAGE: first child of a `relative` `<main>`. `-z-10` puts it behind main's in-flow
 * content while staying above the page backdrop, and `inset-x-0` resolves against
 * main's PADDING box, so it stays full-bleed despite main's `px-6`.
 */
export function LauncherWaves() {
  const mask = "linear-gradient(to top, #000 60%, transparent 100%)";
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-[300px]"
      style={{
        backgroundImage: "url('/assets/tessera-waves-band.png')",
        backgroundRepeat: "no-repeat",
        backgroundPosition: "center bottom",
        backgroundSize: "100% 100%",
        opacity: "var(--launcher-waves-opacity)",
        maskImage: mask,
        WebkitMaskImage: mask,
      }}
    />
  );
}
