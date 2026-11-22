// ECADIN_PHASE3L5_1_REGION_DETAIL_VISUAL_REFINEMENT_V1
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, KpiCard } from "@/components/panel";
import { useFilters } from "@/lib/filter-context";
import {
  DATASET_INFO,
  FORECAST_START,
  GAP_CATEGORY_META,
  PROVINCE_DATA,
  classifyGap,
  fmt,
  formatSignedEnergy,
  formatSignedPercent,
  modelDisplayName,
  qualityLabel,
} from "@/lib/energy-data";
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useEffect, useMemo } from "react";

const PERIOD_START = DATASET_INFO.period[0];
const FORECAST_END = DATASET_INFO.period[1];

export const Route = createFileRoute("/province")({
  head: () => ({
    meta: [
      { title: "Region Detail · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "Historical and production forecast distributed electricity, local generation, and regional accounting differences for a harmonized Indonesian modeling region.",
      },
    ],
  }),
  component: ProvincePage,
});

function ProvincePage() {
  return (
    <AppShell
      title="Region Detail"
      subtitle="Historical and production forecast trajectory of distributed electricity, local generation, and regional accounting differences"
    >
      <Inner />
    </AppShell>
  );
}

function Inner() {
  const { filters, setFilters } = useFilters();

  const fallbackRegion = useMemo(() => {
    if (filters.island !== "All") {
      return (
        PROVINCE_DATA.find((item) => item.island === filters.island) ??
        PROVINCE_DATA.find((item) => item.code === "JB") ??
        PROVINCE_DATA[0]
      );
    }

    return PROVINCE_DATA.find((item) => item.code === "JB") ?? PROVINCE_DATA[0];
  }, [filters.island]);

  const code =
    filters.province === "All" ? fallbackRegion.code : filters.province;

  const region = useMemo(
    () => PROVINCE_DATA.find((item) => item.code === code) ?? fallbackRegion,
    [code, fallbackRegion],
  );

  useEffect(() => {
    if (filters.province === "All" || filters.island !== region.island) {
      setFilters({
        province: region.code,
        island: region.island,
      });
    }
  }, [filters.province, filters.island, region.code, region.island, setFilters]);

  const current =
    region.series.find((point) => point.year === filters.year) ??
    region.series.at(-1)!;

  const category = current.gapCategory ?? classifyGap(current.gap_pct);
  const forecast = region.series.filter(
    (point) => point.year >= FORECAST_START,
  );

  const chartData = useMemo(
    () =>
      region.series.map((point) => ({
        ...point,
        demand_gwh: Number.isFinite(point.demand_gwh) ? point.demand_gwh : null,
        supply_gwh: Number.isFinite(point.supply_gwh) ? point.supply_gwh : null,
        gap_gwh: Number.isFinite(point.gap_gwh) ? point.gap_gwh : null,
        gap_pct: Number.isFinite(point.gap_pct) ? point.gap_pct : null,
        ratio: Number.isFinite(point.ratio) ? point.ratio : null,
      })),
    [region],
  );

  const gapDomain = useMemo<[number, number]>(() => {
    const values = chartData
      .map((point) => point.gap_gwh)
      .filter(
        (value): value is number =>
          typeof value === "number" && Number.isFinite(value),
      );

    if (!values.length) return [-1, 1];

    const minimum = Math.min(0, ...values);
    const maximum = Math.max(0, ...values);
    const spread = Math.max(maximum - minimum, 1);
    const padding = spread * 0.08;

    return [
      minimum < 0 ? minimum - padding : 0,
      maximum > 0 ? maximum + padding : 0,
    ];
  }, [chartData]);

  const missingYears = region.series
    .filter((point) => !point.available)
    .map((point) => point.year);

  const interpolatedYears = region.series
    .filter((point) => point.interpolated)
    .map((point) => point.year);

  const geographyBreakYears = region.series
    .filter((point) =>
      [point.demandValueStatus, point.supplyValueStatus].some((status) =>
        status?.toLowerCase().includes("geography_break"),
      ),
    )
    .map((point) => point.year);

  const perCapita =
    current.population != null &&
    current.population > 0 &&
    Number.isFinite(current.demand_gwh)
      ? (current.demand_gwh * 1_000_000) / current.population
      : Number.NaN;

  const ratioNotice = ratioInterpretation(current.ratio);

  const populationLabel = current.forecast
    ? "Projected Population"
    : "Population";
  const perCapitaLabel = current.forecast
    ? "Projected Distributed Electricity per Capita"
    : "Distributed Electricity per Capita";

  const activeDemandModelName = modelDisplayName(undefined, "demand");
  const activeSupplyModelName = modelDisplayName(undefined, "supply");

  return (
    <div className="space-y-6">
      <div>
        <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
          {region.island} · {DATASET_INFO.regionCount}-region harmonized
          geography
        </div>
        <h2 className="font-display text-2xl font-semibold">{region.name}</h2>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <KpiCard
          label="Distributed Electricity"
          value={fmt(current.demand_gwh)}
          unit="GWh"
        />

        <KpiCard
          label="Local Generation"
          value={fmt(current.supply_gwh)}
          unit="GWh"
        />

        <KpiCard
          label="Regional Accounting Difference"
          value={formatSignedEnergy(current.gap_gwh)}
          unit="GWh"
          tone="neutral"
          delta={`${formatSignedPercent(current.gap_pct)} of distributed electricity`}
        />

        <KpiCard
          label="Local Generation / Distributed Electricity"
          value={
            Number.isFinite(current.ratio)
              ? `${current.ratio.toFixed(2)}×`
              : "N/A"
          }
        />

        <KpiCard
          label="Accounting Category"
          value={GAP_CATEGORY_META[category].shortLabel}
          tone="neutral"
          delta="Distributed electricity comparison"
        />
      </div>

      <Panel title="Interpretation Safeguard">
        <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">
          <p>
            <span className="font-semibold text-foreground">
              Local generation is not total available supply.
            </span>{" "}
            Electricity may enter or leave a region through interconnected
            systems. The regional accounting difference compares where
            electricity is generated with where electricity is distributed; it is
            not an operational adequacy, reserve-margin, shortage, or blackout
            indicator.
          </p>
          {ratioNotice && <p className="text-foreground/90">{ratioNotice}</p>}
        </div>
      </Panel>

      <Panel
        title="Distributed Electricity and Local Generation (GWh)"
        subtitle={`Annual values for ${PERIOD_START}–${FORECAST_END} · straight segments preserve annual observations · forecast horizon is shaded`}
      >
        <div className="h-[320px]">
          <ResponsiveContainer>
            <ComposedChart
              data={chartData}
              margin={{ top: 10, right: 12, bottom: 0, left: -12 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis
                dataKey="year"
                stroke="var(--muted-foreground)"
                fontSize={11}
              />
              <YAxis
                stroke="var(--muted-foreground)"
                fontSize={11}
                tickFormatter={(value) => fmt(value as number)}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--popover)",
                  border: "1px solid var(--border)",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value, name) => [
                  `${fmt(Number(value))} GWh`,
                  String(name ?? ""),
                ]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceArea
                x1={FORECAST_START}
                x2={FORECAST_END}
                fill="var(--chart-gap)"
                fillOpacity={0.06}
                label={{
                  value: "Forecast",
                  fill: "var(--muted-foreground)",
                  fontSize: 10,
                  position: "insideTopRight",
                }}
              />
              <ReferenceLine
                x={filters.year}
                stroke="var(--foreground)"
                strokeDasharray="4 4"
                strokeOpacity={0.55}
              />
              <Line
                type="linear"
                dataKey="demand_gwh"
                stroke="var(--chart-demand)"
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                name="Distributed Electricity"
              />
              <Line
                type="linear"
                dataKey="supply_gwh"
                stroke="var(--chart-supply)"
                strokeWidth={2}
                dot={false}
                connectNulls={false}
                name="Local Generation"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel
          title="Regional Accounting Difference (GWh)"
          subtitle="Local generation minus distributed electricity · positive or negative values are accounting differences, not operational surplus or shortage"
        >
          <div className="h-[270px]">
            <ResponsiveContainer>
              <ComposedChart
                data={chartData}
                margin={{ top: 10, right: 12, bottom: 0, left: -12 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="year"
                  stroke="var(--muted-foreground)"
                  fontSize={11}
                />
                <YAxis
                  domain={gapDomain}
                  stroke="var(--muted-foreground)"
                  fontSize={11}
                  tickFormatter={(value) => fmt(value as number)}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value) => [
                    formatSignedEnergy(Number(value), true),
                    "Accounting Difference",
                  ]}
                />
                <ReferenceArea
                  x1={FORECAST_START}
                  x2={FORECAST_END}
                  fill="var(--chart-gap)"
                  fillOpacity={0.06}
                  label={{
                    value: "Forecast",
                    fill: "var(--muted-foreground)",
                    fontSize: 10,
                    position: "insideTopRight",
                  }}
                />
                <ReferenceLine
                  y={0}
                  stroke="var(--foreground)"
                  strokeOpacity={0.55}
                />
                <ReferenceLine
                  x={filters.year}
                  stroke="var(--foreground)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.45}
                />
                <Bar
                  dataKey="gap_gwh"
                  name="Accounting Difference"
                  radius={[3, 3, 0, 0]}
                >
                  {chartData.map((point) => (
                    <Cell
                      key={point.year}
                      fill={
                        point.year === filters.year
                          ? "var(--chart-demand)"
                          : "var(--chart-gap)"
                      }
                      fillOpacity={point.year === filters.year ? 1 : 0.72}
                      stroke={
                        point.year === filters.year
                          ? "var(--foreground)"
                          : "none"
                      }
                      strokeWidth={point.year === filters.year ? 1 : 0}
                    />
                  ))}
                </Bar>
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title={`Forecast ${FORECAST_START}–${FORECAST_END}`}
          subtitle={`All electricity values are in GWh · Distributed electricity model: ${activeDemandModelName} · Local generation model: ${activeSupplyModelName}`}
        >
          <div className="rounded-md border border-border">
            <table className="w-full table-fixed text-xs">
              <thead className="bg-background/50 text-[9px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="w-[12%] p-2 text-left">Year</th>
                  <th className="w-[21%] p-2 text-right">Distributed</th>
                  <th className="w-[23%] p-2 text-right">Local Generation</th>
                  <th className="w-[25%] p-2 text-right">Difference</th>
                  <th className="w-[19%] p-2 text-right">Difference %</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {forecast.map((point) => (
                  <tr key={point.year} className="border-t border-border">
                    <td className="p-2">{point.year}</td>
                    <td className="p-2 text-right">{fmt(point.demand_gwh)}</td>
                    <td className="p-2 text-right">{fmt(point.supply_gwh)}</td>
                    <td className="p-2 text-right text-foreground">
                      {formatSignedEnergy(point.gap_gwh)}
                    </td>
                    <td className="p-2 text-right">
                      {formatSignedPercent(point.gap_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Panel title="Historical Availability and Geography Notes">
        <div className="grid gap-3 text-xs leading-relaxed text-muted-foreground md:grid-cols-3">
          <AvailabilityItem
            label="Missing Historical Years"
            value={formatYears(missingYears)}
            note="Missing historical values remain blank and are never converted to zero."
          />
          <AvailabilityItem
            label="Interpolated Target Years"
            value={formatYears(interpolatedYears)}
            note="Interpolated targets support continuity and are explicitly identified as interpolated."
          />
          <AvailabilityItem
            label="Excluded Geography-Break Years"
            value={formatYears(geographyBreakYears)}
            note="These years are excluded when historical administrative geography is not comparable."
          />
        </div>
      </Panel>

      <Panel title="Region Profile">
        <dl className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
          <ProfileStat label="Island Group" value={region.island} />
          <ProfileStat
            label="Model Geography"
            value={`${DATASET_INFO.regionCount} harmonized regions`}
          />
          <ProfileStat
            label={populationLabel}
            value={
              current.population == null
                ? "N/A for this year"
                : `${fmt(current.population / 1_000_000)} M people`
            }
          />
          <ProfileStat
            label={perCapitaLabel}
            value={Number.isFinite(perCapita) ? `${fmt(perCapita)} kWh` : "N/A"}
          />
          <ProfileStat label="Data Status" value={qualityLabel(current.quality)} />
          <ProfileStat
            label="Distributed-Electricity Status"
            value={statusLabel(current.demandValueStatus)}
          />
          <ProfileStat
            label="Local-Generation Status"
            value={statusLabel(current.supplyValueStatus)}
          />
          <ProfileStat
            label={current.forecast ? "Forecast Models" : "Data Source"}
            value={
              current.forecast
                ? `Demand · ${modelDisplayName(current.demandModel, "demand")} / Generation · ${modelDisplayName(
                    current.supplyModel,
                    "supply",
                  )}`
                : "Historical harmonized panel"
            }
          />
        </dl>
      </Panel>

      {!current.available && (
        <Panel title="Data Availability Notice">
          <p className="text-sm leading-relaxed text-muted-foreground">
            The complete distributed-electricity and local-generation pair is
            unavailable for {region.name} in {current.year}. The dashboard
            preserves this value as missing and does not replace it with zero.
          </p>
        </Panel>
      )}
    </div>
  );
}

function formatYears(years: number[]): string {
  return years.length ? years.join(", ") : "None";
}

function statusLabel(value: string | null | undefined): string {
  if (!value) return "N/A";

  return value
    .replaceAll("_", " ")
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function ratioInterpretation(ratio: number): string | null {
  if (!Number.isFinite(ratio)) return null;

  if (ratio < 0.05) {
    return "The local-generation ratio is extremely small. This usually reflects that electricity is generated elsewhere in the interconnected system, not that the region receives almost no electricity.";
  }

  if (ratio > 2) {
    return "The local-generation ratio is very high. This indicates that the administrative location of generation differs from the location of distributed electricity; it does not mean that the full accounting difference is idle capacity.";
  }

  return null;
}

function AvailabilityItem({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-mono text-sm text-foreground">{value}</div>
      <p className="mt-2">{note}</p>
    </div>
  );
}

function ProfileStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background/40 p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-display text-sm font-semibold">{value}</div>
    </div>
  );
}
