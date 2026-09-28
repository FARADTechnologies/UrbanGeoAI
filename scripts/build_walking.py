#!/usr/bin/env python
"""Yol ağı üzerinden yürüme skorlarını üretir (kuş uçuşunun karşılığı).

Çıktı ``out/walk_scores.csv``: her H10 hücresi için 18 kategori skoru, yol
ağıyla. Panel bunu teslim modeliyle puanlayıp kuş uçuşuyla yan yana gösterir.

İki motor var:

- ``osrm`` (varsayılan): OSRM ``foot`` profili, kendi bilgisayarımızda Docker
  ile. Yaya kurallarını tam uygular (giriş yasakları, bariyerler, merdiven).
- ``graph``: OpenStreetMap yollarından kendi kurduğumuz çizge + Dijkstra.
  Artık yalnız karşılaştırma için; ``--compare`` iki motoru yan yana ölçer.

OSRM kurulumu (bir kez, ~2 dakika)::

    # 1. Azərbaycan xəritəsi (~45 MB)
    curl -L -o cache/osrm/azerbaijan-latest.osm.pbf
         https://download.geofabrik.de/asia/azerbaijan-latest.osm.pbf
    # 2. Yaya profili ilə hazırlıq (IMAGE = ghcr.io/project-osrm/osrm-backend)
    docker run --rm -v <repo>/cache/osrm:/data IMAGE
         osrm-extract -p /opt/foot.lua /data/azerbaijan-latest.osm.pbf
    docker run --rm -v <repo>/cache/osrm:/data IMAGE osrm-partition /data/azerbaijan-latest.osrm
    docker run --rm -v <repo>/cache/osrm:/data IMAGE osrm-customize /data/azerbaijan-latest.osrm
    # 3. Sunucu (yalnız bu bilgisayardan erişilir)
    docker run -d --name urbangeoai-osrm -p 127.0.0.1:5000:5000 -v <repo>/cache/osrm:/data
         IMAGE osrm-routed --algorithm mld /data/azerbaijan-latest.osrm

Kullanım:
    python scripts/build_walking.py                    # OSRM
    python scripts/build_walking.py --compare          # OSRM + kendi çizgemizle karşılaştırma
    python scripts/build_walking.py --engine graph     # yalnız kendi çizgemiz
    python scripts/build_walking.py --refresh          # çizge yollarını yeniden indir
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import catalogue, config, console, grid, osm, osrm, pipeline, walking  # noqa: E402

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


def graph_scores(settings, cells, pool, refresh: bool) -> tuple[dict, np.ndarray]:
    tile_dir = settings.paths.cache / "walk_tiles"
    print("yol ağı (kendi çizgemiz)…")
    download_tiles(settings, tile_dir, refresh)
    graph = walking.load_graph(tile_dir)
    print(f"  {graph.nodes:,} düğüm · {graph.matrix.nnz // 2:,} kenar (en büyük bağlı parça)")
    cell_node, cell_snap = graph.snap(cells["latitude"], cells["longitude"])
    columns = {}
    for name, frame in pool.items():
        columns[f"{name}_score"] = walking.walking_score(
            graph, cell_node, cell_snap, frame, catalogue.DECAY[name]
        )
    return columns, cell_snap


def osrm_scores(client, cells, pool) -> dict:
    columns = {}
    for name, frame in pool.items():
        t = time.time()
        columns[f"{name}_score"] = osrm.walking_score(client, cells, frame, catalogue.DECAY[name])
        print(f"  {name:<12} {len(frame):>6,} obje  {time.time() - t:>6.1f} sn")
    return columns


def compare_engines(a: dict, b: dict) -> dict:
    """OSRM ile kendi çizgemizi kategori kategori karşılaştırır."""
    out = {}
    for col in a:
        x, y = pd.Series(a[col]), pd.Series(b[col])
        both = (x > 0) & (y > 0)
        out[col.removesuffix("_score")] = {
            "spearman": round(float(x.corr(y, method="spearman")), 4),
            "ratio_median": round(float((x[both] / y[both]).median()), 3) if both.any() else None,
            "reached_osrm": int((x > 0).sum()),
            "reached_graph": int((y > 0).sum()),
        }
    return out


def main() -> int:
    console.use_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["osrm", "graph"], default="osrm")
    parser.add_argument("--osrm-url", default=osrm.DEFAULT_URL)
    parser.add_argument("--compare", action="store_true", help="İki motoru karşılaştır")
    parser.add_argument("--refresh", action="store_true", help="Çizge yollarını yeniden indir")
    args = parser.parse_args()
    started = time.time()

    settings = config.load()
    cells = grid.land_cells(
        settings.bbox, settings.h3_resolution, grid.load_boundary(settings.paths.reference)
    )
    pool = pipeline.load_pool(
        settings.paths.raw_current,
        catalogue.SOURCES,
        pipeline.load_metro(settings).frame(),
        pipeline.load_additions(settings),
        quiet=True,
    )

    graph_columns, snap = None, None
    if args.engine == "graph" or args.compare:
        graph_columns, snap = graph_scores(settings, cells, pool, args.refresh)

    if args.engine == "osrm":
        client = osrm.OSRMClient(args.osrm_url)
        if not client.alive():
            print(
                f"HATA: OSRM {args.osrm_url} adresinde cevap vermiyor (kurulum: betik açıklaması)"
            )
            return 2
        print("OSRM (foot profili)…")
        columns = osrm_scores(client, cells, pool)
    else:
        columns = graph_columns

    table = pd.concat([cells[["h3_index"]].reset_index(drop=True), pd.DataFrame(columns)], axis=1)
    if snap is not None and args.engine == "graph":
        table["snap_m"] = np.round(snap, 1)
    out = settings.paths.output / "walk_scores.csv"
    table.to_csv(out, index=False, encoding="utf-8")

    meta = {
        "generated": date.today().isoformat(),
        "engine": args.engine,
        "profile": "foot" if args.engine == "osrm" else "highway (OSM) + Dijkstra",
        "cutoff_m": osrm.CUTOFF_M,
        "meters_per_minute": osrm.METERS_PER_MINUTE,
        "objects": int(sum(len(f) for f in pool.values())),
        "seconds": round(time.time() - started),
    }
    if args.compare and args.engine == "osrm":
        meta["engines"] = compare_engines(columns, graph_columns)
    (settings.paths.output / "walk_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nçıktı: {out}  ({len(table):,} satır) · {time.time() - started:.0f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
