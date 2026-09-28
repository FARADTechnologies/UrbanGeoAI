"""OSRM ile yol ağı üzerinden yürüme mesafesi.

OSRM (Open Source Routing Machine) OpenStreetMap yolları üzerinde en kısa yolu
bulan açık kaynak motordur; openstreetmap.org'daki yaya rotası da onunla
çalışır. ``foot`` profili yayanın kullanabildiği yolları seçer: kaldırım,
patika, merdiven, park içi yollar; otoyol ve girişi yasak yollar hariç, tek
yön kısıtı yaya için uygulanmaz.

Motor kendi bilgisayarımızda çalışır (Docker), dışarıya istek gitmez, ücret ve
limit yoktur. Kurulum ``scripts/build_walking.py`` açıklamasında.

Skor kuş uçuşuyla aynı formüldür — ``Σ exp(−β × dakika)``, 80 m/dk, 3 km —
yalnız mesafe yol üzerinden ölçülür. Hücre merkezi ve nesne en yakın yola
bağlanır (OSRM "snap"); bu bağlantı mesafesi de yürüyüşe eklenir.

Veri OpenStreetMap katkıcılarına aittir ve ODbL ile lisanslanmıştır.
"""

from __future__ import annotations

import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_MINUTE = 80.0
CUTOFF_M = 3000.0
DEFAULT_URL = "http://127.0.0.1:5000"


def encode_polyline(lat: np.ndarray, lon: np.ndarray, precision: int = 6) -> str:
    """Koordinatları Google polyline biçimine çevirir (OSRM ``polyline6``).

    Binlerce koordinat URL'ye düz yazılınca adres çok uzuyor; kodlanmış hâli
    yaklaşık dörtte biri kadar.
    """
    factor = 10**precision
    out = []
    prev_lat = prev_lon = 0
    for a, b in zip(np.round(np.asarray(lat) * factor).astype(np.int64),
                    np.round(np.asarray(lon) * factor).astype(np.int64), strict=True):  # fmt: skip
        for value in (int(a) - prev_lat, int(b) - prev_lon):
            value = ~(value << 1) if value < 0 else value << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lon = int(a), int(b)
    return "".join(out)


@dataclass
class OSRMClient:
    """Yerel OSRM sunucusu."""

    url: str = DEFAULT_URL
    profile: str = "foot"
    timeout_s: float = 60.0

    def table_from(
        self, lat: float, lon: float, dest_lat: np.ndarray, dest_lon: np.ndarray
    ) -> np.ndarray:
        """Tek kaynaktan hedeflere yol mesafesi (metre), bağlantı payları dahil.

        Ulaşılamayan hedef ``inf`` döner.
        """
        coords = encode_polyline(np.r_[lat, dest_lat], np.r_[lon, dest_lon])
        query = (
            f"{self.url}/table/v1/{self.profile}/polyline6({urllib.request.quote(coords, safe='')})"
            "?sources=0&annotations=distance&generate_hints=false"
        )
        with urllib.request.urlopen(query, timeout=self.timeout_s) as response:
            payload = json.load(response)
        if payload.get("code") != "Ok":
            raise RuntimeError(f"OSRM: {payload.get('code')} {payload.get('message', '')}")
        row = np.array([np.inf if d is None else d for d in payload["distances"][0]], float)
        snap = np.array([w.get("distance", 0.0) for w in payload["destinations"]], float)
        # İlk koordinat kaynağın kendisi; hedefler 1'den başlar. Kaynağın
        # yola bağlantısı da (snap[0]) her hedefe eklenir.
        return row[1:] + snap[0] + snap[1:]

    def alive(self) -> bool:
        try:
            self.table_from(40.3777, 49.852, np.array([40.378]), np.array([49.853]))
            return True
        except Exception:  # noqa: BLE001
            return False


def walking_score(
    client: OSRMClient,
    cells: pd.DataFrame,
    poi: pd.DataFrame,
    beta: float,
    cutoff_m: float = CUTOFF_M,
    workers: int = 8,
) -> np.ndarray:
    """Her hücre için yol üzerinden ``Σ exp(−β × dakika)``.

    Yol mesafesi kuş uçuşundan kısa olamaz; bu yüzden her nesne için yalnız
    kuş uçuşu 3 km içindeki hücreler sorulur. Aynı noktadaki nesneler tek
    istekle hesaplanır, ağırlıkları sayılarıyla çarpılır.
    """
    scores = np.zeros(len(cells))
    if poi.empty:
        return scores
    cell_lat = cells["latitude"].to_numpy(float)
    cell_lon = cells["longitude"].to_numpy(float)
    tree = BallTree(np.radians(np.column_stack([cell_lat, cell_lon])), metric="haversine")

    points = (
        poi[["lat", "lon"]].round(6).value_counts().rename("count").reset_index()
    )  # aynı nokta bir kez
    near = tree.query_radius(
        np.radians(points[["lat", "lon"]].to_numpy()), r=cutoff_m / EARTH_RADIUS_M
    )
    factor = beta / METERS_PER_MINUTE

    def one(i: int):
        idx = near[i]
        if idx.size == 0:
            return idx, None
        dist = client.table_from(
            points.at[i, "lat"], points.at[i, "lon"], cell_lat[idx], cell_lon[idx]
        )
        return idx, dist

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (idx, dist) in enumerate(pool.map(one, range(len(points)))):
            if dist is None:
                continue
            reach = np.isfinite(dist) & (dist <= cutoff_m)
            np.add.at(
                scores,
                idx[reach],
                points.at[i, "count"] * np.exp(-factor * dist[reach]),
            )
    return scores
