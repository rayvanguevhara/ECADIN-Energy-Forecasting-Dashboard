import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, KpiCard } from "@/components/panel";
import {
  DATASET_INFO,
  FORECAST_START,
  PROVINCE_DATA,
  QUALITY_FLAGS_HIGHLIGHTS,
  QUALITY_FLAGS_SUMMARY,
  QUALITY_FLAGS_TOTAL,
  YEARS,
  attentionLabel,
  fmt,
  modelDisplayName,
  qualityLabel,
  type QualityLevel,
} from "@/lib/energy-data";
import { AlertTriangle, ShieldCheck, CircleHelp, Database } from "lucide-react";
import { useMemo, useState } from "react";

const PERIOD_START = DATASET_INFO.period[0];
const FORECAST_END = DATASET_INFO.period[1];

type FlagFilter =
  | "all"
  | "supply_2021"
  | "demand_anomalies"
  | "national_mismatch"
  | "missing_source_value";

export const Route = createFileRoute("/quality")({
  head: () => ({
    meta: [
      { title: "Data Quality · ECADIN Energy Intelligence" },
      {
        name: "description",
        content: `Coverage, matrix treatment, and ${QUALITY_FLAGS_TOTAL} structured BPS/ESDM source audit flags in the ${DATASET_INFO.regionCount}-region ECADIN dashboard dataset.`,
      },
    ],
  }),
  component: QualityPage,
});

function QualityPage() {
  const [flagFilter, setFlagFilter] = useState<FlagFilter>("all");

  const cells = PROVINCE_DATA.flatMap((region) =>
    region.series.map((point) => ({ region, point })),
  );

  const counts = {
    observed: cells.filter(({ point }) => point.quality === "observed").length,
    interpolated: cells.filter(({ point }) => point.quality === "interpolated")
      .length,
    forecast: cells.filter(({ point }) => point.quality === "forecast").length,
    incomplete: cells.filter(({ point }) => point.quality === "incomplete")
      .length,
  };

  const filteredHighlights = useMemo(() => {
    switch (flagFilter) {
      case "supply_2021":
        return QUALITY_FLAGS_HIGHLIGHTS.filter(
          (row) =>
            row.dataset_id === "supply_local_generation" &&
            (row.year === 2021 || row.issue_type === "large_zero_base_jump"),
        );
      case "demand_anomalies":
        return QUALITY_FLAGS_HIGHLIGHTS.filter((row) =>
          row.dataset_id.startsWith("demand_"),
        );
      case "national_mismatch":
        return QUALITY_FLAGS_HIGHLIGHTS.filter(
          (row) => row.issue_type === "national_total_mismatch",
        );
      case "missing_source_value":
        return QUALITY_FLAGS_HIGHLIGHTS.filter(
          (row) => row.issue_type === "missing_source_value",
        );
      default:
        return QUALITY_FLAGS_HIGHLIGHTS;
    }
  }, [flagFilter]);

  const demandModelName = modelDisplayName(undefined, "demand");
  const supplyModelName = modelDisplayName(undefined, "supply");

  return (
    <AppShell
      title="Data Quality"
      subtitle={`Coverage, missing-value treatment, and ${QUALITY_FLAGS_TOTAL} structured BPS/ESDM source audit flags`}
    >
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard
            label="Observed Complete Pairs"
            value={counts.observed.toLocaleString()}
            tone="up"
            icon={<ShieldCheck className="h-4 w-4" />}
          />
          <KpiCard
            label="Interpolated Historical Pairs"
            value={counts.interpolated.toLocaleString()}
            tone="warn"
            icon={<CircleHelp className="h-4 w-4" />}
          />
          <KpiCard
            label="Forecast Complete Pairs"
            value={counts.forecast.toLocaleString()}
            icon={<Database className="h-4 w-4" />}
          />
          <KpiCard
            label="Incomplete Historical Pairs"
            value={counts.incomplete.toLocaleString()}
            tone="down"
            icon={<AlertTriangle className="h-4 w-4" />}
          />
        </div>

        <Panel
          title="Data Quality Matrix"
          subtitle={`${DATASET_INFO.regionCount} harmonized regions × ${PERIOD_START}–${FORECAST_END} · unavailable historical pairs remain missing and are never converted to zero`}
        >
          <div className="max-h-[70vh] overflow-auto rounded-md border border-border/60">
            <table className="min-w-[1200px] border-collapse text-[10px]">
              <thead>
                <tr>
                  <th className="sticky left-0 top-0 z-30 min-w-[190px] bg-card p-2 text-left text-muted-foreground shadow-[1px_0_0_var(--border)]">
                    Harmonized Region
                  </th>
                  {YEARS.map((year) => {
                    const isForecastYear = year >= FORECAST_START;

                    return (
                      <th
                        key={year}
                        className={`sticky top-0 z-20 min-w-[44px] border-b border-border p-1 text-center font-medium ${
                          isForecastYear
                            ? "text-primary"
                            : "bg-card text-muted-foreground"
                        }`}
                        style={
                          isForecastYear
                            ? {
                                backgroundColor:
                                  "color-mix(in srgb, var(--primary) 8%, var(--card))",
                              }
                            : undefined
                        }
                      >
                        {year}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {PROVINCE_DATA.map((region) => (
                  <tr key={region.code} className="hover:bg-muted/20">
                    <td className="sticky left-0 z-10 whitespace-nowrap bg-card p-2 pr-4 text-left font-medium shadow-[1px_0_0_var(--border)]">
                      {region.name}
                    </td>
                    {region.series.map((point) => (
                      <td
                        key={point.year}
                        className={`p-0.5 ${point.year >= FORECAST_START ? "bg-primary/[0.035]" : ""}`}
                      >
                        <div
                          title={`${region.name} · ${point.year} · ${qualityLabel(point.quality)}${
                            point.attentionReason
                              ? ` · ${attentionLabel(point.attentionReason)}`
                              : ""
                          }`}
                          className="mx-auto h-4 w-4 rounded-sm"
                          style={{
                            background: colorFor(point.quality),
                            opacity: point.quality === "forecast" ? 0.82 : 0.94,
                            outline:
                              point.quality === "interpolated"
                                ? "1px dashed var(--foreground)"
                                : "none",
                            outlineOffset: "-2px",
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-3 flex flex-wrap gap-4 text-[11px] text-muted-foreground">
            <LegendChip
              color="var(--surplus-high)"
              label="Observed complete pair"
            />
            <LegendChip
              color="var(--deficit-mod)"
              label="Interpolated historical pair"
              dashed
            />
            <LegendChip
              color="var(--chart-demand)"
              label="Production forecast pair"
            />
            <LegendChip
              color="var(--deficit-high)"
              label="Incomplete distributed-electricity/local-generation pair"
            />
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel title="Historical Treatment">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Nine historical distributed-electricity and local-generation pairs
              remain incomplete: DI Yogyakarta in 2011–2014 and 2020, plus
              Kalimantan Timur and Kalimantan Utara in 2011–2012. These cells
              remain missing and are never converted to zero. The 2016
              historical pairs contain audited interpolation and are identified
              separately.
            </p>
          </Panel>

          <Panel title="Forecast Treatment">
            <p className="text-xs leading-relaxed text-muted-foreground">
              All {DATASET_INFO.regionCount * (FORECAST_END - FORECAST_START + 1)}{" "}
              forecast region-year pairs for {FORECAST_START}–{FORECAST_END} are
              complete. Distributed electricity uses{" "}
              <strong className="text-foreground">{demandModelName}</strong>,
              while local generation uses{" "}
              <strong className="text-foreground">{supplyModelName}</strong>.
              Forecast values are kept separate from observed and interpolated
              historical values, and regional uncertainty intervals are not
              published.
            </p>
          </Panel>
        </div>

        <Panel
          title={`Source Data Quality Audit Flags (${QUALITY_FLAGS_TOTAL} Total Rows)`}
          subtitle="Aggregated summary from canonical data_quality_flags.csv across 5 BPS datasets (104 missing 2016 year rows + 87 non-2016 warning/missing-cell audit flags)"
        >
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[700px] text-xs">
              <thead className="bg-background/50 text-[10px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="p-2 text-left">Dataset ID</th>
                  <th className="p-2 text-left">Issue Type</th>
                  <th className="p-2 text-left">Status</th>
                  <th className="p-2 text-right">Flag Count</th>
                  <th className="p-2 text-right">Year Span</th>
                  <th className="p-2 text-right">Affected Regions</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {QUALITY_FLAGS_SUMMARY.map((row, idx) => (
                  <tr
                    key={`${row.dataset_id}-${row.issue_type}-${idx}`}
                    className="border-t border-border"
                  >
                    <td className="p-2 font-mono text-[11px]">
                      {row.dataset_id}
                    </td>
                    <td className="p-2 font-mono text-[11px]">
                      {row.issue_type}
                    </td>
                    <td className="p-2 text-muted-foreground">
                      {row.quality_status}
                    </td>
                    <td className="p-2 text-right font-medium">
                      {row.flag_count}
                    </td>
                    <td className="p-2 text-right text-muted-foreground">
                      {row.first_year == null
                        ? "N/A"
                        : row.first_year === row.last_year
                          ? String(row.first_year)
                          : `${row.first_year}–${row.last_year}`}
                    </td>
                    <td className="p-2 text-right">{row.affected_regions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel
          title={`Highlighted Source Audit Flags (${filteredHighlights.length} Shown · ${QUALITY_FLAGS_HIGHLIGHTS.length} Non-2016 Flags)`}
          subtitle="Includes SR 2021 large_zero_base_jump (0 → 249.45 GWh), 2021 STPL supply shifts, KR 2020 (−73.48% PT PLN Batam), and national total mismatches"
          right={
            <div className="flex flex-wrap gap-1.5">
              {(
                [
                  ["all", `All (${QUALITY_FLAGS_HIGHLIGHTS.length})`],
                  ["supply_2021", "Supply 2021 & SR Jump"],
                  ["demand_anomalies", "Demand (incl. KR 2020)"],
                  ["national_mismatch", "National Mismatches"],
                  ["missing_source_value", "Missing Source Values"],
                ] as const
              ).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFlagFilter(key)}
                  className={`rounded-md border px-2 py-1 text-[10px] font-medium transition-colors ${
                    flagFilter === key
                      ? "border-primary bg-primary/15 text-primary"
                      : "border-border bg-background/40 text-muted-foreground hover:bg-accent"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          }
        >
          <div className="max-h-[420px] overflow-auto rounded-md border border-border">
            <table className="w-full min-w-[920px] text-xs">
              <thead className="sticky top-0 bg-card text-[10px] uppercase tracking-wider text-muted-foreground shadow-[0_1px_0_var(--border)]">
                <tr>
                  <th className="p-2 text-left">Dataset</th>
                  <th className="p-2 text-left">Region</th>
                  <th className="p-2 text-right">Year</th>
                  <th className="p-2 text-left">Issue Type</th>
                  <th className="p-2 text-right">Observed</th>
                  <th className="p-2 text-right">Comparison</th>
                  <th className="p-2 text-right">Metric / Δ</th>
                  <th className="p-2 text-left">Audit Note</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {filteredHighlights.map((item, idx) => (
                  <tr
                    key={`${item.dataset_id}-${item.region_id ?? "NAT"}-${item.year ?? idx}-${idx}`}
                    className="border-t border-border"
                  >
                    <td className="p-2 font-mono text-[11px]">
                      {item.dataset_id}
                    </td>
                    <td className="p-2">
                      {item.display_name ? (
                        <span>
                          {item.display_name}{" "}
                          <span className="font-mono text-[10px] text-muted-foreground">
                            ({item.region_id})
                          </span>
                        </span>
                      ) : (
                        <span className="text-muted-foreground">
                          Indonesia Total
                        </span>
                      )}
                    </td>
                    <td className="p-2 text-right">{item.year ?? "N/A"}</td>
                    <td className="p-2 font-mono text-[11px]">
                      {item.issue_type}
                    </td>
                    <td className="p-2 text-right">
                      {item.observed_value != null
                        ? fmt(item.observed_value)
                        : "—"}
                    </td>
                    <td className="p-2 text-right text-muted-foreground">
                      {item.comparison_value != null
                        ? fmt(item.comparison_value)
                        : "—"}
                    </td>
                    <td className="p-2 text-right font-medium">
                      {item.metric_value != null
                        ? item.issue_type === "large_consecutive_yoy_change"
                          ? `${item.metric_value > 0 ? "+" : ""}${item.metric_value.toFixed(2)}%`
                          : fmt(item.metric_value)
                        : "—"}
                    </td>
                    <td className="p-2 text-muted-foreground">{item.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        <Panel title="Dataset Coverage Summary">
          <dl className="grid gap-3 text-xs md:grid-cols-4">
            <CoverageItem
              label="Region-Year Pairs"
              value={DATASET_INFO.rowCount.toLocaleString()}
            />
            <CoverageItem
              label="Harmonized Regions"
              value={String(DATASET_INFO.regionCount)}
            />
            <CoverageItem
              label="Complete Pairs"
              value={DATASET_INFO.completeGapCount.toLocaleString()}
            />
            <CoverageItem
              label="Incomplete Historical Pairs"
              value={String(DATASET_INFO.historicalIncompleteGapCount)}
            />
          </dl>
        </Panel>
      </div>
    </AppShell>
  );
}

function colorFor(quality: QualityLevel): string {
  switch (quality) {
    case "observed":
      return "var(--surplus-high)";
    case "interpolated":
      return "var(--deficit-mod)";
    case "forecast":
      return "var(--chart-demand)";
    case "incomplete":
      return "var(--deficit-high)";
  }
}

function LegendChip({
  color,
  label,
  dashed = false,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="h-3 w-3 rounded-sm"
        style={{
          background: color,
          outline: dashed ? "1px dashed var(--foreground)" : "none",
          outlineOffset: "-2px",
        }}
      />
      {label}
    </span>
  );
}

function CoverageItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <dt className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 font-display text-base font-semibold tabular-nums">
        {value}
      </dd>
    </div>
  );
}
