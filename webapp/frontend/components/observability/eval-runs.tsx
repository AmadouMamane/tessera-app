"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ModelComparison, RunRegistry } from "@/lib/api/schemas";

const VERDICT_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  best: "success",
  balanced: "neutral",
  economic: "success",
  avoid: "danger",
};
const KNOWN_VERDICTS = ["best", "balanced", "economic", "avoid"];

function rateTone(r: number): "success" | "warning" | "danger" {
  return r >= 0.8 ? "success" : r >= 0.5 ? "warning" : "danger";
}

function parseRunAt(s: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(s);
  return m ? `${m[3]}/${m[2]} ${m[4]}:${m[5]}` : s;
}

function RateBar({ rate }: { rate: number }) {
  const tone = rateTone(rate);
  const color =
    tone === "success" ? "bg-emerald-500" : tone === "warning" ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <span className={`tabular-nums ${tone === "danger" ? "text-red-500" : ""}`}>
        {Math.round(rate * 100)}%
      </span>
      <span className="hidden h-1.5 w-16 overflow-hidden rounded-full bg-[var(--tessera-border)] sm:block">
        <span className={`block h-full ${color}`} style={{ width: `${rate * 100}%` }} />
      </span>
    </div>
  );
}

function fmtCost(c: number | null, free: string): string {
  if (c == null) return free;
  if (c === 0) return free;
  return `${c.toFixed(3)} €`;
}

function fmtLatency(ms: number | null): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${Math.round(ms)} ms`;
}

/** Eval run registry table + dataset summary (Runs & datasets tab, image 02). */
export function RunsTable({
  registry,
  loading,
  limit,
}: {
  registry: RunRegistry | undefined;
  loading: boolean;
  limit?: number;
}) {
  const tq = useTranslations("quality");

  if (loading && !registry) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("runs.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  const runs = limit ? (registry?.runs ?? []).slice(0, limit) : (registry?.runs ?? []);

  return (
    <Card>
      <CardHeader className="gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm">{tq("runs.title")}</CardTitle>
          <span className="text-xs text-[var(--muted-foreground)]">
            {tq("runs.count", { n: registry?.n ?? 0 })}
          </span>
        </div>
        {registry ? (
          <p className="text-xs text-[var(--muted-foreground)]">
            {tq("runs.catalogue")} · {tq("runs.cases", { n: registry.catalogue_cases })}
            {registry.catalogue_version
              ? ` · ${tq("runs.version", { v: registry.catalogue_version })}`
              : ""}
            {registry.models.length ? ` · ${registry.models.length} ${tq("runs.modelsLabel")}` : ""}
          </p>
        ) : null}
      </CardHeader>
      <CardContent>
        {runs.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("runs.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-4 font-medium">{tq("runs.cols.model")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("runs.cols.lang")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("runs.cols.cases")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("runs.cols.rate")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("runs.cols.cost")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("runs.cols.latency")}</th>
                  <th className="py-2 font-medium">{tq("runs.cols.date")}</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-4 font-medium">{r.model}</td>
                    <td className="py-2 pr-4 uppercase text-[var(--muted-foreground)]">
                      {r.language || "—"}
                    </td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {r.total}
                    </td>
                    <td className="py-2 pr-4">
                      <RateBar rate={r.pass_rate} />
                    </td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {fmtCost(r.est_cost_eur, tq("runs.free"))}
                    </td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {fmtLatency(r.mean_latency_ms)}
                    </td>
                    <td className="py-2 tabular-nums text-[var(--muted-foreground)]">
                      {parseRunAt(r.run_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Per-model comparison table (Comparaisons modèles tab, image 04). */
export function ModelComparisonTable({
  data,
  loading,
}: {
  data: ModelComparison | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const verdictLabel = (v: string) => (KNOWN_VERDICTS.includes(v) ? tq(`models.verdict.${v}`) : v);

  if (loading && !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("models.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  const models = data?.models ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          {tq("models.title")}
          <span className="text-xs font-normal text-[var(--muted-foreground)]">
            {tq("models.count", { n: models.length })}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {models.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("models.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-4 font-medium">{tq("models.cols.model")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("models.cols.cases")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("models.cols.rate")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("models.cols.cost")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("models.cols.latency")}</th>
                  <th className="py-2 font-medium">{tq("models.cols.verdict")}</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.model} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-4 font-medium">{m.model}</td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {m.total_cases}
                    </td>
                    <td className="py-2 pr-4">
                      <RateBar rate={m.pass_rate} />
                    </td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {fmtCost(m.est_cost_eur, tq("runs.free"))}
                    </td>
                    <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                      {fmtLatency(m.mean_latency_ms)}
                    </td>
                    <td className="py-2">
                      <Badge tone={VERDICT_TONE[m.verdict] ?? "neutral"}>
                        {verdictLabel(m.verdict)}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
