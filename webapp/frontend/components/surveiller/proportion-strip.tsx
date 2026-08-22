import { cn } from "@/lib/cn";

/**
 * A thin segmented proportion bar — one strip, ONE unit. Every consumer feeds it values
 * that share a single denominator (responses across judged agents, runs across business
 * agents, agents across an observability split), so the strip can never become the
 * cross-ruler figure the two-rulers rule forbids: it draws shares of one population.
 *
 * It renders nothing when fewer than two segments carry a value — a bar that is one full
 * segment is decoration, not information — and nothing on an empty population.
 */
export interface StripSegment {
  key: string;
  /** Tooltip: "who · how much", in the population's own unit. */
  title: string;
  value: number;
  className: string;
}

export function ProportionStrip({
  segments,
  label,
  className,
}: {
  segments: StripSegment[];
  /** Accessible name for the whole strip (the card's own label). */
  label: string;
  className?: string;
}) {
  const visible = segments.filter((segment) => segment.value > 0);
  const total = visible.reduce((sum, segment) => sum + segment.value, 0);
  if (total <= 0 || visible.length < 2) return null;
  return (
    <div
      role="img"
      aria-label={label}
      className={cn("flex h-1.5 w-full gap-px overflow-hidden rounded-full", className)}
    >
      {visible.map((segment) => (
        <span
          key={segment.key}
          title={segment.title}
          className={cn("min-w-0 basis-0", segment.className)}
          style={{ flexGrow: segment.value }}
        />
      ))}
    </div>
  );
}
