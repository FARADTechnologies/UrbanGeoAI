"use client";

import { cn } from "@/lib/utils";

export type Kpi = {
  label: string;
  value: string;
  /** Rəqəmin altında bir sətir izah. */
  note?: string;
  /** Müsbət/mənfi işarə lazım olan yerlərdə. */
  tone?: "neutral" | "up" | "down";
};

export function KpiGrid({ items }: { items: Kpi[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {items.map((kpi) => (
        <div key={kpi.label} className="rounded-xl border bg-card px-4 py-3 shadow-sm">
          <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            {kpi.label}
          </div>
          <div
            className={cn(
              "mt-1 text-[21px] font-bold leading-none tracking-tight tabular-nums",
              kpi.tone === "up" && "text-[var(--ok-500)]",
              kpi.tone === "down" && "text-[var(--err-500)]"
            )}
          >
            {kpi.value}
          </div>
          {kpi.note ? (
            <div className="mt-1.5 text-[11px] leading-snug text-muted-foreground">{kpi.note}</div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
