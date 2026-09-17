"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { KpiGrid } from "@/components/dashboard/kpi-grid";
import { categoryColor, categoryLabel, formatCount } from "@/lib/data";
import type { Summary } from "@/types/data";

const REASONS: Record<string, string> = {
  "çox kiçik sahə": "Park < 2 000 m² (meydan, ağaclı künc)",
  adsız: "Adı olmayan otel, universitet, muzey…",
  "adı kateqoriyaya uymur": "Kinoteatr, kurs, mini market, yataqxana",
  "ali təhsil deyil (college)": "Peşə məktəbi, sürücülük kursu"
};

export function EnrichmentView({ summary }: { summary: Summary }) {
  const e = summary.enrichment;
  if (!e) {
    return (
      <DashboardCard title="OSM zənginləşdirmə" subtitle="Hesabat tapılmadı">
        <p className="text-[12px] text-muted-foreground">
          Əvvəlcə <span className="font-mono">python scripts/enrich_osm.py</span> işlədilməlidir.
        </p>
      </DashboardCard>
    );
  }

  const rows = [...e.categories].sort((a, b) => b.added - a.added);
  const max = Math.max(...rows.map((r) => r.total), 1);
  const filtered = Object.values(e.rejected_by_reason).reduce((a, b) => a + b, 0);

  return (
    <>
      <KpiGrid
        items={[
          { label: "Yerli hovuz", value: formatCount(e.totals.local), note: "iş ortağının 2026 verisi" },
          { label: "OSM-də tapılan", value: formatCount(e.osm_elements), note: "metro xaric, bütün kateqoriyalar" },
          { label: "Süzgəcdən keçən", value: formatCount(e.after_rules), note: `${formatCount(e.after_dedupe - e.after_rules)} uyğunsuz atıldı` },
          { label: "Artıq var idi", value: formatCount(e.totals.matched), note: "yerli veridə qarşılığı var" },
          { label: "Yeni əlavə", value: `+${formatCount(e.totals.added)}`, note: "hovuza qatıldı", tone: "up" },
          {
            label: "Yeni hovuz",
            value: formatCount(e.totals.local + e.totals.added),
            note: `+${((e.totals.added / e.totals.local) * 100).toFixed(1)}%`,
            tone: "up"
          }
        ]}
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <DashboardCard
          title="Kateqoriya üzrə: yerli + OSM əlavəsi"
          subtitle="Tünd hissə iş ortağının verisi, açıq hissə OpenStreetMap-dən gələn yeni obyektlər"
        >
          <div className="space-y-2">
            {rows.map((r) => (
              <div key={r.category} className="grid grid-cols-[132px_1fr_112px] items-center gap-2">
                <span className="flex items-center gap-1.5 truncate text-[11.5px]">
                  <span className="h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ background: categoryColor(r.category) }} />
                  {categoryLabel(r.category)}
                </span>
                <div className="flex h-3 overflow-hidden rounded-full bg-muted">
                  <div style={{ width: `${(r.local / max) * 100}%`, background: categoryColor(r.category) }} />
                  <div
                    style={{
                      width: `${(r.added / max) * 100}%`,
                      background: categoryColor(r.category),
                      opacity: 0.35
                    }}
                  />
                </div>
                <span className="text-right text-[11px] tabular-nums">
                  <span className="text-muted-foreground">{formatCount(r.local)}</span>
                  <span className="ml-1 font-semibold text-[var(--ok-500)]">+{formatCount(r.added)}</span>
                </span>
              </div>
            ))}
          </div>
        </DashboardCard>

        <div className="grid content-start gap-4">
          <DashboardCard title="Necə işləyir" subtitle="28 May nümunəsi">
            <ol className="list-decimal space-y-2 pl-4 text-[12px] leading-relaxed text-muted-foreground">
              <li>
                Yerli veridə <b className="text-foreground">A, B, C</b> kafeləri var. OpenStreetMap-də{" "}
                <b className="text-foreground">A, B, C, D, E</b>.
              </li>
              <li>
                Hər OSM obyekti üçün ən yaxın yerli qeyd tapılır. Kafe üçün <b className="text-foreground">30 m</b>{" "}
                içindədirsə «artıq var» sayılır — A, B, C atılır.
              </li>
              <li>
                <b className="text-foreground">D, E</b> yerli veridə yoxdur → hovuza əlavə olunur və
                mənbəyi «osm» kimi işarələnir.
              </li>
              <li>Şübhədə əlavə edilmir: kafe restoranla, bağça məktəblə də yoxlanılır.</li>
            </ol>
          </DashboardCard>

          <DashboardCard
            title="Süzgəcdən atılanlar"
            subtitle={`${formatCount(filtered)} OSM obyekti yerli kateqoriyanın tərifinə uymadı`}
          >
            <div className="space-y-1.5">
              {Object.entries(e.rejected_by_reason).map(([reason, n]) => (
                <div key={reason} className="flex items-start justify-between gap-3 rounded-lg border bg-background px-3 py-2">
                  <div>
                    <div className="text-[12px] font-medium">{reason}</div>
                    <div className="text-[11px] text-muted-foreground">{REASONS[reason] ?? ""}</div>
                  </div>
                  <span className="text-[12px] font-semibold tabular-nums">{formatCount(n)}</span>
                </div>
              ))}
            </div>
          </DashboardCard>
        </div>
      </div>

      <DashboardCard title="Tam cədvəl" subtitle="Eşləşmə radiusu obyektin fiziki ölçüsünə görə seçilib">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-separate border-spacing-0 text-left text-[12px]">
            <thead>
              <tr>
                {["Kateqoriya", "Yerli", "OSM", "Süzülən", "Artıq var", "Yeni", "Cəmi", "Artım", "Radius"].map((h, i) => (
                  <th
                    key={h}
                    className={`border-b px-3 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground ${i ? "text-right" : ""}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.category} className="hover:bg-muted/30">
                  <td className="border-b px-3 py-2 font-medium">{categoryLabel(r.category)}</td>
                  <td className="border-b px-3 py-2 text-right tabular-nums">{formatCount(r.local)}</td>
                  <td className="border-b px-3 py-2 text-right tabular-nums">{formatCount(r.osm)}</td>
                  <td className="border-b px-3 py-2 text-right tabular-nums text-muted-foreground">{formatCount(r.filtered)}</td>
                  <td className="border-b px-3 py-2 text-right tabular-nums">{formatCount(r.matched)}</td>
                  <td className="border-b px-3 py-2 text-right font-semibold tabular-nums text-[var(--ok-500)]">+{formatCount(r.added)}</td>
                  <td className="border-b px-3 py-2 text-right font-semibold tabular-nums">{formatCount(r.total)}</td>
                  <td className="border-b px-3 py-2 text-right tabular-nums">{r.growth_pct.toFixed(1)}%</td>
                  <td className="border-b px-3 py-2 text-right tabular-nums text-muted-foreground">{e.match_radius_m[r.category]} m</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          Park kateqoriyası ən çox böyüyən kateqoriyadır: yerli fayl əsasən böyük parkları saxlayır,
          OSM isə bağları və xiyabanları da tanıyır. Yeni gələn parkların orta ölçüsü yerli parklarınkına
          yaxındır, yəni bunlar kiçik küncələr deyil. Veri OpenStreetMap katkıçılarına aiddir (ODbL).
        </p>
      </DashboardCard>
    </>
  );
}
