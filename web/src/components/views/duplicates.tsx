"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { categoryLabel, formatCount } from "@/lib/data";

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Təkrar qeydlər və ad standartlaşdırması (scripts/check_duplicates.py).
 * Hesablama bu qeydləri artıq atır; kart nəyin, niyə atıldığını göstərir.
 */
export function DuplicatesCard({ data }: { data: any }) {
  if (!data) return null;
  const total = data.local_total;
  const osm = data.osm ?? {};
  const osmDropped = Object.values(osm.duplicates_by_reason ?? {}).reduce(
    (a: number, b: any) => a + Number(b),
    0
  ) as number;

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
      <DashboardCard
        title="Təkrar qeydlər"
        subtitle="Eyni yer iki dəfə qeyd olunubsa bal onu iki dəfə sayardı — hesablamadan əvvəl bir qeydə endirilir"
      >
        <div className="grid grid-cols-3 gap-2 text-[12px]">
          {[
            ["Yerli: atıldı", `${total.dropped} / ${formatCount(total.before)}`],
            ["OSM daxili təkrar", formatCount(osmDropped)],
            ["OSM: yerlidə oxşar adla var", formatCount(osm.matched_by_name ?? 0)]
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg border bg-background px-3 py-2">
              <div className="text-muted-foreground">{k}</div>
              <div className="text-[16px] font-semibold tabular-nums">{v}</div>
            </div>
          ))}
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[520px] border-separate border-spacing-0 text-[11.5px]">
            <thead>
              <tr>
                {["Kateqoriya", "Atılan qeyd", "Qalan qeyd", "Məsafə", "Səbəb"].map((h) => (
                  <th
                    key={h}
                    className="border-b px-2.5 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.examples.map((r: any, i: number) => (
                <tr key={i}>
                  <td className="border-b px-2.5 py-1.5">{categoryLabel(r.category)}</td>
                  <td className="border-b px-2.5 py-1.5">{r.name}</td>
                  <td className="border-b px-2.5 py-1.5">{r.kept_name}</td>
                  <td className="border-b px-2.5 py-1.5 tabular-nums">{r.distance_m} m</td>
                  <td className="border-b px-2.5 py-1.5 text-muted-foreground">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          Qaydalar ehtiyatlıdır: nömrə fərqi ayırır («bağça 317» ≠ «bağça 212»), tək ortaq söz kifayət deyil, filiallar
          ayrı qalır (kafe üçün radius {data.rules.name_radius_m.coffee} m), yolun iki tərəfindəki eyni adlı dayanacaqlar
          ayrı qalır. Tam siyahı: <span className="font-mono">out/duplicates_dropped.csv</span>.
        </p>
      </DashboardCard>

      <div className="grid content-start gap-4">
        <DashboardCard title="Ad standartlaşdırması" subtitle="Orijinal ad saxlanılır, yanına standart forma yazılır">
          <div className="grid grid-cols-2 gap-2 text-[12px]">
            <div className="rounded-lg border bg-background px-3 py-2">
              <div className="text-muted-foreground">Yerli veridə dəyişən</div>
              <div className="text-[16px] font-semibold tabular-nums">{data.names.changed_by_source.yerli}</div>
            </div>
            <div className="rounded-lg border bg-background px-3 py-2">
              <div className="text-muted-foreground">OSM-də dəyişən</div>
              <div className="text-[16px] font-semibold tabular-nums">{data.names.changed_by_source.osm}</div>
            </div>
          </div>
          <div className="mt-3 space-y-1 text-[11.5px]">
            {data.names.examples.slice(0, 5).map((r: any, i: number) => (
              <div key={i} className="rounded border bg-background px-2 py-1">
                <span className="text-muted-foreground line-through">{r.before}</span> → {r.after}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
            Yalnız görünməz fərqlər düzəlir: latın sözün içindəki kiril hərf (məs. «mәktәb»-dəki ә), boşluq, tırnaq,
            tire. Böyük/kiçik hərfə toxunulmur. Fərqli adların eyni standart ada düşdüyü qrup sayı:{" "}
            {data.names.collisions.length} (hamısı eyni adın iki yazılışı).
          </p>
        </DashboardCard>

        <DashboardCard title="Veri sahibinə sual" subtitle="Eyni yer iki fərqli yemək növündə — silinmədi">
          <div className="space-y-1 text-[11.5px]">
            {data.cross_food.examples.map((r: any, i: number) => (
              <div key={i} className="flex justify-between gap-3 rounded border bg-background px-2 py-1">
                <span>
                  {r.name_a} <span className="text-muted-foreground">({categoryLabel(r.category_a)})</span>
                </span>
                <span>
                  {r.name_b} <span className="text-muted-foreground">({categoryLabel(r.category_b)})</span>
                </span>
              </div>
            ))}
          </div>
        </DashboardCard>
      </div>
    </div>
  );
}
