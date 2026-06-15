import Image from "next/image";

import { cn } from "@/lib/cn";

/**
 * Tessera brand lockup (gem mark + "TESSERA / AI CONTROL PLANE"). Reusable
 * across the site; control the size with a height utility, e.g.
 * `<TesseraLogo className="h-8" />`. Width auto-scales to keep the aspect ratio.
 */
export function TesseraLogo({ className }: { className?: string }) {
  return (
    <Image
      src="/brand/tessera-interface-lockup.png"
      alt="Tessera AI Control Plane"
      width={280}
      height={72}
      priority
      unoptimized
      className={cn("w-auto object-contain", className)}
    />
  );
}
