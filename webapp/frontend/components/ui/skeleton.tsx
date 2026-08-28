import type { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

/**
 * A block that says "I do not know yet" — as opposed to a panel that says "there is nothing".
 *
 * It used to say neither. The gradient read
 * `linear-gradient(110deg, var(--secondary) 8%, var(--muted) 18%, var(--secondary) 33%)`, and in
 * both themes `--secondary` and `--muted` resolve to the same `--tessera-muted`: three identical
 * stops, so the animation swept a monochrome band and nothing moved. In dark mode that flat
 * block (#071b2e) sat on a card of #06182a — a difference no eye resolves. Every one of the 102
 * skeletons in this app therefore rendered as an empty panel, which is how a ten-second judge
 * calibration read as "this screen is broken" during a review of it.
 *
 * Two dedicated tokens now, for two reasons. The sheen must differ from the base or the sweep is
 * decoration; and the BASE must differ from the card, because `prefers-reduced-motion` stops the
 * sweep entirely and the block still has to be legible as a block.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      data-slot="skeleton"
      className={cn(
        "rounded-md bg-[var(--tessera-skeleton)]",
        "bg-[linear-gradient(110deg,var(--tessera-skeleton)_8%,var(--tessera-skeleton-sheen)_18%,var(--tessera-skeleton)_33%)]",
        "bg-[length:200%_100%] animate-[shimmer_2s_ease-in-out_infinite]",
        className,
      )}
      aria-hidden="true"
      {...props}
    />
  );
}
