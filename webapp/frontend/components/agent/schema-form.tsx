"use client";

import { SendHorizontal } from "lucide-react";
import { useMemo, useState } from "react";

import { cn } from "@/lib/cn";
import {
  type RawFieldValue,
  type SchemaField,
  coerceParams,
  validateLocally,
} from "@/lib/schema-form";

/**
 * Generic capability form (ADR 0019 §A1.2 c) — PLATFORM CAPITAL, agent-agnostic.
 *
 * Renders one input per `SchemaField` (select for enum, checkbox for boolean, number input for
 * integer/number, text otherwise), shows local validation, and hands coerced JSON params to
 * `onSubmit`. Nothing here knows which agent or capability it renders — that is the whole point:
 * an agent gains a typed test bench by declaring an `input_schema`, never by anyone writing this.
 */
export function SchemaForm({
  fields,
  submitLabel,
  requiredLabel,
  pending,
  onSubmit,
}: {
  fields: SchemaField[];
  submitLabel: string;
  requiredLabel: string;
  pending: boolean;
  onSubmit: (params: Record<string, unknown>) => void;
}) {
  const initial = useMemo(() => initialValues(fields), [fields]);
  const [values, setValues] = useState<Record<string, RawFieldValue>>(initial);
  const [showErrors, setShowErrors] = useState(false);

  const errors = validateLocally(fields, values);
  const set = (name: string, value: RawFieldValue) =>
    setValues((prev) => ({ ...prev, [name]: value }));

  const submit = () => {
    if (errors.length > 0) {
      setShowErrors(true);
      return;
    }
    onSubmit(coerceParams(fields, values));
  };

  return (
    <form
      className="flex flex-col gap-2.5"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      {fields.map((field) => (
        <Field
          key={field.name}
          field={field}
          value={values[field.name]}
          requiredLabel={requiredLabel}
          onChange={(v) => set(field.name, v)}
        />
      ))}

      {showErrors && errors.length > 0 ? (
        <ul className="list-inside list-disc text-xs text-[var(--tessera-fg-danger)]">
          {errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : null}

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={pending}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface-2)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
        >
          <SendHorizontal className="h-4 w-4" aria-hidden />
          {submitLabel}
        </button>
      </div>
    </form>
  );
}

function initialValues(fields: SchemaField[]): Record<string, RawFieldValue> {
  const values: Record<string, RawFieldValue> = {};
  for (const field of fields) {
    if (field.type === "boolean") values[field.name] = field.defaultValue === true;
    else values[field.name] = field.defaultValue === undefined ? "" : String(field.defaultValue);
  }
  return values;
}

function Field({
  field,
  value,
  requiredLabel,
  onChange,
}: {
  field: SchemaField;
  value: RawFieldValue | undefined;
  requiredLabel: string;
  onChange: (value: RawFieldValue) => void;
}) {
  const inputId = `cap-field-${field.name}`;
  const describedById = field.description ? `${inputId}-desc` : undefined;
  const label = (
    <label htmlFor={inputId} className="text-[0.78rem] font-medium text-[var(--tessera-text)]">
      {field.label}
      {field.required ? (
        <span className="ml-1 text-xs font-normal uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {requiredLabel}
        </span>
      ) : null}
    </label>
  );

  const help = field.description ? (
    <p id={describedById} className="text-xs text-[var(--tessera-text-muted)]">
      {field.description}
    </p>
  ) : null;

  const inputClass =
    "w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-sm text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-border-strong)]";

  if (field.type === "boolean") {
    return (
      <div className="flex items-start gap-2">
        <input
          id={inputId}
          type="checkbox"
          checked={value === true}
          aria-describedby={describedById}
          onChange={(e) => onChange(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-[var(--tessera-border)]"
        />
        <div className="flex flex-col gap-0.5">
          {label}
          {help}
        </div>
      </div>
    );
  }

  const text = typeof value === "string" ? value : "";

  return (
    <div className="flex flex-col gap-1">
      {label}
      {field.enumValues ? (
        <select
          id={inputId}
          value={text}
          aria-describedby={describedById}
          onChange={(e) => onChange(e.target.value)}
          className={cn(inputClass, "appearance-none")}
        >
          <option value="">—</option>
          {field.enumValues.map((option) => (
            <option key={String(option)} value={String(option)}>
              {String(option)}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={inputId}
          type={field.type === "string" ? "text" : "number"}
          inputMode={
            field.type === "integer" ? "numeric" : field.type === "number" ? "decimal" : undefined
          }
          step={field.type === "integer" ? 1 : field.type === "number" ? "any" : undefined}
          min={field.minimum}
          max={field.maximum}
          value={text}
          aria-describedby={describedById}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        />
      )}
      {help}
    </div>
  );
}
