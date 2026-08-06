import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";
import {
  IndonesiaMap,
  MAP_METRIC_OPTIONS,
  ProvinceDetailPanel,
} from "@/components/indonesia-map";
import { MapMetric, PROVINCE_DATA } from "@/lib/energy-data";
import { useFilters } from "@/lib/filter-context";
import { useEffect, useState } from "react";

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

    setFilters({
      province: "All",
    });
  };

  const activeMetric =
    MAP_METRIC_OPTIONS.find((item) => item.value === metric) ??
    MAP_METRIC_OPTIONS[0]!;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_390px]">
      <Panel
        title="Harmonized Regional Energy Map"
        subtitle={`Bubble area represents ${activeMetric.legendLabel.toLowerCase()} · color indicates whether local generation is above or below distributed electricity`}
        right={
          <select
            value={metric}
            onChange={(event) =>
              setMetric(event.target.value as MapMetric)
            }
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
          onSelect={selectRegion}
          selected={selected}
        />

        <div className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          <p className="rounded-md border border-border bg-background/40 p-3">
            <span className="font-semibold text-foreground">
              Map and interpretation note:
            </span>{" "}
            Region bubbles represent the 34 harmonized modeling regions,
            while administrative polygons are shown only as geographic
            context. Local generation is not total available supply.
            Accounting differences compare the administrative locations of
            local generation and distributed electricity and do not indicate
            shortages, blackouts, reserve margin, operational adequacy, or
            idle capacity because interregional electricity flows are not
            included.
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
        ) : (
          <div className="card-panel flex h-full min-h-[500px] flex-col items-center justify-center p-6 text-center">
            <div className="mb-3 h-10 w-10 rounded-full border-2 border-dashed border-muted-foreground/40" />

            <div className="font-display text-sm font-semibold">
              Select a harmonized region
            </div>

            <p className="mt-1 max-w-[230px] text-xs text-muted-foreground">
              Click any bubble to inspect distributed electricity, local
              generation, accounting difference, and production data status.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}