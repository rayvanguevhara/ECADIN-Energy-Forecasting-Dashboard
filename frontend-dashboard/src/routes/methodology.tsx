// ECADIN_PHASE3L9_2_METHODOLOGY_TARGET_LABEL_REFINEMENT_V1
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";
import {
  DASHBOARD_METADATA,
  DASHBOARD_METADATA_V2,
  DASHBOARD_METHODOLOGY,
  DATASET_INFO,
  FORECAST_START,
  MODEL_SUMMARY,
  modelDisplayName,
} from "@/lib/energy-data";

const PERIOD_START = DATASET_INFO.period[0];
const FORECAST_END = DATASET_INFO.period[1];

export const Route = createFileRoute("/methodology")({
  head: () => ({
    meta: [
      { title: "Methodology · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "Definitions, Demand Drift vs Supply V2 hierarchical formulas, ADR-001 BPS/ESDM governance, K-3 uncertainty calibration, and interpretation caveats.",
      },
    ],
  }),
  component: MethodologyPage,
});

function MethodologyPage() {
  const pm = DASHBOARD_METHODOLOGY.production_models;
  const val = DASHBOARD_METHODOLOGY.validation;
  const adr = DASHBOARD_METHODOLOGY.adr_001_data_governance;
  const k3 = DASHBOARD_METHODOLOGY.uncertainty_calibration_k3;
  const clarifications = DASHBOARD_METHODOLOGY.contract_clarifications;
  const supplyParams = pm.supply_specification.parameters;
  const supplyModelRow = MODEL_SUMMARY.find((m) => m.side === "supply");

  const demandName = modelDisplayName(pm.demand_model_id, "demand");
  const supplyName = modelDisplayName(pm.supply_model_id, "supply");

  return (
    <AppShell
      title="Methodology"
      subtitle="Production forecasting formulas (Demand Drift & Supply V2), ADR-001 data governance, K-3 calibration, and interpretation safeguards"
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Distributed Electricity Definition">
          <p className="text-sm leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">
              Distributed electricity
            </span>{" "}
            is the annual electricity distributed to customers within a
            harmonized modeling region, reported in gigawatt-hours (GWh).
            Historical values cover {pm.historical_period}. Production forecasts
            for {pm.forecast_period} use the{" "}
            <strong className="text-foreground">{demandName}</strong> model (
            <code className="font-mono text-xs">{pm.demand_model_id}</code>).
          </p>
        </Panel>

        <Panel title="Local Generation Definition">
          <p className="text-sm leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">
              Local generation
            </span>{" "}
            is the annual electricity generated within the same harmonized
            region, reported in GWh. It does not represent total electricity
            available to the region because interregional imports, exports, and
            power-system flows are outside the model target. Production
            forecasts use{" "}
            <strong className="text-foreground">{supplyName}</strong> (
            <code className="font-mono text-xs">{pm.supply_model_id}</code>).
          </p>
        </Panel>

        <Panel title="Distributed Electricity Formula · Univariate Regional Drift">
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Regional Endpoint Slope & Extrapolation
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-background/60 p-4 font-mono text-xs leading-relaxed">
{`slope_i = (y_{i,T} − y_{i,t0}) / (T − t0)
ŷ_{i,T+h} = max(0, y_{i,T} + h × slope_i)`}
              </pre>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {pm.demand_specification.model_class}. Applied independently per
              harmonized region between the first usable observation{" "}
              <code className="font-mono">t0</code> and forecast origin{" "}
              <code className="font-mono">T</code>.{" "}
              {pm.demand_specification.selection_basis}
            </p>
          </div>
        </Panel>

        <Panel title="Local Generation Formula · Supply V2 (National Reconciled)">
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                3-Stage Hierarchical + FWL Step-Intervention Damped
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-background/60 p-4 font-mono text-xs leading-relaxed">
{`1. National Drift (t ≥ ${supplyParams.national_start_year ?? 2013}):
   Ŷ_nat(T+h) = max(0, Y_T + h × (Y_T − Y_${supplyParams.national_start_year ?? 2013}) / (T − ${supplyParams.national_start_year ?? 2013}))
2. Regional FWL Step-Intervention (break I(t ≥ ${supplyParams.break_year ?? 2021}), λ=${supplyParams.ridge_lambda ?? 25}, φ=${supplyParams.damping_phi ?? 0.85}):
   b_reg,i = S_{ty,i} / (S_{tt,i} + λ)   [pre/post-break demeaned]
   ỹ_{i,T+h} = max(0, y_{i,T} + b_reg,i × Σ_{j=1..h} φ^j)
3. Proportional Reconciliation:
   ŷ_{i,T+h} = Ŷ_nat(T+h) × ỹ_{i,T+h} / Σ_k ỹ_{k,T+h}`}
              </pre>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {pm.supply_specification.model_class}. Removes the 2021 STPL
              administrative jump via FWL demeaning while anchoring the
              34-region sum to the zero-sum-invariant national growth trajectory.
            </p>
          </div>
        </Panel>

        <Panel title="Active Model Classes & Variables">
          <dl className="space-y-0 text-sm">
            <MethodRow
              label="Demand model class"
              value={pm.demand_specification.model_class}
            />
            <MethodRow
              label="Supply model class"
              value={pm.supply_specification.model_class}
            />
            <MethodRow
              label="Supply V2 parameters"
              value={
                supplyModelRow?.break_year != null
                  ? `break_year=${supplyModelRow.break_year}, ridge_lambda=${supplyModelRow.ridge_lambda}, damping_phi=${supplyModelRow.damping_phi}, national_start_year=${supplyModelRow.national_start_year}`
                  : "N/A"
              }
            />
            <MethodRow
              label="Exogenous predictors (X)"
              value="None in production (step dummy I(t ≥ 2021) is deterministic)"
            />
            <MethodRow
              label="National YoY growth"
              value={clarifications.national_yoy_basis.description}
            />
          </dl>

          <div className="mt-3 rounded-md border border-border bg-background/40 p-3 text-xs leading-relaxed text-muted-foreground">
            <span className="font-semibold text-foreground">
              legacy_ridge_used = {String(clarifications.legacy_ridge_used.value)}:
            </span>{" "}
            {clarifications.legacy_ridge_used.meaning}
          </div>
        </Panel>

        <Panel title="Production Forecasting Approach">
          <dl className="space-y-0 text-sm">
            <MethodRow label="Historical period" value={pm.historical_period} />
            <MethodRow label="Forecast horizon" value={pm.forecast_period} />
            <MethodRow
              label="Modeling geography"
              value={`${DATASET_INFO.regionCount} harmonized regions`}
            />
            <MethodRow label="Frequency" value={pm.frequency} />
            <MethodRow
              label="Distributed electricity model"
              value={`${demandName} (${pm.demand_model_id})`}
            />
            <MethodRow
              label="Local generation model"
              value={`${supplyName} (${pm.supply_model_id})`}
            />
            <MethodRow
              label="Regional uncertainty intervals"
              value={
                DASHBOARD_METADATA_V2.regional_uncertainty === "not_published"
                  ? "Not published (K-3 internal calibration only)"
                  : DASHBOARD_METADATA_V2.regional_uncertainty
              }
            />
          </dl>
        </Panel>

        <Panel
          title="ADR-001 Data Governance & BPS/ESDM Regime Shifts"
          subtitle={`Snapshot freeze policy (${adr.reference}) & primary documentary verification across ${adr.pdf_audit_2020_2024.total_cells_audited} PDF cells`}
          className="lg:col-span-2"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2.5 text-xs leading-relaxed text-muted-foreground">
              <div className="rounded-md border border-border bg-background/40 p-3">
                <div className="font-semibold text-foreground">
                  Snapshot Freeze & PDF Audit (2020–2024)
                </div>
                <p className="mt-1">{adr.snapshot_policy}</p>
                <p className="mt-1 font-mono text-[11px] text-foreground/90">
                  {adr.pdf_audit_2020_2024.total_cells_audited} audited cells:{" "}
                  {adr.pdf_audit_2020_2024.exact_match} exact ·{" "}
                  {adr.pdf_audit_2020_2024.revision_candidate} revision
                  candidates ·{" "}
                  {adr.pdf_audit_2020_2024.canonical_missing_pdf_zero} YO 2020
                  (&apos;-&apos; vs &apos;–&apos;) · Demand{" "}
                  {adr.pdf_audit_2020_2024.demand_2020_2024_exact} · Supply{" "}
                  {adr.pdf_audit_2020_2024.supply_2021_2024_exact}.
                </p>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <div className="font-semibold text-foreground">
                  2021 STPL Questionnaire Shift & ESDM Cross-Check
                </div>
                <p className="mt-1">{adr.regime_shift_2021_stpl}</p>
              </div>
            </div>

            <div className="space-y-2.5 text-xs leading-relaxed text-muted-foreground">
              <div className="rounded-md border border-border bg-background/40 p-3">
                <div className="font-semibold text-foreground">
                  KR 2020 Anomaly (PT PLN Batam)
                </div>
                <p className="mt-1">{adr.kr_2020_anomaly}</p>
              </div>
              <div className="rounded-md border border-border bg-background/40 p-3">
                <div className="font-semibold text-foreground">
                  BT/JK Boundary (2015–2017) & Missing 2016
                </div>
                <p className="mt-1">{adr.bt_jk_boundary_shift_2015_2017}</p>
                <p className="mt-1">{adr.missing_year_2016}</p>
              </div>
            </div>
          </div>
        </Panel>

        <Panel
          title="Uncertainty Calibration (K-3) & Interval Governance"
          subtitle={k3.method}
        >
          <dl className="space-y-0 text-sm">
            <MethodRow
              label="Log-shift constant"
              value={`LOG_SHIFT_GWH = ${k3.log_shift_gwh} GWh`}
            />
            <MethodRow
              label="Size buckets"
              value={k3.size_buckets.join(", ")}
            />
            <MethodRow label="Sample filtering" value={k3.filtering_rules} />
            <MethodRow
              label="Horizon scaling"
              value={k3.horizon_extrapolation}
            />
            <MethodRow
              label="National q95 policy"
              value={k3.national_q95_suppression}
            />
            <MethodRow label="Dashboard UI policy" value={k3.ui_policy} />
          </dl>
        </Panel>

        <Panel title="Validation Design & Metrics">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-background/40 p-4">
              <div className="font-display text-sm font-semibold">
                Rolling One-Step
              </div>
              <dl className="mt-3 space-y-2 text-xs">
                <CompactRow
                  label="Target years"
                  value={val.rolling_one_step_targets}
                />
                <CompactRow label="Forecast horizon" value="1 year" />
                <CompactRow
                  label="Models (D/S)"
                  value={`${val.evaluated_models.demand_count} / ${val.evaluated_models.supply_count}`}
                />
              </dl>
            </div>

            <div className="rounded-md border border-border bg-background/40 p-4">
              <div className="font-display text-sm font-semibold">
                Recursive Multi-Step
              </div>
              <dl className="mt-3 space-y-2 text-xs">
                <CompactRow label="Origins" value={val.recursive_origins} />
                <CompactRow
                  label="Maximum horizon"
                  value={`${val.recursive_max_horizon} years`}
                />
                <CompactRow label="Purpose" value="Forecast-path robustness" />
              </dl>
            </div>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Supported evaluation measures: {val.metrics.join(", ")}.
          </p>
        </Panel>

        <Panel title="Accounting Difference Formula">
          <div className="space-y-3">
            <FormulaBlock
              label="Accounting Difference (GWh)"
              formula="Local Generation − Distributed Electricity"
            />
            <FormulaBlock
              label="Accounting Difference (%)"
              formula="Accounting Difference / Distributed Electricity × 100"
            />
            <FormulaBlock
              label="Local Generation Ratio"
              formula="Local Generation / Distributed Electricity"
            />
          </div>

          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Positive and negative values are spatial accounting differences. They
            do not represent operational surplus, shortage, reserve margin, or
            blackout probability.
          </p>
        </Panel>

        <Panel title="Accounting Difference Categories">
          <dl className="space-y-2 text-sm text-muted-foreground">
            <CategoryRow label="Far Above Distributed Electricity" value="≥ +20%" />
            <CategoryRow
              label="Above Distributed Electricity"
              value="≥ +5% and < +20%"
            />
            <CategoryRow label="Relatively Balanced" value="> −5% and < +5%" />
            <CategoryRow
              label="Below Distributed Electricity"
              value="> −20% and ≤ −5%"
            />
            <CategoryRow label="Far Below Distributed Electricity" value="≤ −20%" />
            <CategoryRow label="Unavailable" value="Incomplete pair" />
          </dl>

          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            These boundaries follow the production classification exactly.
            Values equal to +5% are classified as Above, while values equal to
            −5% are classified as Below.
          </p>
        </Panel>

        <Panel
          title="Published Dashboard Metadata Registry"
          subtitle={`Synchronized directly from dashboard-production.json (${PERIOD_START}–${FORECAST_END})`}
          className="lg:col-span-2"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <dl className="space-y-1.5 text-xs">
              {DASHBOARD_METADATA.map((entry) => (
                <div
                  key={entry.bagian}
                  className="grid grid-cols-[125px_1fr] gap-2 border-b border-border/60 py-1.5 last:border-0"
                >
                  <dt className="font-medium text-foreground">{entry.bagian}</dt>
                  <dd className="text-muted-foreground">{entry.penjelasan}</dd>
                </div>
              ))}
            </dl>
            <div className="rounded-md border border-border bg-background/40 p-3">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                metadata_v2 Contract Keys
              </div>
              <dl className="grid grid-cols-1 gap-1.5 font-mono text-[11px] sm:grid-cols-2">
                {Object.entries(DASHBOARD_METADATA_V2).map(([key, value]) => (
                  <div
                    key={key}
                    className="rounded border border-border/60 bg-card/40 px-2 py-1"
                  >
                    <dt className="text-[10px] text-muted-foreground">{key}</dt>
                    <dd className="truncate font-medium text-foreground" title={value}>
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </Panel>

        <Panel title="Interpretation Caveat" className="lg:col-span-2">
          <p className="text-sm leading-relaxed">
            <span className="font-semibold text-foreground">Important:</span>{" "}
            <span className="text-muted-foreground">
              The regional accounting difference is a spatial accounting proxy.
              Electricity may flow across interconnected regions; therefore,
              local generation below distributed electricity does not imply
              shortage or blackout risk, while local generation above
              distributed electricity does not imply freely available
              operational capacity. System-level utility planning data are
              required for adequacy, reliability, reserve margin, and investment
              decisions.
            </span>
          </p>
        </Panel>
      </div>
    </AppShell>
  );
}

function MethodRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b border-border py-2.5 last:border-0 sm:grid-cols-[190px_1fr] sm:gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-foreground">{value}</dd>
    </div>
  );
}

function CompactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium text-foreground">{value}</dd>
    </div>
  );
}

function FormulaBlock({ label, formula }: { label: string; formula: string }) {
  return (
    <div className="rounded-md border border-border bg-background/60 p-4">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-2 font-mono text-xs leading-relaxed text-foreground">
        {formula}
      </div>
    </div>
  );
}

function CategoryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 border-b border-border pb-2 last:border-0 sm:grid-cols-[1fr_auto] sm:gap-4">
      <dt>{label}</dt>
      <dd className="font-mono text-foreground">{value}</dd>
    </div>
  );
}
