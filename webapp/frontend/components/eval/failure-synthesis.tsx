import { AlertTriangle, ShieldCheck, Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ScorecardResult, Synthesis } from "@/lib/api/schemas";

const KNOWN = new Set([
  "prompt_injection",
  "pii_leak",
  "hallucination",
  "overconfidence",
  "citation_fabrication",
  "tool_misuse",
  "policy_violation",
  "regulatory_misstatement",
  "language_mixing",
  "escalation_failure",
]);

const TONE: Record<string, "danger" | "warning" | "navy" | "info"> = {
  prompt_injection: "danger",
  pii_leak: "danger",
  hallucination: "warning",
  overconfidence: "warning",
  citation_fabrication: "warning",
  tool_misuse: "danger",
  policy_violation: "navy",
  regulatory_misstatement: "navy",
  language_mixing: "info",
  escalation_failure: "danger",
};

/** Short, scannable case chip: the numeric prefix, full id on hover. */
function CaseChip({ caseId }: { caseId: string }) {
  const short = caseId.split("_")[0] ?? caseId;
  return (
    <code
      title={caseId}
      className="rounded bg-[var(--muted)]/60 px-1.5 py-0.5 font-mono text-xs text-[var(--foreground)]"
    >
      {short}
    </code>
  );
}

/** A unified row of the weakness table — one interpretive family or, on runs
 *  with no synthesis, one failing category. `note` (root cause) and `fix` are
 *  the model's when present; `category` is the family's dominant category, used
 *  for the static remediation baseline and the tone badge. */
interface Row {
  key: string;
  label: string;
  category: string;
  caseIds: string[];
  note: string;
  fix: string;
  isFamily: boolean;
}

/** Pick the category most of a family's cases belong to (for the static fix
 *  baseline + tone). Falls back to "unknown" when none is known. */
function dominantCategory(caseIds: string[], catOf: Map<string, string>): string {
  const counts = new Map<string, number>();
  for (const id of caseIds) {
    const cat = catOf.get(id);
    const key = cat && KNOWN.has(cat) ? cat : "unknown";
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  let best = "unknown";
  let bestN = -1;
  for (const [cat, n] of counts) {
    if (n > bestN) {
      best = cat;
      bestN = n;
    }
  }
  return best;
}

/**
 * Superadmin-only weakness map, rendered as ONE table whatever the run carries
 * — so the panel looks the same across runs (it used to switch between a family
 * list and a by-category fallback). Rows are the qualitative `synthesis`
 * families when present (a capable model groups failures by shared root cause,
 * across raw categories), otherwise one row per failing category. The
 * "Recommended fix" column is hybrid: the model's per-family `fix` when present,
 * else a static per-category remediation baseline — so it is never empty.
 */
export async function FailureSynthesis({
  synthesis,
  results,
  locale,
}: {
  synthesis?: Synthesis | null;
  results: ScorecardResult[];
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });
  const failed = results.filter((r) => !r.passed);
  const hasSynthesis = (synthesis?.families.length ?? 0) > 0;
  const catOf = new Map(results.map((r) => [r.case_id, r.category]));

  const fixFor = (category: string, modelFix: string) =>
    modelFix.trim()
      ? modelFix
      : t(`failureSynthesis.fixes.${KNOWN.has(category) ? category : "unknown"}`);

  let rows: Row[];
  if (hasSynthesis) {
    rows = (synthesis?.families ?? []).map((fam) => {
      const category = dominantCategory(fam.case_ids, catOf);
      return {
        key: fam.label,
        label: fam.label,
        category,
        caseIds: [...new Set(fam.case_ids)],
        note: fam.note,
        fix: fixFor(category, fam.fix),
        isFamily: true,
      };
    });
  } else {
    // A case that fails in `fr` AND in `de` is ONE case, not two. `results` holds one row per
    // (case, language), so pushing `case_id` per failed row listed `08 08 11 41 43 43` — six chips
    // for four cases — and handed React two children with the same key. The set is not a
    // formality: the column is headed "cases", and it was counting runs.
    const groups = new Map<string, Set<string>>();
    for (const r of failed) {
      const key = KNOWN.has(r.category) ? r.category : "unknown";
      const bucket = groups.get(key);
      if (bucket) bucket.add(r.case_id);
      else groups.set(key, new Set([r.case_id]));
    }
    rows = [...groups.entries()]
      .sort((a, b) => b[1].size - a[1].size)
      .map(([category, caseIds]) => ({
        key: category,
        label: t(`categories.${category}`),
        category,
        caseIds: [...caseIds],
        note: "",
        fix: t(`failureSynthesis.fixes.${category}`),
        isFamily: false,
      }));
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-[var(--tessera-fg-gold)]" />
          <CardTitle>{t("failureSynthesis.title")}</CardTitle>
          <Badge tone="navy">{t("failureSynthesis.badge")}</Badge>
          {hasSynthesis ? (
            <span className="ml-auto flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
              <Sparkles className="h-3 w-3 text-[var(--tessera-fg-gold)]" />
              {synthesis?.model && synthesis.model !== "manual"
                ? t("failureSynthesis.generatedBy", { model: synthesis.model })
                : t("failureSynthesis.manual")}
            </span>
          ) : null}
        </div>
        <CardDescription>{t("failureSynthesis.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        {failed.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <ShieldCheck className="h-4 w-4 text-[var(--tessera-fg-success)]" />
            {t("failureSynthesis.none")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table className="table-fixed">
              <colgroup>
                <col className="w-[26%]" />
                <col className="w-[16%]" />
                <col className="w-[31%]" />
                <col className="w-[27%]" />
              </colgroup>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("failureSynthesis.columns.pattern")}</TableHead>
                  <TableHead>{t("failureSynthesis.columns.cases")}</TableHead>
                  <TableHead>{t("failureSynthesis.columns.rootCause")}</TableHead>
                  <TableHead>{t("failureSynthesis.columns.fix")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.key}>
                    <TableCell className="max-w-0 overflow-hidden align-top">
                      {row.isFamily ? (
                        <div className="w-full break-words font-medium text-sm leading-[18px] text-[var(--foreground)]">
                          {row.label}
                        </div>
                      ) : (
                        <Badge tone={TONE[row.category] ?? "neutral"}>{row.label}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="align-top">
                      <span className="flex flex-wrap items-center gap-1">
                        {row.caseIds.map((id) => (
                          <CaseChip key={id} caseId={id} />
                        ))}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-0 overflow-hidden align-top">
                      <div className="w-full break-words text-xs leading-[18px] text-[var(--muted-foreground)]">
                        {row.note.trim() ? row.note : t("failureSynthesis.noRootCause")}
                      </div>
                    </TableCell>
                    <TableCell className="max-w-0 overflow-hidden align-top">
                      <div className="w-full break-words text-xs leading-[18px] text-[var(--muted-foreground)]">
                        {row.fix}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {/* The remedy is said ONCE. It used to be printed in every empty root-cause cell —
                six identical parentheses in one column read as noise, not as an instruction. */}
            {rows.some((row) => !row.note.trim()) ? (
              <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                {t("failureSynthesis.noRootCauseHint", {
                  count: rows.filter((row) => !row.note.trim()).length,
                })}
              </p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
