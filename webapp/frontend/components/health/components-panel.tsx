"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { observedAt, relativeNow } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";
import type { ComponentCheck } from "@/lib/api/schemas";

const POLL_MS = 15_000;

/**
 * The stack's components, as the preflight witness sees them.
 *
 * This page used to render four KPI cards fed by `/healthz` and `/readyz` — two probes about
 * the agent process — while its own contextual help promised a component list with a last
 * check and its dependencies. On 2026-08-05 `tessera.preflight` reported ClickHouse FAIL and
 * this page showed everything operational, because nothing on it could go red for a dependency.
 *
 * Three verdicts, not two. `blind` — the probe could not look at all — is rendered as its own
 * state and never as "ok": a witness that cannot see may not report ok (ADR 0026). A reader who
 * cannot tell "the database is down" from "nobody asked the database" has no information.
 *
 * Four facts per row, and they used to be three columns carrying two meanings. One heading —
 * *"ce qui est interrogé"* — held the component's ROLE on a stack row and the QUESTION on a
 * precondition row; beside it *"ce qu'il a répondu"* showed the probe's detail, which for
 * `eval-package` is the question again, word for word, in both cells. The operator's verdict on
 * that was "c'est un peu du charabia", and it was.
 *
 * So: WHAT IT IS sits under the name, WHAT WAS ASKED is its own column and is translated, and
 * WHAT CAME BACK is the probe's own words in monospace — dropped when it merely echoes the
 * question, because a cell that repeats its neighbour is noise wearing the costume of evidence.
 */
export function ComponentsPanel() {
  const t = useTranslations("health.components");
  const format = useFormatter();

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  const tone = (verdict: string) =>
    verdict === "ok" ? "success" : verdict === "fail" ? "danger" : "warning";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data ? (
          <div className="flex items-center gap-2">
            {/* The observation instant, published because it is NOT the render instant: the
                probe is cached, and a component list that does not say when it last looked
                invites the reader to assume "now". */}
            <span className="text-[0.66rem] text-[var(--muted-foreground)]">
              {t("checked", {
                when: format.relativeTime(observedAt(query.data.observed_at), relativeNow()),
              })}
            </span>
            <Badge tone={tone(query.data.verdict === "clear" ? "ok" : query.data.verdict)}>
              {t(`verdict.${query.data.verdict}`, {
                ok: query.data.counts.stack_ok,
                total: query.data.counts.stack_total,
              })}
            </Badge>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : query.error ? (
          // A failed READ is not an empty result: say the read failed, never "0 components".
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : query.data && query.data.components.length > 0 ? (
          // `table-fixed`, per docs/table-rhythm-playbook.md: auto layout hands its leftover
          // width to a column of its own choosing and the choice changes with the viewport,
          // which is what "the columns look random" is. The identity column is sized to its
          // content and left-aligned; the evidence column takes a flat share, right-aligned, so
          // its leading air matches its neighbours' instead of being whatever is left.
          <div className="overflow-x-auto">
            <table className="w-full table-fixed border-collapse text-left text-[0.72rem]">
              <thead>
                <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
                  <th className="w-[11rem] px-1.5 py-1 font-medium 2xl:w-[14rem]">
                    {t("col.name")}
                  </th>
                  <th className="w-[6.5rem] px-1.5 py-1 font-medium">{t("col.verdict")}</th>
                  <th className="px-1.5 py-1 font-medium">{t("col.asked")}</th>
                  <th className="w-[36%] px-1.5 py-1 pr-2 text-right font-medium">
                    {t("col.answered")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(["stack", "precondition"] as const).flatMap((group) => {
                  const rows = query.data.components.filter((c) => c.group === group);
                  if (rows.length === 0) return [];
                  return [
                    <tr key={`h-${group}`}>
                      <th
                        colSpan={4}
                        className="px-1.5 pb-1 pt-3 text-left text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]"
                      >
                        <span className="flex items-baseline gap-2">
                          {t(`group.${group}`, { n: rows.length })}
                          {/* The two halves answer DIFFERENT questions and were rendered
                              identically: Grafana being down is not the agent being broken.
                              A reader who cannot tell the groups apart looks in the wrong
                              place, which is the failure this whole page is about. */}
                          <span className="font-normal normal-case tracking-normal text-[var(--muted-foreground)]/70">
                            {t(`groupAsks.${group}`)}
                          </span>
                        </span>
                      </th>
                    </tr>,
                    ...rows.map((component) => (
                      <ComponentRow key={`${group}-${component.name}`} component={component} />
                    )),
                  ];
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-[var(--muted-foreground)]">{t("empty")}</p>
        )}
      </CardContent>
    </Card>
  );
}

/** Normalise for the echo test: whitespace and case must not make two identical cells differ. */
const flatten = (value: string) => value.trim().toLowerCase().replace(/\s+/g, " ");

function ComponentRow({ component }: { component: ComponentCheck }) {
  const t = useTranslations("health.components");
  const tone =
    component.verdict === "ok" ? "success" : component.verdict === "fail" ? "danger" : "warning";

  // Translated where a translation exists, served English otherwise. A missing key must degrade
  // to the technical string — which is at least true — never to a blank cell or to next-intl's
  // rendering of the key path.
  const role = t.has(`role.${component.name}`) ? t(`role.${component.name}`) : component.role;

  // Looked up per GROUP, never by name alone. `postgres`, `clickhouse` and `prometheus` appear
  // in BOTH halves — the port and the adapter are two different questions with two different
  // answers, which is the whole reason the table has two groups. A name-only lookup gave the
  // stack rows the PRECONDITION's sentence: "postgres · la connexion propre au registre" next to
  // an answer about a DNS name not resolving. The stack's question is derived from the probe
  // and needs no map at all; only the preconditions carry declared prose.
  const asked =
    component.group === "precondition" && t.has(`asks.${component.name}`)
      ? t(`asks.${component.name}`)
      : askedLabel(component.asked, t);

  // `eval-package` answers `import eval, import eval.runner` — its own question, restated. The
  // badge already carries the outcome, so an echoing cell adds nothing and costs the reader a
  // double-take.
  const echoes = flatten(component.detail) === flatten(component.asked);

  // What the probe found, said in the reader's language, with the MACHINE's own words appended
  // and untouched. A stack probe carries an outcome code for exactly this; a precondition does
  // not, and falls back to preflight's own line — which is read identically in a terminal, and
  // which this page has no business paraphrasing.
  const found =
    component.outcome && t.has(`outcome.${component.outcome}`)
      ? [
          `${component.address} — ${t(`outcome.${component.outcome}`)}`,
          component.raw && !component.raw.startsWith("HTTP") ? component.raw : "",
          component.outcome === "http_ok" || component.outcome === "http_error"
            ? component.raw
            : "",
        ]
          .filter(Boolean)
          .join(" · ")
      : component.detail;

  return (
    <tr className="border-b border-[var(--tessera-border)]/60 last:border-0 align-top">
      <td className="px-1.5 py-1">
        <span className="block truncate font-medium text-[var(--foreground)]">
          {component.name}
        </span>
        {role ? (
          <span className="block truncate text-[0.62rem] text-[var(--muted-foreground)]">
            {role}
          </span>
        ) : null}
      </td>
      <td className="px-1.5 py-1">
        <Badge tone={tone}>{t(`state.${component.verdict}`)}</Badge>
      </td>
      <td className="truncate px-1.5 py-1 text-[var(--muted-foreground)]" title={component.asked}>
        {asked || "—"}
      </td>
      <td
        className="truncate px-1.5 py-1 pr-2 text-right font-mono text-[0.66rem] text-[var(--muted-foreground)]"
        title={component.detail}
      >
        {echoes ? <span className="font-sans italic">{t("answeredByVerdict")}</span> : found}
      </td>
    </tr>
  );
}

/**
 * The derived stack question, rendered in the reader's language.
 *
 * The backend sends `TCP connect` / `HTTP GET /ping` — derived from the probe rather than
 * written out per component, so there is no second list to keep in step. Only the shape needs
 * translating, and the path stays verbatim because it is an address, not prose.
 */
function askedLabel(asked: string, t: (key: string, values?: Record<string, string>) => string) {
  if (asked === "TCP connect") return t("asks.tcp");
  const path = asked.match(/^HTTP GET (.+)$/)?.[1];
  return path ? t("asks.http", { path }) : asked;
}
