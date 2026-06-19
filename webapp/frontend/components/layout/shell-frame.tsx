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
  children,
}: {
  sidebar: ReactNode;
  topbar: ReactNode;
  footer: ReactNode;
  children: ReactNode;
}) {
  const { focus } = useShellChrome();
  return (
    <div className="bg-canvas-glow relative flex h-full overflow-hidden bg-[var(--tessera-bg)] text-[var(--tessera-text)]">
      {focus ? null : sidebar}
      <div className="flex h-full min-w-0 flex-1 flex-col">
        {focus ? null : topbar}
        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-5 sm:px-6">
          <div
            className={cn(
              "mx-auto flex h-full w-full flex-col",
              focus ? "max-w-[1760px]" : "max-w-[1600px]",
            )}
          >
            {children}
          </div>
        </main>
        {footer}
      </div>
    </div>
  );
}
