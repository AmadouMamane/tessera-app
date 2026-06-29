import { cn } from "@/lib/cn";

/**
 * A small colour disc that reflects what each appearance actually LOOKS like — the
 * "logo" for a theme. Reads truer than a generic moon/sun glyph now that the dark
 * themes are named by colour (Bleu nuit / Ardoise). Representative tones (not the
 * exact page hex, which would be indistinguishable black discs) so the blue vs
 * graphite character is legible at 14px. "Système" shows a split disc (follows OS).
 */
const SWATCH: Record<string, string> = {
  // Clair — pale neutral.
  light: "#eef2f7",
  // Bleu nuit — the saturated deep blue, lifted so its hue reads.
  dark: "#0e3050",
  // Ardoise — desaturated graphite-navy.
  "deep-night": "#2b3344",
};

export function ThemeSwatch({ theme, className }: { theme: string; className?: string }) {
  const base = cn(
    "inline-block h-3.5 w-3.5 shrink-0 rounded-full ring-1 ring-inset ring-[rgba(148,163,184,0.45)]",
    className,
  );
  if (theme === "system") {
    // Half light / half graphite — "follows the system".
    return (
      <span
        aria-hidden
        className={base}
        style={{ background: "linear-gradient(135deg, #eef2f7 0 50%, #2b3344 50% 100%)" }}
      />
    );
  }
  return <span aria-hidden className={base} style={{ background: SWATCH[theme] ?? "#0e3050" }} />;
}
