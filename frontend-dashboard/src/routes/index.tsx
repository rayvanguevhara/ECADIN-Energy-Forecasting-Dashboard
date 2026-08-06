import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { KpiCard, Panel } from "@/components/panel";
import { useFilters } from "@/lib/filter-context";
import {
  nationalSeries,
  PROVINCE_DATA,
  classifyGap,
  fmt,
  FORECAST_START,
} from "@/lib/energy-data";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import {
  Zap,
  Activity,
  TrendingUp,
  AlertTriangle,
  Gauge,
  Scale,
} from "lucide-react";
import { useMemo } from "react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "National Overview · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "National electricity demand, local generation, and accounting gap for Indonesia, 2011–2030.",
      },
    ],
  }),
  component: NationalOverview,
});

function NationalOverview() {
  return (
    <AppShell
      title="National Overview"
      subtitle="Indonesia national electricity demand, local generation, and accounting gap · 2011–2030"
    >
      <Inner />
    </AppShell>
  );
}

function Inner() {
  const { filters } = useFilters();
  const series = useMemo(() => nationalSeries(), []);
  const current = series.find((point) => point.year === filters.year) ?? series.at(-1)!;

  const regionsThisYear = PROVINCE_DATA.map((region) => {
    const point = region.series.find((item) => item.year === filters.year)!;
    return { region, point, category: classifyGap(point.gap_pct) };
  });

  const regionsBelowDemand = regionsThisYear.filter(
    ({ category }) => category === "defisit_moderat" || category === "defisit_tinggi",
  ).length;
  const regionsAboveDemand = regionsThisYear.filter(
    ({ category }) => category === "surplus_moderat" || category === "surplus_tinggi",
  ).length;
  const regionsRelativelyBalanced = regionsThisYear.filter(
    ({ category }) => category === "relatif_seimbang",
  ).length;

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
          value={fmt(current.gap_gwh)}
          unit="GWh"
          tone="neutral"
          delta={`${current.gap_pct > 0 ? "+" : ""}${current.gap_pct.toFixed(2)}% of demand`}
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
          tone="down"
          icon={<AlertTriangle className="h-4 w-4" />}
        />
        <KpiCard
          label="Regions Above Demand"
          value={String(regionsAboveDemand)}
          tone="up"
          icon={<TrendingUp className="h-4 w-4" />}
        />
      </div>

      <p className="-mt-2 text-right text-xs text-muted-foreground">
        {regionsRelativelyBalanced} regions are relatively balanced and are not included in the
        above/below counts.
      </p>

      <Panel title="How to Interpret the National Figures">
        <p className="text-sm leading-relaxed text-muted-foreground">
          <span className="font-semibold text-foreground">
            Local generation is not total available supply.
          </span>{" "}
          National demand and local generation are aggregates across the 34 harmonized regions.
          The accounting gap is local generation minus electricity distributed to customers. It
          does not measure reserve margin, operational adequacy, shortage risk, or blackout
          probability because power-system flows and operational capacity are not included.
        </p>
      </Panel>

      <Panel
        title="National Demand and Local Generation (GWh) · 2011–2030"
        subtitle={`Forecast horizon is shaded · ${current.completeRegions}/${current.totalRegions} regions have complete demand–generation pairs in ${current.year}`}
      >
        <div className="h-[300px]">
          <ResponsiveContainer>
            <LineChart data={series} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="year" stroke="var(--muted-foreground)" fontSize={11} />
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
                labelStyle={{ color: "var(--foreground)" }}
                formatter={(value: number, name) => [`${fmt(value)} GWh`, name]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <ReferenceArea
                x1={FORECAST_START}
                x2={2030}
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
                name="Demand"
              />
              <Line
                type="linear"
                dataKey="supply_gwh"
                stroke="var(--chart-supply)"
                strokeWidth={2}
                dot={false}
                name="Local Generation"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel
        title="National Accounting Gap · 2011–2030"
        subtitle="Local generation minus demand (GWh). Bars above or below zero are accounting differences, not operational surplus or shortage."
      >
        <div className="h-[220px]">
          <ResponsiveContainer>
            <BarChart data={series} margin={{ top: 10, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="year" stroke="var(--muted-foreground)" fontSize={11} />
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
                labelStyle={{ color: "var(--foreground)" }}
                formatter={(value: number) => [`${fmt(value)} GWh`, "Accounting Gap"]}
              />
              <ReferenceArea
                x1={FORECAST_START}
                x2={2030}
                fill="var(--chart-gap)"
                fillOpacity={0.06}
                label={{
                  value: "Forecast",
                  fill: "var(--muted-foreground)",
                  fontSize: 10,
                  position: "insideTopRight",
                }}
              />
              <ReferenceLine y={0} stroke="var(--muted-foreground)" strokeWidth={1} />
              <Bar dataKey="gap_gwh" name="Accounting Gap" radius={[3, 3, 0, 0]}>
                {series.map((point) => (
                  <Cell
                    key={point.year}
                    fill={
                      point.year === filters.year
                        ? "var(--chart-demand)"
                        : "var(--chart-gap)"
                    }
                    fillOpacity={point.year === filters.year ? 1 : 0.78}
                    stroke={point.year === filters.year ? "var(--foreground)" : "none"}
                    strokeWidth={point.year === filters.year ? 1 : 0}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="National Demand Growth" subtitle="Year-over-year change in national electricity demand">
          <div className="h-[240px]">
            <ResponsiveContainer>
              <LineChart
                data={series.map((point) => ({
                  year: point.year,
                  yoy: Number.isFinite(point.demandGrowthYoyPercent)
                    ? point.demandGrowthYoyPercent
                    : null,
                }))}
                margin={{ top: 10, right: 12, bottom: 0, left: -20 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="year" stroke="var(--muted-foreground)" fontSize={11} />
                <YAxis
                  stroke="var(--muted-foreground)"
                  fontSize={11}
                  tickFormatter={(value) => `${value}%`}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number) => `${value.toFixed(2)}%`}
                />
                <Line
                  type="linear"
                  dataKey="yoy"
                  stroke="var(--chart-demand)"
                  strokeWidth={2}
                  dot={false}
                  name="Demand growth"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title="Regional Distribution by Accounting Category"
          subtitle={`34 harmonized regions · ${filters.year}`}
        >
          <ul className="space-y-2 text-sm">
            {[
              ["surplus_tinggi", "Local generation far above demand"],
              ["surplus_moderat", "Local generation above demand"],
              ["relatif_seimbang", "Relatively balanced"],
              ["defisit_moderat", "Local generation below demand"],
              ["defisit_tinggi", "Local generation far below demand"],
              ["tidak_tersedia", "Unavailable"],
            ].map(([key, label]) => {
              const count = regionsThisYear.filter(({ category }) => category === key).length;
              const percentage = (count / regionsThisYear.length) * 100;
              const colorKey =
                key === "surplus_tinggi"
                  ? "surplus-high"
                  : key === "surplus_moderat"
                    ? "surplus-mod"
                    : key === "relatif_seimbang"
                      ? "balanced"
                      : key === "defisit_moderat"
                        ? "deficit-mod"
                        : key === "defisit_tinggi"
                          ? "deficit-high"
                          : "nodata";
              return (
                <li key={key}>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">{label}</span>
                    <span className="tabular-nums">
                      {count} · {percentage.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-background/60">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${percentage}%`, background: `var(--${colorKey})` }}
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
