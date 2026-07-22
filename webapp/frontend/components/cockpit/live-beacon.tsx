"use client";

import { cn } from "@/lib/cn";

/**
 * The live heartbeat — a small emerald beacon whose ping BEATS only where the
 * reading follows the present BY CONSTRUCTION (URL-derived Live on a temporal
 * rail, a live cassette lens). One per surface, on the reading indicator —
 * never sprinkled on status dots or list rows, and never on a surface whose
 * window is frozen at mint (a heartbeat over a stale window would lie). The
 * ping layer is decorative: it honours prefers-reduced-motion (the static dot
 * remains) and is hidden from assistive tech (the label next to it carries
 * the meaning).
 */
export function LiveBeacon({ className }: { className?: string }) {
  return (
    <span className={cn("relative flex h-1.5 w-1.5 shrink-0", className)} aria-hidden>
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70 [animation-duration:2.2s] motion-reduce:hidden" />
      <span className="relative inline-flex h-full w-full rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.55)]" />
    </span>
  );
}
