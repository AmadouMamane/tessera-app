"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { Truncate } from "@/components/ui/truncate";
import { cn } from "@/lib/cn";

const FOCUSABLE = 'button, a[href], select, input, textarea, [tabindex]:not([tabindex="-1"])';

/** Canonical right-anchored detail drawer for cockpit entity rows. */
export function DetailDrawer({
  title,
  subtitle,
  icon,
  onClose,
  children,
  testId,
  width = "max-w-[480px]",
  belowAgentTabs = false,
}: {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  testId?: string;
  width?: string;
  belowAgentTabs?: boolean;
}) {
  const t = useTranslations("table");
  const [shown, setShown] = useState(false);
  const [rect, setRect] = useState<{ top: number; left: number; width: number; height: number }>();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const frame = requestAnimationFrame(() => {
      setShown(true);
      closeRef.current?.focus();
    });
    return () => {
      cancelAnimationFrame(frame);
      opener?.focus?.();
    };
  }, []);

  useEffect(() => {
    const measure = () => {
      const main = document.querySelector("main");
      if (!main) return;
      const mainRect = main.getBoundingClientRect();
      const content = document.querySelector("[data-shell-content]") ?? main;
      const contentRect = content.getBoundingClientRect();
      const tabs = belowAgentTabs ? document.querySelector("[data-agent-tabs]") : null;
      const top = tabs ? tabs.getBoundingClientRect().bottom : mainRect.top;
      setRect({
        top,
        left: contentRect.left,
        width: contentRect.width,
        height: mainRect.bottom - top,
      });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [belowAgentTabs]);

  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [onClose]);

  function trapFocus(event: React.KeyboardEvent<HTMLDialogElement>) {
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className={cn(
        "fixed z-[70] flex justify-end overflow-hidden bg-[#020817]/70 p-2.5 backdrop-blur-[2px] transition-opacity duration-200 motion-reduce:transition-none max-sm:p-0",
        shown ? "opacity-100" : "opacity-0",
      )}
      style={rect ?? { inset: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <dialog
        ref={dialogRef}
        open
        aria-modal="true"
        aria-label={title}
        onKeyDown={trapFocus}
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        className={cn(
          "static m-0 flex h-full w-full flex-col overflow-hidden border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-0 text-[var(--tessera-text)] shadow-[0_18px_60px_rgba(0,0,0,0.52)] transition-transform duration-200 ease-out motion-reduce:transition-none sm:rounded-lg",
          width,
          shown ? "translate-x-0" : "translate-x-6",
        )}
      >
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--tessera-border)] px-4 py-3.5">
          <div className="flex min-w-0 items-center gap-2.5">
            {icon ? (
              <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-fg-info)]">
                {icon}
              </span>
            ) : null}
            <div className="min-w-0">
              <Truncate
                full={title}
                className="text-sm font-semibold text-[var(--tessera-text-strong)]"
              >
                {title}
              </Truncate>
              {subtitle ? (
                <Truncate
                  full={subtitle}
                  className="mt-0.5 text-xs text-[var(--tessera-text-muted)]"
                >
                  {subtitle}
                </Truncate>
              ) : null}
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={t("close")}
            className="grid h-8 w-8 shrink-0 place-items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] outline-none transition-colors motion-reduce:transition-none hover:text-[var(--tessera-text)] focus-visible:ring-2 focus-visible:ring-[var(--tessera-fg-info)]/45"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div
          data-testid={testId}
          className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4"
        >
          {children}
        </div>
      </dialog>
    </div>
  );
}
