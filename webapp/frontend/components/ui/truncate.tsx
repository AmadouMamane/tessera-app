"use client";

import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";

const CLAMP: Record<number, string> = {
  2: "line-clamp-2",
  3: "line-clamp-3",
  4: "line-clamp-4",
};

type TruncateProps = {
  /** The (possibly clipped) content to display. */
  children: ReactNode;
  /**
   * Full text revealed on hover. Defaults to `children` when it is a plain
   * string; pass it explicitly when `children` is composite (e.g. `{a} - {b}`).
   */
  full?: string;
  /** Lines before clamping. 1 (default) → single-line ellipsis. */
  lines?: number;
  className?: string;
  /**
   * Element to render (default `"span"`). Use `"dd"`/`"dt"`/`"p"` to preserve
   * semantics — e.g. a value cell inside a `<dl>`. Radix `asChild` and
   * `Tooltip.Root` add no DOM wrapper, so the tag stays a real child of its
   * parent.
   */
  as?: "span" | "p" | "div" | "dd" | "dt";
};

/**
 * Clip overflowing text and reveal the full value on hover. Uses the app-wide
 * styled tooltip (≈200 ms via the mounted `<TooltipProvider>`), not the
 * browser's slow, unstyled native `title=`. The single general primitive for
 * dynamic truncated text across the cockpit: the reveal shows ONLY the full
 * string, never richer info (that stays behind the ⓘ).
 *
 * Deliberately dead simple — same shape as the KPI tiles: an UNCONTROLLED Radix
 * tooltip with `<TooltipContent>` ALWAYS rendered. No overflow measurement, no
 * refs, no effects: a measurement gate is fail-closed (if it never flips, the
 * reveal silently disappears), and reliability of the reveal matters more than
 * suppressing the tooltip on the occasional short string.
 */
export function Truncate({
  children,
  full,
  lines = 1,
  className,
  as: Tag = "span",
}: TruncateProps) {
  const reveal = full ?? (typeof children === "string" ? children : "");
  const clip = lines > 1 ? (CLAMP[lines] ?? "line-clamp-2") : "block truncate";

  // Nothing to reveal (composite children with no `full`) → plain clipped span.
  if (!reveal) {
    return <Tag className={cn(clip, className)}>{children}</Tag>;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Tag className={cn(clip, className)}>{children}</Tag>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs break-words">
        {reveal}
      </TooltipContent>
    </Tooltip>
  );
}
