# Katkı kuralları

## Çalışma akışı

Ana dala doğrudan geliştirme yapılmaz. Her anlamlı iş için:

```
Issue  →  çalışma dalı  →  atomik commitler  →  Pull Request  →  CI  →  inceleme  →  merge
```

### Issue

Her özellik, hata, deney ve dokümantasyon işi için önce Issue açılır. Issue
şunları içerir: problem, işin neden gerekli olduğu, beklenen çıktı, kapsam,
kapsam dışı, teknik yaklaşım, ölçülebilir kabul kriterleri ve doğrulama
yöntemi.

Kabul kriterleri ölçülebilir olmalıdır. "Sistem iyi çalışmalı" gibi ifadeler
kullanılmaz; "sınır kutusu dışındaki kayıtlar dosya ve satır bilgisiyle
listelenir" kullanılır.

### Dal adları

İngilizce, kısa ve yapılan işi anlatır. Biçim: `<tür>/<issue>-<konu>`

```
feature/12-service-radius-cap
fix/18-metro-name-filter
data/22-poi-validation-report
docs/31-pca-methodology
test/27-scoring-regression
chore/1-project-scaffold
```

Bir dal tek bir amaç taşır. Bağımsız işler aynı dala doldurulmaz.

### Commit

Commitler küçük, atomik ve tek bir mantıksal değişiklik içerir.

Biçim: `type(scope): açıklama`

Türler: `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `build`, `ci`, `chore`

```
feat(scoring): en yakın POI mesafesine hizmet yarıçapı sınırı ekle
fix(osm): metro isim filtresindeki fazladan boşluğu kaldır
test(indices): bant sınırlarını beraberlik altında sabitle
docs(readme): veri temini adımlarını ekle
```

Tür İngilizce, açıklama Türkçe yazılır. Commit mesajı yapılan işi doğru
anlatır; "updates", "changes", "fix stuff" gibi belirsiz ifadeler kullanılmaz.
Çalıştırılmamış bir test geçmiş gibi gösterilmez.

Commit öncesinde yalnızca ilgili dosyalar stage edilir. `git add .`
kullanılmadan önce değişiklik listesi incelenir.

### Pull Request

PR açıklaması altı bölüm içerir: amaç, yapılan değişiklikler, doğrulama,
kanıt, riskler ve sınırlar, ilgili Issue (`Closes #12`).

PR yalnızca gerçekten yapılanı anlatır. Başarısız veya eksik kalan denemeler
gizlenmez; teknik ve tarafsız biçimde belirtilir.

PR açmadan önce yerelde çalıştırılır:

```bash
ruff check src tests
ruff format --check src tests
pytest
git diff --stat origin/main...HEAD
```

### Merge

Squash merge kullanılır; ana dal geçmişinde her PR tek anlamlı değişiklik
olarak görünür.

Merge öncesi: CI başarılı, kabul kriterleri karşılanmış, PR açıklaması güncel,
alakasız dosya yok, gizli veri yok, gerekiyorsa dokümantasyon güncellenmiş.

Merge, sürüm çıkarma, force push ve dal silme yalnızca depo sahibinin onayıyla
yapılır.

## Depoya girmeyecekler

- Şifre, token, API anahtarı, `.env` dosyaları
- İş ortağına ait ham veri kümeleri
- Kişisel veri
- Üretilen büyük çıktılar (`*.parquet`, büyük `*.csv`, model dosyaları)
- Mutlak yerel yollar
- Kişisel çalışma notları ve iç yazışmalar

CI bunların bir kısmını otomatik kontrol eder, ancak son sorumluluk PR'ı açan
kişidedir. Push öncesi `git diff --cached` ile içerik gözden geçirilir.

## Kod standardı

- Dosya, dal, değişken ve fonksiyon adları İngilizce
- Docstring ve yorumlar Türkçe
- Satır uzunluğu 100 karakter
- `ruff check` ve `ruff format` temiz geçmeli
- Yeni davranış test ile korunur; hata düzeltmesi önce hatayı gösteren bir
  test ile gelir

Yorumlar kodun ne yaptığını değil, neden öyle yaptığını açıklar. Bir seçim
alışılmadıksa gerekçesi yazılır.

## Deney kayıtları

Model ve metodoloji denemeleri şunları kaydeder: veri kaynağı ve sürümü, veri
ayrımı, rastgelelik tohumu, bağımlılık sürümleri, hiperparametreler,
değerlendirme ölçütleri, kabul kriterleri, sonuç ve kabul veya ret gerekçesi.

Başarısız deneyler gizlenmez. Büyük çıktı dosyaları yerine sonuç özeti ve
tekrar üretme komutu paylaşılır.

Daha karmaşık bir yöntem yalnızca ölçülebilir biçimde daha iyi sonuç verirse
tercih edilir. Seçim doğruluk, hata oranı, gecikme, açıklanabilirlik ve
tekrar üretilebilirliğe dayanır.
