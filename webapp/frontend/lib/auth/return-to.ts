/**
 * Accept only same-application paths as post-login destinations.
 *
 * Query strings are user-controlled. Reject protocol-relative paths,
 * backslashes, locale-prefixed paths (the locale-aware router owns that
 * segment), login loops and any value that URL parsing moves off-origin.
 */
export function safeLoginReturnTo(value: string | string[] | undefined): string | null {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (
    !candidate ||
    candidate !== candidate.trim() ||
    !candidate.startsWith("/") ||
    candidate.startsWith("//") ||
    candidate.includes("\\")
  ) {
    return null;
  }

  const base = "https://tessera.invalid";
  const parsed = new URL(candidate, base);
  if (parsed.origin !== base) return null;
  if (/^\/(?:fr|de|en)(?:\/|$)/.test(parsed.pathname)) return null;
  if (/^\/login(?:\/|$)/.test(parsed.pathname)) return null;

  return `${parsed.pathname}${parsed.search}${parsed.hash}`;
}
