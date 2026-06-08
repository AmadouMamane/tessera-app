import type { ChatCitation, Locale } from "@/lib/api/schemas";

export function citationKey(citation: ChatCitation): string {
  return `${citation.language}\u0000${citation.source.trim()}\u0000${citation.locator.trim()}`;
}

export function dedupeCitations(citations: ChatCitation[]): ChatCitation[] {
  const seen = new Set<string>();
  const out: ChatCitation[] = [];
  for (const citation of citations) {
    const key = citationKey(citation);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(citation);
  }
  return out;
}

export function sourceHref(locale: Locale | string, citation: ChatCitation): string {
  const sourcePath = citation.source
    .split("/")
    .filter((segment) => segment.length > 0)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const params = new URLSearchParams({ language: citation.language });
  return `/${locale}/sources/${sourcePath}?${params.toString()}`;
}
