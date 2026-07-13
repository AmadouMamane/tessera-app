/**
 * What the catalogue MEASURES — the tile the pass rate cannot replace.
 *
 * Every other number on this screen answers "how well did the model do". This one answers the
 * question underneath it: **does this bench test the model at all?** It has to be asked,
 * because three measurements say that mostly it does not — the null control (no model, zero
 * tokens) already passes 122 of the 174 runs, fifteen cases pass with an EMPTY answer, and a
 * 1B model scores indistinguishably from a 3B.
 *
 * The classes are derived from repeated passes of a strong and a weak model against the null
 * floor (`eval/discrimination.py`); no case declares its own power. The counts are read off the
 * committed measurement, never recomputed here — a second implementation of the arithmetic is a
 * second answer waiting to disagree with the first.
 *
 * When it cannot be said, the tile says WHY. A tile that renders nothing is indistinguishable
 * from a catalogue with no discriminating power at all, and those are opposite facts.
 */
import { AlertTriangle, FlaskConical, Info } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { CataloguePowerState } from "@/lib/eval-sweep";

export async function CataloguePowerCard({
  state,
  locale,
}: {
  state: CataloguePowerState;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  if (state.kind === "not-measured") {
    return (
      <Card>
        <CardContent className="flex flex-col gap-2 p-5">
          <Header title={t("power.title")} />
          <Note tone="neutral">{t("power.notMeasured")}</Note>
        </CardContent>
      </Card>
    );
  }

  if (state.kind === "unreadable") {
    // The artefact is THERE and this code cannot read it. Saying "not measured yet" would be a
    // witness reporting its own ignorance as a property of the world.
    return (
      <Card>
        <CardContent className="flex flex-col gap-2 p-5">
          <Header title={t("power.title")} />
          <Note tone="warning">{t("power.unreadable", { reason: state.reason })}</Note>
        </CardContent>
      </Card>
    );
  }

  if (state.kind === "off-referential") {
    // A refusal, not a zero. The classification describes cases that no longer exist, so its
    // counts are VOID — printing them next to the current catalogue would be a lie with a
    // plausible shape.
    return (
      <Card>
        <CardContent className="flex flex-col gap-2 p-5">
          <Header title={t("power.title")} />
          <Note tone="warning">
            {t("power.offReferential", {
              measured: state.measuredOn,
              current: state.current,
            })}
          </Note>
        </CardContent>
      </Card>
    );
  }

  const {
    power,
    case_counts,
    catalogue_version,
    strong_model,
    weak_model,
    strong_n,
    weak_n,
    detection_power,
  } = state.power;
  const measured = power.discriminating_cases;

  // The design's detection floor. When it is absent, the experiment could not have rejected the
  // null WHATEVER it observed — and then not one of the counts below may be read as "no effect".
  const blind = "blind_spot" in detection_power;
  const mde = blind ? null : detection_power.minimum_detectable_effect;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <Header title={t("power.title")} />
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="navy" className="font-mono">
              {catalogue_version}
            </Badge>
            <Badge tone="neutral" className="font-mono">
              {t("power.sample", { strong: strong_model, weak: weak_model, n: strong_n + weak_n })}
            </Badge>
          </div>
        </div>

        {/* THE THREE BUCKETS, and they do not share a bucket. Over CASES. */}
        <dl className="grid gap-2 sm:grid-cols-3">
          <Bucket
            label={t("power.bucket.fact")}
            n={
              case_counts.dead +
              case_counts.inverted +
              case_counts.saturated +
              case_counts.unreached
            }
            detail={t("power.bucket.factDetail", {
              dead: case_counts.dead,
              inverted: case_counts.inverted,
              saturated: case_counts.saturated,
              unreached: case_counts.unreached,
            })}
          />
          <Bucket
            label={t("power.bucket.certified")}
            n={case_counts.discriminating + case_counts.reversed}
            detail={t("power.bucket.certifiedDetail", {
              discriminating: case_counts.discriminating,
              reversed: case_counts.reversed,
            })}
            tone="gold"
          />
          <Bucket
            label={t("power.bucket.cannotSay")}
            n={case_counts.underpowered}
            detail={
              mde === null
                ? t("power.bucket.cannotSayNoPower")
                : t("power.bucket.cannotSayDetail", { mde })
            }
          />
        </dl>

        {/* The headline. Everything above is arithmetic; this is the finding. */}
        <p className="font-semibold text-base">
          {t("power.headline", { measured, total: power.total_cases })}
        </p>

        {/* The number that licenses every "does not separate" above it. Never omitted: a count of
            non-discriminating cases with no detection floor beside it is a claim with no power. */}
        <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
          {mde === null
            ? t("power.noPower", {
                blindSpot: (detection_power as { blind_spot: string }).blind_spot,
              })
            : t("power.mde", { mde, strongN: strong_n, weakN: weak_n })}
        </p>

        <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
          {t("power.corrections", {
            holm: power.holm_runs,
            bh: power.bh_runs,
            gap: power.correction_gap.length,
          })}
        </p>

        <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
          {t("power.method", { strongN: strong_n, weakN: weak_n })}
        </p>

        {measured * 2 < power.total_cases ? <Note tone="warning">{t("power.warning")}</Note> : null}
      </CardContent>
    </Card>
  );
}

/** One of the three buckets. The count is large; the composition is small and never hidden. */
function Bucket({
  label,
  n,
  detail,
  tone,
}: {
  label: string;
  n: number;
  detail: string;
  tone?: "gold";
}) {
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--muted)] p-3">
      <dt className="font-medium text-[var(--muted-foreground)] text-xs uppercase tracking-wide">
        {label}
      </dt>
      <dd
        className={`font-semibold text-lg tabular-nums ${
          tone === "gold" ? "text-gold-700 dark:text-gold-400" : ""
        }`}
      >
        {n}
      </dd>
      <dd className="text-[var(--muted-foreground)] text-xs leading-relaxed">{detail}</dd>
    </div>
  );
}

function Header({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-2">
      <FlaskConical className="h-4 w-4 text-gold-600 dark:text-gold-400" />
      <h2 className="font-semibold text-base">{title}</h2>
    </div>
  );
}

/** Same shape as the sweep header's note — an honest-empty must not look like a new dialect. */
function Note({ children, tone }: { children: React.ReactNode; tone: "warning" | "neutral" }) {
  const Icon = tone === "warning" ? AlertTriangle : Info;
  return (
    <div
      className={`flex items-start gap-2 rounded-md border p-2.5 text-xs leading-relaxed ${
        tone === "warning"
          ? "border-warning-500/30 bg-warning-50 text-warning-800 dark:bg-warning-700/15 dark:text-warning-100"
          : "border-[var(--border)] bg-[var(--muted)] text-[var(--muted-foreground)]"
      }`}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
