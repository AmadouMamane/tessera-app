import { ApiError } from "@/lib/api/client";

/**
 * Did this request fail because the caller may not see the data (audit 2026-07-12, F-4)?
 *
 * The distinction this helper exists to force:
 *
 *   honest-empty  — "there is no data"           → a FACT about the world.
 *   access denied — "you may not see this data"  → a FACT about the CALLER.
 *
 * They are not interchangeable, and rendering the second as the first is a lie the repo's own
 * honest-empty doctrine forbids. It is also the easiest mistake to make when gating a surface:
 * `inventory.data?.n_expiring_soon ?? 0` renders a confident **0** for a caller who was
 * refused — a number that reads as "nothing is expiring" when the truth is "we did not tell
 * you". A `?? 0` on a query that can now 401 is a bug, not a default.
 *
 * So: any surface whose data became subject-scoped must branch on this and say which of the
 * two it is.
 */
export function isAccessDenied(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}
