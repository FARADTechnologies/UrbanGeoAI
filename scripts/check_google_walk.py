#!/usr/bin/env python
"""OpenStreetMap yaya mesafesini Google'ın yaya mesafesiyle sınar.

Rastgele hücrelerden en yakın okula, parka, metroya giden yollar hem bizim
yol ağımızla hem Google Routes API ile ölçülür. İkisi yakınsa toplu hesabı
güvenle OSM ile yapabiliriz demektir.

Anahtar ``.env`` içindeki ``GOOGLE_MAPS_API_KEY``. Anahtar kullanılamıyorsa
betik nedenini ve ne istenmesi gerektiğini yazar.

Kullanım:
    python scripts/check_google_walk.py
    python scripts/check_google_walk.py --pairs 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import dijkstra

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import (  # noqa: E402
    catalogue,
    config,
    console,
    google_routes,
    grid,
    pipeline,
    walking,
)

CATEGORIES = ("schl", "parks", "metro", "coffee")


def main() -> int:
    console.use_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=int, default=20, help="Kategori başına örnek çift")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    settings = config.load()
    out = settings.paths.output / "google_walk_check.json"

    key = google_routes.load_key(REPO)
    if not key:
        print("GOOGLE_MAPS_API_KEY bulunamadı (.env ya da ortam değişkeni).")
        return 2

    graph = walking.load_graph(settings.paths.cache / "walk_tiles")
    cells = grid.land_cells(
        settings.bbox, settings.h3_resolution, grid.load_boundary(settings.paths.reference)
    )
    pool = pipeline.load_pool(
        settings.paths.raw_current,
        catalogue.SOURCES,
        pipeline.load_metro(settings).frame(),
        quiet=True,
    )
    rng = np.random.default_rng(args.seed)
    result = {"pairs": [], "status": "ok"}

    for category in CATEGORIES:
        poi = pool[category]
        sample = cells.sample(args.pairs * 3, random_state=int(rng.integers(1e9)))
        p_node, p_snap = graph.snap(poi["lat"], poi["lon"])
        c_node, c_snap = graph.snap(sample["latitude"], sample["longitude"])
        dist = dijkstra(graph.matrix, directed=False, indices=np.unique(p_node), limit=3000)
        row = {n: i for i, n in enumerate(np.unique(p_node))}
        chosen = []
        for k in range(len(sample)):
            totals = dist[[row[n] for n in p_node], c_node[k]] + p_snap + c_snap[k]
            j = int(np.argmin(totals))
            if np.isfinite(totals[j]) and totals[j] > 200:
                chosen.append((k, j, float(totals[j])))
            if len(chosen) == args.pairs:
                break
        origins = [(sample.iloc[k]["latitude"], sample.iloc[k]["longitude"]) for k, _, _ in chosen]
        targets = [(poi.iloc[j]["lat"], poi.iloc[j]["lon"]) for _, j, _ in chosen]
        try:
            legs = []
            for a, b in zip(origins, targets, strict=True):
                legs.extend(google_routes.walking_matrix(key, [a], [b]))
        except google_routes.RoutesError as exc:
            result.update(status="denied", reason=exc.reason, http=exc.status, message=str(exc))
            print(f"GOOGLE REDDETTİ: {exc}")
            out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            return 1
        for (_, _, osm_m), leg in zip(chosen, legs, strict=True):
            result["pairs"].append(
                {"category": category, "osm_m": round(osm_m, 1), "google_m": leg.meters}
            )

    ratios = np.array([p["osm_m"] / p["google_m"] for p in result["pairs"] if p["google_m"]])
    result["summary"] = {
        "pairs": int(len(ratios)),
        "osm_over_google_median": round(float(np.median(ratios)), 3),
        "within_15pct": round(float((np.abs(ratios - 1) <= 0.15).mean() * 100), 1),
    }
    print(json.dumps(result["summary"], ensure_ascii=False))
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
