import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, KpiCard } from "@/components/panel";
import {
  DATASET_INFO,
  PROVINCE_DATA,
  YEARS,
  qualityLabel,
  type QualityLevel,
} from "@/lib/energy-data";
import { AlertTriangle, ShieldCheck, CircleHelp, Database } from "lucide-react";

export const Route = createFileRoute("/quality")({
  head: () => ({
    meta: [
      { title: "Data Quality · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "Coverage and treatment of observed, interpolated, production-forecast, and incomplete region-year pairs in the 34-region ECADIN dashboard dataset.",
      },
    ],
  }),
  component: QualityPage,
});

function QualityPage() {
  const cells = PROVINCE_DATA.flatMap((region) =>
    region.series.map((point) => ({ region, point })),
  );

  const counts = {
    observed: cells.filter(({ point }) => point.quality === "observed").length,
    interpolated: cells.filter(({ point }) => point.quality === "interpolated").length,
    forecast: cells.filter(({ point }) => point.quality === "forecast").length,
    incomplete: cells.filter(({ point }) => point.quality === "incomplete").length,
  };

  return (
    <AppShell
      title="Data Quality"
      subtitle="Coverage and treatment of observed, interpolated, forecast, and incomplete region-year pairs"
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
          subtitle="34 harmonized regions × 2011–2030 · unavailable historical pairs remain missing and are never converted to zero"
        >
          <div className="max-h-[70vh] overflow-auto rounded-md border border-border/60">
            <table className="min-w-[1200px] border-collapse text-[10px]">
              <thead>
                <tr>
                  <th className="sticky left-0 top-0 z-30 min-w-[190px] bg-card p-2 text-left text-muted-foreground shadow-[1px_0_0_var(--border)]">
                    Harmonized Region
                  </th>
                  {YEARS.map((year) => {
                    const isForecastYear = year >= 2025;

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
                        className={`p-0.5 ${point.year >= 2025 ? "bg-primary/[0.035]" : ""}`}
                      >
                        <div
                          title={`${region.name} · ${point.year} · ${qualityLabel(point.quality)}${
                            point.attentionReason ? ` · ${point.attentionReason}` : ""
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
            <LegendChip color="var(--surplus-high)" label="Observed complete pair" />
            <LegendChip
              color="var(--deficit-mod)"
              label="Interpolated historical pair"
              dashed
            />
            <LegendChip color="var(--chart-demand)" label="Production forecast pair" />
            <LegendChip
              color="var(--deficit-high)"
              label="Incomplete distributed-electricity/local-generation pair"
            />
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel title="Historical Treatment">
            <p className="text-xs leading-relaxed text-muted-foreground">
              Nine historical distributed-electricity and local-generation pairs remain
              incomplete: DI Yogyakarta in 2011–2014 and 2020, plus Kalimantan Timur and
              Kalimantan Utara in 2011–2012. These cells remain missing and are never converted
              to zero. The 2016 historical pairs contain audited interpolation and are identified
              separately.
            </p>
          </Panel>

          <Panel title="Forecast Treatment">
            <p className="text-xs leading-relaxed text-muted-foreground">
              All 204 forecast region-year pairs for 2025–2030 are complete. Distributed
              electricity uses the production Drift model, while local generation uses Drift V1.
              Forecast values are kept separate from observed and interpolated historical values,
              and regional uncertainty intervals are not published.
            </p>
          </Panel>
        </div>

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
      <dt className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-display text-base font-semibold tabular-nums">{value}</dd>
    </div>
  );
}
