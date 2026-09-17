"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { categoryLabel, formatCount, groupLabel } from "@/lib/data";
import type { Summary } from "@/types/data";

/** Korelasyon değerini renge çevirir — 1 turuncu, 0 nötr. */
function corrColor(value: number) {
  const t = Math.max(0, Math.min(1, Math.abs(value)));
  return `color-mix(in srgb, var(--brand-500) ${Math.round(t * 88)}%, transparent)`;
}

export function IndicesView({ summary }: { summary: Summary }) {
  const groups = summary.groups;
  const beta = summary.beta ?? {};
  const ranked = Object.entries(beta)
    .map(([key, row]) => ({ key, ...row, worst: Math.max(...Object.values(row.effect)) }))
    .sort((a, b) => b.worst - a.worst);

  return (
    <>
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <DashboardCard
          title="Bileşen yükleri və bant doluluğu"
          subtitle="Hər indeks öz kateqoriyalarının ilk əsas bileşeni"
        >
          <div className="mb-3 rounded-lg border border-dashed px-3 py-2.5 text-[11.5px] leading-relaxed text-muted-foreground">
            <b className="text-foreground">Kateqoriya yanındakı rəqəm</b> — o kateqoriyanın skoru ilə
            indeks arasındakı korelyasiya (ekibin notebook-undakı tərif:{" "}
            <span className="font-mono">components × √explained_variance</span>). 1-ə yaxın = indeksi
            güclü müəyyən edir. Hesablama: skorlar standartlaşdırılır →{" "}
            <span className="font-mono">PCA(n_components=1)</span> → birinci komponent. Kod:{" "}
            <span className="font-mono">src/urbangeoai/indices.py · fit_group</span>
          </div>
          <div className="space-y-3">
            {groups.map((g) => {
              const info = summary.pca[g];
              const empty = Object.entries(info.bands).filter(([, n]) => n === 0);
              const maxBand = Math.max(...Object.values(info.bands));
              return (
                <div key={g} className="rounded-lg border bg-background p-3.5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="text-[12.5px] font-semibold">{groupLabel(g)}</span>
                    <span className="text-[11px] text-muted-foreground">
                      izah edilən varyans{" "}
                      <span className="font-semibold text-foreground">{info.evr}%</span>
                      {info.fittedOnPrevious ? " · model 2025-ə uyduruldu" : " · model cari veridən"}
                    </span>
                  </div>

                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {info.members.map((m, i) => (
                      <span
                        key={m}
                        className="rounded-md border px-2 py-0.5 text-[11px]"
                        title={`korelyasiya ${info.loadings[i]} · puanlama çəkisi ${info.weights?.[i] ?? "—"}`}
                      >
                        {categoryLabel(m)}
                        <span className="ml-1.5 font-semibold tabular-nums text-[var(--brand-600)]">
                          {info.loadings[i].toFixed(2)}
                        </span>
                      </span>
                    ))}
                  </div>

                  <div className="mt-3 flex items-end gap-[3px]">
                    {Object.entries(info.bands).map(([band, count]) => (
                      <div key={band} className="flex-1 text-center" title={`bant ${band}: ${formatCount(count)} hüceyrə`}>
                        <div
                          className="mx-auto w-full rounded-sm"
                          style={{
                            height: `${Math.max(2, (count / maxBand) * 40)}px`,
                            background:
                              count === 0 ? "var(--err-500)" : "var(--brand-400)"
                          }}
                        />
                        <div className="mt-1 text-[9px] text-muted-foreground">{band}</div>
                      </div>
                    ))}
                  </div>
                  {empty.length > 0 ? (
                    <p className="mt-2 text-[11px] text-[var(--err-500)]">
                      Boş bant: {empty.map(([b]) => b).join(", ")} — bu qrupda o balı alan hüceyrə yoxdur.
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </DashboardCard>

        <div className="grid content-start gap-4">
          <DashboardCard
            title="İndekslər bir-birini nə qədər təkrarlayır"
            subtitle={`Yeddi indeks birlikdə çözümlenince fərqin ${summary.cross.evr[0]}%-i tək amilə düşür`}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] border-separate border-spacing-0 text-[11px]">
                <thead>
                  <tr>
                    <th className="sticky left-0 bg-card px-1 py-1" />
                    {groups.map((g) => (
                      <th
                        key={g}
                        className="px-1 py-1 text-center font-medium text-muted-foreground"
                        title={groupLabel(g)}
                      >
                        {groupLabel(g).slice(0, 3)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {groups.map((a) => (
                    <tr key={a}>
                      <td className="sticky left-0 bg-card py-1 pr-2 text-right text-muted-foreground">
                        {groupLabel(a)}
                      </td>
                      {groups.map((b) => {
                        const v = summary.cross.corr[a][b];
                        return (
                          <td key={b} className="p-[2px]">
                            <div
                              className="flex h-7 items-center justify-center rounded tabular-nums"
                              style={{ background: corrColor(v) }}
                              title={`${groupLabel(a)} ↔ ${groupLabel(b)}: ${v}`}
                            >
                              {v.toFixed(2)}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
              Müştəriyə yeddi ayrı bal göstərilir, amma böyük ölçüdə hamısı eyni şeyi deyir:
              &laquo;mərkəzə nə qədər yaxınsan&raquo;. Qalıq bal təklifi buradan çıxdı.
            </p>
          </DashboardCard>

          {ranked.length > 0 ? (
            <DashboardCard
              title="Kalibrasyonun önceliği"
              subtitle="Katsayı yarıya inip iki katına çıkınca bandı dəyişən hüceyrə payı"
            >
              <div className="space-y-1.5">
                {ranked.map((row) => (
                  <div key={row.key} className="grid grid-cols-[124px_1fr_52px] items-center gap-2">
                    <span className="truncate text-[11.5px] text-muted-foreground" title={`β = ${row.beta}`}>
                      {categoryLabel(row.key)}
                    </span>
                    <div className="h-2 rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full"
                        style={{
                          width: `${row.worst}%`,
                          background:
                            row.worst > 50 ? "var(--err-500)" : row.worst > 20 ? "var(--warn-500)" : "var(--ok-500)"
                        }}
                      />
                    </div>
                    <span className="text-right text-[11px] font-semibold tabular-nums">
                      {row.worst.toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
                Az oynadan katsayı yanlış seçilmiş olsa belə nəticəni pozmur. Kalibrasyon verisi
                gələndə əmək yuxarıdakılara verilməlidir.
              </p>
            </DashboardCard>
          ) : null}
        </div>
      </div>
    </>
  );
}
