#!/usr/bin/env python
"""Web panelinin okuduğu veri dosyalarını üretir.

Panel bir sunucuya bağlanmaz; boru hattının çıktısını statik JSON olarak
okur. Böylece arayüz `npm run dev` ile tek başına çalışır, arka uç kurulumu
beklemez.

Harita katmanı H3 hücrelerini kendi indeksleriyle veriyor — geometri
tarayıcıda deck.gl tarafından çözülüyor. Res-10'un tamamı (120 bin hücre)
tarayıcıya taşınamayacağı için üç üst seviye üretiliyor; hangisinin
gösterileceğini kullanıcı seçiyor.

Kullanım:
    python scripts/build_web_data.py
    python scripts/build_web_data.py --out web/public/data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h3
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import (  # noqa: E402
    catalogue,
    config,
    console,
    grid,
    indices,
    io,
    metro,
    osm,
    scoring,
    validation,
)

#: Haritada seçilebilen H3 seviyeleri. Res-10 ana ızgaradır ama tarayıcıya
#: taşınamaz; bunlar onun üzerinden ortalanarak üretiliyor.
MAP_RESOLUTIONS = (7, 8, 9)

#: Nokta katmanı olarak gönderilen kategori başına üst sınır.
MAX_POINTS = 3000


def load_pois(base: Path, settings, sources: dict, metro_frame) -> dict:
    """Katalogdaki kategorileri yükler, metroyu hazır çerçeveden ekler."""
    out = {}
    for name, (fname, typ) in sources.items():
        path = base / fname
        if not path.exists():
            continue
        frame = io.read_poi(path).frame
        out[name] = io.filter_type(frame, typ) if typ else frame
    out["metro"] = metro_frame
    return out


def category_scores(cells: pd.DataFrame, pois: dict) -> pd.DataFrame:
    """Her kategori için mesafeye göre azalan skor."""
    return pd.DataFrame(
        {
            f"{name}_score": scoring.decay_score(cells, frame, catalogue.DECAY[name])
            for name, frame in pois.items()
        },
        index=cells.index,
    )


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "web" / "public" / "data")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    settings = config.load()

    print("ızgara…")
    boundary = grid.load_boundary(settings.paths.reference)
    cells = grid.land_cells(settings.bbox, settings.h3_resolution, boundary)

    print("metro…")
    client = osm.OverpassClient(
        cache_dir=settings.paths.cache,
        mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS,
    )
    report = metro.deduplicate(
        osm.nodes_to_records(client.query(osm.metro_query(settings.bbox), "metro_raw")),
        not_operational=tuple(settings.metro.get("not_operational", ())),
        merge_interchanges=bool(settings.metro.get("merge_interchanges", True)),
    )
    metro_frame = report.frame()

    from compare_versions import LEGACY_SOURCES  # noqa: PLC0415

    print("POI…")
    new_poi = load_pois(settings.paths.raw_current, settings, catalogue.SOURCES, metro_frame)
    old_poi = load_pois(settings.paths.raw_previous, settings, LEGACY_SOURCES, metro_frame)

    print("skorlar…")
    new_scores = pd.concat([cells, category_scores(cells, new_poi)], axis=1)
    old_scores = pd.concat([cells, category_scores(cells, old_poi)], axis=1)

    print("indeksler…")
    bands_new, bands_old, pca_info = {}, {}, {}
    for group, members in catalogue.GROUPS.items():
        usable = [m for m in members if f"{m}_score" in new_scores.columns]
        if not usable:
            continue
        complete = all(f"{m}_score" in old_scores.columns for m in usable)
        model = indices.fit_group(old_scores if complete else new_scores, usable)
        _, bands_new[group] = indices.score_group(new_scores, model)
        if complete:
            _, bands_old[group] = indices.score_group(old_scores, model)
        fit = indices.fit_group(new_scores, usable)
        pca_info[group] = {
            "members": usable,
            "evr": round(fit.explained_variance_ratio * 100, 1),
            "loadings": [round(float(c), 3) for c in fit.components],
            "bands": indices.band_coverage(bands_new[group]),
            "fittedOnPrevious": complete,
        }

    names = list(bands_new)

    # ── Harita katmanları ────────────────────────────────────────────
    frame = pd.DataFrame({g: bands_new[g].astype(float) for g in names})
    for group in names:
        if group in bands_old:
            frame[f"{group}__d"] = bands_new[group].astype(int) - bands_old[group].astype(int)

    for resolution in MAP_RESOLUTIONS:
        print(f"res-{resolution}…")
        frame["parent"] = [h3.cell_to_parent(c, resolution) for c in cells.h3_index]
        coarse = frame.groupby("parent").mean()
        payload = {
            "res": resolution,
            "h3": list(coarse.index),
            "indices": {g: [round(float(v), 2) for v in coarse[g]] for g in names},
            "deltas": {
                g: [round(float(v), 2) for v in coarse[f"{g}__d"]]
                for g in names
                if f"{g}__d" in coarse.columns
            },
        }
        path = args.out / f"cells-r{resolution}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        print(f"  {path.name}  {len(coarse):>6,} hücre  {path.stat().st_size // 1024:>5,} KB")

    # ── Nokta katmanları ─────────────────────────────────────────────
    print("POI katmanları…")
    points = {
        name: [
            [round(float(la), 5), round(float(lo), 5)]
            for la, lo in zip(f["lat"], f["lon"], strict=True)
        ]
        for name, f in new_poi.items()
        if name != "metro" and len(f) <= MAX_POINTS
    }
    points["metro"] = [[round(float(r.lat), 5), round(float(r.lon), 5)] for r in report.kept]
    (args.out / "poi.json").write_text(json.dumps(points, separators=(",", ":")), encoding="utf-8")

    # ── Özet ─────────────────────────────────────────────────────────
    print("doğrulama…")
    reports = validation.validate_directory(
        settings.paths.raw_current,
        bbox=settings.bbox,
        duplicate_radius_m=float(settings.validation.get("duplicate_radius_m", 50)),
        min_decimals=int(settings.validation.get("min_coordinate_decimals", 5)),
    )

    from sklearn.decomposition import PCA  # noqa: PLC0415
    from sklearn.preprocessing import StandardScaler  # noqa: PLC0415

    table = pd.DataFrame({g: bands_new[g].astype(float) for g in names})
    across = PCA().fit(StandardScaler().fit_transform(table))
    corr = table.corr()

    def read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    delivery = settings.paths.output / "accessibility_indices.csv"
    summary = {
        "meta": {
            "cells": int(len(cells)),
            "poi": int(sum(len(v) for k, v in new_poi.items() if k != "metro")),
            "categories": len(new_poi),
            "indices": len(names),
            "metroKept": len(report.kept),
            "metroRaw": len(report.records),
            "csvMb": round(delivery.stat().st_size / 1e6, 1) if delivery.exists() else None,
            "resolution": settings.h3_resolution,
            "mapResolutions": list(MAP_RESOLUTIONS),
            "bbox": list(settings.bbox),
        },
        "groups": names,
        "pca": pca_info,
        "cross": {
            "evr": [round(float(v) * 100, 1) for v in across.explained_variance_ratio_],
            "corr": {a: {b: round(float(corr.loc[a, b]), 2) for b in names} for a in names},
        },
        "metro": {
            "summary": report.summary(),
            "nodes": [
                {
                    "name": r.name,
                    "decision": r.decision.value,
                    "reason": r.reason,
                    "lat": round(float(r.lat), 5),
                    "lon": round(float(r.lon), 5),
                }
                for r in report.records
            ],
        },
        "validation": [r.to_dict() for r in reports],
        "counts": [
            {
                "key": k,
                "new": len(new_poi.get(k, [])),
                "old": len(old_poi[k]) if k in old_poi else None,
            }
            for k in catalogue.SOURCES
        ],
        "comparison": read_json(settings.paths.output / "comparison.json"),
        "beta": read_json(settings.paths.output / "beta_sensitivity.json"),
        "decay": catalogue.DECAY,
        "retired": catalogue.RETIRED,
    }
    path = args.out / "summary.json"
    path.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"  {path.name}  {path.stat().st_size // 1024:,} KB")
    print(f"\nhücre {len(cells):,} · indeks {len(names)} · metro {len(report.kept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
