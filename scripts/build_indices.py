#!/usr/bin/env python
"""Teslim edilecek indeks tablosunu üretir.

Çıktı üç şeyi birden taşır:

**Çoklu çözünürlük.** Ana satır H3 res-10'dur, ama her satır res-6, res-7 ve
res-8 üst hücresini de taşır. Böylece platform hangi seviyede birleştirirse
birleştirsin çalışır; seviye anlaşması beklenmeden teslim edilebilir.

**Dondurulmuş model.** Bant sınırları, ölçekleyici ve bileşen yükleri diske
yazılır. Sonraki veri sürümü bu modelle puanlanır, yeniden sıralanmaz. Böylece
bir hücrenin balı yalnızca kendi çevresi değiştiyse oynar.

**Bütün indeksler.** Yedi indeksin hepsi çıktıda; hangisinin gösterileceği
ürün kararıdır, veri katmanı hepsini üretir.

**OpenStreetMap eklemeleri.** ``scripts/enrich_osm.py`` çalıştırılmışsa,
yerel havuzda olmayan nesneler güncel veriye katılır. ``--no-osm`` ile
yalnız yerel veri kullanılır.

Kullanım:
    python scripts/build_indices.py
    python scripts/build_indices.py --fit-on previous   # modeli 2025'e uydur
    python scripts/build_indices.py --no-osm            # OSM eklemeleri olmadan
    python scripts/build_indices.py --out yol/
"""

from __future__ import annotations

import argparse
import sys
import time
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
    pipeline,
    scoring,
)

#: Çıktıya eklenen üst hücre seviyeleri. Platform hangisini kullanırsa
#: kullansın birleştirme çalışsın diye hepsi veriliyor.
PARENT_RESOLUTIONS = (6, 7, 8)


def load_pois(base: Path, settings, sources: dict, additions=None) -> dict[str, pd.DataFrame]:
    """Bir veri sürümünün havuzu. Metro OpenStreetMap'ten gelir."""
    return pipeline.load_pool(base, sources, pipeline.load_metro(settings).frame(), additions)


def category_scores(cells: pd.DataFrame, pois: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Her kategori için mesafeye göre azalan skor."""
    return pipeline.category_scores(cells, pois)


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fit-on",
        choices=["current", "previous"],
        default="previous",
        help="Modelin uydurulacağı veri sürümü (varsayılan: previous)",
    )
    parser.add_argument("--out", type=Path, help="Çıktı dizini")
    parser.add_argument("--no-osm", action="store_true", help="OpenStreetMap eklemelerini kullanma")
    args = parser.parse_args()

    started = time.time()
    settings = config.load()

    issues = catalogue.check()
    if issues:
        for issue in issues:
            print(f"KATALOG HATASI [{issue.kind}] {issue.detail}", file=sys.stderr)
        return 2

    out_dir = args.out or settings.paths.output
    out_dir.mkdir(parents=True, exist_ok=True)

    boundary = grid.load_boundary(settings.paths.reference)
    cells = grid.land_cells(settings.bbox, settings.h3_resolution, boundary)
    print(f"ızgara: {len(cells):,} hücre (res-{settings.h3_resolution})")

    additions = None if args.no_osm else pipeline.load_additions(settings)
    if additions is not None:
        print(f"OpenStreetMap eklemeleri: {len(additions):,} nesne havuza katılıyor")
    else:
        print("OpenStreetMap eklemeleri kullanılmıyor")

    print("güncel veri puanlanıyor…")
    pois_current = load_pois(settings.paths.raw_current, settings, catalogue.SOURCES, additions)
    current = pd.concat([cells, category_scores(cells, pois_current)], axis=1)

    # Model varsayılan olarak önceki sürüme uydurulur. Böylece güncel verideki
    # hareket, referans çerçevesinin kayması değil gerçek bir değişimdir.
    basis = current
    basis_label = "current"
    if (
        args.fit_on == "previous"
        and settings.paths.raw_previous
        and settings.paths.raw_previous.exists()
    ):
        from compare_versions import LEGACY_SOURCES  # noqa: PLC0415

        print("model 2025 verisine uyduruluyor…")
        basis = pd.concat(
            [
                cells,
                category_scores(
                    cells, load_pois(settings.paths.raw_previous, settings, LEGACY_SOURCES)
                ),
            ],
            axis=1,
        )
        basis_label = "previous"

    print("indeksler…")
    models, columns = {}, {}
    for group, members in catalogue.GROUPS.items():
        usable = [m for m in members if f"{m}_score" in current.columns]
        if not usable:
            continue
        # Grup yalnızca temel veride tam ise oradan uydurulur; değilse
        # (təhlükəsizlik gibi yeni gruplar) güncel veriden.
        source = basis if all(f"{m}_score" in basis.columns for m in usable) else current
        model = indices.fit_group(source, usable)
        models[group] = model
        index, bands = indices.score_group(current, model)
        columns[f"{group}_index"] = index.round(4)
        columns[f"{group}_score"] = bands
        coverage = indices.band_coverage(bands)
        empty = [b for b, n in coverage.items() if n == 0]
        print(
            f"  {group:<15} var={model.explained_variance_ratio:5.1%}  "
            f"tavan={int(bands.max()):2d}  boş bant={empty or '—'}"
        )

    print("en yakın nesne mesafeleri…")
    for name, radius in catalogue.SERVICE_RADIUS_M.items():
        if name not in pois_current:
            continue
        distance, _ = scoring.nearest(cells, pois_current[name], cap_m=radius)
        columns[f"distance_to_{name}_m"] = distance.round(1)

    print("üst hücreler…")
    for resolution in PARENT_RESOLUTIONS:
        columns[f"h3_res{resolution}"] = [h3.cell_to_parent(c, resolution) for c in cells.h3_index]

    table = pd.concat([cells, pd.DataFrame(columns, index=cells.index)], axis=1)

    order = (
        ["h3_index"]
        + [f"h3_res{r}" for r in PARENT_RESOLUTIONS]
        + ["latitude", "longitude"]
        + [f"{g}_score" for g in models]
        + [f"{g}_index" for g in models]
        + [c for c in table.columns if c.startswith("distance_to_")]
    )
    table = table[order]

    csv_path = out_dir / "accessibility_indices.csv"
    model_path = out_dir / "index_model.json"
    table.to_csv(csv_path, index=False, encoding="utf-8")
    indices.save_model(
        models,
        model_path,
        metadata={
            "fitted_on": basis_label,
            "osm_additions": 0 if additions is None else int(len(additions)),
            "grid_cells": int(len(cells)),
            "h3_resolution": settings.h3_resolution,
            "bbox": list(settings.bbox),
            "boundary_sha256": grid.mask_fingerprint(
                settings.paths.reference / grid.PARTNER_MASK_FILE
            )
            if (settings.paths.reference / grid.PARTNER_MASK_FILE).exists()
            else None,
        },
    )

    size_mb = csv_path.stat().st_size / 1e6
    print(
        f"\ntablo : {csv_path}  ({len(table):,} satır × {len(table.columns)} sütun, {size_mb:.1f} MB)"
    )
    print(f"model : {model_path}")
    print(f"süre  : {time.time() - started:.0f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
