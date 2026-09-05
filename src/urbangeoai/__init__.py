"""UrbanGeoAI: Bakı için coğrafi erişilebilirlik indeksleri.

Alt modüller:
    catalogue   Kategoriler, azalım katsayıları ve indeks grupları
    config      Yol ve parametre konfigürasyonu
    console     Konsol çıktısının kodlaması
    io          POI dosyalarının okunması ve normalleştirilmesi
    osm         OpenStreetMap Overpass istemcisi
    grid        H3 ızgarası ve kara maskesi
    metro       Metro istasyonlarının ayıklanması ve tekilleştirilmesi
    scoring     Mesafeye göre azalan erişilebilirlik skorları
    indices     Bileşik indeksler ve 1-10 bantlama
    validation  Ham veri denetimi
"""

__version__ = "0.1.0"

__all__ = [
    "catalogue",
    "config",
    "console",
    "grid",
    "indices",
    "io",
    "metro",
    "osm",
    "scoring",
    "validation",
]
