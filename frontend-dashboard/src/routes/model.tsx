import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, KpiCard } from "@/components/panel";
import {
  DASHBOARD_METHODOLOGY,
  DATASET_INFO,
  FORECAST_START,
  MODEL_SUMMARY,
  ModelSummary,
  formatSignedPercent,
  modelDisplayName,
} from "@/lib/energy-data";

const FORECAST_END = DATASET_INFO.period[1];
const FORECAST_HORIZON = `${FORECAST_START}–${FORECAST_END}`;

export const Route = createFileRoute("/model")({
  head: () => ({
    meta: [
      { title: "Production Models · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "Production forecasting models for distributed electricity (Drift) and local generation (National Reconciled Supply V2), backtest metrics, Phase 2 benchmark summary, and hyperparameters.",
      },
    ],
  }),
  component: ModelPage,
});

function ModelPage() {
  const demandModel = MODEL_SUMMARY.find((model) => model.side === "demand");
  const supplyModel = MODEL_SUMMARY.find((model) => model.side === "supply");

  if (!demandModel || !supplyModel) {
    return (
      <AppShell
        title="Production Models"
        subtitle="Production model registry, backtest metrics, and benchmark evidence"
      >
        <Panel title="Model registry unavailable">
          <p className="text-sm leading-relaxed text-muted-foreground">
            The frontend dataset does not contain both production-model registry
            entries.
          </p>
        </Panel>
      </AppShell>
    );
  }

  const benchmark = DASHBOARD_METHODOLOGY.phase2_benchmark_summary;
  const validation = DASHBOARD_METHODOLOGY.validation;

  return (
    <AppShell
      title="Production Models"
      subtitle="Production model registry, Phase 2–3 benchmark performance, and active V2 configuration"
    >
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Distributed Electricity Model"
            value={modelDisplayName(demandModel.model_version, "demand")}
            delta={`${demandModel.evaluated_backtest_model_count} backtest models`}
          />
          <KpiCard
            label="Local Generation Model"
            value={modelDisplayName(supplyModel.model_version, "supply")}
            delta={`${supplyModel.evaluated_backtest_model_count} backtest models`}
          />
          <KpiCard
            label="Forecast Horizon"
            value={FORECAST_HORIZON}
            delta={`Historical ${DATASET_INFO.period[0]}–${FORECAST_START - 1}`}
          />
          <KpiCard
            label="Phase 2 Benchmark"
            value={`${benchmark.total_evaluated_models} models`}
            delta={`${benchmark.supply_candidates_evaluated} supply · ${benchmark.demand_candidates_evaluated} demand`}
          />
        </div>

        <Panel
          title="Production Backtest Performance Metrics"
          subtitle="Out-of-sample production summary from validated production_model_summary.csv · rolling one-step (2019–2024) & recursive multi-step h=1..3 (origins 2018–2021)"
        >
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full min-w-[780px] text-xs">
              <thead className="bg-background/50 text-[10px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="p-2.5 text-left">Domain & Active Model</th>
                  <th className="p-2.5 text-left">Protocol</th>
                  <th className="p-2.5 text-right">Backtest Models</th>
                  <th className="p-2.5 text-right">N</th>
                  <th className="p-2.5 text-right">Macro sMAPE</th>
                  <th className="p-2.5 text-right">Macro MASE</th>
                  <th className="p-2.5 text-right">Micro RMSE (GWh)</th>
                  <th className="p-2.5 text-right">Aggregate Bias</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {[demandModel, supplyModel].flatMap((m) => [
                  {
                    key: `${m.side}-rolling`,
                    domain:
                      m.side === "demand"
                        ? "Demand · Distributed Electricity"
                        : "Supply · Local Generation",
                    modelName: modelDisplayName(m.model_version, m.side),
                    protocol: `Rolling One-Step (${validation.rolling_one_step_targets})`,
                    evaluatedCount: m.evaluated_backtest_model_count,
                    n: m.rolling_prediction_count,
                    smape: m.rolling_macro_smape_percent,
                    mase: m.rolling_macro_mase,
                    rmse: m.rolling_micro_rmse_gwh,
                    bias: m.rolling_aggregate_bias_percent,
                  },
                  {
                    key: `${m.side}-recursive`,
                    domain:
                      m.side === "demand"
                        ? "Demand · Distributed Electricity"
                        : "Supply · Local Generation",
                    modelName: modelDisplayName(m.model_version, m.side),
                    protocol: `Recursive Multi-Step h=1..${validation.recursive_max_horizon} (${validation.recursive_origins})`,
                    evaluatedCount: m.evaluated_backtest_model_count,
                    n: m.recursive_prediction_count,
                    smape: m.recursive_macro_smape_percent,
                    mase: m.recursive_macro_mase,
                    rmse: m.recursive_micro_rmse_gwh,
                    bias: m.recursive_aggregate_bias_percent,
                  },
                ]).map((row) => (
                  <tr key={row.key} className="border-t border-border">
                    <td className="p-2.5">
                      <div className="font-medium text-foreground">
                        {row.modelName}
                      </div>
                      <div className="text-[10px] text-muted-foreground">
                        {row.domain}
                      </div>
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {row.protocol}
                    </td>
                    <td className="p-2.5 text-right">{row.evaluatedCount}</td>
                    <td className="p-2.5 text-right">{row.n ?? "N/A"}</td>
                    <td className="p-2.5 text-right font-medium text-foreground">
                      {row.smape != null ? `${row.smape.toFixed(2)}%` : "N/A"}
                    </td>
                    <td className="p-2.5 text-right">
                      {row.mase != null ? row.mase.toFixed(3) : "N/A"}
                    </td>
                    <td className="p-2.5 text-right">
                      {row.rmse != null
                        ? row.rmse.toLocaleString("en-US", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })
                        : "N/A"}
                    </td>
                    <td className="p-2.5 text-right">
                      {row.bias != null ? formatSignedPercent(row.bias, 2) : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Backtest evaluation counts differ across domains because Supply
            evaluates <strong>{supplyModel.evaluated_backtest_model_count}</strong>{" "}
            models (4 shared baselines +{" "}
            <code className="font-mono">national_reconciled_supply</code>, n=203
            rolling / n=406 recursive due to DI Yogyakarta missing 2020), while
            Demand evaluates{" "}
            <strong>{demandModel.evaluated_backtest_model_count}</strong>{" "}
            baseline models including the retained{" "}
            <code className="font-mono">drift</code> model (n=204 rolling /
            n=408 recursive).
          </p>
        </Panel>

        <ModelSection model={demandModel} />
        <ModelSection model={supplyModel} />

        <Panel
          title={`Phase 2 Benchmark Evidence (${benchmark.total_evaluated_models} Models Evaluated)`}
          subtitle={`Systematic out-of-sample comparison across ${benchmark.supply_candidates_evaluated} supply candidates and ${benchmark.demand_candidates_evaluated} demand candidates including extended horizon h=4..6`}
        >
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-muted/20 p-4">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Supply Selection · Phase 3 Promotion
              </div>
              <h3 className="mt-1 font-display text-sm font-semibold">
                {modelDisplayName(
                  benchmark.supply_selection.selected_model_id,
                  "supply",
                )}
              </h3>
              <dl className="mt-3 space-y-2 text-xs">
                <BenchmarkRow
                  label="Rolling one-step sMAPE"
                  value={`${benchmark.supply_selection.rolling_one_step_smape_percent.toFixed(2)}% (#1 of 14)`}
                />
                <BenchmarkRow
                  label="Recursive h=1..3 sMAPE"
                  value={`${benchmark.supply_selection.recursive_h3_smape_percent.toFixed(2)}% (win rate ${benchmark.supply_selection.recursive_win_rate_vs_drift_percent.toFixed(2)}% vs Drift)`}
                />
                <BenchmarkRow
                  label="Post-2021 clean origins (origin ≥ 2021)"
                  value={`${benchmark.supply_selection.post_2021_clean_origins_smape_percent.toFixed(2)}% (#1 of 14)`}
                />
                <BenchmarkRow
                  label="2030 national projection"
                  value={`${benchmark.supply_selection.national_2030_projection_gwh.toLocaleString("en-US")} GWh (+${benchmark.supply_selection.national_2024_2030_cagr_percent.toFixed(2)}% CAGR)`}
                />
              </dl>
            </div>

            <div className="rounded-lg border border-border bg-muted/20 p-4">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Demand Retention · Unchanged Baseline
              </div>
              <h3 className="mt-1 font-display text-sm font-semibold">
                {modelDisplayName(
                  benchmark.demand_selection.selected_model_id,
                  "demand",
                )}
              </h3>
              <dl className="mt-3 space-y-2 text-xs">
                <BenchmarkRow
                  label="Rolling one-step sMAPE"
                  value={`${benchmark.demand_selection.rolling_one_step_smape_percent.toFixed(2)}% (#1 of 12, with & without KR 2020)`}
                />
                <BenchmarkRow
                  label="Recursive h=1..3 sMAPE"
                  value={`${benchmark.demand_selection.recursive_h3_smape_percent.toFixed(2)}% (#1 of 12, no challenger > 50% win rate)`}
                />
                <BenchmarkRow
                  label="Extended horizon h=4..6 sMAPE"
                  value={`${benchmark.demand_selection.extended_h4_h6_smape_percent.toFixed(2)}% (#1 of 12)`}
                />
                <BenchmarkRow
                  label="2030 national projection"
                  value={`${benchmark.demand_selection.national_2030_projection_gwh.toLocaleString("en-US")} GWh (+${benchmark.demand_selection.national_2024_2030_cagr_percent.toFixed(2)}% CAGR)`}
                />
              </dl>
            </div>
          </div>
        </Panel>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel
            title="Validation Design & Evaluated Sets"
            subtitle="Zero-leakage backtesting protocol enforced in production validation"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <ValidationCard
                title="Rolling One-Step"
                rows={[
                  ["Target years", validation.rolling_one_step_targets],
                  ["Forecast horizon", "1 year"],
                  ["Demand / Supply models", `${validation.evaluated_models.demand_count} / ${validation.evaluated_models.supply_count}`],
                ]}
              />
              <ValidationCard
                title="Recursive Multi-Step"
                rows={[
                  ["Origins", validation.recursive_origins],
                  ["Maximum horizon", `${validation.recursive_max_horizon} years`],
                  ["Extended benchmark", "h=4..6 verified in Phase 2"],
                ]}
              />
            </div>
          </Panel>

          <Panel
            title="Contract Clarifications & Policy"
            subtitle="Explicit model governance and legacy Ridge disambiguation"
          >
            <div className="space-y-3 text-xs leading-relaxed text-muted-foreground">
              <div className="rounded-md border border-border bg-muted/20 p-3">
                <div className="font-mono text-[11px] font-semibold text-foreground">
                  legacy_ridge_used: {String(DATASET_INFO.legacyRidgeUsed)}
                </div>
                <p className="mt-1">{DATASET_INFO.legacyRidgeClarification}</p>
              </div>
              <p>
                Regional uncertainty intervals are calibrated internally via K-3
                shifted-log empirical quantiles (with national q95 suppressed at
                n=4 &lt; 10) and remain unpublished on the UI (
                <code className="font-mono">
                  regional_uncertainty_display_allowed ={" "}
                  {String(DATASET_INFO.regionalUncertaintyDisplayAllowed)}
                </code>
                ).
              </p>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}

function ModelSection({ model }: { model: ModelSummary }) {
  const details = getModelDetails(model);
  const displayName = modelDisplayName(model.model_version, model.side);
  const hasV2Params =
    model.break_year != null &&
    model.ridge_lambda != null &&
    model.damping_phi != null &&
    model.national_start_year != null;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            {details.scopeLabel}
          </div>
          <h2 className="mt-1 font-display text-xl font-semibold">
            {details.sectionTitle}
          </h2>
        </div>
        <div className="rounded-full border border-primary/60 px-3 py-1 text-xs text-primary">
          Active · {displayName}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Model" value={displayName} />
        <KpiCard label="Status" value={sentenceCase(model.status)} />
        <KpiCard label="Target" value={details.targetShort} />
        <KpiCard label="Forecast Horizon" value={FORECAST_HORIZON} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Model Summary & Active Parameters">
          <dl className="space-y-3 text-sm">
            <RegistryRow label="Model ID" value={model.model_version} mono />
            <RegistryRow label="Official label" value={model.model_label} />
            <RegistryRow label="Target" value={details.targetLong} />
            <RegistryRow
              label="Geography"
              value={`${DATASET_INFO.regionCount} harmonized modeling regions`}
            />
            <RegistryRow label="Selection basis" value={details.selectionBasis} />
            <RegistryRow label="Input" value={details.input} />
            {hasV2Params && (
              <RegistryRow
                label="V2 Hyperparameters"
                value={`break_year=${model.break_year}, ridge_lambda=${model.ridge_lambda}, damping_phi=${model.damping_phi}, national_start_year=${model.national_start_year}`}
                mono
              />
            )}
            <RegistryRow
              label="Regional intervals"
              value={
                model.regional_uncertainty_display_allowed
                  ? "Published"
                  : "Not published (internal K-3 calibration)"
              }
            />
          </dl>
        </Panel>

        <Panel title="Why This Model Is Used">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {details.explanation}
          </p>
          <div className="mt-4 rounded-md border border-border bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
            <span className="font-semibold text-foreground">
              Interpretation:
            </span>{" "}
            {details.interpretation}
          </div>
        </Panel>
      </div>
    </section>
  );
}

function BenchmarkRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/60 pb-1.5 last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium text-foreground tabular-nums">
        {value}
      </dd>
    </div>
  );
}

function RegistryRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[150px_1fr] gap-3 border-b border-border pb-2 last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className={
          mono ? "break-all font-mono text-xs font-medium" : "font-medium"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function ValidationCard({
  title,
  rows,
}: {
  title: string;
  rows: Array<[string, string]>;
}) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <h3 className="font-display text-sm font-semibold">{title}</h3>
      <dl className="mt-3 space-y-2 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="text-right font-medium text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function sentenceCase(value: string): string {
  if (!value) return "N/A";
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
}

function getModelDetails(model: ModelSummary) {
  if (model.side === "demand") {
    return {
      scopeLabel: "Distributed Electricity Production Forecast",
      sectionTitle: "Distributed Electricity Model",
      targetShort: "Distributed Electricity",
      targetLong: "Annual distributed electricity (GWh)",
      selectionBasis:
        "Phase 2 benchmark #1 across all protocols (rolling, recursive h=1..3, extended h=4..6)",
      input: "Univariate historical distributed-electricity series per region",
      explanation:
        "Regional Drift extrapolates the average annual linear change between the first and latest usable historical observations in each region, clipped non-negative. Across 12 demand candidates in Phase 2, it ranked #1 on Macro sMAPE and Macro MASE in rolling one-step (5.83%), recursive h=1..3 (8.14%), and extended h=4..6 (12.36%) both with and without the KR 2020 outlier.",
      interpretation:
        "Retained unchanged from V1 to V2 (byte-identical demand forecasts, 2030 national demand = 374,291.69 GWh, +3.40% CAGR).",
    };
  }

  return {
    scopeLabel: "Local Generation Production Forecast",
    sectionTitle: "Local Generation Model (V2)",
    targetShort: "Local Generation",
    targetLong: "Annual local electricity generation (GWh)",
    selectionBasis:
      "Phase 2 winner & Phase 3 promotion (replaces univariate regional Drift to resolve 2021 STPL shift distortion)",
    input:
      "34-region panel historical local-generation series (national aggregate t ≥ 2013 + regional FWL step-intervention)",
    explanation:
      "National Reconciled Supply (V2) combines a national-level Drift forecast over t ≥ 2013 (invariant to zero-sum interprovincial reallocations) with regional Frisch–Waugh–Lovell (FWL) step-intervention damped regressions that isolate the 2021 STPL administrative jump via I(t ≥ 2021), shrink regional slopes via Ridge damping (λ = 25.0) and geometric damping (φ = 0.85), and reconcile 34 regional forecasts proportionally to the national trajectory.",
    interpretation:
      "Local generation is not total available electricity supply. Eliminating the 2021 administrative jump bias reduces 2030 national supply from 415,450.20 GWh (V1) to 410,265.37 GWh (+2.98% CAGR) and stabilizes LA, BE, KT, SG, KS, SS, and JI.",
  };
}
