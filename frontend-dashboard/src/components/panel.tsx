import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Panel({
  title, subtitle, right, children, className,
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("card-panel p-5", className)}>
      {(title || right) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="font-display text-sm font-semibold">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function KpiCard({
  label, value, unit, delta, tone = "neutral", icon,
}: {
  label: string;
  value: string;
  unit?: string;
  delta?: string;
  tone?: "neutral" | "up" | "down" | "warn";
  icon?: ReactNode;
}) {
  const toneCls =
    tone === "up" ? "text-[color:var(--surplus-high)]" :
    tone === "down" ? "text-[color:var(--deficit-high)]" :
    tone === "warn" ? "text-[color:var(--deficit-mod)]" :
    "text-muted-foreground";
  return (
    <div className="card-panel p-5">
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
          {label}
        </span>
        {icon && <span className="text-muted-foreground">{icon}</span>}
      </div>
      <div className="mt-3 flex items-baseline gap-1.5 font-display">
        <span className="text-2xl font-semibold tabular-nums">{value}</span>
        {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
      </div>
      {delta && <div className={cn("mt-1 text-xs tabular-nums", toneCls)}>{delta}</div>}
    </div>
  );
}
