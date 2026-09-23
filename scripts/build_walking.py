#!/usr/bin/env python
"""Yol ağı üzerinden yürüme skorlarını üretir (kuş uçuşunun karşılığı).

Çıktı ``out/walk_scores.csv``: her H10 hücresi için 18 kategori skoru, yol
ağıyla. Panel bunu teslim modeliyle puanlayıp kuş uçuşuyla yan yana gösterir.

Yol ağı ilk çalıştırmada OpenStreetMap'ten sekiz parça halinde indirilir ve
``cache/walk_tiles`` altına kaydedilir.

Kullanım:
    python scripts/build_walking.py
    python scripts/build_walking.py --refresh   # yol ağını yeniden indir
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import catalogue, config, console, grid, osm, pipeline, walking  # noqa: E402

#: Yol ağı sekiz kutuya bölünerek indirilir; tek sorgu Overpass'ta zaman aşımına düşüyor.
TILE_LONS = (49.5, 49.725, 49.95, 50.175, 50.4)
TILE_LATS = (40.2, 40.4, 40.6)


def download_tiles(settings, tile_dir: Path, refresh: bool) -> None:
    client = osm.OverpassClient(
        cache_dir=tile_dir,
        mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS,
        timeout=400,
    )
    k = 0
    for i in range(len(TILE_LONS) - 1):
        for j in range(len(TILE_LATS) - 1):
            query = walking.walk_query(
                TILE_LATS[j], TILE_LONS[i], TILE_LATS[j + 1], TILE_LONS[i + 1]
            )
            client.query(query, f"tile_{k}", refresh=refresh)
            k += 1


def main() -> int:
    console.use_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Yol ağını yeniden indir")
    args = parser.parse_args()
    started = time.time()

    settings = config.load()
    tile_dir = settings.paths.cache / "walk_tiles"
    print("yol ağı…")
    download_tiles(settings, tile_dir, args.refresh)
    graph = walking.load_graph(tile_dir)
    edges = graph.matrix.nnz // 2
    print(f"  {graph.nodes:,} düğüm · {edges:,} kenar (en büyük bağlı parça)")

    cells = grid.land_cells(
        settings.bbox, settings.h3_resolution, grid.load_boundary(settings.paths.reference)
    )
    cell_node, cell_snap = graph.snap(cells["latitude"], cells["longitude"])
    print(
        f"  hücre → yol bağlantısı: medyan {np.median(cell_snap):.0f} m, %95 {np.percentile(cell_snap, 95):.0f} m"
    )

    pool = pipeline.load_pool(
        settings.paths.raw_current,
        catalogue.SOURCES,
        pipeline.load_metro(settings).frame(),
        pipeline.load_additions(settings),
        quiet=True,
    )

    columns = {}
    for name, frame in pool.items():
        t = time.time()
        columns[f"{name}_score"] = walking.walking_score(
            graph, cell_node, cell_snap, frame, catalogue.DECAY[name]
        )
        print(f"  {name:<12} {len(frame):>6,} obje  {time.time() - t:>6.1f} sn")

    table = pd.concat([cells[["h3_index"]].reset_index(drop=True), pd.DataFrame(columns)], axis=1)
    table["snap_m"] = np.round(cell_snap, 1)
    out = settings.paths.output / "walk_scores.csv"
    table.to_csv(out, index=False, encoding="utf-8")
    print(f"\nçıktı: {out}  ({len(table):,} satır) · {time.time() - started:.0f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
