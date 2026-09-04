"""H3 altıgen ızgarasının kurulması ve kara maskesiyle kırpılması.

Analiz alanı bir sınır kutusundan başlar, altıgenlerle doldurulur ve idari
sınır poligonuyla kesiştirilerek deniz ile alan dışı hücreler atılır.

Kırpma maskesi sonucun hangi hücrelerden oluşacağını tek başına belirler.
Farklı bir maske farklı bir hücre kümesi verir; sürümler arası karşılaştırma
yapılacaksa maskenin sabit tutulması gerekir.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
import requests
import shapely

GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_AZE_1.json"
GADM_FILE = "gadm41_AZE_1.json"

#: GADM birinci seviye bölümlerinden Bakı'yı içeren bölgeyi seçer.
REGION_PATTERN = "Baku|Absheron"

#: İş ortağının sağladığı özgün analiz sınırı. Depoda bulunmaz; referans
#: dizinine elle yerleştirilir. Mevcutsa GADM yerine bu kullanılır.
PARTNER_MASK_FILE = "map_absheron.geojson"

#: Doğrulanmış maskenin parmak izi. Farklı bir dosya konursa uyarı verilir,
#: çünkü maske sonucu tek başına belirler ve sessizce değişmemelidir.
PARTNER_MASK_SHA256 = "89f2f80264ff5ea43b730126711b37cd545f9c06192059364087ffd1c7c43fd3"


def bbox_cells(bbox: tuple[float, float, float, float], resolution: int) -> pd.DataFrame:
    """Sınır kutusunu altıgenlerle doldurur ve merkez koordinatlarını verir.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat)
        resolution: H3 çözünürlüğü.

    Returns:
        ``h3_index``, ``latitude``, ``longitude`` sütunlu tablo.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    ring = [
        (min_lat, min_lon),
        (min_lat, max_lon),
        (max_lat, max_lon),
        (max_lat, min_lon),
        (min_lat, min_lon),
    ]
    cells = h3.polygon_to_cells(h3.LatLngPoly([list(p) for p in ring]), resolution)
    centres = [h3.cell_to_latlng(c) for c in cells]
    return pd.DataFrame(
        {
            "h3_index": list(cells),
            "latitude": [c[0] for c in centres],
            "longitude": [c[1] for c in centres],
        }
    )


def mask_fingerprint(path: Path) -> str:
    """Maske dosyasının sha256 parmak izi."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_boundary(reference_dir: Path, download: bool = True) -> gpd.GeoDataFrame:
    """Kara maskesini yükler.

    İş ortağının sağladığı özgün maske referans dizininde bulunuyorsa o
    kullanılır; sonuç önceki üretim çıktısıyla birebir eşleşir. Bulunmuyorsa
    açık kaynaklı bir sınıra düşülür. İkisi aynı ızgarayı üretmez, bu yüzden
    hangisinin kullanıldığı bildirilir.

    Maskenin dosyaları depoda tutulmaz; referans veriler için geçerli kural
    burada da geçerlidir.

    Raises:
        FileNotFoundError: Yedek sınır da yoksa ve indirme kapalıysa.
    """
    reference_dir.mkdir(parents=True, exist_ok=True)

    partner = reference_dir / PARTNER_MASK_FILE
    if partner.exists():
        digest = mask_fingerprint(partner)
        if digest != PARTNER_MASK_SHA256:
            print(
                f"  [sınır] UYARI: {PARTNER_MASK_FILE} beklenen parmak izini taşımıyor.\n"
                f"          beklenen {PARTNER_MASK_SHA256[:16]}…, bulunan {digest[:16]}…\n"
                f"          Izgara önceki çıktıyla eşleşmeyebilir.",
                file=sys.stderr,
            )
        return repair(gpd.read_file(partner))

    print(
        f"  [sınır] {PARTNER_MASK_FILE} bulunamadı, açık kaynaklı sınıra düşülüyor.\n"
        f"          Izgara önceki üretim çıktısıyla birebir eşleşmeyecek.",
        file=sys.stderr,
    )
    path = reference_dir / GADM_FILE

    if not path.exists():
        if not download:
            raise FileNotFoundError(
                f"Sınır dosyası yok: {path}. İndirmek için download=True verin."
            )
        response = requests.get(GADM_URL, timeout=180, headers={"User-Agent": "UrbanGeoAI/0.1"})
        response.raise_for_status()
        path.write_bytes(response.content)

    regions = gpd.read_file(path)
    mask = regions[regions["NAME_1"].str.contains(REGION_PATTERN, case=False, na=False)]
    if mask.empty:
        raise ValueError(f"'{REGION_PATTERN}' ile eşleşen bölge bulunamadı: {path}")
    return repair(mask)


def repair(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Geçersiz poligonları onarır.

    Kendisiyle kesişen halkalar birleştirme sırasında GEOS hatasına yol açıyor.
    ``make_valid`` bunları geçerli geometriye dönüştürür.
    """
    invalid = (~frame.geometry.is_valid).sum()
    if invalid:
        frame = frame.copy()
        frame["geometry"] = shapely.make_valid(frame.geometry.values)
    return frame


def land_cells(
    bbox: tuple[float, float, float, float],
    resolution: int,
    boundary: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """Sınır kutusunu doldurup kara maskesiyle kırpar.

    Returns:
        Maskenin içine düşen hücreler; ``h3_index``, ``latitude``, ``longitude``.
    """
    cells = bbox_cells(bbox, resolution)
    points = gpd.GeoDataFrame(
        cells,
        geometry=gpd.points_from_xy(cells["longitude"], cells["latitude"]),
        crs="EPSG:4326",
    )
    clipped = gpd.clip(points, boundary.to_crs(points.crs))
    return pd.DataFrame(clipped[["h3_index", "latitude", "longitude"]]).reset_index(drop=True)
