"""Mesafeye göre ağırlıklandırılmış erişilebilirlik skorları.

Bir hücrenin bir POI kategorisindeki skoru, kesme mesafesi içindeki her POI'nin
yürüme süresine göre azalan katkısının toplamıdır::

    skor = Σ exp(-β · dakika)

β kategoriye özgüdür: metroya uzağa da yürünür (küçük β), otobüs durağına
yürünmez (büyük β).

Önceki uygulama POI'leri beş halkaya bölüp her halkadaki bütün POI'lere
halkanın dış kenarına ait ağırlığı veriyordu; 10 m'deki bir kafe 499 m'deki
kafeyle aynı katkıyı yapıyordu. Burada gerçek mesafe kullanılır.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0

#: Ortalama yürüme hızı. Süre bundan türetilir.
METERS_PER_MINUTE = 80.0

#: Katkının ihmal edilebilir hale geldiği mesafe.
DEFAULT_CUTOFF_M = 3000.0


def _tree(poi: pd.DataFrame) -> BallTree:
    return BallTree(np.radians(poi[["lat", "lon"]].to_numpy()), metric="haversine")


def _radians(cells: pd.DataFrame) -> np.ndarray:
    return np.radians(cells[["latitude", "longitude"]].to_numpy())


def decay_score(
    cells: pd.DataFrame,
    poi: pd.DataFrame,
    beta: float,
    cutoff_m: float = DEFAULT_CUTOFF_M,
    meters_per_minute: float = METERS_PER_MINUTE,
) -> np.ndarray:
    """Her hücre için sürekli azalımlı erişilebilirlik skoru.

    Args:
        cells: ``latitude`` ve ``longitude`` sütunlu ızgara.
        poi: ``lat`` ve ``lon`` sütunlu POI tablosu.
        beta: Dakika başına azalım katsayısı. Büyük değer hızlı düşüş.
        cutoff_m: Bu mesafenin ötesindeki POI'ler dikkate alınmaz.
        meters_per_minute: Yürüme hızı.

    Returns:
        Hücre sayısı uzunluğunda skor dizisi. POI yoksa sıfır.
    """
    if poi.empty:
        return np.zeros(len(cells), dtype=float)

    tree = _tree(poi)
    _, distances = tree.query_radius(
        _radians(cells), r=cutoff_m / EARTH_RADIUS_M, return_distance=True
    )
    factor = beta / meters_per_minute
    scores = np.zeros(len(cells), dtype=float)
    for i, d in enumerate(distances):
        if d.size:
            scores[i] = np.exp(-factor * (d * EARTH_RADIUS_M)).sum()
    return scores


def count_within(
    cells: pd.DataFrame, poi: pd.DataFrame, radii_m: list[float]
) -> dict[float, np.ndarray]:
    """Her yarıçap için hücre başına POI sayısı.

    Skorlama için gerekli değildir; veri denetimi ve karşılaştırma için tutulur.
    """
    if poi.empty:
        return {r: np.zeros(len(cells), dtype=int) for r in radii_m}
    tree = _tree(poi)
    coords = _radians(cells)
    return {
        r: tree.query_radius(coords, r=r / EARTH_RADIUS_M, count_only=True).astype(int)
        for r in radii_m
    }


def nearest(
    cells: pd.DataFrame, poi: pd.DataFrame, cap_m: float | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """En yakın POI'nin mesafesi ve adı.

    Args:
        cap_m: Hizmet yarıçapı. Bunun ötesindeki sonuçlar ``NaN`` ve ``None``
            olur. Kapsız bırakıldığında "en yakın metro 39 km" gibi
            erişilebilirlik anlamı taşımayan değerler üretilir.

    Returns:
        (mesafe metre, isim) ikilisi.
    """
    if poi.empty:
        return (
            np.full(len(cells), np.nan),
            np.full(len(cells), None, dtype=object),
        )

    tree = _tree(poi)
    distances, indices = tree.query(_radians(cells), k=1)
    metres = distances.ravel() * EARTH_RADIUS_M
    names = poi["name"].to_numpy()[indices.ravel()].astype(object)

    if cap_m is not None:
        beyond = metres > cap_m
        metres = np.where(beyond, np.nan, metres)
        names = np.where(beyond, None, names)

    return metres, names
