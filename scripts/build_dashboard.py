#!/usr/bin/env python
"""Analitik paneli tek bir HTML dosyası olarak üretir.

Panelde görünen hiçbir sayı elle yazılmaz. Izgara, POI'ler, indeksler,
metro ayıklaması ve doğrulama denetimi burada yeniden hesaplanır;
karşılaştırma ve duyarlılık sonuçları ise ilgili betiklerin kendi JSON
çıktılarından okunur. Böylece panel ile teslim edilen tablo aynı kaynaktan
gelir, ikisi ayrışamaz.

Çıktı tek dosyadır: stil de veri de içine gömülür. İnternet gerekmez,
sunucu gerekmez, dosya çift tıklanarak açılır. Toplantıda dizüstünde
çalışması gereken şey budur.

Kullanım:
    python scripts/build_dashboard.py
    python scripts/build_dashboard.py --out yol/panel.html
"""

from __future__ import annotations

import argparse
import json
import math
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

#: Şablon ve stil. Tabler MIT lisanslıdır, kaynağı assets/dashboard/README.md'de.
ASSETS = REPO / "assets" / "dashboard"

#: Haritanın çizildiği H3 seviyesi. Res-10 hücreler ekranda bir pikselden
#: küçük kalır; res-8 hem okunur hem de tarayıcıyı yormaz.
MAP_RESOLUTION = 8

#: Boylamı enleme göre daraltmak için kullanılan referans enlem (Abşeron).
LAT0 = 40.4

#: Nokta katmanı olarak gömülen kategori başına üst sınır. Daha kalabalık
#: kategoriler haritada okunmaz hale geliyor, dosyayı da gereksiz büyütüyor.
MAX_POINTS = 2000

#: Çizim tuvalinin genişliği (piksel). Yükseklik en/boy oranından türetilir.
CANVAS_W = 1000.0


def load_pois(base: Path, settings, sources: dict, metro_frame: pd.DataFrame):
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


class Projection:
    """Coğrafi koordinatı tuval pikseline çeviren basit eşleme.

    Gerçek bir harita projeksiyonu değil: boylam enleme göre daraltılıp
    veri sınırlarına oturtuluyor. Tek şehirlik bir alanda gözle görülür sapma
    üretmez ve dışarıdan harita kütüphanesi gerektirmez.
    """

    def __init__(self, polygons: list[list[tuple[float, float]]]) -> None:
        xs = [p[0] for poly in polygons for p in poly]
        ys = [p[1] for poly in polygons for p in poly]
        self.x0, self.x1 = min(xs), max(xs)
        self.y0, self.y1 = min(ys), max(ys)
        self.w = CANVAS_W
        self.h = CANVAS_W * (self.y1 - self.y0) / (self.x1 - self.x0)

    @staticmethod
    def flatten(lat: float, lon: float) -> tuple[float, float]:
        return lon * math.cos(math.radians(LAT0)), lat

    def to_px(self, x: float, y: float) -> tuple[float, float]:
        px = (x - self.x0) / (self.x1 - self.x0) * self.w
        py = self.h - (y - self.y0) / (self.y1 - self.y0) * self.h
        return px, py

    def path(self, points: list[tuple[float, float]]) -> str:
        """Düzlemsel nokta listesini SVG yol dizesine çevirir."""
        parts = []
        for i, (x, y) in enumerate(points):
            px, py = self.to_px(x, y)
            parts.append(f"{'M' if i == 0 else 'L'}{px:.1f} {py:.1f}")
        return "".join(parts) + "Z"

    def point(self, lat: float, lon: float) -> list[float]:
        return [round(v, 1) for v in self.to_px(*self.flatten(lat, lon))]


def build_payload(settings) -> dict:
    """Panelin gösterdiği her şeyi tek bir sözlükte toplar."""
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

    # Model önceki sürüme uydurulur; güncel veri onunla puanlanır. Panelde
    # gösterilen fark böylece çerçeve kaymasını değil gerçek değişimi ölçer.
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
        current_fit = indices.fit_group(new_scores, usable)
        pca_info[group] = {
            "members": usable,
            "evr": round(current_fit.explained_variance_ratio * 100, 1),
            "loadings": [round(float(c), 3) for c in current_fit.components],
            "bands": indices.band_coverage(bands_new[group]),
        }

    print(f"res-{MAP_RESOLUTION} birleştirme…")
    aggregate = pd.DataFrame(
        {"parent": [h3.cell_to_parent(c, MAP_RESOLUTION) for c in cells.h3_index]}
    )
    for group, bands in bands_new.items():
        aggregate[group] = bands.astype(int)
        if group in bands_old:
            aggregate[f"{group}__d"] = bands.astype(int) - bands_old[group].astype(int)
    coarse = aggregate.groupby("parent").mean()

    polygons = [
        [Projection.flatten(la, lo) for la, lo in h3.cell_to_boundary(c)] for c in coarse.index
    ]
    proj = Projection(polygons)
    outline = boundary.to_crs(4326).geometry.union_all().simplify(0.003)
    pieces = list(outline.geoms) if outline.geom_type == "MultiPolygon" else [outline]

    print("doğrulama…")
    reports = validation.validate_directory(
        settings.paths.raw_current,
        bbox=settings.bbox,
        duplicate_radius_m=float(settings.validation.get("duplicate_radius_m", 50)),
        min_decimals=int(settings.validation.get("min_coordinate_decimals", 5)),
    )

    from sklearn.decomposition import PCA  # noqa: PLC0415
    from sklearn.preprocessing import StandardScaler  # noqa: PLC0415

    names = list(bands_new)
    table = pd.DataFrame({g: bands_new[g].astype(float) for g in names})
    across = PCA().fit(StandardScaler().fit_transform(table))
    corr = table.corr()

    def read_json(path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    delivery = settings.paths.output / "accessibility_indices.csv"
    return {
        "meta": {
            "cells": int(len(cells)),
            "cells8": int(len(coarse)),
            "poi": int(sum(len(v) for k, v in new_poi.items() if k != "metro")),
            "categories": len(new_poi),
            "indices": len(names),
            "metro_kept": len(report.kept),
            "metro_raw": len(report.records),
            "csv_mb": round(delivery.stat().st_size / 1e6, 1) if delivery.exists() else None,
            "bbox": list(settings.bbox),
            "resolution": settings.h3_resolution,
        },
        "map": {
            "w": round(proj.w),
            "h": round(proj.h),
            "hexes": [proj.path(p) for p in polygons],
            "border": [
                proj.path([Projection.flatten(la, lo) for lo, la in g.exterior.coords])
                for g in pieces
                if len(g.exterior.coords) > 3
            ],
        },
        "indices": {
            g: [None if pd.isna(v) else round(float(v), 2) for v in coarse[g]] for g in names
        },
        "deltas": {
            g: [None if pd.isna(v) else round(float(v), 3) for v in coarse[f"{g}__d"]]
            for g in names
            if f"{g}__d" in coarse.columns
        },
        "pca": pca_info,
        "cross": {
            "evr": [round(float(v) * 100, 1) for v in across.explained_variance_ratio_],
            "labels": names,
            "corr": {a: {b: round(float(corr.loc[a, b]), 2) for b in names} for a in names},
        },
        "metro": {
            "summary": report.summary(),
            "nodes": [
                {"n": r.name, "d": r.decision.value, "r": r.reason, "p": proj.point(r.lat, r.lon)}
                for r in report.records
            ],
        },
        "poiPoints": {
            k: [proj.point(la, lo) for la, lo in zip(v["lat"], v["lon"], strict=True)]
            for k, v in new_poi.items()
            if k != "metro" and len(v) <= MAX_POINTS
        },
        "validation": [r.to_dict() for r in reports],
        "counts": [
            {
                "k": k,
                "new": len(new_poi.get(k, [])),
                "old": len(old_poi[k]) if k in old_poi else None,
            }
            for k in catalogue.SOURCES
        ],
        "comparison": read_json(settings.paths.output / "comparison.json"),
        "beta": read_json(settings.paths.output / "beta_sensitivity.json"),
        "retired": catalogue.RETIRED,
    }


def assemble(payload: dict, destination: Path) -> Path:
    """Şablon, stil ve veriyi tek dosyada birleştirir."""
    shell = (ASSETS / "shell.html").read_text(encoding="utf-8")
    style = (ASSETS / "tabler.min.css").read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # </script> dizisi veri içinde geçerse tarayıcı bloğu erken kapatır.
    data = data.replace("</", "<\\/")
    html = shell.replace("__TABLER__", style).replace("__DATA__", data)
    destination.write_text(html, encoding="utf-8")
    return destination


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=REPO / "urbangeoai_panel.html", help="Çıktı dosyası"
    )
    args = parser.parse_args()

    settings = config.load()
    payload = build_payload(settings)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = assemble(payload, args.out)

    meta = payload["meta"]
    size_kb = written.stat().st_size // 1024
    print(f"\npanel : {written}  ({size_kb:,} KB)")
    print(
        f"hücre {meta['cells']:,} · res-{MAP_RESOLUTION} {meta['cells8']} · "
        f"indeks {meta['indices']} · metro {meta['metro_kept']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
