/**
 * What happens when a translation key resolves to nothing — ONE answer, both renderers.
 *
 * `components/providers/intl-provider.tsx` has handled this on the CLIENT since it was written.
 * `i18n/request.ts` did not, and that is the half that mattered least often and worst: every
 * page under `app/[locale]/` that reads through `getTranslations` renders on the server, so a
 * miss there printed next-intl's default — the full dotted key path — into the product UI. The
 * two renderers of one application disagreed about what a missing key looks like.
 *
 * Both now import from here, so they cannot drift again.
 *
 * ON THE CHOICE OF `—`, because it is a trade-off and not an obvious win. This repository's
 * doctrine is that a fallback must never pass for content, and an em dash is precisely what a
 * legitimately-absent value renders as elsewhere in the cockpit — so a missing translation is
 * indistinguishable from an empty measurement, which is the exact confusion the honest-empty
 * rule exists to prevent. It is kept anyway, for one measured reason: the three catalogues are
 * at **perfect key parity** (7292 leaves each, zero missing, asserted by
 * `messages/catalogue-parity.test.ts`), so the set of keys this can fire on is empty today. A
 * louder marker would change nothing visible while risking a cockpit full of debug tokens the
 * first time a backend sends an enum value nobody mapped. The parity ratchet is what keeps the
 * set empty; this is the seat belt, and `reportMissingMessage` is what makes it audible.
 */

/** Reported on every i18n error, on both renderers. Never swallowed — and named correctly. */
export function reportMissingMessage(error: unknown): void {
  // `console.error` on the server reaches container logs; in the browser it reaches the console
  // and any error reporter attached to it. Either way the problem leaves a trace, which the em
  // dash below deliberately does not.
  //
  // next-intl routes EVERY error through this one hook, not only missing keys: a
  // MISSING_MESSAGE, an ENVIRONMENT_FALLBACK (a formatter with no `now`/`timeZone` guessing
  // from the local environment) and a FORMATTING_ERROR all arrive here. Labelling all of them
  // "missing message" is how an ENVIRONMENT_FALLBACK sat in the console for weeks looking like
  // a catalogue gap — and the catalogues are at perfect parity, so the label was actively
  // misleading about where to look. The code says which it is.
  const code = (error as { code?: string } | null)?.code;
  console.error(`[i18n] ${code ?? "error"}`, error);
}

/** What renders in place of the missing string. See the note above before changing it. */
export function missingMessageFallback(): string {
  return "—";
}
