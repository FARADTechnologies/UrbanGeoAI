"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import type { Summary } from "@/types/data";

/**
 * Karar bekleyen maddeler.
 *
 * Metinler `docs/oneriler.md` ilə eyni mövzuları izləyir; burada qısaldılmış
 * halı var ki, iclasda ekrandan oxuna bilsin. Ölçülən rəqəmlər summary.json'dan
 * gəlir, əl ilə yazılmır.
 */

type Proposal = {
  title: string;
  situation: string;
  options: { label: string; body: string; recommended?: boolean }[];
};

const PROPOSALS: Proposal[] = [
  {
    title: "Yürüyüş məsafəsi: quş uçuşu yerinə yol şəbəkəsi",
    situation:
      "Bütün məsafələr düz xətt. Kod bazasında yol şəbəkəsi ilə bağlı heç nə yoxdur. Dəmiryolunun o tayındakı məktəb ilə küçənin o tayındakı məktəb eyni balı verir.",
    options: [
      {
        label: "Google Directions API",
        body: "Ən dəqiq, amma miqyas uymur: 120 349 hüceyrə × kateqoriya başına bir neçə nöqtə ≈ milyonlarla sorğu. Tək mənzil hesabatı üçün canlı sorğu məntiqlidir, toplu indeks üçün deyil."
      },
      {
        label: "OpenStreetMap yol şəbəkəsi + yerli yönləndirmə",
        body: "Bakının piyada şəbəkəsi OSM-də var. Yerli motor qurulur, məsafələr bir dəfə hesablanır. İnternet lazım deyil, sorğu haqqı yoxdur, nəticə təkrar istehsal oluna bilir. Quraşdırma bir günlük iş.",
        recommended: true
      },
      {
        label: "Maneə cəriməsi",
        body: "Quş uçuşu qalır, amma iki nöqtə arasında dəniz, dəmiryolu və ya çevrə yolu keçirsə məsafəyə cərimə əlavə olunur. Doğru deyil, amma indikindən yaxşıdır və bir gündə olur."
      }
    ]
  },
  {
    title: "POI keyfiyyət çəkisi",
    situation:
      "Mənbə fayllarda yalnız id, ad, tip və koordinat var. Beş ulduzlu otel ilə kiçik qonaq evi eyni çəkidə sayılır. OpenStreetMap etiketləri ölçüldü: otellərin yalnız 5%-ində ulduz, 6%-ində otaq sayı var.",
    options: [
      {
        label: "İş ortağından əlavə sütun",
        body: "Ən təmizi. Tutum, ulduz, tələbə sayı, sahə — hansı varsa. Bir sütun belə işə yarayır.",
        recommended: true
      },
      {
        label: "Bina sahəsi",
        body: "OSM-də poliqon kimi çəkilmiş obyektlərin sahəsi hesablana bilər. Ulduz qədər yaxşı deyil, amma əhatəsi genişdir."
      },
      {
        label: "Olduğu kimi qalsın",
        body: "Bu seyrəklikdə çəkiləndirmə zərər verir: ulduzu bilinən 5%-i çəkiləndirib 95%-ini standart dəyərdə qoymaq sistematik sapma yaradır. Bərabər çəki, bilinməyən çəkidən dürüstdür."
      }
    ]
  },
  {
    title: "Veri yeniləməsinin avtomatlaşdırılması",
    situation:
      "CSV-lər əl ilə hazırlanır; iki sürüm arasında 14 ay keçib. Bu müddətdə ticarət mərkəzi 22%, muzey 22%, idman zalı 21% artıb. İndeks yayımlandığı gün belə bir illik gecikmə ilə başlayır.",
    options: [
      {
        label: "Kademe 1 — yarı avtomatik",
        body: "Əl ilə hazırlanan fayllar sabit bir yerə qoyulur. Boru hattı oranı izləyir, fayl dəyişəndə özünü işə salır, doğrulamadan keçirir və nəticəni üretir. İnsan yalnız faylı qoyur. Bir həftəlik iş.",
        recommended: true
      },
      {
        label: "Kademe 2 — qismən avtomatik toplama",
        body: "Dayanacaq, park, muzey, teatr kimi kateqoriyalar OSM-dən çəkilə bilər. Diqqət: OSM ilə iş ortağının verisi eyni şeyi ölçmür — ticarət mərkəzində OSM 166, yerli veri 88 qeyd verir. Avtomatik mənbə əvəz etmək üçün deyil, əskik yoxlaması üçündür."
      },
      {
        label: "Kademe 3 — davamlı izləmə",
        body: "Ayda bir avtomatik işləmə, əvvəlki sürümlə müqayisə, həddi aşanda xəbərdarlıq."
      }
    ]
  },
  {
    title: "Qalıq bal",
    situation:
      "Yeddi indeksin arasındakı fərqin böyük hissəsi tək bir amildir — praktikada &laquo;mərkəzə nə qədər yaxınsan&raquo;. Müştəriyə yeddi ayrı bal göstərilir, amma hamısı böyük ölçüdə eyni şeyi deyir.",
    options: [
      {
        label: "Ortaq amil ayrılıb qalıq göstərilsin",
        body: "&laquo;Bu nöqtənin təhsili, yerləşməsinə görə gözləniləndən yaxşıdır.&raquo; Mövcud bal qorunur, yanına ikinci sütun əlavə olunur. İnvestor üçün əsl məlumat budur: mərkəzdə olmağın baha olduğunu onsuz da bilir.",
        recommended: true
      },
      { label: "Olduğu kimi qalsın", body: "Yeddi bal göstərilməyə davam edir." }
    ]
  }
];

export function ProposalsView({ summary }: { summary: Summary }) {
  const shared = summary.cross.evr[0];

  return (
    <>
      <div className="rounded-xl border border-dashed bg-card px-5 py-4">
        <p className="text-[12px] leading-relaxed text-muted-foreground">
          Bu səhifədəki maddələr iş ortağından gəlmədi — iş zamanı ortaya çıxdı və təklif olaraq
          verilir. Qərar onlarındır. Ölçülən rəqəmlər boru hattından gəlir; məsələn yeddi indeksin
          fərqinin <span className="font-semibold text-foreground">{shared}%</span>-i tək amilə
          düşür.
        </p>
      </div>

      {PROPOSALS.map((proposal) => (
        <DashboardCard key={proposal.title} title={proposal.title} subtitle="Durum və seçimlər">
          <p
            className="text-[12px] leading-relaxed text-muted-foreground"
            dangerouslySetInnerHTML={{ __html: proposal.situation }}
          />
          <div className="mt-3 grid gap-2.5 lg:grid-cols-3">
            {proposal.options.map((option) => (
              <div
                key={option.label}
                className="rounded-lg border bg-background p-3.5"
                style={
                  option.recommended
                    ? { borderColor: "var(--brand-500)", boxShadow: "0 0 0 1px var(--brand-500)" }
                    : undefined
                }
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[12px] font-semibold">{option.label}</span>
                  {option.recommended ? (
                    <span className="flex-shrink-0 rounded-full bg-[var(--brand-500)] px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-white">
                      Təklif
                    </span>
                  ) : null}
                </div>
                <p
                  className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground"
                  dangerouslySetInnerHTML={{ __html: option.body }}
                />
              </div>
            ))}
          </div>
        </DashboardCard>
      ))}
    </>
  );
}
