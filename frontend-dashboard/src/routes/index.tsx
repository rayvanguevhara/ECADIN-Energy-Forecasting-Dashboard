import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { KpiCard, Panel } from "@/components/panel";
import { useFilters } from "@/lib/filter-context";
import {
  DATASET_INFO,
  FORECAST_START,
  GAP_CATEGORY_META,
  GAP_CATEGORY_ORDER,
  NationalPoint,
  PROVINCE_DATA,
  classifyGap,
  fmt,
  formatSignedEnergy,
  formatSignedPercent,
  nationalSeries,
} from "@/lib/energy-data";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Gauge,
  Scale,
  Zap,
} from "lucide-react";
import { useMemo } from "react";

const PERIOD_START = DATASET_INFO.period[0];
const FORECAST_END = DATASET_INFO.period[1];

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "National Overview · ECADIN Energy Intelligence" },
      {
        name: "description",
        content: `National electricity demand, local generation, and accounting gap for Indonesia, ${PERIOD_START}–${FORECAST_END}.`,
      },
    ],
  }),
  component: NationalOverview,
});

function NationalOverview() {
  return (
    <AppShell
      title="National Overview"
      subtitle={`Indonesia national electricity demand, local generation, and accounting gap · ${PERIOD_START}–${FORECAST_END}`}
    >
      <Inner />
    </AppShell>
  );
}

type ChartTooltipPayloadItem = {
  name?: string | number;
  value?: unknown;
  color?: string;
  dataKey?: string | number;
  payload?: NationalPoint & {
    demandYoy?: number | null;
    supplyYoy?: number | null;
  };
};

function NationalLevelTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: readonly ChartTooltipPayloadItem[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  return (
    <div className="rounded-md border border-border bg-popover/95 p-3 text-xs shadow-lg backdrop-blur">
      <div className="font-display font-semibold text-foreground">
        {label} {point?.forecast ? "· Production Forecast" : "· Historical"}
      </div>
      <div className="mt-1.5 space-y-1 tabular-nums">
        {payload.map((entry, idx) => {
          const val = Number(entry.value);
          return (
            <div key={idx} className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">{entry.name}</span>
              <span className="font-medium text-foreground">
                {Number.isFinite(val) ? `${fmt(val)} GWh` : "N/A"}
              </span>
            </div>
          );
        })}
      </div>
      {point && (
        <div className="mt-2 border-t border-border pt-1.5 text-[10px] text-muted-foreground">
          Coverage: {point.completeRegions}/{point.totalRegions} complete regions (
          {point.dataCompleteness === "partial_overlap"
            ? "partial overlap"
            : "complete"}
          )
        </div>
      )}
    </div>
  );
}

function NationalYoyTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: readonly ChartTooltipPayloadItem[];
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload;
  const basisLabel =
    point?.yoyBasis === "first_year"
      ? "First historical year (no prior year)"
      : point?.yoyBasis === "partial_overlap_matched"
        ? `Partial-overlap matched intersection (${point.yoyCommonRegions ?? "N/A"}/${point.totalRegions} regions)`
        : `Complete matched regions (${point?.yoyCommonRegions ?? "N/A"}/${point?.totalRegions ?? DATASET_INFO.regionCount} regions)`;

  return (
    <div className="rounded-md border border-border bg-popover/95 p-3 text-xs shadow-lg backdrop-blur">
      <div className="font-display font-semibold text-foreground">
        {label} {point?.forecast ? "· Forecast" : "· Historical"}
      </div>
      <div className="mt-1.5 space-y-1 tabular-nums">
        {payload.map((entry, idx) => {
          const val = entry.value == null ? Number.NaN : Number(entry.value);
          return (
            <div key={idx} className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">{entry.name}</span>
              <span className="font-medium text-foreground">
                {Number.isFinite(val) ? formatSignedPercent(val, 2) : "N/A"}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-2 border-t border-border pt-1.5 text-[10px] text-muted-foreground">
        {basisLabel}
      </div>
    </div>
  );
}

function renderPartialOverlapDot(color: string, mode: "level" | "yoy") {
  return (props: {
    cx?: number;
    cy?: number;
    index?: number;
    payload?: {
      completeRegions?: number;
      totalRegions?: number;
      dataCompleteness?: string;
      yoyBasis?: string;
    };
  }) => {
    const isPartial =
      mode === "level"
        ? props.payload?.dataCompleteness === "partial_overlap" ||
          (props.payload?.completeRegions != null &&
            props.payload?.totalRegions != null &&
            props.payload.completeRegions < props.payload.totalRegions)
        : props.payload?.yoyBasis === "partial_overlap_matched";
    if (!isPartial || props.cx == null || props.cy == null) {
      return (
        <circle
          key={`empty-dot-${props.index ?? 0}`}
          cx={0}
          cy={0}
          r={0}
          fill="none"
        />
      );
    }
    return (
      <circle
        key={`partial-dot-${props.index ?? 0}`}
        cx={props.cx}
        cy={props.cy}
        r={3.5}
        fill="var(--card)"
        stroke={color}
        strokeWidth={1.8}
      />
    );
  };
}

function Inner() {
  const { filters } = useFilters();
  const series = useMemo(() => nationalSeries(), []);
  const current =
    series.find((point) => point.year === filters.year) ?? series.at(-1)!;

  const regionsThisYear = PROVINCE_DATA.map((region) => {
    const point = region.series.find((item) => item.year === filters.year)!;
    return {
      region,
      point,
      category: point.gapCategory ?? classifyGap(point.gap_pct),
    };
  });

  const regionsBelowDemand = regionsThisYear.filter(
    ({ category }) =>
      category === "di_bawah_demand" || category === "jauh_di_bawah_demand",
  ).length;
  const regionsAboveDemand = regionsThisYear.filter(
    ({ category }) =>
      category === "di_atas_demand" || category === "jauh_di_atas_demand",
  ).length;
  const regionsRelativelyBalanced = regionsThisYear.filter(
    ({ category }) => category === "relatif_seimbang",
  ).length;
  const regionsUnavailable = regionsThisYear.filter(
    ({ category }) => category === "tidak_tersedia",
  ).length;

  const yoyChartData = useMemo(
    () =>
      series.map((point) => ({
        ...point,
        demandYoy: Number.isFinite(point.demandGrowthYoyPercent)
          ? point.demandGrowthYoyPercent
          : null,
        supplyYoy: Number.isFinite(point.supplyGrowthYoyPercent)
          ? point.supplyGrowthYoyPercent
          : null,
      })),
    [series],
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <KpiCard
          label="National Demand"
          value={fmt(current.demand_gwh)}
          unit="GWh"
          icon={<Activity className="h-4 w-4" />}
        />
        <KpiCard
          label="National Local Generation"
          value={fmt(current.supply_gwh)}
          unit="GWh"
          icon={<Zap className="h-4 w-4" />}
        />
        <KpiCard
          label="National Accounting Gap"
          value={formatSignedEnergy(current.gap_gwh)}
          unit="GWh"
          tone="neutral"
          delta={`${formatSignedPercent(current.gap_pct, 2)} of demand`}
          icon={<Scale className="h-4 w-4" />}
        />
        <KpiCard
          label="Local Generation / Demand"
          value={`${current.ratio.toFixed(2)}×`}
          icon={<Gauge className="h-4 w-4" />}
        />
        <KpiCard
          label="Regions Below Demand"
          value={String(regionsBelowDemand)}
          tone="neutral"
          delta="Spatial accounting below 5%"
          icon={<ArrowDownRight className="h-4 w-4" />}
        />
        <KpiCard
          label="Regions Above Demand"
          value={String(regionsAboveDemand)}
          tone="neutral"
          delta="Spatial accounting above 5%"
          icon={<ArrowUpRight className="h-4 w-4" />}
        />
      </div>

      <p className="-mt-2 text-right text-xs text-muted-foreground">
        {regionsRelativelyBalanced}{" "}
        {regionsRelativelyBalanced === 1 ? "region is" : "regions are"}{" "}
        relatively balanced and {regionsUnavailable}{" "}
        {regionsUnavailable === 1 ? "is" : "are"} unavailable in {current.year} (
        {DATASET_INFO.regionCount} total regions).
      </p>

      <Panel title="How to Interpret the National Figures">
        <p className="text-sm leading-relaxed text-muted-foreground">
          <span className="font-semibold text-foreground">
            Local generation is not total available supply.
          </span>{" "}
          National demand and local generation are aggregates across the{" "}
          {DATASET_INFO.regionCount} harmonized regions. The accounting gap is
          local generation minus electricity distributed to customers. It does
          not measure reserve margin, operational adequacy, shortage risk, or
          blackout probability because power-system flows and operational
          capacity are not included.
        </p>
      </Panel>

      <Panel
        title={`National Demand and Local Generation (GWh) · ${PERIOD_START}–${FORECAST_END}`}
        subtitle={`Forecast horizon is shaded · hollow markers denote partial-overlap years · ${current.completeRegions}/${current.totalRegions} complete regions in ${current.year}`}
      >
        <div className="h-[300px]">
          <ResponsiveContainer>
            <LineChart
              data={series}
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
              <Tooltip content={<NationalLevelTooltip />} />
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
                dot={renderPartialOverlapDot("var(--chart-demand)", "level")}
                name="Demand"
              />
              <Line
                type="linear"
                dataKey="supply_gwh"
                stroke="var(--chart-supply)"
                strokeWidth={2}
                dot={renderPartialOverlapDot("var(--chart-supply)", "level")}
                name="Local Generation"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel
        title={`National Accounting Gap · ${PERIOD_START}–${FORECAST_END}`}
        subtitle="Local generation minus demand (GWh). Bars above or below zero are accounting differences, not operational surplus or shortage."
      >
        <div className="h-[220px]">
          <ResponsiveContainer>
            <BarChart
              data={series}
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
              <Tooltip content={<NationalLevelTooltip />} />
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
                stroke="var(--muted-foreground)"
                strokeWidth={1}
              />
              <Bar dataKey="gap_gwh" name="Accounting Gap" radius={[3, 3, 0, 0]}>
                {series.map((point) => (
                  <Cell
                    key={point.year}
                    fill={
                      point.year === filters.year
                        ? "var(--chart-demand)"
                        : point.dataCompleteness === "partial_overlap"
                          ? "#94A3B8"
                          : "var(--chart-gap)"
                    }
                    fillOpacity={point.year === filters.year ? 1 : 0.78}
                    stroke={
                      point.year === filters.year
                        ? "var(--foreground)"
                        : "none"
                    }
                    strokeWidth={point.year === filters.year ? 1 : 0}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel
          title="National Year-over-Year Growth (Matched Regions)"
          subtitle="Demand & local generation YoY on matched complete-region intersections · hollow markers mark partial-overlap years"
        >
          <div className="h-[240px]">
            <ResponsiveContainer>
              <LineChart
                data={yoyChartData}
                margin={{ top: 10, right: 12, bottom: 0, left: -20 }}
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
                  tickFormatter={(value) => `${value}%`}
                />
                <Tooltip content={<NationalYoyTooltip />} />
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
                  y={0}
                  stroke="var(--muted-foreground)"
                  strokeWidth={1}
                />
                <ReferenceLine
                  x={filters.year}
                  stroke="var(--foreground)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.45}
                />
                <Line
                  type="linear"
                  dataKey="demandYoy"
                  stroke="var(--chart-demand)"
                  strokeWidth={2}
                  dot={renderPartialOverlapDot("var(--chart-demand)", "yoy")}
                  connectNulls={false}
                  name="Demand YoY"
                />
                <Line
                  type="linear"
                  dataKey="supplyYoy"
                  stroke="var(--chart-supply)"
                  strokeWidth={2}
                  dot={renderPartialOverlapDot("var(--chart-supply)", "yoy")}
                  connectNulls={false}
                  name="Local Generation YoY"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title="Regional Distribution by Accounting Category"
          subtitle={`${DATASET_INFO.regionCount} harmonized regions · ${filters.year}`}
        >
          <ul className="space-y-2 text-sm">
            {GAP_CATEGORY_ORDER.map((key) => {
              const meta = GAP_CATEGORY_META[key];
              const count = regionsThisYear.filter(
                ({ category }) => category === key,
              ).length;
              const percentage = (count / regionsThisYear.length) * 100;
              return (
                <li key={key}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">{meta.label}</span>
                    <span className="tabular-nums">
                      {count} · {percentage.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-background/60">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${percentage}%`,
                        background: meta.color,
                      }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
