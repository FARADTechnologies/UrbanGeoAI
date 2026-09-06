# Web paneli

Əlçatanlıq indekslərinin arayüzü. GeoInvest platformasının arayüzündən
miras alınıb və bu layihə üçün paralel inkişaf etdirilir.

## Nə miras alındı

Platformadan olduğu kimi gələnlər:

| Parça | Nə üçün |
|---|---|
| `src/app/globals.css`, `tailwind.config.ts` | Rəng tokenləri, işıqlı/qaranlıq tema, marka narıncısı |
| `src/components/ui/*` | shadcn primitivləri |
| `src/components/theme-provider.tsx` | Tema seçimi və yaddaşda saxlanması |
| `src/components/dashboard/dashboard-card.tsx` | Standart kart |
| deck.gl `H3HexagonLayer` + MapLibre quruluşu | Xəritə |

Yığın da eynidir: Next.js 15, React 19, Tailwind, deck.gl 9, MapLibre GL.
Beləliklə iki tərəf bir-birindən uzaqlaşmır — platformada dəyişən bir token
buraya da gətirilə bilir.

## Nə yenidir

Yeddi görünüş: **İcmal**, **Xəritə**, **İndekslər**, **Metro**,
**Veri denetimi**, **Dəyişim**, **Təkliflər**.

Xəritə H3 hüceyrələrini üç səviyyədə (H7 / H8 / H9) göstərir; rəng seçilmiş
indeksin balıdır, ikinci rejimdə isə iki veri sürümü arasındakı fərqdir.
Hüceyrənin üstünə gələndə yeddi indeksin hamısı və dəyişimləri görünür.
POI qatı istənilən kateqoriyanı nöqtə olaraq üstünə çəkir.

## Veri

Arxa uç yoxdur. Panel `public/data/` altındakı statik JSON-u oxuyur:

| Fayl | İçindəkilər |
|---|---|
| `summary.json` | Sayğaclar, PCA, korelyasiya, metro qərarları, doğrulama, müqayisə, β həssaslığı |
| `cells-r7.json`, `cells-r8.json`, `cells-r9.json` | Hər səviyyə üçün H3 indeksləri və bal/fərq dizileri |
| `poi.json` | Kateqoriya başına nöqtələr |

Bu fayllar depoda saxlanmır — iş ortağının POI koordinatlarını daşıyır.

```bash
python scripts/build_web_data.py     # depo kökündən
```

Panelin göstərdiyi heç bir rəqəm əl ilə yazılmır; hamısı bu betiyin
çıxışından gəlir.

## İşə salmaq

```bash
cd web
npm install
npm run dev
```

<http://localhost:3000>

Alt xəritə plitələri CARTO-dan çəkilir, ona görə xəritə görünüşü internet
tələb edir. Qalan görünüşlər oflayn işləyir.

## Yoxlamalar

```bash
npm run typecheck
npm run lint
```
