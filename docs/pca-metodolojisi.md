# Temel bileşen analizi: bu projede neden ve nasıl

Erişilebilirlik indeksleri temel bileşen analiziyle (PCA) üretiliyor. Bu belge
yöntemin matematiksel temelini, projede verilen kararları ve o kararların
gerekçelerini açıklıyor.

Belgedeki bütün sayılar çalıştırılarak üretilmiştir. Doğrulamak için:

```bash
python scripts/pca_demo.py
```

---

## 1. Çözülen problem

Təhsil erişilebilirliği için üç ayrı ölçüm var: bir hücrenin bağça, məktəb ve
universitet skorları. Müşteriye üç sayı göstermek istemiyoruz; tek bir "təhsil
indeksi" istiyoruz.

En basit yol ortalama almak olurdu. Ama bu, üç ölçümün eşit önemde ve
birbirinden bağımsız olduğunu varsayar. İkisi de doğru değil: bağça ve məktəb
neredeyse birlikte hareket eder (aynı mahallelerde bulunurlar), universitet ise
daha bağımsızdır. Ortalama bu yapıyı görmezden gelir.

PCA verinin **kendi içindeki ortak yönü** bulur ve ağırlıkları o yöne göre
belirler.

---

## 2. Kovaryans matrisi

Ortak yönü bulmak için önce ölçümlerin birlikte nasıl değiştiğine bakılır.

İki ölçümlü küçük bir örnek alalım:

```
      A     B
      2.0   1.0
      3.0   2.5
      1.0   0.5
      4.0   3.5
      2.5   2.0
```

Her sütundan kendi ortalaması çıkarılır (ortalanmış veri), sonra kovaryans
matrisi hesaplanır:

```
C = [ 1.2500   1.3125 ]
    [ 1.3125   1.4250 ]
```

Köşegendeki değerler her ölçümün kendi varyansı, köşegen dışındakiler ikisinin
birlikte değişimi. `1.3125` pozitif ve büyük: A arttığında B de artıyor.

---

## 3. Özdeğer ve özvektör

Bir matris, çarptığı vektörleri genelde hem döndürür hem uzatır. Ama bazı özel
vektörleri **döndürmez**, sadece uzatır veya kısaltır. Bunlara özvektör, uzatma
katsayısına özdeğer denir:

```
C · v = λ · v
```

Burada `v` özvektör (yön), `λ` özdeğer (o yöndeki yayılım).

Örneğimizin özdeğerleri ve özvektörleri:

| Bileşen | Özdeğer λ | Özvektör v | Açıklanan varyans |
|---|---|---|---|
| PC1 | 2.652913 | (0.683184, 0.730246) | %99.17 |
| PC2 | 0.022087 | (−0.730246, 0.683184) | %0.83 |

Doğrulama: `C · v₁ = λ₁ · v₁` eşitliği sağlanıyor.

PC1'in özvektörü `(0.683, 0.730)`. İkisi de pozitif ve birbirine yakın: veri
esas olarak "A ve B birlikte artar" yönünde yayılıyor. PC2'nin özdeğeri çok
küçük, yani o yönde neredeyse hiç bilgi yok.

**Açıklanan varyans oranı** bir özdeğerin toplam özdeğere oranıdır. %99.17
demek: iki ölçümü tek sayıya indirirsek bilginin %99.17'sini koruyor, %0.83'ünü
atıyoruz.

---

## 4. Özayrışım ile tekil değer ayrışımı

Yukarıdaki hesap kovaryans matrisinin **özayrışımıdır**. Kullandığımız
kütüphane (`scikit-learn`) bunun yerine veri matrisinin **tekil değer
ayrışımını** (SVD) uygular.

İkisi aynı sonucu verir. Ortalanmış veri matrisi `X` için `X = U Σ Vᵀ` ise,
kovaryans matrisi `C = XᵀX / (n−1)` olur ve:

- `V`'nin sütunları `C`'nin özvektörleridir
- `σᵢ² / (n−1)` değerleri `C`'nin özdeğerleridir

SVD tercih edilir çünkü kovaryans matrisini hiç kurmaz. `XᵀX` çarpımı sayısal
hassasiyet kaybına yol açar; SVD doğrudan `X` üzerinde çalışır ve daha kararlı
sonuç verir. `scripts/pca_demo.py` ikisinin aynı sonucu verdiğini gösterir.

---

## 5. Standartlaştırma neden zorunlu

PCA varyansı en büyük yönü arar. Ölçümler farklı birimlerde veya farklı
büyüklüklerdeyse, en büyük varyansa sahip olan ölçüm sonucu tek başına belirler.

Bu projede bu risk somut. Kategori skorları POI sayısından türetiliyor ve
sayılar çok farklı:

| Kategori | Yaklaşık POI sayısı |
|---|---|
| kafe | 3 800 |
| restoran | 1 533 |
| metro | 24 |

Standartlaştırma yapılmazsa kafe skorunun varyansı diğerlerini ezer ve "yemək
indeksi" pratikte "kafe indeksi" olur. Her ölçüm ortalaması sıfır, standart
sapması bir olacak şekilde ölçeklenir; böylece hepsi eşit ağırlıkla başlar ve
ağırlıkları veri yapısı belirler, ölçek değil.

---

## 6. İşaret belirsizliği

`C · v = λ · v` denklemini `v` sağlıyorsa `−v` de sağlıyor. Yani **özvektörün
işareti matematiksel olarak belirsizdir.** Kütüphane birini seçer, hangisini
seçtiği veriye ve uygulamaya bağlıdır.

Bu bizim için ciddi bir sorun. Yükler negatif çıkarsa indeks tersine döner: en
erişilebilir hücre en düşük puanı alır, en kötüsü en yükseğini. Hiçbir hata
mesajı çıkmaz, hesap doğrudur, sonuç anlamsızdır.

Çözüm iki satır:

```python
if component.sum() < 0:
    component = -component
    index = -index
```

Yüklerin toplamı negatifse her şey ters çevrilir. Böylece yüksek indeks daima
"daha erişilebilir" anlamına gelir.

**Ölçüm notu.** Bu riski test ettim: 2026 verisiyle altı indeks grubunun
hiçbirinde işaret ters çıkmadı, 40 rastgele alt örneklemde de dönmedi. Yani şu
an patlayan bir hata değil, **gizli bir risk**. Kategori bileşimi değişirse
(yeni bir indeks eklenirse, bir kategori çıkarılırsa) patlayabilir ve sessizce
patlar. `tests/test_indices.py` bunu koruyor.

---

## 7. Yüklerin okunması

Yükler her ölçümün bileşene katkısını gösterir. `pca.components_` ham
katsayıları verir; bunları `√λ` ile çarpınca ölçümle bileşen arasındaki
korelasyona dönüşürler ve yorumlanmaları kolaylaşır.

Projenin gerçek çıktısından, təhsil grubu:

| Ölçüm | Yük |
|---|---|
| bağça | +0.95 |
| məktəb | +0.94 |
| universitet | +0.85 |

Okunuşu: üç ölçüm de aynı yönde katkı veriyor, yani "təhsile erişim" tek bir
ortak yapıdır. Bağça ve məktəb bu yapıyı universitetten daha güçlü temsil
ediyor — beklenen sonuç, çünkü universitet daha az sayıda ve daha merkezde.

Bir yükün **negatif** çıkması, o ölçümün diğerlerine ters hareket ettiğini
gösterir. O durumda grup gerçekten tek bir kavramı ölçmüyor demektir ve grup
tanımının gözden geçirilmesi gerekir.

---

## 8. Açıklanan varyans nasıl yorumlanır

Projenin altı indeks grubu için ölçülen değerler:

| Grup | Üye sayısı | Açıklanan varyans |
|---|---|---|
| yemək | 3 | %91.8 |
| istirahət | 2 | %86.7 |
| turizm | 5 | %84.9 |
| təhsil | 3 | %83.7 |
| nəqliyyat | 2 | %79.6 |
| əyləncə | 9 | %75.9 |

Değerler 2026 veri sürümüyle ölçülmüştür. Veri değiştikçe değişirler.

Kaba bir okuma:

- **%80 üzeri** — grup üyeleri birlikte hareket ediyor, tek indeks onları iyi
  temsil ediyor
- **%60–80** — kabul edilebilir, ama bilginin bir kısmı atılıyor
- **%60 altı** — grup muhtemelen tek bir kavram değil, bölünmesi düşünülmeli

`əyləncə` grubunun en düşük değere sahip olması beklenen bir sonuç: dokuz üyesi
var ve muzeyden fast-fooda kadar birbirinden uzak kategorileri barındırıyor.

`nəqliyyat` grubu yalnızca iki üye taşıyor (metro ve dayanacaq) ve ikisi
birbirinden bağımsız yayılıyor: metro 24 noktada yoğunlaşırken duraklar bütün
şehre dağılmış durumda. Bu yüzden tek bileşen ikisini ötekiler kadar iyi
temsil edemiyor.

---

## 9. Bilinen sınır: indeksler bağımsız değil

Altı indeksi birbirine karşı analiz ettim. İndekslerin kendi üzerinde PCA
çalıştırınca:

```
PC1: %84.3   ← tek ortak faktör
PC2:  %9.1
PC3:  %3.0
```

Bütün farklılığın **%84.3'ü tek bir faktör**. PC1 yükleri altı indekste de
neredeyse eşit; bu faktör pratikte "merkeze ne kadar yakınsın" demek.

Bunun iki sebebi var. Birincisi gruplar arasında ortak kategoriler bulunuyor:
`park` hem istirahət hem əyləncə grubunda, `kafe` hem yemək hem əyləncə
grubunda. İkincisi, Bakı'da her tür hizmet aynı merkezde yoğunlaşıyor.

Sonuç: müşteriye altı ayrı puan gösteriliyor ama hepsi büyük ölçüde aynı şeyi
söylüyor. Bir yeri "təhsil 9, yemək 9, əyləncə 9" diye göstermek ek bilgi
vermiyor.

**Olası yaklaşım.** Ortak faktörü ayırıp kalan kısmı göstermek: "bu nöqtənin
təhsili, yerləşməsinə görə gözləniləndən yaxşıdır." Yatırımcı için asıl bilgi
orada. Bu bir ürün kararıdır ve henüz verilmedi.

---

## 10. Özet

| Karar | Gerekçe |
|---|---|
| Ortalama yerine PCA | Ölçümler eşit önemde ve bağımsız değil |
| Standartlaştırma | 3 800 kafe ile 24 metro aynı terazide tartılamaz |
| Tek bileşen | Açıklanan varyans %76–92; ikinci bileşen az bilgi taşıyor |
| İşaret sabitleme | İşaret matematiksel olarak keyfî; sessizce ters dönebilir |
| Yüklerin kaydı | Grup tanımının doğruluğu ancak yüklere bakılarak denetlenebilir |

## Kaynaklar

- Jolliffe, I. T. ve Cadima, J. (2016). Principal component analysis: a review
  and recent developments. *Philosophical Transactions of the Royal Society A*,
  374(2065).
- Shlens, J. (2014). A tutorial on principal component analysis.
  arXiv:1404.1100.
- Strang, G. *Introduction to Linear Algebra*, özdeğer ve özvektör bölümü.
