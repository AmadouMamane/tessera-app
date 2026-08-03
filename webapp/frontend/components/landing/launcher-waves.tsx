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
 * Its opacity is a token (`--launcher-waves-opacity`), pinned to 0 under "Clair":
 * `tessera-waves-band.png` is 8-bit RGB with no alpha, so dimming it composites the
 * whole navy plate rather than revealing the page underneath. See
 * `launcher-surface-contrast.test.ts` for that one.
 *
 * USAGE: direct child of the page wrapper, after the backdrop and before the in-flow
 * content. It stays at the same stacking level as the backdrop and wins by source order;
 * the content wrapper remains above both at `z-10`.
 */
export function LauncherWaves({
  /** Multiplier on the theme's own allowance — `/login` runs the artwork at 0.7 so the
   *  sign-in card stays the loudest thing on a page that has nothing else. */
  strength = 1,
  /** Where the top fade starts. Lower = the artwork reaches further up the page. */
  fadeFrom = "60%",
}: {
  strength?: number;
  fadeFrom?: string;
}) {
  const mask = `linear-gradient(to top, #000 ${fadeFrom}, transparent 100%)`;
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 bottom-0 z-0 h-[300px]"
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
