"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { formatCount, groupLabel } from "@/lib/data";
import type { EffectRow, Summary } from "@/types/data";

function EffectTable({ rows }: { rows: Record<string, EffectRow> }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-separate border-spacing-0 text-left text-[12px]">
        <thead>
          <tr>
            {["İndeks", "Spearman", "Oynayan", "Yuxarı", "Aşağı", "Tavan"].map((h) => (
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
          {Object.entries(rows).map(([group, row]) => (
            <tr key={group} className="hover:bg-muted/30">
              <td className="border-b px-3 py-2 font-medium">{groupLabel(group)}</td>
              <td className="border-b px-3 py-2 tabular-nums">{row.spearman.toFixed(3)}</td>
              <td className="border-b px-3 py-2">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-16 rounded-full bg-muted">
                    <div
                      className="h-1.5 rounded-full bg-[var(--brand-500)]"
                      style={{ width: `${Math.min(100, row.moved_pct)}%` }}
                    />
                  </div>
                  <span className="tabular-nums">{row.moved_pct.toFixed(1)}%</span>
                </div>
              </td>
              <td className="border-b px-3 py-2 tabular-nums text-[var(--ok-500)]">
                {row.up_pct.toFixed(1)}%
              </td>
              <td className="border-b px-3 py-2 tabular-nums text-[var(--err-500)]">
                {row.down_pct.toFixed(1)}%
              </td>
              <td className="border-b px-3 py-2 tabular-nums text-muted-foreground">
                {row.max_band_before} → {row.max_band_after}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChangeView({ summary }: { summary: Summary }) {
  const comparison = summary.comparison;

  if (!comparison) {
    return (
      <DashboardCard title="Dəyişim" subtitle="Müqayisə hesabatı tapılmadı">
        <p className="text-[12px] text-muted-foreground">
          Əvvəlcə <span className="font-mono">python scripts/compare_versions.py --json
          out/comparison.json</span> işlədilməlidir.
        </p>
      </DashboardCard>
    );
  }

  return (
    <>
      <DashboardCard
        title="Veri etkisi — yöntem sabit, veri yeni"
        subtitle={`${formatCount(comparison.cells)} hüceyrə · 2025 verisi ilə 2026 verisi eyni kodla puanlandı`}
      >
        <EffectTable rows={comparison.data_effect} />
        <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          POI sayı hər kateqoriyada artdığı halda indekslərin çoxunda daha çox hüceyrə{" "}
          <span className="font-semibold text-[var(--err-500)]">aşağı</span> düşür. Səbəb bal
          deyil, sıralama: model hər sürümdə yenidən uydurulanda ətrafı dəyişməyən bir hüceyrə də
          yerini itirir. Dondurulmuş model bunun üçün gətirildi.
        </p>
      </DashboardCard>

      <DashboardCard
        title="Yöntem etkisi — veri sabit, yöntem yeni"
        subtitle="Eyni veri köhnə və yeni kodla puanlandı"
      >
        <EffectTable rows={comparison.method_effect} />
        <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          Spearman 0.99-un üstündə: sıralama demək olar ki, qorunur. Dəyişən şey bant tavanı —
          əvvəl heç bir hüceyrə 10-a çatmırdı, indi çatır. Bu bərabərlik düzəlişinin nəticəsidir.
        </p>
      </DashboardCard>
    </>
  );
}
