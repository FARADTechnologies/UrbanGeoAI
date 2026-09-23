#!/usr/bin/env python
"""Web panelinin okuduğu veri dosyalarını üretir.

Panel bir sunucuya bağlanmaz; boru hattının çıktısını statik JSON olarak
okur. Böylece arayüz `npm run dev` ile tek başına çalışır, arka uç kurulumu
beklemez.

Üç veri sürümü yan yana üretilir ve aynı dondurulmuş modelle puanlanır:

- ``2025``    — iş ortağının önceki verisi
- ``2026``    — iş ortağının güncel verisi
- ``2026osm`` — güncel veri + OpenStreetMap eklemeleri (teslim edilen)

Harita katmanı H3 hücrelerini kendi indeksleriyle veriyor — geometri
tarayıcıda deck.gl tarafından çözülüyor. H10 ana ızgaradır; H7–H9 onun
ortalamasıdır.

Önce ``build_indices.py`` çalışmış olmalı: model oradan okunur ki panel ile
teslim tablosu aynı cetveli kullansın.

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
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import (  # noqa: E402
    catalogue,
    config,
    console,
    grid,
    indices,
    pipeline,
    validation,
)

#: Haritada seçilebilen H3 seviyeleri. H10 hesaplamanın yapıldığı seviye;
#: diğerleri onun ortalaması.
MAP_RESOLUTIONS = (7, 8, 9, 10)

VERSIONS = (
    ("2025", "2025 · iş ortağı"),
    ("2026", "2026 · iş ortağı"),
    ("2026osm", "2026 + OpenStreetMap"),
)

#: Yol ağı üzerinden yürüme sürümü (scripts/build_walking.py üretir).
WALK = ("walk", "2026 + OSM · piyada")


def points(frame: pd.DataFrame) -> list[list[float]]:
    return [
        [round(float(a), 5), round(float(b), 5)]
        for a, b in zip(frame["lat"], frame["lon"], strict=True)
    ]


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "web" / "public" / "data")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    settings = config.load()
    output = settings.paths.output
    model_path = output / "index_model.json"
    if not model_path.exists():
        print("HATA: index_model.json yok. Önce scripts/build_indices.py çalıştırılmalı.")
        return 2
    models = indices.load_model(model_path)
    model_meta = json.loads(model_path.read_text(encoding="utf-8")).get("metadata", {})

    print("ızgara…")
    boundary = grid.load_boundary(settings.paths.reference)
    cells = grid.land_cells(settings.bbox, settings.h3_resolution, boundary)

    print("metro…")
    report = pipeline.load_metro(settings)
    metro_frame = report.frame()

    from compare_versions import LEGACY_SOURCES  # noqa: PLC0415

    print("havuzlar…")
    additions = pipeline.load_additions(settings)
    pools = {
        "2025": pipeline.load_pool(
            settings.paths.raw_previous, LEGACY_SOURCES, metro_frame, quiet=True
        ),
        "2026": pipeline.load_pool(settings.paths.raw_current, catalogue.SOURCES, metro_frame),
        "2026osm": pipeline.load_pool(
            settings.paths.raw_current, catalogue.SOURCES, metro_frame, additions
        ),
    }

    walk_path = output / "walk_scores.csv"
    versions = list(VERSIONS)
    if walk_path.exists():
        versions.append(WALK)

    bands: dict[str, dict[str, np.ndarray]] = {}
    walk_ratio: dict[str, float] = {}
    for version, _ in versions:
        if version == WALK[0]:
            print("skorlar · piyada (yol ağı)…")
            walk = (
                pd.read_csv(walk_path, encoding="utf-8").set_index("h3_index").loc[cells.h3_index]
            )
            scores = pd.concat([cells, walk.reset_index(drop=True).set_index(cells.index)], axis=1)
            crow = pipeline.category_scores(cells, pools["2026osm"])
            for col in crow.columns:
                has = crow[col] > 0
                if has.any():
                    walk_ratio[col.removesuffix("_score")] = round(
                        float((scores.loc[has, col] / crow.loc[has, col]).median()), 3
                    )
            bands[version] = {}
            for group, model in models.items():
                _, bands[version][group] = indices.score_group(scores, model)
            continue
        print(f"skorlar · {version}…")
        scores = pd.concat([cells, pipeline.category_scores(cells, pools[version])], axis=1)
        bands[version] = {}
        for group, model in models.items():
            if all(f"{m}_score" in scores.columns for m in model.members):
                _, bands[version][group] = indices.score_group(scores, model)

    names = list(models)
    delivered = bands["2026osm"]

    pca_info = {
        g: {
            "members": m.members,
            "evr": round(m.explained_variance_ratio * 100, 1),
            "weights": [round(float(c), 3) for c in m.components],
            "loadings": pipeline.original_loadings(m),
            "bands": indices.band_coverage(delivered[g]),
            "fittedOnPrevious": all(x in pools["2025"] for x in m.members),
        }
        for g, m in models.items()
    }

    # ── Harita katmanları ────────────────────────────────────────────
    frame = pd.DataFrame(
        {f"{v}|{g}": bands[v][g].astype(np.int16) for v, _ in versions for g in bands[v]}
    )
    for resolution in MAP_RESOLUTIONS:
        print(f"H{resolution}…")
        if resolution == settings.h3_resolution:
            keys = list(cells.h3_index)
            values = {
                v: {g: frame[f"{v}|{g}"].astype(int).tolist() for g in bands[v]}
                for v, _ in versions
            }
        else:
            parent = [h3.cell_to_parent(c, resolution) for c in cells.h3_index]
            coarse = frame.groupby(parent).mean()
            keys = list(coarse.index)
            values = {
                v: {g: [round(float(x), 2) for x in coarse[f"{v}|{g}"]] for g in bands[v]}
                for v, _ in versions
            }
        payload = {"res": resolution, "h3": keys, "v": values}
        path = args.out / f"cells-r{resolution}.json"
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        print(f"  {path.name}  {len(keys):>7,} hücre  {path.stat().st_size // 1024:>6,} KB")

    # ── Nokta katmanları ─────────────────────────────────────────────
    print("POI katmanları…")
    poi = {
        "2025": {k: points(f) for k, f in pools["2025"].items()},
        "2026": {k: points(f) for k, f in pools["2026"].items()},
        "osm": {}
        if additions is None
        else {k: points(f) for k, f in additions.groupby("category")},
    }
    (args.out / "poi.json").write_text(json.dumps(poi, separators=(",", ":")), encoding="utf-8")

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

    table = pd.DataFrame({g: delivered[g].astype(float) for g in names})
    across = PCA().fit(StandardScaler().fit_transform(table))
    corr = table.corr()

    def read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    osm_added = {} if additions is None else additions["category"].value_counts().to_dict()
    delivery = output / "accessibility_indices.csv"
    summary = {
        "meta": {
            "cells": int(len(cells)),
            "poi": int(sum(len(v) for k, v in pools["2026osm"].items() if k != "metro")),
            "poiLocal": int(sum(len(v) for k, v in pools["2026"].items() if k != "metro")),
            "poiOsm": int(0 if additions is None else len(additions)),
            "categories": len(pools["2026osm"]),
            "indices": len(names),
            "metroKept": len(report.kept),
            "metroRaw": len(report.records),
            "csvMb": round(delivery.stat().st_size / 1e6, 1) if delivery.exists() else None,
            "resolution": settings.h3_resolution,
            "mapResolutions": list(MAP_RESOLUTIONS),
            "bbox": list(settings.bbox),
            "versions": [{"key": k, "label": label} for k, label in versions],
            "model": model_meta,
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
                "old": len(pools["2025"][k]) if k in pools["2025"] else None,
                "new": len(pools["2026"].get(k, [])),
                "osm": int(osm_added.get(k, 0)),
            }
            for k in catalogue.SOURCES
        ],
        "comparison": read_json(output / "comparison.json"),
        "beta": read_json(output / "beta_sensitivity.json"),
        "enrichment": read_json(output / "osm_enrichment.json"),
        "h10": read_json(output / "h10_verification.json"),
        "teamComparison": read_json(output / "team_comparison.json"),
        "bandCheck": read_json(output / "band_check.json"),
        "google": read_json(output / "google_walk_check.json"),
        "walking": {
            "available": walk_path.exists(),
            "score_ratio_median": walk_ratio,
            "band_shift": {
                g: {
                    "mean": round(float((bands[WALK[0]][g] - delivered[g]).mean()), 3),
                    "lower_pct": round(float((bands[WALK[0]][g] < delivered[g]).mean() * 100), 1),
                    "same_pct": round(float((bands[WALK[0]][g] == delivered[g]).mean() * 100), 1),
                }
                for g in names
            }
            if WALK[0] in bands
            else {},
        },
        "decay": catalogue.DECAY,
        "retired": catalogue.RETIRED,
    }
    path = args.out / "summary.json"
    path.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"  {path.name}  {path.stat().st_size // 1024:,} KB")
    print(
        f"\nhücre {len(cells):,} · indeks {len(names)} · metro {len(report.kept)} · "
        f"POI {summary['meta']['poi']:,} (OSM +{summary['meta']['poiOsm']:,})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
