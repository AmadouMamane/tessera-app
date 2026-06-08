/**
 * Typed fetch client.
 *
 * Every public function wraps `fetch` with two invariants:
 *
 * 1. The path is prefixed with `/api` so that the Next.js rewrite layer
 *    forwards to the FastAPI backend (configured via the `TESSERA_BACKEND_URL`
 *    env var at build time).
 * 2. The response is validated through the matching Zod schema. Validation
 *    failures throw `ApiError` rather than returning malformed data.
 */
import type { z } from "zod";

import {
  type AuditIntegrity,
  AuditIntegritySchema,
  type AuditOutcome,
  type AuditPage,
  AuditPageSchema,
  type BudgetSnapshot,
  BudgetSnapshotSchema,
  type Calibration,
  CalibrationSchema,
  type EvalScoresResponse,
  EvalScoresResponseSchema,
  type HealthResponse,
  HealthResponseSchema,
} from "./schemas";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<TSchema extends z.ZodTypeAny>(
  path: string,
  init: RequestInit,
  schema: TSchema,
): Promise<z.infer<TSchema>> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.headers ?? {}),
    },
  });

  const text = await response.text();
  let body: unknown = null;
  if (text.length > 0) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const message =
      (body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : null) ?? `request to ${path} failed`;
    throw new ApiError(message, response.status, body);
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    throw new ApiError(
      `response from ${path} did not match the expected schema`,
      response.status,
      parsed.error.format(),
    );
  }
  return parsed.data;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export interface FetchAuditOptions {
  cursor?: number;
  limit?: number;
  target?: string;
  outcome?: AuditOutcome;
  signal?: AbortSignal;
}

export async function fetchAudit(options: FetchAuditOptions = {}): Promise<AuditPage> {
  const params = new URLSearchParams();
  if (options.cursor != null) params.set("cursor", String(options.cursor));
  if (options.limit != null) params.set("limit", String(options.limit));
  if (options.target) params.set("target", options.target);
  if (options.outcome) params.set("outcome", options.outcome);
  const query = params.toString();
  return request(`/audit${query ? `?${query}` : ""}`, { signal: options.signal }, AuditPageSchema);
}

export async function fetchAuditIntegrity(signal?: AbortSignal): Promise<AuditIntegrity> {
  return request("/audit/integrity", { signal }, AuditIntegritySchema);
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request("/healthz", { signal }, HealthResponseSchema);
}

export async function fetchReadiness(signal?: AbortSignal): Promise<HealthResponse> {
  return request("/readyz", { signal }, HealthResponseSchema);
}

/** Recent online-eval scores (eval-as-telemetry; public aggregate surface). */
export async function fetchEvalScores(signal?: AbortSignal): Promise<EvalScoresResponse> {
  return request("/observability/scores", { signal }, EvalScoresResponseSchema);
}

/** Judge calibration against the human gold set (computed server-side, cached). */
export async function fetchCalibration(signal?: AbortSignal): Promise<Calibration> {
  return request("/observability/calibration", { signal }, CalibrationSchema);
}

/**
 * The /budget endpoint emits text/plain key/value lines. We parse it here so
 * callers see a typed snapshot.
 */
export async function fetchBudget(signal?: AbortSignal): Promise<BudgetSnapshot> {
  const response = await fetch(`${BASE}/budget`, {
    signal,
    headers: { Accept: "text/plain" },
  });
  if (!response.ok) {
    throw new ApiError("/budget failed", response.status, null);
  }
  const text = await response.text();
  const parsed = Object.fromEntries(
    text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split(" ");
        return [key, rest.join(" ")];
      }),
  );
  return BudgetSnapshotSchema.parse({
    input_tokens: Number(parsed.input_tokens ?? 0),
    output_tokens: Number(parsed.output_tokens ?? 0),
    estimated_cost_eur: Number(parsed.estimated_cost_eur ?? 0),
  });
}
