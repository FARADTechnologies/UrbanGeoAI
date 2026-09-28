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
            {["İndeks", "Spearman", "Oynayan", "Yuxarı", "Aşağı", "Orta dəyişim", "Tavan"].map((h) => (
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
              <td className="border-b px-3 py-2 tabular-nums">
                {row.mean_shift > 0 ? "+" : ""}
                {row.mean_shift.toFixed(2)}
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
        title="Veri etkisi — eyni metod, eyni cədvəl, yeni veri"
        subtitle={`${formatCount(comparison.cells)} hüceyrə · model və bant sərhədləri 2025-də uyduruldu və donduruldu, 2026 eyni cədvəllə ölçüldü`}
      >
        <EffectTable rows={comparison.data_effect} />
        <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          Hüceyrələrin böyük əksəriyyəti ya yerində qalır, ya{" "}
          <span className="font-semibold text-[var(--ok-500)]">yuxarı</span> qalxır: 2025 → 2026 arasında
          obyekt sayı artıb. Əvvəlki hesabatda model hər sürüm üçün yenidən uydurulurdu; onda bantlar hər
          sürümdə yenə bərabər paylanır və ətrafı yaxşılaşan hüceyrə də sırada geri düşmüş görünürdü (məs.
          əyləncədə 19.9% «aşağı»). Düzgün müqayisə eyni cədvəllədir — xəritədəki «Dəyişim» də belə işləyir.
          Metro hər iki sürümdə bugünkü siyahıdandır, ona görə nəqliyyatdakı fərq yalnız dayanacaqlardan gəlir.
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
