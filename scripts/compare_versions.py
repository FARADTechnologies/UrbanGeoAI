#!/usr/bin/env python
"""Yeni çıktıyı önceki üretim çıktısıyla hücre bazında karşılaştırır.

İki etki iç içe geçmiş durumda ve ayrılmaları gerekiyor:

**Veri etkisi.** POI kümesi 2025'ten 2026'ya değişti. Yeni yerler açıldı,
kapsam düzeldi, metro listesi temizlendi.

**Yöntem etkisi.** Bant sınırları, işaret sabitlemesi, sürekli mesafe azalımı
ve konsert zalının çıkarılması. Bunlar aynı veriyle bile farklı sonuç verir.

Betik ikisini ayrı ölçer: önce eski yöntemi iki veri sürümüne uygular (saf veri
etkisi), sonra aynı veriye iki yöntemi uygular (saf yöntem etkisi).

Kullanım:
    python scripts/compare_versions.py
    python scripts/compare_versions.py --json rapor.json
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

#: Önceki veri sürümünde kullanılan dosya adları.
LEGACY_SOURCES: dict[str, tuple[str, str | None]] = {
    "kdgr": ("school_data.csv", "uşaq bağçası"),
    "schl": ("school_data.csv", "məktəb"),
    "univ": ("ali_mekteb.csv", None),
    "bus": ("dayanacaq.csv", None),
    "shopping": ("shopping_malls.csv", None),
    "parks": ("parks.csv", None),
    "museum": ("muzey.csv", None),
    "theatre": ("theatre.csv", None),
    "coffee": ("qida.csv", "kafe"),
    "restaurant": ("qida.csv", "restoran"),
    "fast_food": ("qida.csv", "fast-food"),
    "bars": ("qida.csv", "bar"),
    "sport": ("sport_facility.csv", None),
    "hotel": ("hotel.csv", None),
    "monuments": ("historic_monuments.csv", None),
}

#: Önceki yöntemdeki halka yarıçapları.
LEGACY_BANDS_M = [500, 1000, 1500, 2000, 3000]
METERS_PER_MINUTE = 80.0


def load_category(name: str, base: Path, sources: dict, settings) -> pd.DataFrame:
    """Bir kategoriyi verilen veri sürümünden yükler."""
    if name == "metro":
        client = osm.OverpassClient(
            cache_dir=settings.paths.cache,
            mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS,
        )
        payload = client.query(osm.metro_query(settings.bbox), "metro_raw")
        return metro.deduplicate(osm.nodes_to_records(payload)).frame()
    fname, typ = sources[name]
    frame = io.read_poi(base / fname).frame
    return io.filter_type(frame, typ) if typ else frame


def legacy_score(cells: pd.DataFrame, poi: pd.DataFrame, beta: float) -> np.ndarray:
    """Önceki yöntem: halkalara böl, her halkaya dış kenar ağırlığını ver.

    Bir halkadaki bütün noktalar aynı ağırlığı alır; 10 m'deki bir kafe
    499 m'dekiyle eşit sayılır.
    """
    counts = scoring.count_within(cells, poi, LEGACY_BANDS_M)
    score = np.zeros(len(cells), dtype=float)
    previous = 0
    for radius in LEGACY_BANDS_M:
        current = counts[radius]
        score += (current - previous) * np.exp(-beta * radius / METERS_PER_MINUTE)
        previous = current
    return score


def legacy_bands(index: np.ndarray) -> np.ndarray:
    """Önceki bantlama: pd.qcut, beraberlikleri sessizce silen hâliyle."""
    return (pd.qcut(pd.Series(index), 10, labels=False, duplicates="drop") + 1).to_numpy()


def build(cells, base, sources, members, settings, method: str) -> pd.DataFrame:
    """Bir veri sürümünü bir yöntemle puanlar."""
    scores = {}
    for name in members:
        poi = load_category(name, base, sources, settings)
        beta = catalogue.DECAY[name]
        scores[f"{name}_score"] = (
            legacy_score(cells, poi, beta)
            if method == "legacy"
            else scoring.decay_score(cells, poi, beta)
        )
    return pd.concat([cells, pd.DataFrame(scores, index=cells.index)], axis=1)


def index_of(frame: pd.DataFrame, members: list[str], method: str) -> tuple[np.ndarray, np.ndarray]:
    """Grup indeksini ve bandını üretir."""
    model = indices.fit_group(frame, members)
    index, bands = indices.score_group(frame, model)
    if method == "legacy":
        bands = legacy_bands(index)
    return index, bands


def compare(a_idx, a_band, b_idx, b_band) -> dict:
    """İki puanlamayı karşılaştırır."""
    spearman = float(pd.Series(a_idx).corr(pd.Series(b_idx), method="spearman"))
    delta = b_band.astype(int) - a_band.astype(int)
    return {
        "spearman": round(spearman, 4),
        "moved_pct": round(float((delta != 0).mean() * 100), 1),
        "up_pct": round(float((delta > 0).mean() * 100), 1),
        "down_pct": round(float((delta < 0).mean() * 100), 1),
        "mean_shift": round(float(delta.mean()), 3),
        "top_before": int((a_band == 10).sum()),
        "top_after": int((b_band == 10).sum()),
        "max_band_before": int(a_band.max()),
        "max_band_after": int(b_band.max()),
    }


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Raporu JSON olarak yaz")
    args = parser.parse_args()

    settings = config.load()
    if settings.paths.raw_previous is None or not settings.paths.raw_previous.exists():
        print("HATA: önceki veri sürümü yok (paths.raw_previous)", file=sys.stderr)
        return 2

    cells = grid.land_cells(
        settings.bbox, settings.h3_resolution, grid.load_boundary(settings.paths.reference)
    )
    print(f"ızgara: {len(cells):,} hücre\n")

    # Yalnızca iki veri sürümünde de bulunan gruplar karşılaştırılabilir.
    comparable = {
        g: m
        for g, m in catalogue.GROUPS.items()
        if all(x == "metro" or x in LEGACY_SOURCES for x in m)
    }
    members = sorted({x for m in comparable.values() for x in m})

    print("puanlanıyor…")
    old_legacy = build(
        cells, settings.paths.raw_previous, LEGACY_SOURCES, members, settings, "legacy"
    )
    new_legacy = build(
        cells, settings.paths.raw_current, catalogue.SOURCES, members, settings, "legacy"
    )
    new_current = build(
        cells, settings.paths.raw_current, catalogue.SOURCES, members, settings, "current"
    )

    data_effect, method_effect = {}, {}
    for group, mem in comparable.items():
        a_i, a_b = index_of(old_legacy, mem, "legacy")
        b_i, b_b = index_of(new_legacy, mem, "legacy")
        data_effect[group] = compare(a_i, a_b, b_i, b_b)

        c_i, c_b = index_of(new_current, mem, "current")
        method_effect[group] = compare(b_i, b_b, c_i, c_b)

    def show(title, table, note):
        print("\n" + "=" * 92)
        print(title)
        print("=" * 92)
        print(f"  {note}\n")
        print(
            f"  {'indeks':<13}{'spearman':>10}{'oynayan':>10}{'yukari':>9}"
            f"{'asagi':>9}{'ort.':>8}{'tavan':>12}"
        )
        for group, r in table.items():
            ceiling = f"{r['max_band_before']}→{r['max_band_after']}"
            print(
                f"  {group:<13}{r['spearman']:>10.4f}{r['moved_pct']:>9.1f}%"
                f"{r['up_pct']:>8.1f}%{r['down_pct']:>8.1f}%"
                f"{r['mean_shift']:>+8.2f}{ceiling:>12}"
            )

    show(
        "VERİ ETKİSİ  —  aynı yöntem, 2025 → 2026 verisi",
        data_effect,
        "Yalnızca veri değişti. Hareket gerçek bir değişimi gösterir.",
    )
    show(
        "YÖNTEM ETKİSİ  —  aynı veri (2026), eski → yeni yöntem",
        method_effect,
        "Veri sabit. Hareket yöntem düzeltmelerinden geliyor.",
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "cells": int(len(cells)),
                    "data_effect": data_effect,
                    "method_effect": method_effect,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"\nJSON rapor: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
