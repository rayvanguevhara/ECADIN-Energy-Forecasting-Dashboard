import rawData from "@/data/dashboard-production.json";

export type GapCategory =
  | "jauh_di_atas_demand"
  | "di_atas_demand"
  | "relatif_seimbang"
  | "di_bawah_demand"
  | "jauh_di_bawah_demand"
  | "tidak_tersedia";

export type QualityLevel = "observed" | "interpolated" | "forecast" | "incomplete";
export type YoYBasis =
  | "first_year"
  | "partial_overlap_matched"
  | "matched_complete_regions";

export type GapCategoryMetaEntry = {
  shortLabel: string;
  label: string;
  fullLabel: string;
  color: string;
  comparison: string;
  description: string;
};

export const GAP_CATEGORY_ORDER: GapCategory[] = [
  "jauh_di_atas_demand",
  "di_atas_demand",
  "relatif_seimbang",
  "di_bawah_demand",
  "jauh_di_bawah_demand",
  "tidak_tersedia",
];

export const GAP_CATEGORY_META: Record<GapCategory, GapCategoryMetaEntry> = {
  jauh_di_atas_demand: {
    shortLabel: "Far Above",
    label: "Far above distributed electricity",
    fullLabel: "Far Above Distributed Electricity",
    color: "#2563EB",
    comparison: "≥ +20% vs distributed",
    description: "Local generation is at least 20% above distributed electricity.",
  },
  di_atas_demand: {
    shortLabel: "Above",
    label: "Above distributed electricity",
    fullLabel: "Above Distributed Electricity",
    color: "#38BDF8",
    comparison: "+5% to < +20%",
    description: "Local generation is 5% to below 20% above distributed electricity.",
  },
  relatif_seimbang: {
    shortLabel: "Balanced",
    label: "Relatively balanced",
    fullLabel: "Relatively Balanced",
    color: "#94A3B8",
    comparison: "> −5% to < +5%",
    description: "Local generation and distributed electricity differ by less than 5%.",
  },
  di_bawah_demand: {
    shortLabel: "Below",
    label: "Below distributed electricity",
    fullLabel: "Below Distributed Electricity",
    color: "#F59E0B",
    comparison: "> −20% to ≤ −5%",
    description: "Local generation is 5% to below 20% below distributed electricity.",
  },
  jauh_di_bawah_demand: {
    shortLabel: "Far Below",
    label: "Far below distributed electricity",
    fullLabel: "Far Below Distributed Electricity",
    color: "#EA580C",
    comparison: "≤ −20% vs distributed",
    description: "Local generation is at least 20% below distributed electricity.",
  },
  tidak_tersedia: {
    shortLabel: "Unavailable",
    label: "Unavailable",
    fullLabel: "Unavailable",
    color: "#64748B",
    comparison: "Incomplete regional pair",
    description:
      "A complete distributed-electricity and local-generation pair is unavailable for this region and year.",
  },
};

export function classifyGap(gapPct: number | null | undefined): GapCategory {
  if (gapPct == null || !Number.isFinite(gapPct)) return "tidak_tersedia";
  if (gapPct >= 20) return "jauh_di_atas_demand";
  if (gapPct >= 5) return "di_atas_demand";
  if (gapPct > -5) return "relatif_seimbang";
  if (gapPct > -20) return "di_bawah_demand";
  return "jauh_di_bawah_demand";
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
  gap_category?: GapCategory;
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
  yoy_common_regions: number | null;
  yoy_basis: YoYBasis;
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
  model_label: string;
  evaluated_backtest_model_count: number;
  rolling_prediction_count: number | null;
  rolling_macro_smape_percent: number | null;
  rolling_macro_mase: number | null;
  rolling_micro_rmse_gwh: number | null;
  rolling_aggregate_bias_percent: number | null;
  recursive_prediction_count: number | null;
  recursive_macro_smape_percent: number | null;
  recursive_macro_mase: number | null;
  recursive_micro_rmse_gwh: number | null;
  recursive_aggregate_bias_percent: number | null;
  break_year: number | null;
  ridge_lambda: number | null;
  damping_phi: number | null;
  national_start_year: number | null;
}

export interface QualityFlagSummaryRow {
  dataset_id: string;
  issue_type: string;
  quality_status: string;
  flag_count: number;
  first_year: number | null;
  last_year: number | null;
  affected_regions: number;
}

export interface QualityFlagHighlightRow {
  dataset_id: string;
  region_id: string | null;
  display_name: string | null;
  year: number | null;
  variable_name: string;
  quality_status: string;
  issue_type: string;
  observed_value: number | null;
  comparison_value: number | null;
  metric_value: number | null;
  treatment: string;
  note: string;
}

export interface ProtocolMetrics {
  prediction_count: number | null;
  macro_smape_percent: number | null;
  macro_mase: number | null;
  micro_rmse_gwh: number | null;
  aggregate_bias_percent: number | null;
}

export interface DashboardMethodology {
  schema_version: string;
  definitions: {
    demand: string;
    supply: string;
    accounting_difference: string;
  };
  production_models: {
    demand: string;
    demand_model_id: string;
    demand_active_model: string;
    demand_specification: {
      model_class: string;
      formula: string;
      evaluated_backtest_models: number;
      rolling_metrics: ProtocolMetrics | null;
      recursive_metrics: ProtocolMetrics | null;
      selection_basis: string;
    };
    supply: string;
    supply_model_id: string;
    supply_active_model: string;
    supply_specification: {
      model_class: string;
      formula: string;
      parameters: Record<string, number>;
      evaluated_backtest_models: number;
      rolling_metrics: ProtocolMetrics | null;
      recursive_metrics: ProtocolMetrics | null;
      selection_basis: string;
    };
    frequency: string;
    historical_period: string;
    forecast_period: string;
  };
  validation: {
    rolling_one_step_targets: string;
    recursive_origins: string;
    recursive_max_horizon: number;
    evaluated_models: {
      demand_count: number;
      demand_models: string[];
      supply_count: number;
      supply_models: string[];
    };
    metrics: string[];
  };
  data_treatment: Record<string, string>;
  phase2_benchmark_summary: {
    total_evaluated_models: number;
    supply_candidates_evaluated: number;
    demand_candidates_evaluated: number;
    supply_selection: {
      selected_model: string;
      selected_model_id: string;
      rolling_one_step_smape_percent: number;
      recursive_h3_smape_percent: number;
      recursive_win_rate_vs_drift_percent: number;
      post_2021_clean_origins_smape_percent: number;
      national_2030_projection_gwh: number;
      national_2024_2030_cagr_percent: number;
    };
    demand_selection: {
      selected_model: string;
      selected_model_id: string;
      rolling_one_step_smape_percent: number;
      recursive_h3_smape_percent: number;
      extended_h4_h6_smape_percent: number;
      national_2030_projection_gwh: number;
      national_2024_2030_cagr_percent: number;
    };
  };
  adr_001_data_governance: {
    reference: string;
    snapshot_policy: string;
    pdf_audit_2020_2024: {
      total_cells_audited: number;
      exact_match: number;
      revision_candidate: number;
      canonical_missing_pdf_zero: number;
      demand_2020_2024_exact: string;
      supply_2021_2024_exact: string;
    };
    regime_shift_2021_stpl: string;
    kr_2020_anomaly: string;
    bt_jk_boundary_shift_2015_2017: string;
    missing_year_2016: string;
  };
  uncertainty_calibration_k3: {
    method: string;
    log_shift_gwh: number;
    size_buckets: string[];
    filtering_rules: string;
    horizon_extrapolation: string;
    national_q95_suppression: string;
    regional_uncertainty_display_allowed: boolean;
    ui_policy: string;
  };
  contract_clarifications: {
    legacy_ridge_used: {
      value: boolean;
      meaning: string;
    };
    national_yoy_basis: {
      method: string;
      description: string;
    };
  };
  geography: string;
  accounting_disclaimer: string;
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
  legacy_ridge_clarification: string;
  provinces: RawProvince[];
  national: RawNationalPoint[];
  models: ModelSummary[];
  quality_flags_total: number;
  quality_flags_summary: QualityFlagSummaryRow[];
  quality_flags_highlights: QualityFlagHighlightRow[];
  methodology: DashboardMethodology;
  metadata: { bagian: string; penjelasan: string }[];
  metadata_v2: Record<string, string>;
};

const RAW = rawData as unknown as ProductionPayload;
const asNumber = (value: number | null): number =>
  value == null ? Number.NaN : value;

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
  legacyRidgeClarification: RAW.legacy_ridge_clarification,
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
  gapCategory: GapCategory;
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
  gapCategory: point.gap_category ?? classifyGap(point.gap_pct),
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

export const ISLANDS = Array.from(
  new Set(PROVINCE_DATA.map((province) => province.island)),
);

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
  yoyCommonRegions: number | null;
  yoyBasis: YoYBasis;
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
  yoyCommonRegions: point.yoy_common_regions,
  yoyBasis: point.yoy_basis,
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

export function metricValue(
  province: ProvinceRecord,
  year: number,
  metric: MapMetric,
): number {
  const point = province.series.find((item) => item.year === year);
  if (!point) return Number.NaN;
  switch (metric) {
    case "demand_gwh":
      return point.demand_gwh;
    case "supply_gwh":
      return point.supply_gwh;
    case "gap_gwh":
      return point.gap_gwh;
    case "gap_pct":
      return point.gap_pct;
    case "ratio":
      return point.ratio;
  }
}

export function fmt(value: number | null | undefined, unit = ""): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  const suffix = unit ? ` ${unit}` : "";
  if (Math.abs(value) >= 1_000_000)
    return `${(value / 1_000_000).toFixed(1)}M${suffix}`;
  if (Math.abs(value) >= 1_000)
    return `${(value / 1_000).toFixed(1)}k${suffix}`;
  if (Number.isInteger(value))
    return `${value.toLocaleString("en-US")}${suffix}`;
  return `${value.toFixed(2)}${suffix}`;
}

export function formatSignedEnergy(
  value: number | null | undefined,
  withUnit = false,
): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  const body = fmt(Math.abs(value));
  return `${sign}${body}${withUnit ? " GWh" : ""}`;
}

export function fmtPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  return `${value.toFixed(digits)}%`;
}

export function formatSignedPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits)}%`;
}

export function qualityLabel(quality: QualityLevel): string {
  switch (quality) {
    case "observed":
      return "Observed complete";
    case "interpolated":
      return "Includes interpolation";
    case "forecast":
      return "Production forecast";
    case "incomplete":
      return "Incomplete";
  }
}

export function attentionLabel(reason: string | null | undefined): string {
  switch (reason) {
    case "jauh_di_bawah_demand_perlu_konteks_interkoneksi":
      return "Large negative accounting difference — interpret with interconnection";
    case "jauh_di_atas_demand_perlu_konteks_interkoneksi":
      return "Large positive accounting difference — interpret with interconnection";
    case "gap_tidak_lengkap":
      return "Incomplete distributed-electricity / local-generation pair";
    case null:
    case undefined:
    case "":
      return "No attention flag";
    default:
      return reason.replaceAll("_", " ");
  }
}

export const MODEL_SUMMARY = RAW.models;
export const QUALITY_FLAGS_TOTAL = RAW.quality_flags_total ?? 0;
export const QUALITY_FLAGS_SUMMARY = RAW.quality_flags_summary ?? [];
export const QUALITY_FLAGS_HIGHLIGHTS = RAW.quality_flags_highlights ?? [];
export const DASHBOARD_METHODOLOGY = RAW.methodology;
export const DASHBOARD_METADATA = RAW.metadata;
export const DASHBOARD_METADATA_V2 = RAW.metadata_v2;

export function modelDisplayName(
  idOrName?: string | null,
  side?: "demand" | "supply",
): string {
  let raw = String(idOrName ?? "").trim();
  if (!raw && side) {
    const entry = MODEL_SUMMARY.find((item) => item.side === side);
    raw = entry?.active_model || entry?.model_version || "";
  }
  const normalized = raw.toLowerCase();
  if (
    normalized === "national_reconciled_supply" ||
    normalized === "supply_production_national_reconciled_v2" ||
    normalized.includes("national_reconciled")
  ) {
    return "National Reconciled Supply (V2)";
  }
  if (normalized === "drift" || normalized === "demand_production_drift") {
    return "Regional Drift (V1)";
  }
  if (!raw) {
    return side === "supply"
      ? "National Reconciled Supply (V2)"
      : "Regional Drift (V1)";
  }
  return raw
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
