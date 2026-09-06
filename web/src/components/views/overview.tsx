"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { categoryLabel, formatCount, groupLabel } from "@/lib/data";
import type { Summary } from "@/types/data";

export function OverviewView({ summary }: { summary: Summary }) {
  const { meta } = summary;

  const grown = [...summary.counts]
    .filter((c) => c.old !== null && c.old > 0)
    .map((c) => ({ ...c, pct: ((c.new - (c.old as number)) / (c.old as number)) * 100 }))
    .sort((a, b) => b.pct - a.pct);

  const introduced = summary.counts.filter((c) => c.old === null);

  return (
    <>
      <KpiGrid
        items={[
          { label: "Hüceyrə", value: formatCount(meta.cells), note: `H3 res-${meta.resolution}` },
          { label: "POI", value: formatCount(meta.poi), note: `${meta.categories} kateqoriya` },
          { label: "İndeks", value: String(meta.indices), note: "hamısı çıxışda" },
          {
            label: "Metro",
            value: `${meta.metroKept}`,
            note: `${meta.metroRaw} düyündən saxlanıldı`
          },
          {
            label: "Cədvəl",
            value: meta.csvMb ? `${meta.csvMb} MB` : "—",
            note: "accessibility_indices.csv"
          },
          {
            label: "Ortaq amil",
            value: `${summary.cross.evr[0]}%`,
            note: "yeddi indeksin fərqinin payı"
          }
        ]}
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <DashboardCard
          title="Kateqoriya artımı"
          subtitle="2025 sürümü ilə müqayisədə qeyd sayı"
        >
          <div className="space-y-1.5">
            {grown.map((row) => {
              const width = Math.min(100, Math.abs(row.pct) * 3.4);
              return (
                <div key={row.key} className="grid grid-cols-[132px_1fr_78px] items-center gap-2">
                  <span className="truncate text-[11.5px] text-muted-foreground">
                    {categoryLabel(row.key)}
                  </span>
                  <div className="h-2 rounded-full bg-muted">
                    <div
                      className="h-2 rounded-full"
                      style={{
                        width: `${width}%`,
                        background: row.pct >= 0 ? "var(--brand-500)" : "var(--err-500)"
                      }}
                    />
                  </div>
                  <span className="text-right text-[11px] tabular-nums">
                    <span className="text-muted-foreground">{formatCount(row.new)}</span>
                    <span
                      className="ml-1.5 font-semibold"
                      style={{ color: row.pct >= 0 ? "var(--ok-500)" : "var(--err-500)" }}
                    >
                      {row.pct >= 0 ? "+" : ""}
                      {row.pct.toFixed(0)}%
                    </span>
                  </span>
                </div>
              );
            })}
            {introduced.length > 0 ? (
              <div className="!mt-4 rounded-lg border border-dashed p-3 text-[11.5px] leading-relaxed text-muted-foreground">
                <span className="font-semibold text-foreground">Yalnız yeni sürümdə: </span>
                {introduced.map((c) => `${categoryLabel(c.key)} (${formatCount(c.new)})`).join(", ")}.
                Bu fayllar iş ortağından yeni gəldi və əvvəlki kodda istifadə olunmurdu.
              </div>
            ) : null}
          </div>
        </DashboardCard>

        <div className="grid gap-4">
          <DashboardCard title="İndekslər" subtitle="Hər qrupun ilk bileşeninin açıkladığı varyans">
            <div className="space-y-1.5">
              {summary.groups.map((g) => (
                <div key={g} className="grid grid-cols-[112px_1fr_46px] items-center gap-2">
                  <span className="truncate text-[11.5px] text-muted-foreground">
                    {groupLabel(g)}
                  </span>
                  <div className="h-2 rounded-full bg-muted">
                    <div
                      className="h-2 rounded-full bg-[var(--brand-500)]"
                      style={{ width: `${summary.pca[g].evr}%` }}
                    />
                  </div>
                  <span className="text-right text-[11px] font-semibold tabular-nums">
                    {summary.pca[g].evr}%
                  </span>
                </div>
              ))}
            </div>
          </DashboardCard>

          <DashboardCard title="Çıxarılan kateqoriyalar" subtitle="Səbəbi ilə birlikdə">
            <div className="space-y-2">
              {Object.entries(summary.retired).map(([key, reason]) => (
                <div key={key} className="rounded-lg border bg-background p-3">
                  <div className="text-[12px] font-semibold">{categoryLabel(key)}</div>
                  <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground">
                    {reason}
                  </p>
                </div>
              ))}
              {Object.keys(summary.retired).length === 0 ? (
                <p className="text-[11.5px] text-muted-foreground">Çıxarılan kateqoriya yoxdur.</p>
              ) : null}
            </div>
          </DashboardCard>
        </div>
      </div>
    </>
  );
}
