import { createContext, ReactNode, useContext, useState } from "react";

export interface Filters {
  year: number;
  province: string; // code or "All"
  island: string; // name or "All"
}

const defaultFilters: Filters = {
  year: 2024,
  province: "All",
  island: "All",
};

const Ctx = createContext<{
  filters: Filters;
  setFilters: (patch: Partial<Filters>) => void;
} | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<Filters>(defaultFilters);
  const setFilters = (patch: Partial<Filters>) =>
    setState((current) => ({ ...current, ...patch }));
  return <Ctx.Provider value={{ filters, setFilters }}>{children}</Ctx.Provider>;
}

export function useFilters() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFilters outside FilterProvider");
  return ctx;
}
