# UrbanGeoAI

Bakı ve Abşeron için coğrafi erişilebilirlik indeksleri üreten veri hattı.
Şehir altıgen bir ızgaraya bölünür, her hücrenin çevresindeki hizmetler
mesafeye göre ağırlıklandırılır ve temel bileşen analiziyle kategori başına
tek bir erişilebilirlik puanına indirgenir.

Üretilen puanlar bir emlak analitiği ürününde konum değerlendirmesi için
kullanılır: bir adresin eğitim, ulaşım, yeme-içme, eğlence, turizm ve
istirahat açısından ne kadar erişilebilir olduğu.

## Nasıl çalışır

| Adım | Yapılan iş |
|---|---|
| 1 | Analiz alanı H3 çözünürlük 10 altıgenlerle doldurulur (altıgen başına ~15 000 m², kenar ~76 m) |
| 2 | İdari sınır poligonuyla kesiştirilerek deniz ve alan dışı hücreler atılır |
| 3 | Her hizmet kategorisi (məktəb, kafe, metro, park…) konum tablosu olarak yüklenir |
| 4 | Her hücre için kategori skoru hesaplanır: kesme mesafesi içindeki her noktanın `exp(-β · yürüme dakikası)` katkısının toplamı |
| 5 | İlişkili kategoriler gruplanır ve temel bileşen analiziyle tek indekse indirgenir |
| 6 | Sürekli indeks 1–10 arası banda çevrilir |

`β` katsayısı kategoriye göre değişir: metroya uzağa yürünür (küçük `β`),
otobüs durağına yürünmez (büyük `β`).

## Tasarım kararları

Üç konu, yöntemin sonucunu doğrudan etkilediği için açıkça ele alınmıştır.

**Bileşenin işareti sabitlenir.** Temel bileşen analizinde birinci bileşenin
işareti keyfîdir; kütüphane onu veriye göre seçer. Yükler negatif çıkarsa
indeks tersine döner ve en erişilebilir hücre en düşük puanı alır. Bu hiçbir
hata üretmeden gerçekleşir. Yüklerin toplamı negatifse bileşen çevrilir.

**Taban kütlesi ayrı ele alınır.** Hücrelerin önemli bir bölümü çevresinde hiç
hizmet bulunmadığı için aynı en düşük değeri taşır. Eşit değerler aynı dilime
düşmek zorunda olduğundan yüzdelik dilimleme fazla dilimleri sessizce siler;
on bant istenirken beş bant üretilebilir. Taban kütlesi doğrudan birinci banda
verilir, kalan hücreler dokuz dilime bölünür. Böylece en yüksek bant gerçekten
onuncu banttır.

**Model dondurulur.** Ölçekleyici, bileşen yükleri ve bant sınırları her
çalıştırmada yeniden öğrenilirse referans çerçevesi kayar: çevresinde hiçbir
şey değişmemiş bir hücrenin puanı, başka hücreler değiştiği için oynar. Model
bir kez uydurulup diske yazılır; sonraki veri sürümleri bu modelle puanlanır.
Böylece puan değişimi gerçek bir değişimi gösterir.

## Kurulum

Python 3.11 veya üzeri gerekir. Coğrafi bağımlılıklar derlenmiş kütüphaneler
içerdiği için sanal ortam önerilir.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,notebooks]"
```

Konfigürasyonu oluşturun ve kendi yollarınızı yazın:

```bash
cp config/paths.example.yml config/paths.yml
```

Doğrulayın:

```bash
python -m urbangeoai.config
```

Bu komut kullanılan konfigürasyon dosyasını, çözülen yolları ve varsa eksik
dizinleri listeler.

## Veri

Depo veri içermez. Üç kaynak vardır:

| Kaynak | Nereden | Depoda |
|---|---|---|
| POI veri kümeleri | İş ortağı tarafından sağlanır | Hayır |
| İdari sınırlar | İlk çalıştırmada indirilir | Hayır, lisans nedeniyle |
| OpenStreetMap sorguları | Overpass API, önbelleğe alınır | Hayır, lisans nedeniyle |
| Sentetik örnek veri | Depoyla gelir | `data/sample/` |

POI dosyalarını `config/paths.yml` içinde `paths.raw_current` ile gösterilen
dizine yerleştirin. Beklenen biçim en az `lat` ve `lon` sütunlarıdır; `long`,
`longitude`, `latitude` varyantları otomatik normalleştirilir. `name` sütunu
bulunmayan dosyalar (durak, kamera) desteklenir.

OpenStreetMap verisi OpenStreetMap katkıcılarına aittir ve ODbL ile
lisanslanmıştır.

## Kullanım

```python
from pathlib import Path

from urbangeoai import config, grid, io, indices, scoring

settings = config.load()
boundary = grid.load_boundary(settings.paths.reference)
cells = grid.land_cells(settings.bbox, settings.h3_resolution, boundary)

schools = io.read_poi(settings.paths.raw_current / "mekteb.csv").frame
cells["schl_score"] = scoring.decay_score(cells, schools, beta=0.2)
```

İndeks uydurma ve puanlama:

```python
model = indices.fit_group(cells, ["kdgr", "schl", "univ"])
index, bands = indices.score_group(cells, model)
indices.save_model({"education": model}, Path("out/model.json"))
```

Sonraki veri sürümleri aynı modelle puanlanır:

```python
model = indices.load_model(Path("out/model.json"))["education"]
index, bands = indices.score_group(new_cells, model)
```

## Veri denetimi

POI dosyalarını kullanmadan önce doğruluk denetiminden geçirin:

```bash
python scripts/validate_data.py
```

Denetim veriyi değiştirmez; ölçer ve raporlar. Kontrol ettikleri: zorunlu
sütunlar, koordinat aralığı ve hassasiyeti, analiz alanı dışındaki kayıtlar,
boş isim ve kategori alanları, birebir ve yakın tekrarlar, dosya kodlaması.

Bulgular üç düzeyde raporlanır. `error` veriyi kullanılamaz kılar, `warning`
sonucu bozabilir, `info` yalnızca kayıt amaçlıdır.

```bash
python scripts/validate_data.py --dir yol/         # belirli bir dizin
python scripts/validate_data.py --json rapor.json  # makine okunur çıktı
python scripts/validate_data.py --strict           # hata varsa 1 döndür
```

Eşik değerleri `config/paths.yml` içindeki `validation` bölümünden okunur.

Birebir tekrar ile yakın tekrar ayrı raporlanır, çünkü yorumları farklıdır:
aynı zincirin iki şubesi meşru olabilir, aynı okulun iki kaydı değildir. İsim
sütunu bulunmayan dosyalarda isim karşılaştırılamadığı için bunun yerine
yakın konum yoğunluğu ölçülür.

## Testler

```bash
pytest
ruff check src tests scripts
ruff format --check src tests scripts
```

Testler sentetik veri kullanır; ağ erişimi veya iş ortağı verisi gerektirmez.

## Depo yapısı

```
src/urbangeoai/     Kütüphane kodu
  config.py         Yol ve parametre konfigürasyonu
  io.py             POI dosyalarının okunması ve normalleştirilmesi
  osm.py            Overpass istemcisi
  grid.py           H3 ızgarası ve kara maskesi
  scoring.py        Mesafeye göre azalan skorlar
  indices.py        Bileşik indeksler ve bantlama
  validation.py     Veri doğruluk denetimi
notebooks/          Keşif ve analiz defterleri
scripts/            Komut satırı araçları
tests/              Birim testleri ve sentetik veri
docs/               Metodoloji belgeleri
config/             Konfigürasyon şablonu
```

## Bilinen sınırlar

**Analiz alanı sınır kutusuyla tanımlıdır.** Kutu Bakı'nın idari sınırının
tamamını kapsamaz; Qaradağ rayonunun güney kesimi kapsam dışında kalır.
Kapsam kararı gözden geçirilmeyi bekliyor.

**Mesafeler kuş uçuşudur.** Yol ağı, deniz ve demiryolu gibi engeller
modellenmez. Gerçek yürüme mesafesi tipik olarak daha uzundur.

**Azalım katsayıları kalibre edilmemiştir.** Mevcut değerler önceki
çalışmadan devralınmıştır; türetildikleri hedef değişken belgelenmemiş.

**İndeksler birbiriyle güçlü ilişkilidir.** Gruplar arasında ortak kategoriler
bulunduğu ve hepsi merkeze yakınlıkla ilişkili olduğu için indeksler bağımsız
değildir.

**Kara maskesi sonucu belirler.** Farklı bir sınır dosyası farklı bir hücre
kümesi üretir. Sürümler arası karşılaştırma yapılacaksa maske sabit tutulmalıdır.

## Yol haritası

- POI veri kümeleri için sistematik doğrulama denetimi
- OpenStreetMap metro verisinin tekilleştirilmesi
- Kategori kapsamının dış kaynaklarla karşılaştırılması
- Bant yönteminin alternatiflerinin değerlendirilmesi
- Temel bileşen analizi metodolojisinin belgelenmesi

## Lisans

Tüm hakları saklıdır. Ayrıntılar için `LICENSE` dosyasına bakın.
