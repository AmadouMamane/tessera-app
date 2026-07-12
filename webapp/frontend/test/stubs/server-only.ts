/**
 * No-op stand-in for Next's `server-only` marker (see vitest.config.ts).
 *
 * The real package exists only to make a build FAIL when a server module is imported into a
 * client bundle. It has no runtime behaviour, and it cannot be resolved outside the Next
 * compiler — which would otherwise make every `import "server-only"` module untestable.
 */
export {};
