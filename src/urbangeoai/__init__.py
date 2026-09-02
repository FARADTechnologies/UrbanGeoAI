"""UrbanGeoAI: Bakı için coğrafi erişilebilirlik indeksleri.

Alt modüller:
    config    Yol ve parametre konfigürasyonu
    io        POI dosyalarının okunması ve normalleştirilmesi
    osm       OpenStreetMap Overpass istemcisi
    grid      H3 ızgarası ve kara maskesi
    scoring   Mesafeye göre azalan erişilebilirlik skorları
    indices   Bileşik indeksler ve 1-10 bantlama
"""

__version__ = "0.1.0"

__all__ = ["config", "io", "osm", "grid", "scoring", "indices"]
