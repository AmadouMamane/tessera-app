import Image from "next/image";

import { cn } from "@/lib/cn";

/**
 * Tessera brand lockup (gem mark + "TESSERA / AI CONTROL PLANE"). The gem reads on
 * any background; only the wordmark needs to flip, so we ship two lockups — a light
 * wordmark for the dark themes and a dark wordmark for "Clair" — and toggle them via
 * the `.light` class in CSS (no theme hook, so no hydration flash). Control the size
 * with a height utility, e.g. `<TesseraLogo className="h-8" />`.
 */
export function TesseraLogo({ className }: { className?: string }) {
  const common = cn("w-auto object-contain", className);
  return (
    <>
      <Image
        src="/brand/tessera-interface-lockup.png"
        alt="Tessera AI Control Plane"
        width={280}
        height={72}
        priority
        unoptimized
        className={cn("brand-logo-dark", common)}
      />
      <Image
        src="/brand/tessera-interface-lockup-light.png"
        alt="Tessera AI Control Plane"
        width={280}
        height={72}
        priority
        unoptimized
        className={cn("brand-logo-light", common)}
      />
    </>
  );
}
