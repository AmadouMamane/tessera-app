import { describe, expect, it } from "vitest";

import { type SchemaField, coerceParams, fieldsFromSchema, validateLocally } from "./schema-form";

/**
 * ADR 0019 §A1.2 (c) — the generic schema→form model. These pin the platform-capital
 * behaviour: any declared `input_schema` becomes fields, coerces to the JSON types the backend
 * validator expects, and gives immediate (non-authoritative) feedback. Nothing here is
 * agent-specific.
 */
function only(schema: unknown): SchemaField {
  const fields = fieldsFromSchema(schema);
  expect(fields).toHaveLength(1);
  return fields[0] as SchemaField;
}

describe("fieldsFromSchema", () => {
  it("falls back to the property name when a property declares no title", () => {
    const field = only({ type: "object", properties: { amount_eur: { type: "number" } } });
    expect(field.label).toBe("amount_eur");
  });

  it("uses the title as the label when present", () => {
    const field = only({
      type: "object",
      properties: { amount_eur: { type: "number", title: "Amount (EUR)" } },
    });
    expect(field.label).toBe("Amount (EUR)");
  });

  it("marks a property listed in required", () => {
    const fields = fieldsFromSchema({
      type: "object",
      properties: { a: { type: "string" }, b: { type: "string" } },
      required: ["a"],
    });
    expect(fields.find((f) => f.name === "a")?.required).toBe(true);
    expect(fields.find((f) => f.name === "b")?.required).toBe(false);
  });

  it("carries enum, description, and min/max through", () => {
    const field = only({
      type: "object",
      properties: {
        months: {
          type: "integer",
          description: "How many months",
          enum: [3, 6, 12],
          minimum: 1,
          maximum: 24,
        },
      },
    });
    expect(field.enumValues).toEqual([3, 6, 12]);
    expect(field.description).toBe("How many months");
    expect(field.minimum).toBe(1);
    expect(field.maximum).toBe(24);
  });

  it("drops a property whose type is outside the renderable subset", () => {
    const fields = fieldsFromSchema({
      type: "object",
      properties: { ok: { type: "string" }, nested: { type: "object" } },
    });
    expect(fields.map((f) => f.name)).toEqual(["ok"]);
  });

  it.each([
    ["a non-object schema", { type: "string" }],
    ["a schema with no properties", { type: "object" }],
    ["a bare string", "nope"],
    ["null", null],
  ])("returns [] for %s", (_label, schema) => {
    expect(fieldsFromSchema(schema)).toEqual([]);
  });
});

describe("coerceParams", () => {
  const fields: SchemaField[] = [
    { name: "count", label: "Count", type: "integer", required: true },
    { name: "rate", label: "Rate", type: "number", required: false },
    { name: "note", label: "Note", type: "string", required: false },
    { name: "urgent", label: "Urgent", type: "boolean", required: false },
  ];

  it("parses integer vs number distinctly", () => {
    const out = coerceParams(fields, { count: "12", rate: "3.5", note: "x", urgent: false });
    expect(out.count).toBe(12);
    expect(out.rate).toBe(3.5);
    expect(Number.isInteger(out.count)).toBe(true);
  });

  it("produces a real boolean from a checkbox value", () => {
    expect(coerceParams(fields, { count: "1", urgent: true }).urgent).toBe(true);
    expect(coerceParams(fields, { count: "1", urgent: false }).urgent).toBe(false);
  });

  it("omits an optional field left empty rather than sending an empty string", () => {
    const out = coerceParams(fields, { count: "1", rate: "", note: "" });
    expect("rate" in out).toBe(false);
    expect("note" in out).toBe(false);
    expect(out.count).toBe(1);
  });
});

describe("validateLocally", () => {
  it("flags a required field left empty", () => {
    const fields: SchemaField[] = [{ name: "a", label: "A", type: "string", required: true }];
    expect(validateLocally(fields, { a: "" })).toEqual(["A: required"]);
    expect(validateLocally(fields, { a: "x" })).toEqual([]);
  });

  it("flags a non-numeric numeric", () => {
    const fields: SchemaField[] = [{ name: "n", label: "N", type: "integer", required: true }];
    expect(validateLocally(fields, { n: "abc" })).toEqual(["N: not a number"]);
  });

  it("flags out-of-range values against minimum and maximum", () => {
    const fields: SchemaField[] = [
      { name: "m", label: "Months", type: "integer", required: true, minimum: 1, maximum: 24 },
    ];
    expect(validateLocally(fields, { m: "0" })).toEqual(["Months: ≥ 1"]);
    expect(validateLocally(fields, { m: "36" })).toEqual(["Months: ≤ 24"]);
    expect(validateLocally(fields, { m: "12" })).toEqual([]);
  });

  it("never complains about an optional empty field", () => {
    const fields: SchemaField[] = [{ name: "o", label: "O", type: "number", required: false }];
    expect(validateLocally(fields, { o: "" })).toEqual([]);
  });
});
