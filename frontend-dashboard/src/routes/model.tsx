// ECADIN_PHASE3L7_1_PRODUCTION_MODELS_METHOD_REFINEMENT_V1
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel, KpiCard } from "@/components/panel";
import {
  DATASET_INFO,
  FORECAST_START,
  MODEL_SUMMARY,
  ModelSummary,
} from "@/lib/energy-data";

export const Route = createFileRoute("/model")({
  head: () => ({
    meta: [
      { title: "Production Models · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "Production forecasting models for distributed electricity and local generation, including targets, validation design, model versions, and supported evaluation measures.",
      },
    ],
  }),
  component: ModelPage,
});

const FORECAST_END = DATASET_INFO.period[1];
const FORECAST_HORIZON = `${FORECAST_START}–${FORECAST_END}`;

function ModelPage() {
  const demandModel = MODEL_SUMMARY.find((model) => model.side === "demand");
  const supplyModel = MODEL_SUMMARY.find((model) => model.side === "supply");

  if (!demandModel || !supplyModel) {
    return (
      <AppShell
        title="Production Models"
        subtitle="Production model registry, validation design, and supported reporting"
      >
        <Panel title="Model registry unavailable">
          <p className="text-sm leading-relaxed text-muted-foreground">
            The frontend dataset does not contain both production-model registry entries.
          </p>
        </Panel>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Production Models"
      subtitle="Production model registry, validation design, and supported reporting"
    >
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Distributed Electricity Model"
            value={displayModelName(demandModel)}
          />
          <KpiCard
            label="Local Generation Model"
            value={displayModelName(supplyModel)}
          />
          <KpiCard label="Forecast Horizon" value={FORECAST_HORIZON} />
          <KpiCard
            label="Modeling Regions"
            value={String(DATASET_INFO.regionCount)}
          />
        </div>

        <ModelSection model={demandModel} />
        <ModelSection model={supplyModel} />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Panel
            title="Validation Design"
            subtitle="Out-of-sample evaluation used for production-model assessment"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <ValidationCard
                title="Rolling One-Step"
                rows={[
                  ["Target years", "2019–2024"],
                  ["Forecast horizon", "1 year"],
                  ["Purpose", "Near-term stability"],
                ]}
              />
              <ValidationCard
                title="Recursive Multi-Step"
                rows={[
                  ["Origins", "2018–2021"],
                  ["Maximum horizon", "3 years"],
                  ["Purpose", "Forecast-path robustness"],
                ]}
              />
            </div>
          </Panel>

          <Panel
            title="Supported Performance Measures"
            subtitle="Measures supported by the current forecasting methodology"
          >
            <div className="flex flex-wrap gap-2">
              {[
                "Macro sMAPE",
                "Macro MASE",
                "Micro RMSE",
                "Aggregate Bias",
                "Challenger Win Rate vs Drift",
              ].map((metric) => (
                <span
                  key={metric}
                  className="rounded-full border border-border bg-muted/35 px-3 py-1.5 text-xs font-medium text-foreground"
                >
                  {metric}
                </span>
              ))}
            </div>
            <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
              Metric values will be displayed after the production-metric outputs are
              integrated into the frontend data contract. Challenger win rate is used
              during model comparison against the Drift benchmark and is not interpreted
              as a standalone accuracy measure for the active Drift model.
            </p>
          </Panel>
        </div>

        <Panel title="Validation and Reporting Note">
          <p className="text-sm leading-relaxed text-muted-foreground">
            Production models are evaluated using rolling one-step and recursive
            multi-step backtesting. Supported evaluation measures include sMAPE, MASE,
            RMSE, aggregate bias, and challenger comparisons against the Drift benchmark.
            Generic R², unsupported feature-importance displays, and unvalidated regional
            uncertainty intervals are intentionally excluded from the production
            dashboard.
          </p>
        </Panel>
      </div>
    </AppShell>
  );
}

function ModelSection({ model }: { model: ModelSummary }) {
  const details = getModelDetails(model);

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
          Active · {displayModelName(model)}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Model" value={displayModelName(model)} />
        <KpiCard label="Status" value={sentenceCase(model.status)} />
        <KpiCard label="Target" value={details.targetShort} />
        <KpiCard label="Forecast Horizon" value={FORECAST_HORIZON} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Model Summary">
          <dl className="space-y-3 text-sm">
            <RegistryRow label="Model version" value={model.model_version} mono />
            <RegistryRow label="Target" value={details.targetLong} />
            <RegistryRow
              label="Geography"
              value={`${DATASET_INFO.regionCount} harmonized modeling regions`}
            />
            <RegistryRow label="Selection basis" value={details.selectionBasis} />
            <RegistryRow label="Input" value={details.input} />
            <RegistryRow
              label="Regional intervals"
              value={
                model.regional_uncertainty_display_allowed
                  ? "Published"
                  : "Not published"
              }
            />
          </dl>
        </Panel>

        <Panel title="Why This Model Is Used">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {details.explanation}
          </p>
          <div className="mt-4 rounded-md border border-border bg-muted/25 p-3 text-xs leading-relaxed text-muted-foreground">
            <span className="font-semibold text-foreground">Interpretation:</span>{" "}
            {details.interpretation}
          </div>
        </Panel>
      </div>
    </section>
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
      <dd className={mono ? "break-all font-mono text-xs font-medium" : "font-medium"}>
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

function displayModelName(model: ModelSummary): string {
  if (model.model_version.toLowerCase().includes("drift_v1")) {
    return "Drift V1";
  }

  return sentenceCase(model.active_model);
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
      selectionBasis: "Rolling and recursive out-of-sample backtesting",
      input: "Historical distributed-electricity series by harmonized region",
      explanation:
        "Drift extrapolates the average annual change implied by the first and latest observations in each regional historical series. It was retained because it provided stable out-of-sample performance under the current short annual dataset and validation protocol, while more complex challenger models did not demonstrate a sufficiently consistent improvement.",
      interpretation:
        "This is a simple annual time-series forecast. Its production value comes from validation stability and transparent behavior rather than model complexity.",
    };
  }

  return {
    scopeLabel: "Local Generation Production Forecast",
    sectionTitle: "Local Generation Model",
    targetShort: "Local Generation",
    targetLong: "Annual local electricity generation (GWh)",
    selectionBasis: "Nested robustness validation",
    input: "Historical local-generation series by harmonized region",
    explanation:
      "Drift V1 extrapolates the average annual change implied by the first and latest observations in each regional local-generation series. It was retained after challenger models did not demonstrate sufficiently robust improvement under nested validation. The V1 designation identifies the validated production implementation used by the dashboard.",
    interpretation:
      "Local generation is not total available electricity supply. Interregional electricity flows and operational adequacy are outside the model target.",
  };
}
