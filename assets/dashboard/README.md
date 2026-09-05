# Panel varlıkları

`python scripts/build_dashboard.py` bu dizindeki iki dosyayı boru hattının
gerçek çıktısıyla birleştirip tek bir HTML üretir.

| Dosya | Nedir |
|---|---|
| `shell.html` | Panelin iskeleti. `__TABLER__` ve `__DATA__` yer tutucularını betik doldurur. |
| `tabler.min.css` | Arayüz stili. |

## Neden gömülü

Üretilen dosya dışarıdan hiçbir betik ya da stil çekmez. Şirket ağında,
uçakta, sunucusuz bir dizüstünde — her yerde açılır. Tek dış bağlantı Google
Fonts'a giden yazı tipi isteğidir; o da erişilemezse sistem yazı tipiyle
sorunsuz çalışır.

Bu yüzden `tabler.min.css` CDN'den çekilmek yerine depoda tutuluyor.
Dosyadaki bütün `url()` başvuruları `data:` gömülüdür; ayrıca indirilecek
resim ya da yazı tipi yoktur.

## Kaynak ve lisans

`tabler.min.css`, Tabler v1.0.0-beta20 dağıtımından değiştirilmeden alındı.

- Proje: <https://tabler.io>
- Kaynak: <https://github.com/tabler/tabler>
- Lisans: MIT — Copyright 2018-2023 The Tabler Authors, codecalm.net Paweł Kuna

MIT lisansı ticari kullanıma ve yeniden dağıtıma izin verir; tek koşul telif
bildiriminin korunmasıdır. Bildirim dosyanın ilk satırlarındaki yorum
bloğunda duruyor, silinmemeli.

Sürüm yükseltmek gerekirse dosya aynı adresten yenisiyle değiştirilir;
`shell.html` Tabler'ın standart sınıflarını kullanır, özel bir yamaya
dayanmaz.

## Panelin verisi

Veri ayrı bir dosyada tutulmaz; betik onu doğrudan `__DATA__` yer tutucusuna
gömer. Ara dosya olmayınca panelin gösterdiği sayı ile boru hattının ürettiği
sayı ayrışamaz.

Üretilen `urbangeoai_panel.html` depo dışındadır: iş ortağının POI
koordinatlarını gömülü olarak taşır. Depoda duran şey onu üreten betik ve bu
dizindeki şablon.
