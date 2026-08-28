import { type HTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/cn";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="card"
      className={cn(
        // `min-w-0` is load-bearing, not tidiness. A grid or flex item defaults to
        // `min-width: auto`, which means it refuses to shrink below its content's
        // min-content width. Measured at 390px on /surveiller/qualite-ia: the grid
        // was correctly responsive (one column below sm) and five chart cards still
        // rendered 324px wide inside a 278px column, clipped by an ancestor that
        // hides its overflow — so the right-hand third of five charts was simply
        // unreachable on a phone. A card that shrinks is better than a card you
        // cannot scroll to.
        "min-w-0 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--card-foreground)] shadow-[var(--shadow-card)]",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col gap-1 px-4 pt-3 pb-1.5", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

export const CardTitle = forwardRef<HTMLHeadingElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      data-slot="card-title"
      className={cn("text-base font-semibold leading-tight tracking-tight font-serif", className)}
      {...props}
    />
  ),
);
CardTitle.displayName = "CardTitle";

export const CardDescription = forwardRef<
  HTMLParagraphElement,
  HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p ref={ref} className={cn("text-sm text-[var(--muted-foreground)]", className)} {...props} />
));
CardDescription.displayName = "CardDescription";

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-4 py-2", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex items-center px-4 pb-4 pt-2.5 border-t border-[var(--border)]",
        className,
      )}
      {...props}
    />
  ),
);
CardFooter.displayName = "CardFooter";
