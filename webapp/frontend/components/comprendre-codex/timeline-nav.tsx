"use client";

import { useEffect, useRef, useState } from "react";

interface TimelineItem {
  target: string;
  time: string;
  label: string;
}

export function TimelineNav({ label, items }: { label: string; items: TimelineItem[] }) {
  const [activeTarget, setActiveTarget] = useState(items[0]?.target ?? "");
  const railRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    let animationFrame = 0;

    const updateFromPosition = () => {
      const readingLine = Math.min(window.innerHeight * 0.32, 320);
      let currentTarget = items[0]?.target ?? "";

      for (const item of items) {
        const section = document.getElementById(item.target);
        if (section && section.getBoundingClientRect().top <= readingLine) {
          currentTarget = item.target;
        }
      }

      setActiveTarget(currentTarget);
    };

    const schedulePositionUpdate = () => {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(updateFromPosition);
    };

    const updateFromHash = () => {
      const target = window.location.hash.slice(1);
      if (items.some((item) => item.target === target)) {
        setActiveTarget(target);
        document.getElementById(target)?.scrollIntoView({ block: "start", behavior: "auto" });
      } else {
        schedulePositionUpdate();
      }
    };

    updateFromHash();
    window.addEventListener("hashchange", updateFromHash);
    window.addEventListener("resize", schedulePositionUpdate);
    document.addEventListener("scroll", schedulePositionUpdate, true);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener("hashchange", updateFromHash);
      window.removeEventListener("resize", schedulePositionUpdate);
      document.removeEventListener("scroll", schedulePositionUpdate, true);
    };
  }, [items]);

  useEffect(() => {
    const rail = railRef.current;
    const activeItem = rail?.querySelector<HTMLElement>(`[data-timeline-target="${activeTarget}"]`);
    if (!rail || !activeItem || typeof rail.scrollTo !== "function") return;

    const itemOffset = activeItem.parentElement?.offsetLeft ?? activeItem.offsetLeft;
    const centeredOffset = itemOffset - (rail.clientWidth - activeItem.clientWidth) / 2;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
    rail.scrollTo({
      left: Math.max(0, centeredOffset),
      behavior: reduceMotion ? "auto" : "smooth",
    });
  }, [activeTarget]);

  return (
    <nav
      aria-label={label}
      className="sticky top-0 z-20 -mx-4 border-b border-[var(--tessera-border)] bg-[color-mix(in_srgb,var(--tessera-bg)_88%,transparent)] px-4 backdrop-blur-xl before:absolute before:inset-x-0 before:-top-6 before:h-6 before:bg-[var(--tessera-bg)] sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8"
    >
      <ol
        ref={railRef}
        className="mx-auto flex max-w-[1320px] min-w-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {items.map((item) => {
          const isActive = activeTarget === item.target;
          return (
            <li
              key={item.target}
              className="min-w-[7.5rem] flex-1 border-l border-[var(--tessera-border)] first:border-l-0"
            >
              <a
                href={`#${item.target}`}
                data-timeline-target={item.target}
                aria-current={isActive ? "step" : undefined}
                onClick={() => setActiveTarget(item.target)}
                className="group relative flex h-[4.5rem] flex-col justify-center px-4 transition-colors hover:bg-[var(--tessera-surface)] focus-visible:bg-[var(--tessera-surface)] focus-visible:outline-none"
              >
                <span className="font-mono text-[0.62rem] font-semibold tracking-[0.12em] text-[var(--tessera-green)]">
                  {item.time}
                </span>
                <span className="mt-1 text-xs font-medium whitespace-nowrap text-[var(--tessera-text-muted)] transition-colors group-hover:text-[var(--tessera-text)]">
                  {item.label}
                </span>
                <span
                  aria-hidden="true"
                  className={`absolute inset-x-4 bottom-0 h-px bg-[var(--tessera-green)] transition-opacity ${
                    isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                  }`}
                />
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
