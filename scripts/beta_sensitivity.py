#!/usr/bin/env python
"""Azalım katsayılarının sonuca ne kadar etki ettiğini ölçer.

Katsayılar önceki çalışmadan devralındı ve türetildikleri hedef değişken
belgelenmemiş. Kalibrasyon verisi olmadan doğru değerleri bulamayız, ama
**ne kadar önemli olduklarını** ölçebiliriz.

Her katsayı ayrı ayrı yarıya indirilip iki katına çıkarılıyor ve indeksin ne
kadar oynadığına bakılıyor. Az oynayan bir katsayı, yanlış seçilmiş olsa bile
sonucu bozmuyor demektir; çok oynayan biri kalibrasyonun asıl hedefidir.

Kullanım:
    python scripts/beta_sensitivity.py
    python scripts/beta_sensitivity.py --json out/beta.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    io,
    metro,
    osm,
    scoring,
)

#: Katsayı bu çarpanlarla denenir.
FACTORS = (0.5, 2.0)


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Sonucu JSON olarak yaz")
    args = parser.parse_args()

    settings = config.load()
    cells = grid.land_cells(
        settings.bbox, settings.h3_resolution, grid.load_boundary(settings.paths.reference)
    )

    pois: dict[str, pd.DataFrame] = {}
    for name, (fname, typ) in catalogue.SOURCES.items():
        path = settings.paths.raw_current / fname
        if not path.exists():
            continue
        frame = io.read_poi(path).frame
        pois[name] = io.filter_type(frame, typ) if typ else frame
    client = osm.OverpassClient(
        cache_dir=settings.paths.cache, mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS
    )
    pois["metro"] = metro.deduplicate(
        osm.nodes_to_records(client.query(osm.metro_query(settings.bbox), "metro_raw"))
    ).frame()

    print(f"ızgara {len(cells):,} hücre · {len(pois)} kategori\n")

    def bands_for(overrides: dict[str, float]) -> dict[str, np.ndarray]:
        """Verilen katsayılarla bütün grupların bandını üretir."""
        scores = {}
        for name, frame in pois.items():
            beta = overrides.get(name, catalogue.DECAY[name])
            scores[f"{name}_score"] = scoring.decay_score(cells, frame, beta)
        table = pd.concat([cells, pd.DataFrame(scores, index=cells.index)], axis=1)
        out = {}
        for group, members in catalogue.GROUPS.items():
            usable = [m for m in members if f"{m}_score" in table.columns]
            if usable:
                _, out[group] = indices.score_group(table, indices.fit_group(table, usable))
        return out

    baseline = bands_for({})

    # Her kategori hangi gruplara giriyor
    membership = {
        name: [g for g, m in catalogue.GROUPS.items() if name in m] for name in catalogue.DECAY
    }

    results = {}
    print(f"{'kategori':<14}{'β':>7}{'grup':<26}{'yarıya':>9}{'iki katına':>12}")
    print("-" * 72)
    for name in sorted(catalogue.DECAY, key=lambda n: -len(membership[n])):
        if name not in pois:
            continue
        beta = catalogue.DECAY[name]
        row = {"beta": beta, "groups": membership[name], "effect": {}}
        cells_moved = []
        for factor in FACTORS:
            changed = bands_for({name: beta * factor})
            worst = 0.0
            for group in membership[name]:
                moved = float((changed[group] != baseline[group]).mean() * 100)
                worst = max(worst, moved)
            row["effect"][str(factor)] = round(worst, 1)
            cells_moved.append(worst)
        results[name] = row
        groups = ", ".join(membership[name])
        print(f"{name:<14}{beta:>7.2f}{groups:<26}{cells_moved[0]:>8.1f}%{cells_moved[1]:>11.1f}%")

    ranked = sorted(results.items(), key=lambda kv: -max(kv[1]["effect"].values()))
    print("\n" + "=" * 72)
    print("KALİBRASYONUN ÖNCELİĞİ  —  en çok oynatan katsayılar")
    print("=" * 72)
    for name, row in ranked[:5]:
        worst = max(row["effect"].values())
        print(
            f"  {name:<14} en fazla {worst:5.1f}% hücre oynuyor   (grup: {', '.join(row['groups'])})"
        )
    print("\n  Az oynatan katsayılar yanlış seçilmiş olsa bile sonucu bozmuyor;")
    print("  kalibrasyon verisi geldiğinde önce yukarıdakilere bakılmalı.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
