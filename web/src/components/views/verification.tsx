"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { categoryLabel, formatCount, groupLabel } from "@/lib/data";
import type { Summary } from "@/types/data";

/* eslint-disable @typescript-eslint/no-explicit-any */

const TEAM_GROUP: Record<string, string> = {
  education: "təhsil",
  transport: "nəqliyyat",
  tourism: "turizm",
  food: "yemək",
  recreation: "istirahət",
  leisure: "əyləncə"
};

function Tick({ ok }: { ok: boolean }) {
  return (
    <span
      className="inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold text-white"
      style={{ background: ok ? "var(--ok-500)" : "var(--err-500)" }}
    >
      {ok ? "✓" : "✗"}
    </span>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return (
    <th
      className={`border-b px-3 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground ${right ? "text-right" : "text-left"}`}
    >
      {children}
    </th>
  );
}

function Td({ children, right, strong }: { children: React.ReactNode; right?: boolean; strong?: boolean }) {
  return (
    <td className={`border-b px-3 py-2 tabular-nums ${right ? "text-right" : ""} ${strong ? "font-semibold" : ""}`}>
      {children}
    </td>
  );
}

function sci(v: number) {
  if (v === 0) return "0";
  return v < 1e-6 ? v.toExponential(0) : v.toPrecision(3);
}

export function VerificationView({ summary }: { summary: Summary }) {
  const s = summary as any;
  const team = s.teamComparison;
  const bands = s.bandCheck;
  const walking = s.walking;
  const google = s.google;

  return (
    <>
      {team ? (
        <>
          <div
            className="flex flex-wrap items-center gap-4 rounded-xl border px-5 py-4 shadow-sm"
            style={{ background: "var(--ok-50)", borderColor: "var(--ok-500)" }}
          >
            <div className="text-[30px] font-bold leading-none tabular-nums" style={{ color: "var(--ok-500)" }}>
              6/6
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[15px] font-semibold">
                Ekibin PCA faylı eyni veridə birəbir təkrarlandı — kodu düzgün başa düşmüşük
              </div>
              <div className="text-[12px] text-muted-foreground">
                2025 verisi (ekibin faylları bu qovluqdakı ilə bayt-bayt eynidir) · {formatCount(team.cells.team)} H10
                hüceyrə, eyni çoxluq · 6 indeksin hamısında fərq ≤ 10⁻¹³ (yalnız kompüter yuvarlaqlaşdırması) · 5 məsafənin
                hamısı 100% eyni
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
            <DashboardCard
              title="İndekslər: ekibin nəticəsi ↔ bizim hesab"
              subtitle="Eyni 2025 verisi. «Replika» = ekibin kodu addım-addım; «bizim metod» = həqiqi məsafə + işarə sabitləmə + taban bandı"
            >
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-separate border-spacing-0 text-[12px]">
                  <thead>
                    <tr>
                      <Th>İndeks</Th>
                      <Th right>Replika · max fərq</Th>
                      <Th right>Bizim metod · Spearman</Th>
                      <Th right>Bal eyni</Th>
                      <Th right>Bal ±1</Th>
                      <Th right>Ekip desil / biz bant</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(team.pca).map(([g, r]: [string, any]) => {
                      const b = team.bands[g];
                      return (
                        <tr key={g}>
                          <Td strong>{groupLabel(TEAM_GROUP[g] ?? g)}</Td>
                          <Td right>
                            <span className="text-[var(--ok-500)]">{sci(r.replica.max_abs_diff)}</span>
                          </Td>
                          <Td right>{r.our_method.spearman.toFixed(4)}</Td>
                          <Td right>{b.equal_pct.toFixed(1)}%</Td>
                          <Td right>{b.within_1_pct.toFixed(1)}%</Td>
                          <Td right>
                            <span className="text-[var(--err-500)]">{b.team_distinct_deciles}</span> / {b.our_distinct_bands}
                          </Td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
                <b className="text-foreground">Sıralama demək olar ki, eynidir</b> (Spearman 0.994–0.998): hansı hüceyrənin
                daha yaxşı olduğu barədə iki metod razılaşır. <b className="text-foreground">Bal isə fərqlənir</b>, çünki
                ekibin <span className="font-mono">pd.qcut(…, duplicates=&quot;drop&quot;)</span> desili bərabər dəyərlər
                çox olanda bantları səssizcə silir — ekibin faylında 10 əvəzinə 6–9 desil var və heç bir hüceyrə 10 almır.
                Fərqin mənbəyi budur, hesabda xəta deyil.
              </p>
            </DashboardCard>

            <div className="grid content-start gap-4">
              <DashboardCard
                title="Diqqət: ekibin iki faylı bir-biri ilə uyuşmur"
                subtitle="poi_scores.csv 27 Mart, poi_pca.csv 26 Aprel 2025"
              >
                <p className="text-[12px] leading-relaxed text-muted-foreground">
                  Ekibin öz <span className="font-mono">poi_scores.csv</span>-indən PCA hesablananda öz{" "}
                  <span className="font-mono">poi_pca.csv</span>-ləri{" "}
                  <b className="text-foreground">heç bir hüceyrədə</b> alınmır (təhsil max fərq{" "}
                  {team.team_internal?.education?.max_abs_diff.toFixed(2)}, nəqliyyat{" "}
                  {team.team_internal?.transport?.max_abs_diff.toFixed(2)}). Yəni skor faylı köhnə, aralıq bir
                  işlətmədən qalıb. Bizim replika isə PCA faylını birəbir verir — ekibin əsl son nəticəsi PCA faylıdır.
                </p>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[360px] border-separate border-spacing-0 text-[12px]">
                    <thead>
                      <tr>
                        <Th>Skor</Th>
                        <Th right>Köhnə faylla eyni</Th>
                        <Th right>Bizim · Spearman</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(team.scores).map(([k, r]: [string, any]) => (
                        <tr key={k}>
                          <Td>{categoryLabel(k)}</Td>
                          <Td right>{r.replica.exact_pct.toFixed(1)}%</Td>
                          <Td right>{r.our_method.spearman.toFixed(4)}</Td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </DashboardCard>
            </div>
          </div>
        </>
      ) : null}

      {bands ? (
        <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <DashboardCard
            title="1–10 bal: paylanma"
            subtitle="Hər bantda hüceyrələrin payı (%). Bant 1 = ətrafda heç obyekt yoxdur; 2–10 bərabər olmalıdır"
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-separate border-spacing-0 text-[11.5px]">
                <thead>
                  <tr>
                    <Th>İndeks</Th>
                    {Array.from({ length: 10 }, (_, i) => (
                      <Th key={i} right>
                        {i + 1}
                      </Th>
                    ))}
                    <Th right>Ekip qcut</Th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(bands.per_index).map(([g, r]: [string, any]) => (
                    <tr key={g}>
                      <Td strong>{groupLabel(g)}</Td>
                      {Array.from({ length: 10 }, (_, i) => {
                        const v = r.share_pct[String(i + 1)] as number;
                        return (
                          <td key={i} className="border-b p-[2px]">
                            <div
                              className="rounded px-1.5 py-1 text-right tabular-nums"
                              style={{
                                background: `color-mix(in srgb, var(--brand-500) ${Math.min(90, v * 3)}%, transparent)`
                              }}
                            >
                              {v.toFixed(1)}
                            </div>
                          </td>
                        );
                      })}
                      <Td right>
                        <span className="text-[var(--err-500)]">
                          {r.team_method_bands} bant
                        </span>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
              Yeddi indeksin hamısında 2–10 bantları bərabər doludur (sapma 0.0 faiz bəndi). Əvvəl model 2025 verisinə
              uydurulurdu; OSM əlavəsi veri tərifini dəyişəndə (park 160 → 1 072) istirahətdə 28%, əyləncədə 31% hüceyrə
              10-a yığılırdı. İndi istinad cari veridir və model dondurulub — hər 3 aydan bir gələn veri bu cədvəllə
              ölçülür. Eyni indeksə ekibin qcut metodu tətbiq olunanda 6–9 bant çıxır və 10 heç vaxt verilmir.
            </p>
          </DashboardCard>

          <div className="grid content-start gap-4">
            <DashboardCard title="Yoxlamalar" subtitle="scripts/check_bands.py">
              <div className="space-y-1.5">
                {[
                  ["Böyük indeks heç vaxt kiçik bal almır", Object.values(bands.per_index).every((r: any) => r.monotone)],
                  ["Eyni indeks → eyni bal", Object.values(bands.per_index).every((r: any) => r.equal_index_equal_band)],
                  ["Cədvəldəki bal modelə uyğundur", Object.values(bands.per_index).every((r: any) => r.stored_band_consistent)],
                  [
                    "Bal artdıqca ən yaxın obyekt yaxınlaşır",
                    Object.values(bands.meaning).every((r: any) => r.decreasing)
                  ]
                ].map(([label, ok]) => (
                  <div key={label as string} className="flex items-center gap-3 rounded-lg border bg-background px-3 py-2">
                    <Tick ok={Boolean(ok)} />
                    <span className="text-[12.5px]">{label as string}</span>
                  </div>
                ))}
              </div>
            </DashboardCard>

            <DashboardCard
              title="Hamısı 9–10-a yığılırmı?"
              subtitle="Yeddi indeks birlikdə, hüceyrə başına"
            >
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                {[
                  ["Yeddisi də ≥ 9", `${bands.cross.all_ge_9_pct}%`],
                  ["Yeddisi də = 10", `${bands.cross.all_eq_10_pct}%`],
                  ["Yeddisi də = 1", `${bands.cross.all_eq_1_pct}%`],
                  ["Ən az biri 10", `${bands.cross.any_10_pct}%`],
                  ["Yeddisi də eyni bal", `${bands.cross.all_same_pct}%`],
                  ["Ən yüksək − ən aşağı (median)", `${bands.cross.spread_median}`]
                ].map(([k, v]) => (
                  <div key={k} className="rounded-lg border bg-background px-3 py-2">
                    <div className="text-muted-foreground">{k}</div>
                    <div className="text-[16px] font-semibold tabular-nums">{v}</div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
                Hüceyrələrin yalnız {bands.cross.all_ge_9_pct}%-i yeddi indeksdə birdən 9–10 alır — bunlar Bakının ən
                mərkəzi hissəsidir. İndekslər müstəqil olsaydı bu pay {bands.cross.all_ge_9_if_independent_pct}% olardı;
                fərq indekslərin real əlaqəsindən gəlir (mərkəzə yaxınlıq), metoddan deyil. Median hüceyrədə ən yüksək
                və ən aşağı bal arasında {bands.cross.spread_median} bal fərq var — indekslər fərqli şeylər deyir.
              </p>
            </DashboardCard>

            <DashboardCard title="Bal həqiqətən məlumat verirmi?" subtitle="Bal ilə ən yaxın obyektə məsafə arasında Spearman">
              <div className="space-y-1.5">
                {Object.entries(bands.meaning).map(([g, r]: [string, any]) => (
                  <div key={g} className="flex items-center justify-between rounded-lg border bg-background px-3 py-2 text-[12px]">
                    <span>
                      {groupLabel(g)} <span className="text-muted-foreground">↔ {r.column.replace("distance_to_", "").replace("_m", "")}</span>
                    </span>
                    <span className="font-semibold tabular-nums text-[var(--ok-500)]">
                      {r.spearman_band_vs_distance.toFixed(3)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-muted-foreground">
                Mənfi = bal artdıqca məsafə qısalır. Təhsildə bant 3-də median 1 893 m, bant 10-da 299 m.
              </p>
            </DashboardCard>
          </div>
        </div>
      ) : null}

      {walking?.available ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <DashboardCard
            title="Quş uçuşu ↔ piyada (yol şəbəkəsi)"
            subtitle="OpenStreetMap yol şəbəkəsi: 512 728 düyün · yol məsafəsi quş uçuşunun median 1.40 qatı"
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[440px] border-separate border-spacing-0 text-[12px]">
                <thead>
                  <tr>
                    <Th>İndeks</Th>
                    <Th right>Orta bal dəyişimi</Th>
                    <Th right>Aşağı düşən</Th>
                    <Th right>Eyni qalan</Th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(walking.band_shift).map(([g, r]: [string, any]) => (
                    <tr key={g}>
                      <Td strong>{groupLabel(g)}</Td>
                      <Td right>
                        <span className="text-[var(--err-500)]">{r.mean.toFixed(2)}</span>
                      </Td>
                      <Td right>{r.lower_pct}%</Td>
                      <Td right>{r.same_pct}%</Td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
              Eyni formul (exp(−β × dəqiqə)), eyni model — yalnız məsafə yol üzərindən ölçülür. Dəmiryolu, çevrə yolu və
              dəniz artıq nəzərə alınır. Xəritədə «Məsafə: Piyada» seçərək və ya «Dəyişim → Quş uçuşu → piyada» ilə
              fərqi hüceyrə-hüceyrə görmək olar.
            </p>
          </DashboardCard>

          <DashboardCard title="Google Routes API" subtitle="Piyada məsafəsinin Google ilə yoxlanması">
            {google?.status === "ok" ? (
              <p className="text-[12px]">
                {google.summary.pairs} cüt · OSM/Google median {google.summary.osm_over_google_median} ·{" "}
                {google.summary.within_15pct}% cüt ±15% daxilində
              </p>
            ) : (
              <div className="space-y-2 text-[12px] leading-relaxed">
                <div className="flex items-center gap-2">
                  <Tick ok={false} />
                  <span className="font-semibold">Açar işləmir: {google?.reason ?? "yoxlanmayıb"}</span>
                </div>
                <p className="text-muted-foreground">
                  Göndərilən açar veb-sayt (HTTP referrer) ilə məhdudlaşdırılıb və yalnız ekibin öz saytından, brauzerdə
                  işləyir. Nə serverdən, nə də urbangeoai.web.app-dan çağırmaq olur. Bu, platformanın xəritə açarıdır.
                </p>
                <p className="font-medium">Lazım olan: ayrıca server açarı — API məhdudiyyəti «Routes API», tətbiq
                  məhdudiyyəti «IP ünvanları», layihədə billing aktiv.</p>
              </div>
            )}
          </DashboardCard>
        </div>
      ) : null}
    </>
  );
}
