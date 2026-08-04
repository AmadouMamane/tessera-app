import { describe, expect, it } from "vitest";

import { SkewReportSchema } from "./schemas";

const unknownPayload = {
  query_model: "bge-m3",
  query_dimension: 1024,
  corpus_model: "bge-m3",
  corpus_dimension: 1024,
  dimension_mismatch: false,
  model_mismatch: false,
  skew: false,
  severity: "unknown",
  reason: "the corpus fingerprint is unavailable",
  corpus_known: false,
  corpus_rows: 241,
  unfingerprinted_rows: 241,
  spaces: [],
};

describe("embedding-skew wire contract", () => {
  it("accepts the production blind-spot payload without converting it to success", () => {
    const parsed = SkewReportSchema.parse(unknownPayload);

    expect(parsed.severity).toBe("unknown");
    expect(parsed.corpus_known).toBe(false);
    expect(parsed.unfingerprinted_rows).toBe(241);
  });

  it.each(["none", "soft", "hard", "unknown"] as const)(
    "keeps %s as a distinct verdict",
    (severity) => {
      const payload =
        severity === "none"
          ? {
              ...unknownPayload,
              severity,
              corpus_known: true,
              unfingerprinted_rows: 0,
              spaces: [{ model: "bge-m3", dimension: 1024, rows: 241 }],
            }
          : { ...unknownPayload, severity };
      expect(SkewReportSchema.parse(payload).severity).toBe(severity);
    },
  );

  it("rejects a clean verdict over incomplete evidence", () => {
    expect(() => SkewReportSchema.parse({ ...unknownPayload, severity: "none" })).toThrow();
  });
});
