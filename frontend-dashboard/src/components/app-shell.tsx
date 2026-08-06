// ECADIN_PHASE3L9_METHODOLOGY_SCOPE_V1
import { Link, useRouterState } from "@tanstack/react-router";
import { ReactNode, useState } from "react";
import {
  LayoutDashboard,
  Map as MapIcon,
  BarChart3,
  Trophy,
  Cpu,
  Database,
  BookOpen,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useFilters } from "@/lib/filter-context";
import {
  DATASET_INFO,
  FORECAST_START,
  YEARS,
  ISLANDS,
  PROVINCE_DATA,
} from "@/lib/energy-data";

const ECADIN_MARK_SRC = "/ecadin-mark.png";

const NAV = [
  { to: "/", label: "National Overview", icon: LayoutDashboard },
  { to: "/map", label: "Indonesia Energy Map", icon: MapIcon },
  { to: "/province", label: "Region Detail", icon: BarChart3 },
  { to: "/ranking", label: "Regional Difference Ranking", icon: Trophy },
  { to: "/model", label: "Production Models", icon: Cpu },
  { to: "/quality", label: "Data Quality", icon: Database },
  { to: "/methodology", label: "Methodology", icon: BookOpen },
];

function isNationalScopeRoute(pathname: string): boolean {
  return pathname === "/" || pathname.startsWith("/ranking");
}

function isProductionModelRoute(pathname: string): boolean {
  return pathname.startsWith("/model");
}

function isDataQualityRoute(pathname: string): boolean {
  return pathname.startsWith("/quality");
}

function isMethodologyRoute(pathname: string): boolean {
  return pathname.startsWith("/methodology");
}

function SidebarInner() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { filters, setFilters } = useFilters();
  const isNationalOverview = pathname === "/";
  const isNationalRanking = pathname.startsWith("/ranking");
  const isNationalScope = isNationalOverview || isNationalRanking;
  const isProductionModel = isProductionModelRoute(pathname);
  const isDataQuality = isDataQualityRoute(pathname);
  const isMethodology = isMethodologyRoute(pathname);

  return (
    <aside
      className={cn(
        "sticky top-0 h-screen shrink-0 border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-200",
        collapsed ? "w-16" : "w-72",
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
        <div className="flex items-center gap-2 overflow-hidden">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-white/95 p-1 shadow-[0_0_18px_-4px_rgba(125,205,55,0.6)]">
            <img
              src={ECADIN_MARK_SRC}
              alt="ECADIN"
              className="h-full w-full object-contain"
            />
          </div>

          {!collapsed && (
            <div className="leading-tight">
              <div className="font-display text-sm font-bold tracking-wide text-sidebar-foreground">
                ECADIN
              </div>
              <div className="text-[9px] uppercase tracking-[0.18em] text-sidebar-foreground/60">
                Energy Academy Indonesia
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => setCollapsed((current) => !current)}
          className="rounded-md p-1 text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          aria-label="Toggle sidebar"
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="p-2">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active =
            item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);

          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "mb-0.5 flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "border-l-2 border-[color:var(--brand-lime)] bg-sidebar-accent pl-[10px] text-sidebar-accent-foreground shadow-inner"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />

              {!collapsed && <span className="truncate">{item.label}</span>}

              {!collapsed && active && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[color:var(--brand-lime)] shadow-[0_0_8px_var(--brand-lime)]" />
              )}
            </Link>
          );
        })}
      </nav>

      {!collapsed && (
        <div className="mx-3 mt-4 space-y-4 rounded-lg border border-sidebar-border bg-white/5 p-3 text-xs">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">
            {isProductionModel
              ? "Model Scope"
              : isDataQuality
                ? "Data Scope"
                : isMethodology
                  ? "Methodology Scope"
                  : isNationalScope
                    ? "National Filter"
                    : "Filters"}
          </div>

          {isProductionModel ? (
            <ModelScopeCard />
          ) : isDataQuality ? (
            <DataQualityScopeCard />
          ) : isMethodology ? (
            <MethodologyScopeCard />
          ) : (
            <>
              <FilterSelect
                label="Year"
                value={String(filters.year)}
                onChange={(value) => setFilters({ year: Number(value) })}
                options={YEARS.map((year) => ({
                  value: String(year),
                  label: `${year}${year >= FORECAST_START ? " · forecast" : ""}`,
                }))}
              />

              {isNationalScope ? (
                <div className="rounded-md border border-white/10 bg-black/15 px-2.5 py-2">
                  <div className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/50">
                    Scope
                  </div>
                  <div className="mt-1 text-xs font-medium text-sidebar-foreground">
                    {isNationalOverview
                      ? "Indonesia national aggregate"
                      : "Indonesia national comparison"}
                  </div>
                  <div className="mt-0.5 text-[10px] leading-relaxed text-sidebar-foreground/55">
                    {DATASET_INFO.regionCount} harmonized regions
                  </div>
                </div>
              ) : (
                <>
                  <FilterSelect
                    label="Island Group"
                    value={filters.island}
                    onChange={(value) =>
                      setFilters({ island: value, province: "All" })
                    }
                    options={[
                      { value: "All", label: "All regions" },
                      ...ISLANDS.map((island) => ({ value: island, label: island })),
                    ]}
                  />

                  <FilterSelect
                    label="Harmonized Region"
                    value={filters.province}
                    onChange={(value) => setFilters({ province: value })}
                    options={[
                      { value: "All", label: "All harmonized regions" },
                      ...PROVINCE_DATA.filter(
                        (province) =>
                          filters.island === "All" ||
                          province.island === filters.island,
                      ).map((province) => ({
                        value: province.code,
                        label: province.name,
                      })),
                    ]}
                  />
                </>
              )}
            </>
          )}
        </div>
      )}
    </aside>
  );
}

function ModelScopeCard() {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 px-2.5 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/50">
        Scope
      </div>
      <div className="mt-1 text-xs font-medium text-sidebar-foreground">
        Indonesia production model registry
      </div>
      <div className="mt-1 space-y-0.5 text-[10px] leading-relaxed text-sidebar-foreground/55">
        <div>{DATASET_INFO.regionCount} harmonized regions</div>
        <div>
          Forecast horizon {FORECAST_START}–{DATASET_INFO.period[1]}
        </div>
      </div>
    </div>
  );
}

function DataQualityScopeCard() {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 px-2.5 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/50">
        Scope
      </div>
      <div className="mt-1 text-xs font-medium text-sidebar-foreground">
        Indonesia dashboard dataset
      </div>
      <div className="mt-1 space-y-0.5 text-[10px] leading-relaxed text-sidebar-foreground/55">
        <div>{DATASET_INFO.regionCount} harmonized regions</div>
        <div>Coverage period {DATASET_INFO.period[0]}–{DATASET_INFO.period[1]}</div>
      </div>
    </div>
  );
}

function MethodologyScopeCard() {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 px-2.5 py-2.5">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/50">
        Scope
      </div>
      <div className="mt-1 text-xs font-medium text-sidebar-foreground">
        Indonesia production methodology
      </div>
      <div className="mt-1 space-y-0.5 text-[10px] leading-relaxed text-sidebar-foreground/55">
        <div>{DATASET_INFO.regionCount} harmonized regions</div>
        <div>Historical period {DATASET_INFO.period[0]}–{FORECAST_START - 1}</div>
        <div>Forecast horizon {FORECAST_START}–{DATASET_INFO.period[1]}</div>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/60">
        {label}
      </div>

      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-white/10 bg-black/25 px-2 py-1.5 text-xs text-sidebar-foreground outline-none focus:ring-1 focus:ring-[color:var(--brand-lime)]"
      >
        {options.map((option) => (
          <option
            key={option.value}
            value={option.value}
            className="bg-[color:var(--sidebar)] text-sidebar-foreground"
          >
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function AppShell({
  children,
  title,
  subtitle,
}: {
  children: ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex min-h-screen w-full">
      <SidebarInner />

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-background/70 px-6 backdrop-blur">
          <div>
            <h1 className="font-display text-base font-semibold leading-tight">
              {title}
            </h1>
            {subtitle && (
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            )}
          </div>

          <StatusPill />
        </header>

        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}

function StatusPill() {
  const { filters } = useFilters();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const isProductionModel = isProductionModelRoute(pathname);
  const isDataQuality = isDataQualityRoute(pathname);
  const isMethodology = isMethodologyRoute(pathname);
  const isNationalScope = isNationalScopeRoute(pathname);
  const isForecast = filters.year >= FORECAST_START;

  if (isProductionModel) {
    return (
      <div className="flex items-center gap-3">
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          Indonesia · {DATASET_INFO.regionCount} regions
        </span>
        <span className="flex items-center gap-1.5 rounded-full border border-[color:var(--brand-lime)] px-2.5 py-1 text-[10px] font-medium uppercase tracking-widest text-[color:var(--brand-lime)]">
          <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--brand-lime)]" />
          Production
        </span>
      </div>
    );
  }

  if (isDataQuality) {
    return (
      <div className="flex items-center gap-3">
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          Indonesia · {DATASET_INFO.regionCount} regions
        </span>
        <span className="flex items-center gap-1.5 rounded-full border border-primary px-2.5 py-1 text-[10px] font-medium uppercase tracking-widest text-primary">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          Data Quality
        </span>
      </div>
    );
  }


  if (isMethodology) {
    return (
      <div className="flex items-center gap-3">
        <span className="hidden text-[11px] text-muted-foreground sm:inline">
          Indonesia · {DATASET_INFO.regionCount} regions
        </span>
        <span className="flex items-center gap-1.5 rounded-full border border-primary px-2.5 py-1 text-[10px] font-medium uppercase tracking-widest text-primary">
          <span className="h-1.5 w-1.5 rounded-full bg-primary" />
          Methodology
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="hidden text-[11px] text-muted-foreground sm:inline">
        {isNationalScope ? "Indonesia" : filters.island} · Year{" "}
        <span className="tabular-nums text-foreground">{filters.year}</span>
      </span>

      <span
        className={cn(
          "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-widest",
          isForecast
            ? "border-[color:var(--chart-gap)] text-[color:var(--chart-gap)]"
            : "border-primary text-primary",
        )}
      >
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            isForecast ? "bg-[color:var(--chart-gap)]" : "bg-primary",
          )}
        />
        {isForecast ? "Forecast" : "Historical"}
      </span>
    </div>
  );
}
