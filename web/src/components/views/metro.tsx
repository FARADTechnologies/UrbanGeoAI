"use client";

import { useState } from "react";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { cn } from "@/lib/utils";
import type { Summary } from "@/types/data";

/** Kararların insan tarafından okunan adları ve rengi. */
const DECISIONS: Record<string, { label: string; tone: string }> = {
  tutuldu: { label: "Saxlanıldı", tone: "var(--ok-500)" },
  isletmede_degil: { label: "İşləmir", tone: "var(--err-500)" },
  servis_noktasi: { label: "Servis düyünü", tone: "var(--warn-500)" },
  birebir_tekrar: { label: "Təkrar", tone: "var(--ink-400)" },
  aktarma_kompleksi: { label: "Ötürmə", tone: "var(--ink-400)" }
};

export function MetroView({ summary }: { summary: Summary }) {
  const [filter, setFilter] = useState<string | null>(null);
  const nodes = filter
    ? summary.metro.nodes.filter((n) => n.decision === filter)
    : summary.metro.nodes;

  const entries = Object.entries(summary.metro.summary).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilter(null)}
          className={cn(
            "rounded-xl border bg-card px-4 py-3 text-left shadow-sm transition-colors",
            filter === null && "ring-2 ring-[var(--brand-500)]"
          )}
        >
          <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            Bütün düyünlər
          </div>
          <div className="mt-1 text-[21px] font-bold leading-none tabular-nums">
            {summary.metro.nodes.length}
          </div>
        </button>
        {entries.map(([key, count]) => {
          const meta = DECISIONS[key] ?? { label: key, tone: "var(--ink-400)" };
          return (
            <button
              key={key}
              onClick={() => setFilter(key === filter ? null : key)}
              className={cn(
                "rounded-xl border bg-card px-4 py-3 text-left shadow-sm transition-colors",
                filter === key && "ring-2 ring-[var(--brand-500)]"
              )}
            >
              <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                {meta.label}
              </div>
              <div
                className="mt-1 text-[21px] font-bold leading-none tabular-nums"
                style={{ color: meta.tone }}
              >
                {count}
              </div>
            </button>
          );
        })}
      </div>

      <DashboardCard
        title="Hər düyün üçün qərar və səbəb"
        subtitle="Siyahı OpenStreetMap'dən gəlir; qərarı kod verir, əl ilə yazılmır"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-separate border-spacing-0 text-left text-[12px]">
            <thead>
              <tr>
                {["Ad", "Qərar", "Səbəb", "Koordinat"].map((h) => (
                  <th
                    key={h}
                    className="border-b px-3 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {nodes.map((node, i) => {
                const meta = DECISIONS[node.decision] ?? {
                  label: node.decision,
                  tone: "var(--ink-400)"
                };
                return (
                  <tr key={`${node.name}-${i}`} className="hover:bg-muted/30">
                    <td className="border-b px-3 py-2 font-medium">{node.name}</td>
                    <td className="border-b px-3 py-2">
                      <span
                        className="rounded-full px-2 py-0.5 text-[10.5px] font-semibold text-white"
                        style={{ background: meta.tone }}
                      >
                        {meta.label}
                      </span>
                    </td>
                    <td className="border-b px-3 py-2 text-muted-foreground">{node.reason}</td>
                    <td className="border-b px-3 py-2 font-mono text-[11px] tabular-nums text-muted-foreground">
                      {node.lat.toFixed(4)}, {node.lon.toFixed(4)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </DashboardCard>
    </>
  );
}
