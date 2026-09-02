"""OpenStreetMap Overpass istemcisi.

İki dayanıklılık önlemi var. Overpass, ``User-Agent`` başlığı taşımayan
istekleri HTTP 406 ile reddediyor; ayrıca yoğun saatlerde tek sunucu 504
dönebiliyor. Bu yüzden her istek kimlik başlığı taşır ve sunucular sırayla
denenir. Yanıt önbelleğe alınır, böylece tekrar çalıştırmalar ağa çıkmaz.

Veri OpenStreetMap katkıcılarına aittir ve ODbL ile lisanslanmıştır.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

USER_AGENT = "UrbanGeoAI/0.1 (geospatial accessibility research)"

DEFAULT_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
)


class OverpassError(RuntimeError):
    """Hiçbir sunucu kullanılabilir yanıt vermediğinde."""


@dataclass
class OverpassClient:
    """Önbellekli, birden fazla sunucu deneyen Overpass istemcisi."""

    cache_dir: Path
    mirrors: tuple[str, ...] = DEFAULT_MIRRORS
    timeout: int = 90
    retry_pause_s: float = 2.0

    def query(self, overpass_ql: str, cache_key: str, refresh: bool = False) -> dict:
        """Sorguyu çalıştırır, ayrıştırılmış JSON yanıtı döndürür.

        Args:
            overpass_ql: Overpass QL sorgusu.
            cache_key: Önbellek dosyasının adı (uzantısız).
            refresh: True ise önbellek yok sayılır ve yeniden indirilir.

        Raises:
            OverpassError: Bütün sunucular başarısız olursa.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cached = self.cache_dir / f"{cache_key}.json"

        if cached.exists() and not refresh:
            return json.loads(cached.read_text(encoding="utf-8"))

        failures: list[str] = []
        for index, url in enumerate(self.mirrors):
            try:
                response = requests.get(
                    url,
                    params={"data": overpass_ql},
                    headers={"User-Agent": USER_AGENT},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as exc:
                failures.append(f"{url}: {type(exc).__name__}")
                if index + 1 < len(self.mirrors):
                    time.sleep(self.retry_pause_s)
                continue

            cached.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return payload

        raise OverpassError(
            "Overpass sunucularının hiçbiri yanıt vermedi:\n  "
            + "\n  ".join(failures)
            + f"\nÖnbellek dosyası mevcutsa ağ olmadan çalışılabilir: {cached}"
        )


def nodes_to_records(payload: dict) -> list[dict]:
    """Overpass yanıtındaki düğümleri düz kayıtlara çevirir.

    Alan ve yol tipindeki nesnelerde ``center`` koordinatı kullanılır.
    """
    records = []
    for element in payload.get("elements", []):
        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            centre = element.get("center") or {}
            lat, lon = centre.get("lat"), centre.get("lon")
        if lat is None or lon is None:
            continue
        tags = element.get("tags", {}) or {}
        records.append(
            {
                "osm_id": element.get("id"),
                "osm_type": element.get("type"),
                "name": tags.get("name"),
                "lat": lat,
                "lon": lon,
                "tags": tags,
            }
        )
    return records


def metro_query(bbox: tuple[float, float, float, float]) -> str:
    """Verilen sınır kutusundaki metro istasyonu düğümleri için sorgu.

    Overpass sınır kutusunu (güney, batı, kuzey, doğu) sırasıyla bekler.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        "[out:json];"
        'node["railway"="station"]["station"="subway"]'
        f"({min_lat},{min_lon},{max_lat},{max_lon});"
        "out body;"
    )
