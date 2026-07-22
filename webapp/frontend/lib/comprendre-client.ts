import { type ComprendreResponse, ComprendreResponseSchema } from "@/lib/api/schemas";

/** Refresh the public `/comprendre` aggregate through its BFF and validate the wire. */
export async function fetchComprendreFacts(): Promise<ComprendreResponse | null> {
  try {
    const response = await fetch("/api/comprendre", { cache: "no-store" });
    if (!response.ok) return null;
    const parsed = ComprendreResponseSchema.safeParse(await response.json());
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}
