"use client";

/**
 * The route-level error boundary. There was none, anywhere under `app/`.
 *
 * Thirteen screens destructure `useQuery` without reading `isError` and render `…` while the
 * request is failing, so a backend outage arrived as a page that looked like it was still
 * loading — for as long as the operator was willing to wait. Anything that throws during
 * render had no boundary at all above it and took the whole cockpit to a blank frame.
 *
 * This says the three things a mute ellipsis never said: something failed, here is the digest
 * to correlate it with the server logs, and here is a button that retries. It deliberately
 * does NOT interpret the error — a boundary that guesses at causes invents them.
 */
import { useEffect } from "react";

import { useTranslations } from "next-intl";

export default function LocaleError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("errorBoundary");

  useEffect(() => {
    // The browser console is the only place this is recoverable from once the frame is
    // replaced; the digest is what ties it to the server-side log line.
    console.error("[tessera] route error", error.digest ?? "(no digest)", error);
  }, [error]);

  return (
    <main className="flex min-h-[60vh] items-center justify-center px-6">
      <div className="max-w-md text-center">
        <p className="font-serif text-2xl font-semibold tracking-tight text-[var(--tessera-text-strong)]">
          {t("title")}
        </p>
        <p className="mt-3 text-sm text-[var(--tessera-text-muted)]">{t("detail")}</p>
        {error.digest ? (
          <p className="mt-4 font-mono text-[0.7rem] text-[var(--tessera-text-muted)]">
            {t("digest", { digest: error.digest })}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          className="mt-6 inline-block rounded-md bg-[var(--tessera-accent)] px-4 py-2 text-sm font-medium text-[var(--tessera-accent-foreground)]"
        >
          {t("retry")}
        </button>
      </div>
    </main>
  );
}
