import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";
import {
  IndonesiaMap,
  MAP_METRIC_OPTIONS,
  ProvinceDetailPanel,
} from "@/components/indonesia-map";
import {
  MapMetric,
  PROVINCE_DATA,
  fmt,
  formatSignedEnergy,
  formatSignedPercent,
  GAP_CATEGORY_META,
  classifyGap,
} from "@/lib/energy-data";
import { useFilters } from "@/lib/filter-context";
import { useEffect, useMemo, useState } from "react";

export const Route = createFileRoute("/map")({
  head: () => ({
    meta: [
      {
        title: "Indonesia Energy Map · ECADIN Energy Intelligence",
      },
      {
        name: "description",
        content:
          "Interactive map of Indonesia showing distributed electricity, local generation, and regional accounting differences for 34 harmonized modeling regions.",
      },
    ],
  }),
  component: MapPage,
});

function MapPage() {
  return (
    <AppShell
      title="Indonesia Energy Map"
      subtitle="34 harmonized modeling regions · regional accounting view"
    >
      <Inner />
    </AppShell>
  );
}

function Inner() {
  const { filters, setFilters } = useFilters();
  const [metric, setMetric] = useState<MapMetric>("gap_pct");
  const [selected, setSelected] = useState<string | null>(
    filters.province !== "All" ? filters.province : null,
  );

  useEffect(() => {
    setSelected(filters.province !== "All" ? filters.province : null);
  }, [filters.province]);

  const selectRegion = (code: string) => {
    const region = PROVINCE_DATA.find((item) => item.code === code);
    setSelected(code);
    setFilters({
      province: code,
      island: region?.island ?? filters.island,
    });
  };

  const clearSelection = () => {
    setSelected(null);
    setFilters({ province: "All" });
  };

  const islandSummary = useMemo(() => {
    if (filters.island === "All") return null;
    const members = PROVINCE_DATA.filter(
      (province) => province.island === filters.island,
    );
    const items = members.map((province) => ({
      province,
      point: province.series.find((s) => s.year === filters.year),
    }));
    const complete = items.filter(
      (entry): entry is { province: (typeof members)[number]; point: NonNullable<typeof entry.point> } =>
        Boolean(entry.point && entry.point.available),
    );
    const demandSum = complete.reduce((acc, item) => acc + item.point.demand_gwh, 0);
    const supplySum = complete.reduce((acc, item) => acc + item.point.supply_gwh, 0);
    const gapSum = supplySum - demandSum;
    const gapPct = demandSum > 0 ? (gapSum / demandSum) * 100 : Number.NaN;
    const ratio = demandSum > 0 ? supplySum / demandSum : Number.NaN;

    return {
      island: filters.island,
      totalCount: members.length,
      completeCount: complete.length,
      demandSum,
      supplySum,
      gapSum,
      gapPct,
      ratio,
      items,
    };
  }, [filters.island, filters.year]);

  const activeMetric =
    MAP_METRIC_OPTIONS.find((item) => item.value === metric) ??
    MAP_METRIC_OPTIONS[0]!;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_390px]">
      <Panel
        title="Harmonized Regional Energy Map"
        subtitle={`Bubble area represents ${activeMetric.legendLabel.toLowerCase()} · ${
          filters.island !== "All" ? `highlighted: ${filters.island}` : "all 34 regions active"
        }`}
        right={
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value as MapMetric)}
            className="rounded-md border border-border bg-background/60 px-2 py-1.5 text-xs outline-none focus:ring-1 focus:ring-ring"
          >
            {MAP_METRIC_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        }
      >
        <IndonesiaMap
          year={filters.year}
          metric={metric}
          island={filters.island}
          onSelect={selectRegion}
          selected={selected}
        />

        <div className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          <p className="rounded-md border border-border bg-background/40 p-3">
            <span className="font-semibold text-foreground">
              Map and interpretation note:
            </span>{" "}
            Region bubbles represent the 34 harmonized modeling regions, while
            administrative polygons are shown only as geographic context. Local
            generation is not total available supply. Accounting differences
            compare the administrative locations of local generation and
            distributed electricity and do not indicate shortages, blackouts,
            reserve margin, operational adequacy, or idle capacity because
            interregional electricity flows are not included.
          </p>
        </div>
      </Panel>

      <div className="min-h-[500px]">
        {selected ? (
          <ProvinceDetailPanel
            code={selected}
            year={filters.year}
            onClose={clearSelection}
          />
        ) : islandSummary ? (
          <div className="card-panel flex h-full flex-col p-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Island Group Filter · {filters.year}
                </div>
                <h3 className="mt-1 font-display text-lg font-semibold">
                  {islandSummary.island}
                </h3>
              </div>
              <button
                onClick={() => setFilters({ island: "All", province: "All" })}
                className="rounded-md border border-border px-2 py-1 text-[10px] uppercase tracking-widest text-muted-foreground hover:bg-accent"
              >
                Show All
              </button>
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-md border border-border bg-background/40 p-2.5">
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Distributed Electricity
                </div>
                <div className="mt-1 font-display text-sm font-semibold tabular-nums">
                  {fmt(islandSummary.demandSum, "GWh")}
                </div>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-2.5">
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Local Generation
                </div>
                <div className="mt-1 font-display text-sm font-semibold tabular-nums">
                  {fmt(islandSummary.supplySum, "GWh")}
                </div>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-2.5">
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Accounting Difference
                </div>
                <div className="mt-1 font-display text-sm font-semibold tabular-nums">
                  {formatSignedEnergy(islandSummary.gapSum, true)} (
                  {formatSignedPercent(islandSummary.gapPct)})
                </div>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-2.5">
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  Complete Regions
                </div>
                <div className="mt-1 font-display text-sm font-semibold tabular-nums">
                  {islandSummary.completeCount}/{islandSummary.totalCount}
                </div>
              </div>
            </dl>

            <div className="mt-4 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Regions in {islandSummary.island} (click to inspect)
            </div>
            <ul className="mt-2 max-h-[290px] space-y-1 overflow-y-auto pr-1 text-xs">
              {islandSummary.items.map(({ province, point }) => {
                const cat =
                  point?.gapCategory ?? classifyGap(point?.gap_pct);
                const meta = GAP_CATEGORY_META[cat];
                return (
                  <li key={province.code}>
                    <button
                      onClick={() => selectRegion(province.code)}
                      className="flex w-full items-center justify-between rounded-md border border-border/70 bg-background/30 px-2.5 py-2 text-left transition-colors hover:bg-accent/60"
                    >
                      <span className="flex items-center gap-2 font-medium">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: meta.color }}
                        />
                        {province.name}
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        {point?.available
                          ? formatSignedPercent(point.gap_pct)
                          : "N/A"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : (
          <div className="card-panel flex h-full min-h-[500px] flex-col items-center justify-center p-6 text-center">
            <div className="mb-3 h-10 w-10 rounded-full border-2 border-dashed border-muted-foreground/40" />

            <div className="font-display text-sm font-semibold">
              Select a harmonized region
            </div>

            <p className="mt-1 max-w-[240px] text-xs text-muted-foreground">
              Click any bubble or province polygon—or pick an Island Group in
              the sidebar—to inspect distributed electricity, local generation,
              accounting difference, and production data status.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
