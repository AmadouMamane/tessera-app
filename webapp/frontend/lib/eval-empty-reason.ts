import type { SweepUnavailable } from "@/lib/eval-sweep";

/**
 * Turn "why is the sweep missing" into the message key and values a screen prints.
 *
 * Pure, and separate from the reader, so a test can assert the mapping without a backend and
 * without rendering a page. The whole point of the four keys is that they are not
 * interchangeable: three of them describe a failed READ and one describes an observed ABSENCE,
 * and an operator acts differently on each. Collapsing them was how the old single sentence came
 * to name `data/eval/` — a bundle this reader stopped opening when the sweep moved to HTTP.
 */
export type EmptyReasonKey = "unreachable" | "refused" | "contract" | "absent";

/**
 * `null` means the read SUCCEEDED and there is simply nothing in it — an observed absence, the
 * one case where the screen may state a fact about the evaluation rather than about itself.
 */
export function emptyReasonKey(reason: SweepUnavailable | null): EmptyReasonKey {
  return reason ? reason.kind : "absent";
}

/**
 * Values for the message. `status` is the operator's first clue on a refusal and is meaningless
 * elsewhere, so it is always supplied (next-intl throws on a missing placeholder, never on a
 * spare one) and only the `refused` sentence spends it.
 */
export function emptyReasonValues(reason: SweepUnavailable | null): { status: number } {
  return { status: reason?.kind === "refused" ? reason.status : 0 };
}
