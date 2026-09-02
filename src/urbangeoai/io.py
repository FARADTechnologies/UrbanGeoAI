"""POI dosyalarının okunması ve sütun adlarının normalleştirilmesi.

Veri kümeleri sürümden sürüme farklı dosya ve sütun adları kullanıyor:
``long`` / ``lon``, başlıkta bayt sırası imi, bazı dosyalarda ``name``
sütununun hiç bulunmaması. Buradaki yükleyici bu farkları tek bir şemaya
indirger, böylece analiz kodu tek bir biçimle çalışır.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

#: Normalleştirilmiş şemada beklenen sütunlar.
REQUIRED_COLUMNS = ("lat", "lon")

#: Kaynak dosyalarda görülen sütun adı varyantları.
COLUMN_ALIASES = {
    "long": "lon",
    "longitude": "lon",
    "latitude": "lat",
    "enlem": "lat",
    "boylam": "lon",
}


@dataclass
class LoadResult:
    """Okunan tablo ve okuma sırasında fark edilenler."""

    frame: pd.DataFrame
    source: Path
    encoding: str
    synthesised_name: bool
    dropped_rows: int


def read_poi(path: Path, encoding: str | None = None) -> LoadResult:
    """Tek bir POI dosyasını normalleştirilmiş şemaya okur.

    Args:
        path: CSV dosyası.
        encoding: Verilmezse UTF-8 (BOM toleranslı) denenir, başarısız olursa
            ISO-8859-1'e düşülür. Eski veri sürümünde bir dosya bu kodlamada.

    Returns:
        ``lat``, ``lon`` ve ``name`` sütunları garanti edilen bir tablo.

    Raises:
        ValueError: Dosyada koordinat sütunu bulunamazsa.
    """
    encodings = [encoding] if encoding else ["utf-8-sig", "ISO-8859-1"]
    frame = None
    used = ""
    last_error: Exception | None = None
    for enc in encodings:
        try:
            frame = pd.read_csv(path, encoding=enc, engine="python")
            used = enc
            break
        except (UnicodeDecodeError, LookupError) as exc:
            last_error = exc
    if frame is None:
        raise ValueError(f"{path.name} okunamadı: {last_error}")

    frame.columns = [str(c).strip().lower() for c in frame.columns]
    frame = frame.rename(columns=COLUMN_ALIASES)
    frame = frame.loc[:, ~frame.columns.duplicated()]

    missing = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"{path.name}: koordinat sütunu yok ({', '.join(missing)})")

    for col in REQUIRED_COLUMNS:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    # Bazı dosyalarda (durak, kamera) isim sütunu bulunmuyor. Hata vermek yerine
    # dosya adından türetilmiş bir etiket koyuyoruz; çağıran taraf bunu bilir.
    synthesised = "name" not in frame.columns
    if synthesised:
        frame["name"] = path.stem

    before = len(frame)
    frame = frame.dropna(subset=list(REQUIRED_COLUMNS)).reset_index(drop=True)

    return LoadResult(
        frame=frame,
        source=path,
        encoding=used,
        synthesised_name=synthesised,
        dropped_rows=before - len(frame),
    )


def filter_type(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    """Tek dosyada birden fazla kategori barındıran tabloları böler.

    Örneğin yemek dosyası kafe, restoran, fast-food ve barı birlikte tutuyor.
    Karşılaştırma büyük/küçük harf ve baştaki sondaki boşluklardan bağımsızdır.
    """
    if "type" not in frame.columns:
        raise ValueError("Tabloda 'type' sütunu yok")
    normalised = frame["type"].astype(str).str.strip().str.casefold()
    return frame[normalised == value.strip().casefold()].reset_index(drop=True)


def to_geoframe(frame: pd.DataFrame):
    """Normalleştirilmiş tabloyu WGS 84 nokta katmanına çevirir."""
    import geopandas as gpd

    return gpd.GeoDataFrame(
        frame,
        geometry=gpd.points_from_xy(frame["lon"], frame["lat"]),
        crs="EPSG:4326",
    )
