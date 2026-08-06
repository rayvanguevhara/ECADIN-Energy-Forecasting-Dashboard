import rawData from "@/data/dashboard-production.json";

export type GapCategory =
  | "surplus_tinggi"
  | "surplus_moderat"
  | "relatif_seimbang"
  | "defisit_moderat"
  | "defisit_tinggi"
  | "tidak_tersedia";

export type QualityLevel = "observed" | "interpolated" | "forecast" | "incomplete";

export const gapCategoryMeta: Record<
  GapCategory,
  { label: string; color: string; description: string }
> = {
  surplus_tinggi: {
    label: "Local Gen Jauh di Atas Demand",
    color: "var(--surplus-high)",
    description: "Local generation exceeds demand by at least 20%.",
  },
  surplus_moderat: {
    label: "Local Gen di Atas Demand",
    color: "var(--surplus-mod)",
    description: "Local generation exceeds demand by 5% to below 20%.",
  },
  relatif_seimbang: {
    label: "Relatif Seimbang",
    color: "var(--balanced)",
    description: "Local generation and demand are within ±5%.",
  },
  defisit_moderat: {
    label: "Local Gen di Bawah Demand",
    color: "var(--deficit-mod)",
    description: "Local generation is 5% to below 20% lower than demand.",
  },
  defisit_tinggi: {
    label: "Local Gen Jauh di Bawah Demand",
    color: "var(--deficit-high)",
    description: "Local generation is at least 20% lower than demand.",
  },
  tidak_tersedia: {
    label: "Tidak Tersedia",
    color: "var(--nodata)",
    description: "A complete demand–supply pair is unavailable for this region and year.",
  },
};

export function classifyGap(gapPct: number | null | undefined): GapCategory {
  if (gapPct == null || !Number.isFinite(gapPct)) return "tidak_tersedia";
  if (gapPct >= 20) return "surplus_tinggi";
  if (gapPct >= 5) return "surplus_moderat";
  if (gapPct > -5) return "relatif_seimbang";
  if (gapPct > -20) return "defisit_moderat";
  return "defisit_tinggi";
}

type RawYearPoint = {
  year: number;
  demand_gwh: number | null;
  supply_gwh: number | null;
  gap_gwh: number | null;
  gap_pct: number | null;
  ratio: number | null;
  data_type: "historical" | "forecast";
  forecast: boolean;
  available: boolean;
  quality: QualityLevel;
  quality_badge: string;
  interpolated: boolean;
  attention: boolean;
  attention_reason: string | null;
  population_jiwa: number | null;
  demand_model: string | null;
  supply_model: string | null;
  demand_value_status: string | null;
  supply_value_status: string | null;
};

type RawProvince = {
  code: string;
  source_name: string;
  name: string;
  island: string;
  lat: number;
  lng: number;
  population_2030_jiwa: number | null;
  series: RawYearPoint[];
};

type RawNationalPoint = {
  year: number;
  demand_gwh: number;
  supply_gwh: number;
  gap_gwh: number;
  gap_pct: number;
  ratio: number;
  forecast: boolean;
  data_type: "historical" | "forecast";
  complete_regions: number;
  total_regions: number;
  data_completeness: string;
  demand_growth_yoy_percent: number | null;
  supply_growth_yoy_percent: number | null;
};

export interface ModelSummary {
  side: "demand" | "supply";
  active_model: string;
  model_version: string;
  status: string;
  forecast_period: string;
  geography: string;
  selection_basis: string;
  legacy_model_reused: boolean;
  regional_uncertainty_display_allowed: boolean;
  note: string;
}

type ProductionPayload = {
  schema_version: string;
  source_dashboard_stage: string;
  source_registry_status: string;
  production_ready: boolean;
  geography: string;
  period: [number, number];
  forecast_start: number;
  region_count: number;
  row_count: number;
  complete_gap_count: number;
  historical_incomplete_gap_count: number;
  regional_uncertainty_display_allowed: boolean;
  legacy_ridge_used: boolean;
  provinces: RawProvince[];
  national: RawNationalPoint[];
  models: ModelSummary[];
  metadata: { bagian: string; penjelasan: string }[];
  metadata_v2: Record<string, string>;
};

const RAW = rawData as unknown as ProductionPayload;
const asNumber = (value: number | null): number => value == null ? Number.NaN : value;

export const DATASET_INFO = {
  schemaVersion: RAW.schema_version,
  sourceDashboardStage: RAW.source_dashboard_stage,
  registryStatus: RAW.source_registry_status,
  productionReady: RAW.production_ready,
  geography: RAW.geography,
  period: RAW.period,
  regionCount: RAW.region_count,
  rowCount: RAW.row_count,
  completeGapCount: RAW.complete_gap_count,
  historicalIncompleteGapCount: RAW.historical_incomplete_gap_count,
  regionalUncertaintyDisplayAllowed: RAW.regional_uncertainty_display_allowed,
  legacyRidgeUsed: RAW.legacy_ridge_used,
};

export const YEARS = Array.from(
  { length: RAW.period[1] - RAW.period[0] + 1 },
  (_, index) => RAW.period[0] + index,
);
export const FORECAST_START = RAW.forecast_start;

export interface YearPoint {
  year: number;
  demand_gwh: number;
  supply_gwh: number;
  gap_gwh: number;
  gap_pct: number;
  ratio: number;
  forecast: boolean;
  dataType: "historical" | "forecast";
  available: boolean;
  quality: QualityLevel;
  qualityBadge: string;
  interpolated: boolean;
  attention: boolean;
  attentionReason: string | null;
  population: number | null;
  demandModel: string | null;
  supplyModel: string | null;
  demandValueStatus: string | null;
  supplyValueStatus: string | null;
}

export interface Province {
  code: string;
  sourceName: string;
  name: string;
  island: string;
  lat: number;
  lng: number;
  population2030: number | null;
}

export interface ProvinceRecord extends Province {
  series: YearPoint[];
}

const toYearPoint = (point: RawYearPoint): YearPoint => ({
  year: point.year,
  demand_gwh: asNumber(point.demand_gwh),
  supply_gwh: asNumber(point.supply_gwh),
  gap_gwh: asNumber(point.gap_gwh),
  gap_pct: asNumber(point.gap_pct),
  ratio: asNumber(point.ratio),
  forecast: point.forecast,
  dataType: point.data_type,
  available: point.available,
  quality: point.quality,
  qualityBadge: point.quality_badge,
  interpolated: point.interpolated,
  attention: point.attention,
  attentionReason: point.attention_reason,
  population: point.population_jiwa,
  demandModel: point.demand_model,
  supplyModel: point.supply_model,
  demandValueStatus: point.demand_value_status,
  supplyValueStatus: point.supply_value_status,
});

export const PROVINCE_DATA: ProvinceRecord[] = RAW.provinces.map((province) => ({
  code: province.code,
  sourceName: province.source_name,
  name: province.name,
  island: province.island,
  lat: province.lat,
  lng: province.lng,
  population2030: province.population_2030_jiwa,
  series: province.series.map(toYearPoint),
}));

export const PROVINCES: Province[] = PROVINCE_DATA.map(({ series: _series, ...province }) => province);
export const ISLANDS = Array.from(new Set(PROVINCE_DATA.map((province) => province.island)));

export function getProvinceYear(code: string, year: number): YearPoint | undefined {
  return PROVINCE_DATA.find((province) => province.code === code)?.series.find(
    (point) => point.year === year,
  );
}

export interface NationalPoint {
  year: number;
  demand_gwh: number;
  supply_gwh: number;
  gap_gwh: number;
  gap_pct: number;
  ratio: number;
  forecast: boolean;
  dataType: "historical" | "forecast";
  completeRegions: number;
  totalRegions: number;
  dataCompleteness: string;
  demandGrowthYoyPercent: number;
  supplyGrowthYoyPercent: number;
}

const NATIONAL_SERIES: NationalPoint[] = RAW.national.map((point) => ({
  year: point.year,
  demand_gwh: point.demand_gwh,
  supply_gwh: point.supply_gwh,
  gap_gwh: point.gap_gwh,
  gap_pct: point.gap_pct,
  ratio: point.ratio,
  forecast: point.forecast,
  dataType: point.data_type,
  completeRegions: point.complete_regions,
  totalRegions: point.total_regions,
  dataCompleteness: point.data_completeness,
  demandGrowthYoyPercent: asNumber(point.demand_growth_yoy_percent),
  supplyGrowthYoyPercent: asNumber(point.supply_growth_yoy_percent),
}));

export function nationalSeries(): NationalPoint[] {
  return NATIONAL_SERIES;
}

export type MapMetric =
  | "demand_gwh"
  | "supply_gwh"
  | "gap_gwh"
  | "gap_pct"
  | "ratio";

export const MAP_METRICS: { value: MapMetric; label: string; unit: string }[] = [
  { value: "demand_gwh", label: "Electricity Demand", unit: "GWh" },
  { value: "supply_gwh", label: "Local Generation", unit: "GWh" },
  { value: "gap_gwh", label: "Regional Accounting Gap", unit: "GWh" },
  { value: "gap_pct", label: "Accounting Gap % of Demand", unit: "%" },
  { value: "ratio", label: "Local Gen / Demand Ratio", unit: "×" },
];

export function metricValue(province: ProvinceRecord, year: number, metric: MapMetric): number {
  const point = province.series.find((item) => item.year === year);
  if (!point) return Number.NaN;
  switch (metric) {
    case "demand_gwh": return point.demand_gwh;
    case "supply_gwh": return point.supply_gwh;
    case "gap_gwh": return point.gap_gwh;
    case "gap_pct": return point.gap_pct;
    case "ratio": return point.ratio;
  }
}

export function fmt(value: number | null | undefined, unit = ""): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  const suffix = unit ? ` ${unit}` : "";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M${suffix}`;
  if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}k${suffix}`;
  if (Number.isInteger(value)) return `${value.toLocaleString("en-US")}${suffix}`;
  return `${value.toFixed(2)}${suffix}`;
}

export function fmtPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  return `${value.toFixed(digits)}%`;
}

export function qualityLabel(quality: QualityLevel): string {
  switch (quality) {
    case "observed": return "Observed complete";
    case "interpolated": return "Includes interpolation";
    case "forecast": return "Production forecast";
    case "incomplete": return "Incomplete";
  }
}

export function attentionLabel(reason: string | null): string {
  switch (reason) {
    case "defisit_tinggi": return "Large negative accounting gap";
    case "surplus_tinggi_perlu_interpretasi_interkoneksi": return "Large positive accounting gap — interpret with interconnection";
    case "gap_tidak_lengkap": return "Incomplete demand–supply pair";
    default: return reason ?? "No attention flag";
  }
}

export const MODEL_SUMMARY = RAW.models;
export const DASHBOARD_METADATA = RAW.metadata;
export const DASHBOARD_METADATA_V2 = RAW.metadata_v2;
