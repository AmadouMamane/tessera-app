"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { useShellChrome } from "./shell-chrome";

/**
 * Client layout frame that reacts to the shell chrome state. In focus mode it
 * hides BOTH the sidebar and the topbar for maximum content and lets the active
 * page exceed the standard cap (an explicit operator choice). Out of focus the
 * topbar stays visible (it carries global context — no auto-hide) and the
 * content keeps the single ~1600px cap.
 */
export function ShellFrame({
  sidebar,
  topbar,
  footer,
  pageSubtitle,
  children,
}: {
  sidebar: ReactNode;
  topbar: ReactNode;
  footer: ReactNode;
  pageSubtitle?: string;
  children: ReactNode;
}) {
  const { focus } = useShellChrome();
  return (
    <div className="bg-canvas-glow relative flex h-full overflow-hidden bg-[var(--tessera-bg)] text-[var(--tessera-text)]">
      {focus ? null : sidebar}
      <div className="flex h-full min-w-0 flex-1 flex-col">
        {focus ? null : topbar}
        {/* The shell owns the bottom space, for EVERY page. `py-5` gave the end of a long
            scroll the same 20px the top gets and read as the last card sitting on the footer;
            48px then read as a hole. 24px is the settled value — and it is homogeneous only
            because the page roots no longer add their own `pb-*` on top of it (19 of them did,
            which is what made the same "end of page" measure differently across the cockpit). */}
        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 pt-5 pb-6 sm:px-6">
          <div
            data-shell-content
            className={cn(
              // `min-h-full`, never `h-full`. With a fixed 100% height this box is exactly the
              // viewport and its children OVERFLOW it — so the scroll container's own
              // padding-bottom never applied to the end of a long page. Measured on 2026-08-07:
              // the last card ended 1px above the footer on /observabilite, 0px on /qualite-ia
              // and 69px BEHIND it on /vue-ensemble, while the padding was declared and
              // seemingly present. `min-h-full` still fills the viewport on a short page (so
              // `flex-1` children stretch exactly as before) and grows with content on a long
              // one, which is the only shape in which trailing padding means anything.
              "mx-auto flex min-h-full w-full flex-col gap-2.5",
              focus ? "max-w-[1760px]" : "max-w-[1600px]",
            )}
          >
            {pageSubtitle ? (
              <p className="max-w-4xl text-sm text-[var(--tessera-text-muted)]">{pageSubtitle}</p>
            ) : null}
            {children}
          </div>
        </main>
        {footer}
      </div>
    </div>
  );
}
