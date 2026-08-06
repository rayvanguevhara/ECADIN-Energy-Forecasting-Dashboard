import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import type { MultiPolygon } from "geojson";
import {
  PROVINCE_DATA,
  MODEL_SUMMARY,
  MapMetric,
  metricValue,
  classifyGap,
  fmt,
  qualityLabel,
  ProvinceRecord,
} from "@/lib/energy-data";
import geoRaw from "@/data/indonesia-provinces.json";

interface Props {
  year: number;
  metric: MapMetric;
  onSelect?: (code: string) => void;
  selected?: string | null;
  compact?: boolean;
}

type ProvFeature = {
  type: "Feature";
  properties: { name: string; code: string };
  geometry: MultiPolygon;
};
const GEO_CODE_BY_NAME: Record<string, string> = {
  "Bangka Belitung": "BB",
  Bengkulu: "BE",
};
const rawGeo = geoRaw as unknown as {
  type: "FeatureCollection";
  features: ProvFeature[];
};
const GEO = {
  ...rawGeo,
  features: rawGeo.features.map((feature) => ({
    ...feature,
    properties: {
      ...feature.properties,
      code: feature.properties.code || GEO_CODE_BY_NAME[feature.properties.name] || "",
    },
  })),
};


const OCEAN = "#071521";
const LAND = "#29475A";
const LAND_HL = "#3d6a86";
const PROV_BORDER = "rgba(255,255,255,0.30)";
const COASTLINE = "rgba(255,255,255,0.55)";

const MIN_ZOOM = 1;
const MAX_ZOOM = 8;
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));

export const MAP_METRIC_OPTIONS: {
  value: MapMetric;
  label: string;
  legendLabel: string;
  unit: string;
  useAbsoluteMagnitude: boolean;
}[] = [
  {
    value: "demand_gwh",
    label: "Distributed Electricity",
    legendLabel: "Distributed electricity",
    unit: "GWh",
    useAbsoluteMagnitude: false,
  },
  {
    value: "supply_gwh",
    label: "Local Generation",
    legendLabel: "Local generation",
    unit: "GWh",
    useAbsoluteMagnitude: false,
  },
  {
    value: "gap_gwh",
    label: "Absolute Accounting Difference",
    legendLabel: "Absolute accounting difference",
    unit: "GWh",
    useAbsoluteMagnitude: true,
  },
  {
    value: "gap_pct",
    label: "Absolute Accounting Difference (% of Distributed Electricity)",
    legendLabel: "Absolute accounting difference (% of distributed electricity)",
    unit: "%",
    useAbsoluteMagnitude: true,
  },
  {
    value: "ratio",
    label: "Local Generation / Distributed Electricity Ratio",
    legendLabel: "Local generation / distributed electricity ratio",
    unit: "×",
    useAbsoluteMagnitude: false,
  },
];

type MapCategory = ReturnType<typeof classifyGap>;

const MAP_CATEGORY_ORDER: MapCategory[] = [
  "surplus_tinggi",
  "surplus_moderat",
  "relatif_seimbang",
  "defisit_moderat",
  "defisit_tinggi",
  "tidak_tersedia",
];

const MAP_CATEGORY_META: Record<
  MapCategory,
  { label: string; color: string; description: string }
> = {
  surplus_tinggi: {
    label: "Far above distributed electricity",
    color: "#2563EB",
    description: "Local generation is at least 20% above distributed electricity.",
  },
  surplus_moderat: {
    label: "Above distributed electricity",
    color: "#38BDF8",
    description: "Local generation is 5% to below 20% above distributed electricity.",
  },
  relatif_seimbang: {
    label: "Relatively balanced",
    color: "#94A3B8",
    description: "Local generation and distributed electricity differ by less than 5%.",
  },
  defisit_moderat: {
    label: "Below distributed electricity",
    color: "#F59E0B",
    description: "Local generation is 5% to below 20% below distributed electricity.",
  },
  defisit_tinggi: {
    label: "Far below distributed electricity",
    color: "#EA580C",
    description: "Local generation is at least 20% below distributed electricity.",
  },
  tidak_tersedia: {
    label: "Unavailable",
    color: "#64748B",
    description:
      "A complete distributed-electricity and local-generation pair is unavailable for this region and year.",
  },
};

const metricMeta = (metric: MapMetric) =>
  MAP_METRIC_OPTIONS.find((item) => item.value === metric) ?? MAP_METRIC_OPTIONS[0]!;

const sizeMagnitude = (value: number, metric: MapMetric) => {
  if (!Number.isFinite(value)) return Number.NaN;
  return metricMeta(metric).useAbsoluteMagnitude ? Math.abs(value) : value;
};

const formatLegendValue = (value: number, metric: MapMetric) => {
  if (!Number.isFinite(value)) return "N/A";
  const meta = metricMeta(metric);
  if (metric === "ratio") return `${value.toFixed(2)}×`;
  if (metric === "gap_pct") return `${value.toFixed(1)}%`;
  return `${fmt(value)} ${meta.unit}`;
};

const formatPanelEnergy = (
  value: number,
  signed = false,
): string => {
  if (!Number.isFinite(value)) return "N/A";

  const absolute = Math.abs(value);
  const formatted =
    absolute >= 1_000
      ? `${(absolute / 1_000).toFixed(1)}k`
      : absolute.toFixed(1);

  const sign =
    signed && value > 0
      ? "+"
      : signed && value < 0
        ? "−"
        : "";

  return `${sign}${formatted} GWh`;
};

const formatSignedPercent = (value: number) => {
  if (!Number.isFinite(value)) return "N/A";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
};

const displayModelName = (side: "demand" | "supply") => {
  const summary = MODEL_SUMMARY.find((item) => item.side === side);
  if (!summary) return side === "demand" ? "Drift" : "Drift V1";
  if (side === "supply" && summary.model_version.toLowerCase().includes("drift_v1")) {
    return "Drift V1";
  }
  return summary.active_model.toLowerCase() === "drift"
    ? "Drift"
    : summary.active_model;
};

const regionalInterpretation = (gapPct: number, available: boolean) => {
  if (!available || !Number.isFinite(gapPct)) {
    return "A complete distributed-electricity and local-generation pair is unavailable for this region and year.";
  }

  const magnitude = Math.abs(gapPct).toFixed(1);
  if (Math.abs(gapPct) < 5) {
    return `Local generation and distributed electricity differ by ${magnitude}%. This describes their administrative accounting relationship, not operational adequacy.`;
  }

  const direction = gapPct > 0 ? "above" : "below";
  return `Local generation is ${magnitude}% ${direction} distributed electricity in this harmonized region. Interregional electricity flows are not included, so this does not indicate operational surplus, shortage, reserve margin, or blackout risk.`;
};

export function IndonesiaMap({
  year,
  metric,
  onSelect,
  selected,
  compact,
}: Props) {
  const [hover, setHover] = useState<{
    code: string;
    x: number;
    y: number;
  } | null>(null);
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    x: number;
    y: number;
    ox: number;
    oy: number;
  } | null>(null);

  const width = 1000;
  const height = compact ? 380 : 480;

  const { pathFn, project } = useMemo(() => {
    const projection = geoMercator().fitExtent(
      [
        [12, 12],
        [width - 12, height - 12],
      ],
      GEO,
    );
    return {
      pathFn: geoPath(projection),
      project: (lng: number, lat: number) => {
        const p = projection([lng, lat]);
        return { x: p?.[0] ?? 0, y: p?.[1] ?? 0 };
      },
    };
  }, [width, height]);

  const values = useMemo(
    () =>
      PROVINCE_DATA.map((p) => {
        const value = metricValue(p, year, metric);
        return { p, sizeValue: sizeMagnitude(value, metric) };
      }),
    [year, metric],
  );
  const finiteValues = values.map((item) => item.sizeValue).filter(Number.isFinite);
  const min = finiteValues.length ? Math.min(...finiteValues) : 0;
  const max = finiteValues.length ? Math.max(...finiteValues) : 1;

  const radius = (value: number) => {
    if (!Number.isFinite(value)) return 5;
    const norm = max === min ? 0.5 : (value - min) / (max - min);
    return 5 + Math.sqrt(Math.max(0, norm)) * (compact ? 16 : 22);
  };

  // wheel zoom, anchored at cursor (native non-passive listener)
  const wheelRef = useRef<(e: WheelEvent) => void>(() => {});
  wheelRef.current = (e: WheelEvent) => {
    const el = containerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 100 : 1);
    const next = clamp(zoom * Math.exp(-dy * 0.0018), MIN_ZOOM, MAX_ZOOM);
    const scale = width / rect.width;
    const px = (e.clientX - rect.left) * scale;
    const py = (e.clientY - rect.top) * scale;
    const k = next / zoom;
    setOffset({ x: px - (px - offset.x) * k, y: py - (py - offset.y) * k });
    setZoom(next);
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      wheelRef.current(e);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const reset = useCallback(() => {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }, []);

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    // Do not start map dragging when the pointer is pressed on an
    // interactive province layer. Otherwise pointer capture on the SVG
    // swallows the bubble click and the detail panel never receives onSelect.
    const target = e.target as Element;
    if (target.closest("[data-map-interactive='true']")) return;

    dragRef.current = { x: e.clientX, y: e.clientY, ox: offset.x, oy: offset.y };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = dragRef.current;
    const el = containerRef.current;
    if (!d || !el) return;
    const scale = width / el.getBoundingClientRect().width;
    setOffset({
      x: d.ox + (e.clientX - d.x) * scale,
      y: d.oy + (e.clientY - d.y) * scale,
    });
  };
  const endDrag = () => {
    dragRef.current = null;
  };

  const hoverP = hover ? PROVINCE_DATA.find((p) => p.code === hover.code) : null;
  const hoverY = hoverP?.series.find((s) => s.year === year);
  const activeCode = hover?.code ?? selected ?? null;

  const t = `translate(${offset.x} ${offset.y}) scale(${zoom})`;

  return (
    <div className="relative" ref={containerRef}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full touch-none select-none rounded-lg border border-border"
        style={{ background: OCEAN, cursor: dragRef.current ? "grabbing" : "grab" }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
      >
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M40 0H0V40" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="0.5" />
          </pattern>
          <filter id="glow"><feGaussianBlur stdDeviation="4" /></filter>
        </defs>

        {/* 1 · ocean */}
        <rect width={width} height={height} fill="url(#grid)" />

        <g transform={t}>
          {/* 2 · land polygons + 3 · province boundaries */}
          {GEO.features.map((f, i) => {
            const d = pathFn(f as never);
            if (!d) return null;
            const isActive = !!f.properties.code && f.properties.code === selected;
            return (
              <path
                key={`${f.properties.name}-${i}`}
                d={d}
                fill={isActive ? LAND_HL : LAND}
                stroke={isActive ? "#fff8c4" : PROV_BORDER}
                strokeWidth={(isActive ? 1.6 : 0.5) / zoom}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
          {/* coastline emphasis */}
          <path
            d={
              pathFn({ type: "FeatureCollection", features: GEO.features } as never) ??
              undefined
            }
            fill="none"
            stroke={COASTLINE}
            strokeWidth={0.6}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />

          {/* 4 · province labels */}
          {values.map(({ p, sizeValue }) => {
            if (p.code !== activeCode) return null;
            const { x, y } = project(p.lng, p.lat);
            return (
              <text
                key={`lbl-${p.code}`}
                x={x}
                y={y - radius(sizeValue) - 4 / zoom}
                textAnchor="middle"
                fontSize={9 / zoom}
                fill={p.code === activeCode ? "#fff" : "rgba(226,238,247,0.72)"}
                stroke="rgba(7,21,33,0.85)"
                strokeWidth={2.5 / zoom}
                paintOrder="stroke"
                pointerEvents="none"
                fontFamily="var(--font-display)"
              >
                {p.name}
              </text>
            );
          })}

          {/* 5 · bubbles */}
          {values.map(({ p, sizeValue }) => {
            const { x, y } = project(p.lng, p.lat);
            const y0 = p.series.find((s) => s.year === year)!;
            const cat = classifyGap(y0.gap_pct);
            const color = MAP_CATEGORY_META[cat].color;
            const r = radius(sizeValue) / zoom;
            const isSel = selected === p.code;
            return (
              <g
                key={p.code}
                data-map-interactive="true"
                role="button"
                tabIndex={0}
                aria-label={`Select harmonized region ${p.name}`}
                onPointerDown={(e) => {
                  // Prevent the parent SVG from starting drag/pointer capture.
                  e.stopPropagation();
                }}
                onMouseEnter={() => {
                  const el = containerRef.current;
                  const rect = el?.getBoundingClientRect();
                  void rect;
                  setHover({ code: p.code, x: x * zoom + offset.x, y: y * zoom + offset.y });
                }}
                onMouseLeave={() => setHover(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect?.(p.code);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect?.(p.code);
                  }
                }}
                className="cursor-pointer outline-none"
              >
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={color}
                  opacity={0.2}
                  filter="url(#glow)"
                />
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={color}
                  fillOpacity={0.8}
                  stroke={isSel ? "#fff8c4" : "rgba(255,255,255,0.75)"}
                  strokeWidth={(isSel ? 2.5 : 1) / zoom}
                />
                {/* 6 · selection highlight */}
                {isSel && (
                  <circle
                    cx={x}
                    cy={y}
                    r={r + 5 / zoom}
                    fill="none"
                    stroke="#fff8c4"
                    strokeWidth={1 / zoom}
                    opacity={0.7}
                  />
                )}
              </g>
            );
          })}
        </g>
      </svg>

      <div className="absolute right-3 top-3 flex flex-col gap-1">
        <button
          onClick={() => setZoom((z) => clamp(z * 1.4, MIN_ZOOM, MAX_ZOOM))}
          className="h-7 w-7 rounded-md border border-white/20 bg-black/40 text-sm text-white/90 backdrop-blur hover:bg-black/60"
          aria-label="Zoom in"
        >
          +
        </button>
        <button
          onClick={() => setZoom((z) => clamp(z / 1.4, MIN_ZOOM, MAX_ZOOM))}
          className="h-7 w-7 rounded-md border border-white/20 bg-black/40 text-sm text-white/90 backdrop-blur hover:bg-black/60"
          aria-label="Zoom out"
        >
          −
        </button>
        <button
          onClick={reset}
          className="rounded-md border border-white/20 bg-black/40 px-1.5 py-1 text-[10px] uppercase tracking-widest text-white/90 backdrop-blur hover:bg-black/60"
        >
          Reset
        </button>
      </div>

      {hover && hoverP && hoverY && (
        <div
          className="pointer-events-none absolute z-10 min-w-[200px] -translate-x-1/2 -translate-y-full rounded-md border border-border bg-popover/95 p-3 text-xs shadow-xl backdrop-blur"
          style={{
            left: `${(hover.x / width) * 100}%`,
            top: `${(hover.y / height) * 100}%`,
          }}
        >
          <div className="font-display text-sm font-semibold">{hoverP.name}</div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
            {hoverP.island}
          </div>
          <div className="mt-2 space-y-1 tabular-nums">
            <Row
              label="Distributed Electricity"
              value={formatPanelEnergy(hoverY.demand_gwh)}
            />
            <Row
              label="Local Generation"
              value={formatPanelEnergy(hoverY.supply_gwh)}
            />
            <Row
              label="Accounting Difference"
              value={`${formatPanelEnergy(
                hoverY.gap_gwh,
                true,
              )} (${formatSignedPercent(hoverY.gap_pct)})`}
            />
            <Row
              label="Category"
              value={MAP_CATEGORY_META[classifyGap(hoverY.gap_pct)].label}
            />
            <Row label="Data Status" value={qualityLabel(hoverY.quality)} />
          </div>
        </div>
      )}

      <MapLegend metric={metric} min={min} max={max} />
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}


export function MapLegend({
  metric,
  min,
  max,
}: {
  metric: MapMetric;
  min: number;
  max: number;
}) {
  const meta = metricMeta(metric);
  const middle = min + (max - min) / 2;
  const examples = [
    { value: min, size: "h-2.5 w-2.5" },
    { value: middle, size: "h-4 w-4" },
    { value: max, size: "h-6 w-6" },
  ];

  return (
    <div className="mt-3 rounded-md border border-border bg-card/60 p-3 text-xs">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Bubble area · {meta.legendLabel} · example scale
          </div>
          <div className="mt-2 flex flex-wrap items-end gap-4 text-muted-foreground">
            {examples.map((item, index) => (
              <div key={`${item.value}-${index}`} className="flex items-center gap-1.5">
                <span
                  className={`inline-block rounded-full bg-muted-foreground/40 ${item.size}`}
                />
                <span>{formatLegendValue(item.value, metric)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex max-w-[760px] flex-wrap justify-end gap-x-3 gap-y-2">
          {MAP_CATEGORY_ORDER.map((category) => {
            const item = MAP_CATEGORY_META[category];
            return (
              <div key={category} className="flex items-center gap-1.5">
                <span
                  className="h-3 w-3 rounded-full"
                  style={{ background: item.color }}
                />
                <span className="text-muted-foreground">{item.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-3 border-t border-border pt-2 text-[10px] leading-relaxed text-muted-foreground">
        Category thresholds: far below &lt; −20% · below −20% to −5% · balanced −5% to +5% ·
        above +5% to +20% · far above &gt; +20%. Bubble color indicates whether local generation
        is above or below distributed electricity; bubble area indicates magnitude only.
      </div>
    </div>
  );
}

export function ProvinceDetailPanel({
  code,
  year,
  onClose,
}: {
  code: string;
  year: number;
  onClose: () => void;
}) {
  const region = PROVINCE_DATA.find(
    (item) => item.code === code,
  ) as ProvinceRecord | undefined;
  if (!region) return null;
  const point = region.series.find((item) => item.year === year);
  if (!point) return null;
  const category = classifyGap(point.gap_pct);
  const meta = MAP_CATEGORY_META[category];
  const perCapita =
    point.population != null && Number.isFinite(point.demand_gwh)
      ? (point.demand_gwh * 1_000_000) / point.population
      : Number.NaN;

  const sourceOrModels = point.forecast ? (
    <span className="block space-y-1 leading-relaxed">
      <span className="block">
        Demand · {displayModelName("demand")}
      </span>
      <span className="block">
        Generation · {displayModelName("supply")}
      </span>
    </span>
  ) : (
    "Harmonized historical panel"
  );

  return (
    <div className="card-panel flex h-full flex-col p-5">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
            {region.island} · {year} ·{" "}
            {point.forecast ? "Production Forecast" : "Historical"}
          </div>
          <h3 className="mt-1 font-display text-lg font-semibold">{region.name}</h3>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:bg-accent"
          aria-label="Close regional detail"
        >
          ✕
        </button>
      </div>

      <div
        className="mt-3 flex items-center gap-2 rounded-md border px-3 py-2 text-xs"
        style={{ borderColor: meta.color, color: meta.color }}
      >
        <span
          className="h-2 w-2 rounded-full"
          style={{ background: meta.color }}
        />
        <span className="font-semibold uppercase tracking-widest">
          {meta.label}
        </span>
        <span className="ml-auto tabular-nums">
          {formatSignedPercent(point.gap_pct)}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <Stat
          label="Distributed Electricity"
          value={formatPanelEnergy(point.demand_gwh)}
        />
        <Stat
          label="Local Generation"
          value={formatPanelEnergy(point.supply_gwh)}
        />
        <Stat
          label="Accounting Difference"
          value={formatPanelEnergy(point.gap_gwh, true)}
        />
        <Stat
          label="Local Generation / Distributed Electricity"
          value={Number.isFinite(point.ratio) ? `${point.ratio.toFixed(2)}×` : "N/A"}
        />
        <Stat
          label={point.forecast ? "Projected Population" : "Population"}
          value={
            point.population == null
              ? "N/A"
              : `${fmt(point.population / 1_000_000)} M`
          }
        />
        <Stat
          label={
            point.forecast
              ? "Projected Distributed Electricity per Capita"
              : "Distributed Electricity per Capita"
          }
          value={
            Number.isFinite(perCapita) ? `${fmt(perCapita)} kWh` : "N/A"
          }
        />
        <Stat label="Data Status" value={qualityLabel(point.quality)} />
        <Stat
          label={point.forecast ? "Forecast Models" : "Data Source"}
          value={sourceOrModels}
        />
      </dl>

      <p className="mt-4 rounded-md border border-border bg-background/40 p-3 text-[11px] leading-relaxed text-muted-foreground">
        <span className="font-semibold text-foreground">Interpretation:</span>{" "}
        {regionalInterpretation(point.gap_pct, point.available)}
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-background/40 p-2.5">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-display text-sm font-semibold tabular-nums">
        {value}
      </div>
    </div>
  );
}