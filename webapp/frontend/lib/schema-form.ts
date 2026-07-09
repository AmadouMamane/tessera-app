/**
 * Generic JSON-Schema → form model (ADR 0019 §A1.2 c).
 *
 * PLATFORM CAPITAL: built once, agent-agnostic. Nothing here names an agent or a capability —
 * it turns any capability `input_schema` the backend forwards into a flat list of renderable
 * fields, coerces the string-valued form back into the JSON types the invocation route
 * validates, and does the same required/type/range checks locally for immediate feedback.
 *
 * The backend (`capability_schema.py`) remains the authority: `validateLocally` is UX, not a
 * gate. The two stay in lockstep on the same supported subset — primitive typed properties of a
 * `type: "object"` schema — so a schema the backend refuses to load never reaches here.
 */

const SUPPORTED_TYPES = ["string", "integer", "number", "boolean"] as const;
export type SchemaFieldType = (typeof SUPPORTED_TYPES)[number];

export interface SchemaField {
  name: string;
  label: string;
  type: SchemaFieldType;
  required: boolean;
  description?: string;
  enumValues?: (string | number)[];
  minimum?: number;
  maximum?: number;
  defaultValue?: string | number | boolean;
}

/** A raw form value: text/number inputs and selects yield strings, checkboxes yield booleans. */
export type RawFieldValue = string | boolean;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asType(value: unknown): SchemaFieldType | null {
  return SUPPORTED_TYPES.includes(value as SchemaFieldType) ? (value as SchemaFieldType) : null;
}

/**
 * Flatten a JSON Schema into ordered fields. Tolerant by construction: a schema shape the
 * renderer cannot honour yields `[]` rather than throwing, so a malformed declaration degrades
 * to "no form" instead of a crashed console. (The backend already rejects such schemas at load;
 * this is the browser's own belt.)
 */
export function fieldsFromSchema(schema: unknown): SchemaField[] {
  if (!isRecord(schema) || schema.type !== "object") return [];
  const properties = schema.properties;
  if (!isRecord(properties)) return [];
  const required = new Set(Array.isArray(schema.required) ? schema.required.map(String) : []);

  const fields: SchemaField[] = [];
  for (const [name, raw] of Object.entries(properties)) {
    if (!isRecord(raw)) continue;
    const type = asType(raw.type);
    if (type === null) continue;
    const enumValues = Array.isArray(raw.enum)
      ? raw.enum.filter((v): v is string | number => typeof v === "string" || typeof v === "number")
      : undefined;
    const field: SchemaField = {
      name,
      label: typeof raw.title === "string" && raw.title ? raw.title : name,
      type,
      required: required.has(name),
    };
    if (typeof raw.description === "string") field.description = raw.description;
    if (enumValues && enumValues.length > 0) field.enumValues = enumValues;
    if (typeof raw.minimum === "number") field.minimum = raw.minimum;
    if (typeof raw.maximum === "number") field.maximum = raw.maximum;
    if (
      typeof raw.default === "string" ||
      typeof raw.default === "number" ||
      typeof raw.default === "boolean"
    ) {
      field.defaultValue = raw.default;
    }
    fields.push(field);
  }
  return fields;
}

/**
 * Coerce raw form values into the JSON types the backend validator expects. An optional field
 * left empty is OMITTED (not sent as `""`), so an untouched optional parameter reads as absent
 * rather than as a deliberate empty string. A required-but-empty field is left out too — local
 * validation flags it first, and the backend refuses it regardless.
 */
export function coerceParams(
  fields: SchemaField[],
  raw: Record<string, RawFieldValue>,
): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const field of fields) {
    const value = raw[field.name];
    if (field.type === "boolean") {
      params[field.name] = value === true;
      continue;
    }
    const text = typeof value === "string" ? value.trim() : "";
    if (text === "") continue; // untouched → omit; required-empty is caught by validateLocally
    if (field.type === "integer") params[field.name] = Number.parseInt(text, 10);
    else if (field.type === "number") params[field.name] = Number.parseFloat(text);
    else params[field.name] = text;
  }
  return params;
}

/**
 * Local, UX-only validation: required-missing, non-numeric numerics, and out-of-range. The
 * message strings are intentionally terse and English-free where possible (field labels carry
 * the meaning); the backend produces the authoritative, localisable violations.
 */
export function validateLocally(
  fields: SchemaField[],
  raw: Record<string, RawFieldValue>,
): string[] {
  const errors: string[] = [];
  for (const field of fields) {
    const value = raw[field.name];
    const text = typeof value === "string" ? value.trim() : "";
    if (field.type === "boolean") continue;
    if (text === "") {
      if (field.required) errors.push(`${field.label}: required`);
      continue;
    }
    if (field.type === "integer" || field.type === "number") {
      const parsed = field.type === "integer" ? Number.parseInt(text, 10) : Number.parseFloat(text);
      if (Number.isNaN(parsed)) {
        errors.push(`${field.label}: not a number`);
        continue;
      }
      if (field.minimum !== undefined && parsed < field.minimum) {
        errors.push(`${field.label}: ≥ ${field.minimum}`);
      }
      if (field.maximum !== undefined && parsed > field.maximum) {
        errors.push(`${field.label}: ≤ ${field.maximum}`);
      }
    }
  }
  return errors;
}
