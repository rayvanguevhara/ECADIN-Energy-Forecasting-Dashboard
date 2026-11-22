// ECADIN_PHASE3L6_REGIONAL_RANKING_NATIONAL_SCOPE_V1
import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Panel } from "@/components/panel";
import { useFilters } from "@/lib/filter-context";
import {
  DATASET_INFO,
  GAP_CATEGORY_META,
  GAP_CATEGORY_ORDER,
  GapCategory,
  PROVINCE_DATA,
  attentionLabel,
  classifyGap,
  formatSignedEnergy,
  formatSignedPercent,
} from "@/lib/energy-data";

export const Route = createFileRoute("/ranking")({
  head: () => ({
    meta: [
      {
        title: "Regional Difference Ranking · ECADIN Energy Intelligence",
      },
      {
        name: "description",
        content: `National ranking of positive and negative regional accounting differences plus descriptive review flags for Indonesia's ${DATASET_INFO.regionCount} harmonized modeling regions.`,
      },
    ],
  }),
  component: RankingPage,
});

function RankingPage() {
  return (
    <AppShell
      title="Regional Difference Ranking"
      subtitle="National ranking of regional accounting differences and descriptive review flags"
    >
      <Inner />
    </AppShell>
  );
}

function Inner() {
  const { filters } = useFilters();

  const rows = PROVINCE_DATA.map((region) => {
    const point = region.series.find((item) => item.year === filters.year)!;

    return {
      region,
      point,
      category: point.gapCategory ?? classifyGap(point.gap_pct),
    };
  });

  const availableRows = rows.filter(
    ({ point }) => point.available && Number.isFinite(point.gap_gwh),
  );

  const negativeDifferences = availableRows
    .filter(({ point }) => point.gap_gwh < 0)
    .sort((a, b) => a.point.gap_gwh - b.point.gap_gwh)
    .slice(0, 8);

  const positiveDifferences = availableRows
    .filter(({ point }) => point.gap_gwh > 0)
    .sort((a, b) => b.point.gap_gwh - a.point.gap_gwh)
    .slice(0, 8);

  const reviewRows = rows.filter(({ point }) => point.attention);

  const categoryCounts = GAP_CATEGORY_ORDER.map((key) => ({
    key,
    ...GAP_CATEGORY_META[key],
    count: rows.filter(({ category }) => category === key).length,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel
          title="Largest Negative Accounting Differences"
          subtitle={`Local generation furthest below distributed electricity · ${filters.year}`}
        >
          <RankTable rows={negativeDifferences} direction="below" />
        </Panel>

        <Panel
          title="Largest Positive Accounting Differences"
          subtitle={`Local generation furthest above distributed electricity · ${filters.year}`}
        >
          <RankTable rows={positiveDifferences} direction="above" />
        </Panel>
      </div>

      <Panel
        title="Accounting-Difference Category Distribution"
        subtitle={`Descriptive thresholds applied to ${DATASET_INFO.regionCount} harmonized regions · not an operational adequacy classification`}
      >
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {categoryCounts.map((item) => (
            <div
              key={item.key}
              className="rounded-md border border-border bg-background/40 p-4"
            >
              <div className="mb-3 flex items-start gap-2">
                <span
                  className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: item.color }}
                />

                <div className="min-w-0">
                  <div className="text-[11px] font-medium uppercase tracking-widest text-foreground">
                    {item.shortLabel}
                  </div>
                  <div className="mt-0.5 text-[10px] leading-snug text-muted-foreground">
                    {item.comparison}
                  </div>
                </div>
              </div>

              <div className="font-display text-2xl font-semibold tabular-nums">
                {item.count}
              </div>
              <div className="text-[10px] text-muted-foreground">
                {((item.count / rows.length) * 100).toFixed(0)}% of regions
              </div>
            </div>
          ))}
        </div>

        <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
          Thresholds: far below ≤ −20% · below &gt; −20% to ≤ −5% · balanced
          &gt; −5% to &lt; +5% · above ≥ +5% to &lt; +20% · far above ≥ +20%.
        </p>
      </Panel>

      <Panel title="Interpretation Safeguard">
        <p className="text-sm leading-relaxed text-muted-foreground">
          Rankings compare the administrative location of local generation with
          electricity distributed in each harmonized region. Positive or
          negative accounting differences do not indicate operational surplus,
          shortage, blackout risk, reserve margin, or idle capacity because
          interregional electricity flows and operational system conditions are
          not included.
        </p>
      </Panel>

      <Panel
        title="Accounting Difference Review List"
        subtitle={`Descriptive large-magnitude difference flags for ${filters.year} · not operational alerts`}
      >
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full min-w-[880px] table-fixed text-xs">
            <colgroup>
              <col className="w-[15%]" />
              <col className="w-[14%]" />
              <col className="w-[16%]" />
              <col className="w-[12%]" />
              <col className="w-[21%]" />
              <col className="w-[22%]" />
            </colgroup>

            <thead className="bg-background/50 text-[10px] uppercase tracking-widest text-muted-foreground">
              <tr>
                <th className="p-2 text-left">Region</th>
                <th className="p-2 text-left">Island Group</th>
                <th className="p-2 text-right">Accounting Difference</th>
                <th className="p-2 text-right">Difference %</th>
                <th className="p-2 text-left">Category</th>
                <th className="p-2 text-left">Review Note</th>
              </tr>
            </thead>

            <tbody className="tabular-nums">
              {reviewRows.map(({ region, point, category }) => {
                const meta = GAP_CATEGORY_META[category];

                return (
                  <tr key={region.code} className="border-t border-border">
                    <td className="p-2 font-medium">{region.name}</td>
                    <td className="p-2 text-muted-foreground">
                      {region.island}
                    </td>
                    <td className="p-2 text-right text-foreground">
                      {point.available
                        ? formatSignedEnergy(point.gap_gwh, true)
                        : "N/A"}
                    </td>
                    <td className="p-2 text-right">
                      {point.available
                        ? formatSignedPercent(point.gap_pct)
                        : "N/A"}
                    </td>
                    <td className="p-2">
                      <span
                        className="inline-flex rounded-md border px-2 py-1 text-[10px] font-medium uppercase tracking-wider"
                        style={{
                          borderColor: meta.color,
                          color: meta.color,
                          backgroundColor: `${meta.color}12`,
                        }}
                      >
                        {meta.fullLabel}
                      </span>
                    </td>
                    <td className="p-2 text-muted-foreground">
                      {attentionLabel(point.attentionReason)}
                    </td>
                  </tr>
                );
              })}

              {reviewRows.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="p-6 text-center text-muted-foreground"
                  >
                    No descriptive review flags for this year.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function RankTable({
  rows,
  direction,
}: {
  rows: {
    region: (typeof PROVINCE_DATA)[number];
    point: (typeof PROVINCE_DATA)[number]["series"][number];
    category: GapCategory;
  }[];
  direction: "above" | "below";
}) {
  const directionColor = direction === "above" ? "#2563EB" : "#EA580C";

  return (
    <ol className="space-y-1">
      {rows.map(({ region, point }, index) => (
        <li
          key={region.code}
          className="grid grid-cols-[24px_1fr_auto_auto] items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-accent/40"
        >
          <span className="text-[11px] text-muted-foreground tabular-nums">
            {index + 1}
          </span>

          <div>
            <div className="font-medium">{region.name}</div>
            <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
              {region.island}
            </div>
          </div>

          <span className="tabular-nums" style={{ color: directionColor }}>
            {formatSignedEnergy(point.gap_gwh, true)}
          </span>

          <span className="w-16 text-right text-xs text-muted-foreground tabular-nums">
            {formatSignedPercent(point.gap_pct)}
          </span>
        </li>
      ))}

      {rows.length === 0 && (
        <li className="rounded-md px-2 py-6 text-center text-sm text-muted-foreground">
          No regions in this direction for the selected year.
        </li>
      )}
    </ol>
  );
}
