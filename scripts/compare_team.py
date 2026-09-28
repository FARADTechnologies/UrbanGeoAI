#!/usr/bin/env python
"""Ekibin kendi çıktılarıyla birebir karşılaştırma.

Ekip iki dosya gönderdi: ``poi_scores.csv`` (7 kategori skoru + 5 mesafe) ve
``poi_pca.csv`` (6 PCA indeksi + 5 mesafe). İkisi de 2025 veri klasöründeki
(``Receb_data/calculated poi scores``) dosyalarla byte byte aynı, yani 2025
verisiyle üretildi. Karşılaştırma bu yüzden 2025 verisiyle yapılıyor.

Üç soru cevaplanıyor:

1. **Kodu doğru anladık mı?** Notebook'un yöntemi (halka sayımı, UTM tamponu,
   notebook'taki dosya okuma ve metro süzgeci, OSM'in Mart 2025 hali) aynen
   yeniden kuruluyor. Aynı veride aynı sayıyı veriyorsa, bu kodun ne yaptığını
   eksiksiz biliyoruz demektir.
2. **Bizim yöntemimiz aynı yere varıyor mu?** Aynı 2025 verisinde bizim
   hesaplamamız (gerçek mesafe, işaret sabitleme, taban bandı) ekibin
   sonucuyla sıralama bakımından karşılaştırılıyor.
3. **Bal (1–10) ne kadar örtüşüyor?** Ekibin desil yöntemi ile bizim bant
   yöntemi hücre hücre karşılaştırılıyor.

Kullanım:
    python scripts/compare_team.py
    python scripts/compare_team.py --scores yol/poi_scores.csv --pca yol/poi_pca.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.neighbors import BallTree
from sklearn.preprocessing import StandardScaler

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import config, console, grid, indices, osm  # noqa: E402

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_MINUTE = 80
RINGS_M = (500, 1000, 1500, 2000, 3000)

#: Notebook'taki ``decay_weights`` — birebir.
DECAY = {
    "kdgr": 0.1, "schl": 0.2, "univ": 0.1, "bus": 0.7, "metro": 0.05,
    "shopping": 0.1, "parks": 0.1, "museum": 0.1, "theatre": 0.1,
    "coffee": 0.5, "restaurant": 0.3, "fast_food": 0.3, "bars": 0.2,
    "sport": 0.2, "hotel": 0.1, "monuments": 0.1, "concert_hall": 0.05,
}  # fmt: skip

#: Notebook'taki gruplar — birebir (hücre 34).
GROUPS = {
    "education": ["kdgr", "schl", "univ"],
    "transport": ["metro", "bus"],
    "tourism": ["museum", "theatre", "hotel", "monuments", "concert_hall"],
    "food": ["coffee", "restaurant", "fast_food"],
    "recreation": ["parks", "sport"],
    "leisure": ["museum", "shopping", "parks", "theatre", "concert_hall",
                "coffee", "restaurant", "fast_food", "bars"],
}  # fmt: skip

#: Bizim indeks adlarımız → ekibin sütun adları.
OUR_GROUP = {
    "education": "təhsil",
    "transport": "nəqliyyat",
    "tourism": "turizm",
    "food": "yemək",
    "recreation": "istirahət",
    "leisure": "əyləncə",
}

#: Ekibin mesafe sütunu → kategori.
DISTANCES = {
    "distance_to_nearest_kindergarten": "kdgr",
    "distance_to_nearest_schl": "schl",
    "distance_to_nearest_metro": "metro",
    "distance_to_nearest_shopping_mall": "shopping",
    "distance_to_nearest_parks": "parks",
}

#: Ekibin metro sorgusunun tarihi: poi_scores.csv'nin oluşturulduğu gün.
METRO_DATE = "2025-03-27T00:00:00Z"


# ── Notebook'un veri okuması (hücre 12 ve 14), birebir ────────────────────────


def load_notebook_pois(base: Path) -> dict[str, pd.DataFrame]:
    def read(name, **kw):
        frame = pd.read_csv(base / name, **kw)
        return frame.rename(columns={"long": "lon"})

    data = read("school_data.csv")
    food = read("qida.csv")
    shopping = read("shopping_malls.csv").drop_duplicates(subset="name")
    return {
        "kdgr": data[data["type"] == "uşaq bağçası"],
        "schl": data[data["type"] == "məktəb"],
        "univ": read("ali_mekteb.csv"),
        "bus": read("dayanacaq.csv"),
        "shopping": shopping,
        "parks": read("parks.csv"),
        "museum": read("muzey.csv"),
        "theatre": read("theatre.csv"),
        "coffee": food[food["type"] == "kafe"],
        "restaurant": food[food["type"] == "restoran"],
        "fast_food": food[food["type"] == "fast-food"],
        "bars": food[food["type"] == "bar"],
        "sport": read("sport_facility.csv"),
        "hotel": read("hotel.csv", encoding="ISO-8859-1"),
        "monuments": read("historic_monuments.csv"),
        "concert_hall": read("concert_halls.csv"),
    }


def load_notebook_metro(settings) -> pd.DataFrame:
    """Ekibin ``download_metro_stations_for_baku`` fonksiyonu, OSM'in o günkü haliyle."""
    min_lon, min_lat, max_lon, max_lat = settings.bbox
    query = (
        f'[out:json][date:"{METRO_DATE}"];'
        'node["railway"="station"]["station"="subway"]'
        f"({min_lat},{min_lon},{max_lat},{max_lon});out body;"
    )
    client = osm.OverpassClient(cache_dir=settings.paths.cache)
    payload = client.query(query, f"metro_{METRO_DATE[:10]}")
    if not payload.get("elements"):
        # Tarihli (attic) sorguyu her Overpass sunucusu desteklemiyor ve boş
        # dönebiliyor. Bu tarihsel bir anlık görüntü, değişmez: veri deposunda
        # cache/metro_2025-03-27.json olarak sabit tutuluyor.
        raise RuntimeError(
            f"Overpass {METRO_DATE[:10]} tarihli metro sorgusu boş döndü; "
            f"cache/metro_{METRO_DATE[:10]}.json anlık görüntüsü gerekli"
        )
    rows = [
        {
            "lat": e["lat"],
            "lon": e["lon"],
            "name": (e.get("tags") or {}).get("name", "Unnamed"),
        }
        for e in payload["elements"]
        if e["type"] == "node"
    ]
    frame = pd.DataFrame(rows).drop_duplicates(subset="name")
    # Notebook'taki süzgeç — "Məhəmməd Hadi " sondaki boşlukla birlikte.
    drop = frame["name"].str.contains("Azər Neft Yağ|Məhəmməd Hadi |B-4", case=False, na=False)
    return frame[~drop].reset_index(drop=True)


# ── Notebook'un skoru (hücre 19, 21, 25, 28), birebir ─────────────────────────

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32639", always_xy=True)

#: geopandas ``buffer`` varsayılanı: çeyrek daire başına 16 kenar → 64 kenarlı çokgen.
_SIDES = 64


def _utm(lat, lon) -> np.ndarray:
    x, y = _TO_UTM.transform(np.asarray(lon, float), np.asarray(lat, float))
    return np.column_stack([x, y])


def ring_counts(cells_xy: np.ndarray, poi: pd.DataFrame) -> dict[int, np.ndarray]:
    """UTM 39N'de tampon içindeki nokta sayısı (notebook: buffer + sjoin 'contains').

    Tampon bir daire değil, daireye içten çizilmiş 64 kenarlı çokgen; kenar
    ortası merkeze ``r·cos(π/64)`` uzaklıkta. Bu halkadaki noktalar açıya
    göre içeride ya da dışarıda kalıyor, burada tam o geometriyle sayılıyor.
    """
    pts = _utm(poi["lat"], poi["lon"])
    tree = cKDTree(pts)
    step = 2 * np.pi / _SIDES
    inner = np.cos(np.pi / _SIDES)
    out = {}
    for r in RINGS_M:
        counts = np.zeros(len(cells_xy), dtype=int)
        for i, members in enumerate(tree.query_ball_point(cells_xy, r)):
            if not members:
                continue
            d = pts[members] - cells_xy[i]
            dist = np.hypot(d[:, 0], d[:, 1])
            sure = dist < r * inner
            n = int(sure.sum())
            edge = ~sure
            if edge.any():
                ang = np.mod(np.arctan2(d[edge, 1], d[edge, 0]), step) - step / 2
                n += int((dist[edge] * np.cos(ang) < r * inner).sum())
            counts[i] = n
        out[r] = counts
    return out


def notebook_score(counts: dict[int, np.ndarray], beta: float) -> np.ndarray:
    score = np.zeros_like(counts[RINGS_M[0]], dtype=float)
    previous = 0
    for r in RINGS_M:
        score += (counts[r] - previous) * np.exp(-beta * (r / METERS_PER_MINUTE))
        previous = counts[r]
    return score


def continuous_score(cells_rad: np.ndarray, poi: pd.DataFrame, beta: float) -> np.ndarray:
    """Bizim yöntem: her noktanın gerçek mesafesi (scoring.decay_score ile aynı)."""
    tree = BallTree(np.radians(poi[["lat", "lon"]].to_numpy(float)), metric="haversine")
    _, dists = tree.query_radius(cells_rad, r=3000 / EARTH_RADIUS_M, return_distance=True)
    factor = beta / METERS_PER_MINUTE
    return np.array([np.exp(-factor * d * EARTH_RADIUS_M).sum() for d in dists])


# ── Karşılaştırma ölçüleri ────────────────────────────────────────────────────


def agreement(ours: np.ndarray, theirs: np.ndarray) -> dict:
    ours, theirs = np.asarray(ours, float), np.asarray(theirs, float)
    diff = np.abs(ours - theirs)
    scale = max(float(np.abs(theirs).max()), 1e-12)
    return {
        "exact_pct": round(float((diff < 1e-9 * scale + 1e-12).mean() * 100), 3),
        "within_1pct_pct": round(
            float((diff <= 0.01 * np.maximum(np.abs(theirs), 1e-9)).mean() * 100), 3
        ),
        "max_abs_diff": float(diff.max()),
        "pearson": round(float(np.corrcoef(ours, theirs)[0, 1]), 6)
        if ours.std() and theirs.std()
        else None,
        "spearman": round(float(spearmanr(ours, theirs).statistic), 6),
    }


def team_deciles(series: pd.Series) -> np.ndarray:
    """Notebook hücre 44/45: ``pd.qcut(s, 10, duplicates='drop') + 1``."""
    return (pd.qcut(series, 10, labels=False, duplicates="drop") + 1).to_numpy()


def main() -> int:
    console.use_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    settings = config.load()
    default_dir = settings.paths.raw_previous / "calculated poi scores"
    parser.add_argument("--scores", type=Path, default=default_dir / "poi_scores.csv")
    parser.add_argument("--pca", type=Path, default=default_dir / "poi_pca.csv")
    parser.add_argument("--json", type=Path, default=settings.paths.output / "team_comparison.json")
    args = parser.parse_args()

    team_scores = pd.read_csv(args.scores).set_index("h3_index")
    team_pca = pd.read_csv(args.pca).set_index("h3_index")

    print("ızgara…")
    cells = grid.land_cells(
        settings.bbox, settings.h3_resolution, grid.load_boundary(settings.paths.reference)
    )
    cells = cells.set_index("h3_index")
    same_cells = set(cells.index) == set(team_scores.index) == set(team_pca.index)
    cells = cells.loc[team_scores.index]
    team_pca = team_pca.loc[team_scores.index]
    print(f"  bizim {len(cells):,} · ekip {len(team_scores):,} · aynı küme: {same_cells}")

    print("2025 verisi (notebook okuması)…")
    pois = load_notebook_pois(settings.paths.raw_previous)
    pois["metro"] = load_notebook_metro(settings)
    counts_poi = {k: int(len(v)) for k, v in pois.items()}
    print("  " + ", ".join(f"{k} {v}" for k, v in counts_poi.items()))

    cells_xy = _utm(cells["latitude"], cells["longitude"])
    cells_rad = np.radians(cells[["latitude", "longitude"]].to_numpy(float))

    print("skorlar (notebook yöntemi + bizim yöntem)…")
    nb_scores, our_scores = {}, {}
    for name, poi in pois.items():
        nb_scores[name] = notebook_score(ring_counts(cells_xy, poi), DECAY[name])
        our_scores[name] = continuous_score(cells_rad, poi, DECAY[name])
    nb_frame = pd.DataFrame(nb_scores, index=cells.index)
    our_frame = pd.DataFrame(our_scores, index=cells.index)

    result = {
        "data": "2025 (Receb_data) — ekibin dosyalarıyla byte byte aynı klasör",
        "metro_osm_date": METRO_DATE,
        "cells": {
            "ours": int(len(cells)),
            "team": int(len(team_scores)),
            "same_set": bool(same_cells),
        },
        "poi_counts": counts_poi,
        "scores": {},
        "distances": {},
        "pca": {},
        "bands": {},
    }

    # 0) Ekibin iki dosyası birbirini üretiyor mu? poi_scores.csv 27 Mart,
    # poi_pca.csv 26 Nisan tarihli. Skor dosyasındaki gruplardan PCA yeniden
    # hesaplanıp PCA dosyasıyla karşılaştırılıyor.
    print("\n0) EKİBİN İKİ DOSYASI BİRBİRİYLE TUTARLI MI?")
    result["team_internal"] = {}
    for group in ("education", "transport"):
        cols = [f"{m}_score" for m in GROUPS[group]]
        idx = (
            PCA(n_components=1)
            .fit_transform(StandardScaler().fit_transform(team_scores[cols]))
            .ravel()
        )
        theirs = team_pca[f"{group}_index_pca"].to_numpy()
        sign = np.sign(np.corrcoef(idx, theirs)[0, 1]) or 1.0
        a = agreement(idx * sign, theirs)
        result["team_internal"][group] = a
        print(
            f"  {group:<10} poi_scores → PCA ↔ poi_pca: tam eşit %{a['exact_pct']:.2f}  max fark {a['max_abs_diff']:.3f}"
        )

    print("\n1) KATEGORİ SKORLARI  (ekip ↔ notebook yöntemi · ekip ↔ bizim yöntem)")
    for col in [c for c in team_scores.columns if c.endswith("_score")]:
        name = col.removesuffix("_score")
        theirs = team_scores[col].to_numpy()
        a = agreement(nb_frame[name].to_numpy(), theirs)
        b = agreement(our_frame[name].to_numpy(), theirs)
        result["scores"][name] = {"replica": a, "our_method": b}
        print(
            f"  {name:<9} replika: tam eşit %{a['exact_pct']:>7.3f}  max fark {a['max_abs_diff']:.2e}"
            f"   |  bizim yöntem: spearman {b['spearman']:.4f}  pearson {b['pearson']}"
        )

    print("\n2) EN YAKIN MESAFE")
    for col, name in DISTANCES.items():
        tree = BallTree(np.radians(pois[name][["lat", "lon"]].to_numpy(float)), metric="haversine")
        d, _ = tree.query(cells_rad, k=1)
        a = agreement(d.ravel() * EARTH_RADIUS_M, team_pca[col].to_numpy())
        result["distances"][name] = a
        print(f"  {name:<9} tam eşit %{a['exact_pct']:>7.3f}  max fark {a['max_abs_diff']:.3f} m")

    print("\n3) PCA İNDEKSLERİ  (notebook yöntemi · bizim yöntem)")
    for group, members in GROUPS.items():
        theirs = team_pca[f"{group}_index_pca"].to_numpy()
        # (a) notebook kodu aynen: StandardScaler → PCA(1).fit_transform
        nb_idx = (
            PCA(n_components=1)
            .fit_transform(StandardScaler().fit_transform(nb_frame[members]))
            .ravel()
        )
        sign = np.sign(np.corrcoef(nb_idx, theirs)[0, 1]) or 1.0
        a = agreement(nb_idx * sign, theirs)
        a["sign_flipped"] = bool(sign < 0)
        # (b) bizim fit_group (işaret sabitleme dahil), aynı 2025 verisi, bizim skorlar
        ours_members = [m for m in members if m != "concert_hall"]
        model = indices.fit_group(our_frame.rename(columns=lambda c: f"{c}_score"), ours_members)
        our_idx, our_band = indices.score_group(
            our_frame.rename(columns=lambda c: f"{c}_score"), model
        )
        b = agreement(our_idx, theirs)
        # (c) bal karşılaştırması
        their_dec = team_deciles(team_pca[f"{group}_index_pca"])
        bands = {
            "team_distinct_deciles": int(pd.Series(their_dec).nunique()),
            "team_max_decile": int(np.nanmax(their_dec)),
            "our_distinct_bands": int(pd.Series(our_band).nunique()),
            "equal_pct": round(float((our_band == their_dec).mean() * 100), 2),
            "within_1_pct": round(float((np.abs(our_band - their_dec) <= 1).mean() * 100), 2),
            "team_distribution": pd.Series(their_dec)
            .value_counts()
            .sort_index()
            .astype(int)
            .to_dict(),
            "our_distribution": pd.Series(our_band)
            .value_counts()
            .sort_index()
            .astype(int)
            .to_dict(),
        }
        result["pca"][group] = {"replica": a, "our_method": b, "our_name": OUR_GROUP[group]}
        result["bands"][group] = bands
        print(
            f"  {group:<10} replika: pearson {a['pearson']:.6f}  max fark {a['max_abs_diff']:.2e}"
            f"   |  bizim: spearman {b['spearman']:.4f}   |  bal: eşit %{bands['equal_pct']:.1f}"
            f"  ±1 %{bands['within_1_pct']:.1f}  (ekip {bands['team_distinct_deciles']} desil, biz "
            f"{bands['our_distinct_bands']} bant)"
        )

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=lambda o: int(o) if isinstance(o, np.integer) else float(o),
        ),
        encoding="utf-8",
    )
    print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
