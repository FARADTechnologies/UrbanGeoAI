# Öneriler

Bu belgedeki maddeler iş ortağından gelmedi; çalışma sırasında ortaya çıktı ve
teklif olarak sunuluyor. Her biri için ne olduğu, neden gerektiği ve maliyeti
yazılı.

---

## 1. Yürüme mesafesi: kuş uçuşu yerine yol şebekesi

### Durum

Bütün mesafeler düz çizgi. Kod tabanında yol şebekesiyle ilgili hiçbir şey yok;
başlangıçtan beri böyle.

Gerçek yürüme mesafesi tipik olarak kuş uçuşunun **1.3–1.4 katı**. Daha
önemlisi, engeller hiç modellenmiyor: deniz, dəmiryolu, çevrə yolu, uçurum.

Somut sonuç: bir məktəb küçənin o tayında da olsa, dəmiryolunun o tayında da
olsa aynı balı veriyor. Biri iki dəqiqə, digəri iyirmi.

### Üç seçenek

**a) Google Directions API.** En güncel veri, en doğru sonuç.

Ama ölçek uymuyor. 120 349 hüceyrə × kategori başına en yakın birkaç nokta ≈
milyonlarca sorgu. Google'ın ücretlendirmesi bin sorgu başına; bu hacimde
maliyet altı haneli rakamlara çıkar. Ayrıca hız sınırı var ve sonuçların
saklanması lisans şartlarına tabi.

Küçük ölçekte anlamlı: bir mənzil raporu açıldığında **o tek nokta için**
canlı sorgu atmak mümkün ve makul. Toplu indeks üretimi için değil.

**b) OpenStreetMap yol şebekesi + yerel yönlendirme.** Önerilen yol.

Bakının yürüyüş şebekesi OSM'de mevcut. Yerel bir yönlendirme motoru (OSRM
veya benzeri) kurulur ve mesafeler bir kez hesaplanır. İnternet gerekmez,
sorgu ücreti yoktur, sonuç tekrar üretilebilir.

Maliyet: kurulum bir günlük iş, ilk hesaplama birkaç saat. Sonrasında veri
yenilendikçe tekrar çalıştırılır.

**c) Engel cezası.** Ucuz yaklaşım.

Kuş uçuşu korunur ama iki nokta arasında dəniz, dəmiryolu veya çevrə yolu
kesişiyorsa mesafeye ceza eklenir. Doğru değil ama şu ankinden iyi ve bir
günde yapılabilir.

### Öneri

**(b)** kalıcı çözüm, **(c)** ara çözüm. **(a)** yalnızca tek nokta raporu için.

---

## 2. POI kalite ağırlığı

### Durum

Kaynak dosyalarda yalnız `id`, `ad`, `tip` ve koordinat var. Sonuç olarak beş
ulduzlu otel ile kiçik qonaq evi, iyirmi min tələbəli universitet ilə balaca
kollec eyni çəkidə sayılır.

### Araştırıldı: OpenStreetMap yeterli mi?

Hayır. Bakıdaki nesneler için etiket doluluk oranı ölçüldü:

| Etiket | Otel | Universitet | Ticarət mərkəzi |
|---|---|---|---|
| `stars` | %5 | — | — |
| `rooms` | %6 | — | — |
| `building:levels` | %7 | %20 | %33 |

Bu seyreklikte ağırlıklandırma **zarar verir**. Yıldızı bilinen %5'i
ağırlıklandırıp %95'ini varsayılan değerde bırakmak, hiç ağırlıklandırmamaktan
daha yanlış bir sıralama üretir: veri eksikliği sistematik bir sapmaya dönüşür.

### Seçenekler

**a) İş ortağından ek alan.** En temizi. Tutum, ulduz, tələbə sayı, sahə —
hangisi varsa. Bir sütun bile işe yarar.

**b) Bina alanı.** OSM'de poligon olarak çizilmiş nesnelerin alanı
hesaplanabilir. Ulduz sayısı kadar iyi değil ama büyüklük göstergesi ve
kapsamı daha geniş. Ara çözüm olarak denenebilir.

**c) Olduğu gibi bırak.** Şu anki durum. Savunulabilir: eşit ağırlık,
bilinmeyen bir ağırlıktan dürüsttür.

### Öneri

**(a)** sorulmalı. Cevap olumsuzsa **(c)** kalır; **(b)** ancak ölçülüp
faydası gösterilirse.

---

## 3. Veri yenilemenin otomatikleştirilmesi

### Durum

CSV'ler elle hazırlanıyor. İki sürüm arasında **14 ay** geçmiş.

Bu sürede ölçülen değişim:

| Kategori | Artış |
|---|---|
| ticarət mərkəzi | %22 |
| muzey | %22 |
| idman zalı | %21 |
| dayanacaq | %13 |
| restoran | %12 |
| kafe | %9 |

Ekibin "gündə bir restoran açılır" tespiti doğru. Ama on dört ayda bir
yenileme o hızı tutamaz: indeks yayımlandığı gün bile bir yıllık gecikmeyle
başlıyor.

### Kademeli plan

**Kademe 1 — yarı otomatik (bir haftalık iş).**
Elle hazırlanan dosyalar sabit bir konuma bırakılır. Boru hattı orayı izler,
dosya değişince kendini çalıştırır, doğrulama denetiminden geçirir ve sonucu
üretir. İnsan yalnızca dosyayı bırakır.

Kazanç: üretim adımındaki gecikme ve hata sıfırlanır. Veri toplama hâlâ elle.

**Kademe 2 — kısmi otomatik toplama (iki-üç haftalık iş).**
Bazı kategoriler dış kaynaklardan otomatik çekilebilir. Metro zaten öyle
çalışıyor. Dayanacaq, park, muzey, teatr gibi kategoriler OpenStreetMap'te
makul kapsamda; otomatik çekilip elle hazırlanan veriyle karşılaştırılabilir.

Burada dikkat: OpenStreetMap ile iş ortağının verisi **aynı şeyi ölçmüyor**.
Ticarət mərkəzi örneğinde ölçtük — OSM 166, yerel veri 88 kayıt veriyor ve
OSM'dekilerin çoğu market ya da depo. Otomatik kaynak, elle veriyi
**değiştirmek için değil, eksik kontrolü için** kullanılmalı.

**Kademe 3 — sürekli izleme (aylık döngü).**
Ayda bir otomatik çalışma, önceki sürümle karşılaştırma, eşik aşılırsa uyarı.
"Bu ay kafe sayısı %5 arttı, indeks güncellendi" gibi.

### Öneri

**Kademe 1** hemen yapılabilir ve en büyük kazancı sağlar: üretim artık elle
tetiklenmez. Kademe 2 ve 3, veri sahibiyle kapsam netleştikten sonra.

---

## 4. Kalibrasyonun önceliği

### Durum

On sekiz azalım katsayısı önceki çalışmadan devralındı. Türetildikleri hedef
değişken belgelenmemiş; doğru değerleri kalibrasyon verisi olmadan bulamayız.

### Ölçülen

Doğru değerleri bilmesek de **hangilerinin önemli olduğunu** ölçebiliriz. Her
katsayı ayrı ayrı yarıya indirilip ikiye katlandı ve indeksin ne kadar oynadığı
ölçüldü (`scripts/beta_sensitivity.py`):

| Kategori | En fazla oynayan hücre | Katsayı |
|---|---|---|
| muzey | %84.6 | 0.10 |
| bar | %71.3 | 0.20 |
| park | %68.9 | 0.10 |
| tarixi abidə | %63.1 | 0.10 |
| teatr | %55.0 | 0.10 |
| … | | |
| metro | **%1.5** | 0.05 |
| ali məktəb | %8.0 | 0.10 |

### Okunuşu

**Metro katsayısı neredeyse hiç önemli değil.** İki katına çıkarsa bile
hücrelerin yalnızca %1.5'i oynuyor. Yani 0.05 değeri yanlış seçilmiş olsa bile
sonucu bozmuyor.

**Az sayıda ve merkezde toplanan kategoriler en hassas.** Muzey, teatr, abidə,
bar — hepsi az sayıda ve şəhər mərkəzində yığılmış. Katsayı değişince kimin
"yakın" sayıldığı büyük ölçüde değişiyor.

### Öneri

Kalibrasyon verisi geldiğinde bütün katsayılara aynı emeği vermek gereksiz.
Önce yukarıdaki beşine bakılmalı; alttakiler mevcut değerlerinde bırakılabilir.

---

## 5. Qalıq bal (indekslerin bağımlılığı için)

### Durum

Yedi indeksin arasındaki farklılığın **%78'i tek bir amildir** — pratikte
"mərkəzə nə qədər yaxınsan". Müştəriyə yeddi ayrı bal göstərilir ama hepsi
büyük ölçüde aynı şeyi söyler.

### Öneri

Ortak amil ayrıştırılıp **qalıq** gösterilebilir: "bu nöqtənin təhsili,
yerləşməsinə görə gözləniləndən yaxşıdır."

Mevcut bal korunur, yanına ikinci bir sütun eklenir. Hesaplama maliyeti düşük;
zaten hesaplanan bileşenlerden türetilir.

İnvestor için asıl bilgi budur: mərkəzdə olmanın pahalı olduğunu zaten bilir,
bilmediği şey aynı fiyata daha iyisini bulup bulamayacağıdır.

### Öneri

Ürün tarafı isterse bir günlük iş. Karar onların.

---

## 6. Dayanacaqta yolun iki yönü

### Durum

`dayanacaq.csv`'de yolun karşılıklı iki yönü ayrı kayıt. 1 846 kaydın hiçbirinde
isim yok — hepsinin `name` değeri "dayanacaq" — dolayısıyla eşleştirme ancak
coğrafi olarak kurulabilir.

### Ölçülen

En yakın komşu mesafesi:

| Yüzdelik | Mesafe |
|---|---|
| %5 | 21 m |
| %10 | 27 m |
| %25 | 44 m |
| medyan | 87 m |

Belirli bir yarıçapta komşusu olan durak sayısı:

| Yarıçap | Durak | Pay |
|---|---|---|
| 20 m | 76 | %4.1 |
| 30 m | 223 | %12.1 |
| 50 m | 554 | %30.0 |

Yarıçap büyüdükçe karşılıklı çift olmayan, sadece yakın duran duraklar da
toplanıyor. 20–30 m aralığı gerçek karşılıklı çiftin tipik genişliği; 50 m'de
aynı kavşaktaki farklı hatlar da birleşmeye başlıyor.

### Sonuca etkisi

Duraklar birleştirilip `nəqliyyat` indeksi yeniden üretildi:

| Yarıçap | Durak | Bandı değişen hücre | En büyük fark |
|---|---|---|---|
| 30 m | 1 846 → 1 735 | %1.9 | 1 bant |
| 50 m | 1 846 → 1 567 | %4.3 | 1 bant |

### Okunuşu

**Bu soru işi aksatmıyor.** En agresif birleştirmede bile hücrelerin %95.7'si
yerinde kalıyor ve oynayan hiçbir hücre bir banttan fazla oynamıyor.

Sebebi azalım katsayısının kendisi: `metro` ve `bus` için mesafe eğrisi
yumuşak, 30 metrelik bir kayma skoru neredeyse hiç değiştirmiyor. Aynı sonuç
β duyarlılığı ölçümünde de görülmüştü — metro katsayısı iki katına çıksa bile
hücrelerin yalnızca %1.5'i oynuyordu.

### Öneri

Cevap beklenebilir; bir şeyi bloke etmiyor. Ekip "tek durak sayılsın" derse
30 metrelik birleştirme uygulanır, maliyeti yarım günlük iş.

Not: karşılıklı iki durağı ayrı saymak savunulabilir bir tercih de olabilir —
iki yönde de servis olması gerçekten daha iyi bir erişilebilirliktir. Karar
ürün tarafının.
