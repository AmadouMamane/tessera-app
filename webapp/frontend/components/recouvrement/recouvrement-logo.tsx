import Image from "next/image";

import { cn } from "@/lib/cn";

export function RecouvrementMark({ className }: { className?: string }) {
  return (
    <Image
      src="/brand/recouvrement-mark.png"
      alt=""
      aria-hidden="true"
      width={243}
      height={256}
      priority
      unoptimized
      className={cn("h-[2.1rem] w-auto shrink-0 object-contain", className)}
    />
  );
}

/**
 * The recouvrement console's OWN logo — a distinct product identity, not the
 * Tessera control-plane lockup. The shield comes from the normative product logo
 * under `docs/ui-reference/produit/recouvrement/logo-normative-recouvrement`;
 * the wordmark is rendered as text so it stays crisp at sidebar size.
 */
export function RecouvrementLogo({
  label,
  tagline,
  className,
}: {
  label: string;
  tagline?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-[50px] w-[196px] min-w-0 flex-col items-center justify-center",
        className,
      )}
    >
      <RecouvrementMark />
      <span className="font-semibold text-[0.95rem] leading-[0.95rem] text-[#d9b46f]">{label}</span>
      {tagline ? <span className="sr-only">{tagline}</span> : null}
    </div>
  );
}
