// ECADIN_PHASE3L9_2_METHODOLOGY_TARGET_LABEL_REFINEMENT_V1
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";

export const Route = createFileRoute("/methodology")({
  head: () => ({
    meta: [
      { title: "Methodology · ECADIN Energy Intelligence" },
      {
        name: "description",
        content:
          "Definitions, Drift forecasting formulas, model variables, validation design, accounting-difference categories, harmonized geography, and interpretation caveats.",
      },
    ],
  }),
  component: MethodologyPage,
});

function MethodologyPage() {
  return (
    <AppShell
      title="Methodology"
      subtitle="Production forecasting definitions, formulas, validation design, and interpretation safeguards"
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Distributed Electricity Definition">
          <p className="text-sm leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Distributed electricity</span> is the
            annual electricity distributed to customers within a harmonized modeling region,
            reported in gigawatt-hours (GWh). Historical values cover 2011–2024. Production
            forecasts for 2025–2030 use the regional Drift model.
          </p>
        </Panel>

        <Panel title="Local Generation Definition">
          <p className="text-sm leading-relaxed text-muted-foreground">
            <span className="font-medium text-foreground">Local generation</span> is the annual
            electricity generated within the same harmonized region, reported in GWh. It does not
            represent total electricity available to the region because interregional imports,
            exports, and power-system flows are outside the model target. Production forecasts use
            Drift V1.
          </p>
        </Panel>

        <Panel title="Production Forecast Formula">
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Average Annual Change
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-background/60 p-4 font-mono text-xs leading-relaxed">
{`slope = (y_T − y_1) / (t_T − t_1)`}
              </pre>
            </div>

            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                Forecast
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-background/60 p-4 font-mono text-xs leading-relaxed">
{`ŷ_(T+h) = y_T + h × slope`}
              </pre>
            </div>

            <p className="text-xs leading-relaxed text-muted-foreground">
              Drift estimates the average annual change implied by the first and latest usable
              observations in each regional series, then extends that change into the forecast
              horizon. The calculation is applied separately to every harmonized region and
              separately to distributed electricity and local generation.
            </p>
          </div>
        </Panel>

        <Panel title="Active Model Variables">
          <dl className="space-y-0 text-sm">
            <MethodRow
              label="Distributed electricity target"
              value="Annual distributed electricity (GWh)"
            />
            <MethodRow
              label="Local generation target"
              value="Annual local generation (GWh)"
            />
            <MethodRow label="Time index" value="t = annual observation year" />
            <MethodRow label="Exogenous predictors (X)" value="None in production" />
            <MethodRow label="Model class" value="Univariate annual time-series models" />
          </dl>

          <p className="mt-3 rounded-md border border-border bg-background/40 p-3 text-xs leading-relaxed text-muted-foreground">
            Population, GRDP, inflation, technology mix, and other enriched variables were assessed
            in challenger experiments. They are not inputs to the active production forecasts.
          </p>
        </Panel>

        <Panel title="Production Forecasting Approach">
          <dl className="space-y-0 text-sm">
            <MethodRow label="Historical period" value="2011–2024" />
            <MethodRow label="Forecast horizon" value="2025–2030" />
            <MethodRow label="Modeling geography" value="34 harmonized regions" />
            <MethodRow label="Frequency" value="Annual" />
            <MethodRow label="Distributed electricity model" value="Drift" />
            <MethodRow label="Local generation model" value="Drift V1" />
            <MethodRow label="Regional uncertainty intervals" value="Not published" />
          </dl>
        </Panel>

        <Panel title="Validation Design">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-background/40 p-4">
              <div className="font-display text-sm font-semibold">Rolling One-Step</div>
              <dl className="mt-3 space-y-2 text-xs">
                <CompactRow label="Target years" value="2019–2024" />
                <CompactRow label="Forecast horizon" value="1 year" />
                <CompactRow label="Purpose" value="Near-term stability" />
              </dl>
            </div>

            <div className="rounded-md border border-border bg-background/40 p-4">
              <div className="font-display text-sm font-semibold">Recursive Multi-Step</div>
              <dl className="mt-3 space-y-2 text-xs">
                <CompactRow label="Origins" value="2018–2021" />
                <CompactRow label="Maximum horizon" value="3 years" />
                <CompactRow label="Purpose" value="Forecast-path robustness" />
              </dl>
            </div>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            Supported evaluation measures are macro sMAPE, macro MASE, micro RMSE, aggregate bias,
            and challenger win rate against the Drift benchmark.
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
            Positive and negative values are spatial accounting differences. They do not represent
            operational surplus, shortage, reserve margin, or blackout probability.
          </p>
        </Panel>

        <Panel title="Accounting Difference Categories">
          <dl className="space-y-2 text-sm text-muted-foreground">
            <CategoryRow label="Far Above Distributed Electricity" value="≥ +20%" />
            <CategoryRow label="Above Distributed Electricity" value="≥ +5% and < +20%" />
            <CategoryRow label="Relatively Balanced" value="> −5% and < +5%" />
            <CategoryRow label="Below Distributed Electricity" value="> −20% and ≤ −5%" />
            <CategoryRow label="Far Below Distributed Electricity" value="≤ −20%" />
            <CategoryRow label="Unavailable" value="Incomplete pair" />
          </dl>

          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            These boundaries follow the production classification exactly. Values equal to +5% are
            classified as Above, while values equal to −5% are classified as Below.
          </p>
        </Panel>

        <Panel title="Harmonized Geography">
          <p className="text-sm leading-relaxed text-muted-foreground">
            The dashboard uses 34 harmonized modeling regions. Papua Selatan, Papua Tengah, and
            Papua Pegunungan are represented within Papua, while Papua Barat Daya is represented
            within Papua Barat. Earlier Kalimantan Timur and Kalimantan Utara observations follow
            the audited geography-break treatment. Values are not duplicated across split
            provinces.
          </p>
        </Panel>

        <Panel title="Historical Data Treatment">
          <ul className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <li>
              • The 2016 historical distributed-electricity and local-generation pairs include
              audited interpolation for continuity. They are explicitly identified as interpolated
              and are not treated as observed values.
            </li>
            <li>
              • Nine historical pairs remain incomplete: DI Yogyakarta in 2011–2014 and 2020, plus
              Kalimantan Timur and Kalimantan Utara in 2011–2012.
            </li>
            <li>• Missing historical values are preserved and are never converted to zero.</li>
            <li>• Forecast years 2025–2030 contain 204 complete region-year pairs.</li>
          </ul>
        </Panel>

        <Panel title="Interpretation Caveat" className="lg:col-span-2">
          <p className="text-sm leading-relaxed">
            <span className="font-semibold text-foreground">Important:</span>{" "}
            <span className="text-muted-foreground">
              The regional accounting difference is a spatial accounting proxy. Electricity may
              flow across interconnected regions; therefore, local generation below distributed
              electricity does not imply shortage or blackout risk, while local generation above
              distributed electricity does not imply freely available operational capacity.
              System-level utility planning data are required for adequacy, reliability, reserve
              margin, and investment decisions.
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
      <div className="mt-2 font-mono text-xs leading-relaxed text-foreground">{formula}</div>
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