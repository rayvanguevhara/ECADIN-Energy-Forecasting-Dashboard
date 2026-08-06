import { createContext, ReactNode, useContext, useState } from "react";

export interface Filters {
  year: number;
  province: string; // code or "All"
  island: string; // name or "All"
  dataType: "historical" | "forecast" | "both";
}

const defaultFilters: Filters = {
  year: 2024,
  province: "All",
  island: "All",
  dataType: "both",
};

const Ctx = createContext<{
  filters: Filters;
  setFilters: (patch: Partial<Filters>) => void;
} | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<Filters>(defaultFilters);
  const setFilters = (patch: Partial<Filters>) => setState((f) => ({ ...f, ...patch }));
  return <Ctx.Provider value={{ filters, setFilters }}>{children}</Ctx.Provider>;
}

export function useFilters() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useFilters outside FilterProvider");
  return c;
}
