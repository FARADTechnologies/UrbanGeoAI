#!/usr/bin/env python
"""Teslim tablosunun gerçekten H10'da hesaplandığını doğrular.

Ekip sordu: hesap H10'da mı yapılıyor, yapılıyorsa tam olarak ne yapılıyor
ve hepsi yapılıyor mu? Bu betik tabloyu açıp her iddiayı tek tek sınar ve
sonucu ``out/h10_verification.json``'a yazar; panel bu dosyayı gösterir.

Kullanım:
    python scripts/verify_h10.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import h3
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import catalogue, config, console, indices  # noqa: E402

#: İş ortağının üretim çıktısındaki hücre sayısı. Kendi maskeleriyle birebir
#: yeniden üretildi (fark 0).
PRODUCTION_CELLS = 120_349

PARENT_RESOLUTIONS = (6, 7, 8)


def check(name: str, ok: bool, detail: str) -> dict:
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name:<46} {detail}")
    return {"name": name, "ok": bool(ok), "detail": detail}


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    settings = config.load()
    table_path = settings.paths.output / "accessibility_indices.csv"
    model_path = settings.paths.output / "index_model.json"
    if not table_path.exists():
        print(f"HATA: {table_path} yok. Önce scripts/build_indices.py çalıştırılmalı.")
        return 2

    table = pd.read_csv(table_path, encoding="utf-8")
    models = indices.load_model(model_path)
    groups = list(models)
    n = len(table)
    print(f"tablo: {n:,} satır × {len(table.columns)} sütun\n")

    results = []

    resolutions = table["h3_index"].map(h3.get_resolution)
    results.append(
        check(
            "Bütün hüceyrələr H10-dur",
            bool((resolutions == 10).all()),
            f"{int((resolutions == 10).sum()):,} / {n:,}",
        )
    )
    results.append(
        check(
            "Təkrar hüceyrə yoxdur",
            table["h3_index"].is_unique,
            f"{table['h3_index'].nunique():,} unikal",
        )
    )
    results.append(
        check(
            "Hüceyrə sayı istehsalla eynidir",
            n == PRODUCTION_CELLS,
            f"{n:,} = {PRODUCTION_CELLS:,}",
        )
    )

    score_cols = [f"{g}_score" for g in groups]
    bands = table[score_cols]
    in_range = bands.notna().all(axis=1) & bands.ge(1).all(axis=1) & bands.le(10).all(axis=1)
    results.append(
        check(
            f"{len(groups)} indeksin balı hər hüceyrədə var (1–10)",
            bool(in_range.all()),
            f"{int(in_range.sum()):,} / {n:,}",
        )
    )

    index_cols = [f"{g}_index" for g in groups]
    finite = np.isfinite(table[index_cols].to_numpy()).all(axis=1)
    results.append(
        check(
            f"{len(groups)} xam indeks hər hüceyrədə hesablanıb",
            bool(finite.all()),
            f"{int(finite.sum()):,} / {n:,}",
        )
    )

    ceilings = {g: int(table[f"{g}_score"].max()) for g in groups}
    results.append(
        check(
            "Hər indeks 1-dən 10-a qədər çatır",
            all(v == 10 for v in ceilings.values()) and bool((bands.min() == 1).all()),
            ", ".join(f"{g} {ceilings[g]}" for g in groups),
        )
    )

    # Üst hücre sütunları gerçekten H10 hücresinin atası mı?
    parents_ok = {}
    for r in PARENT_RESOLUTIONS:
        expected = table["h3_index"].map(lambda c, r=r: h3.cell_to_parent(c, r))
        parents_ok[r] = bool((expected == table[f"h3_res{r}"]).all())
    results.append(
        check(
            "Üst hüceyrələr (H6/H7/H8) H10-un əcdadıdır",
            all(parents_ok.values()),
            ", ".join(
                f"H{r}: {table[f'h3_res{r}'].nunique():,} hüceyrə" for r in PARENT_RESOLUTIONS
            ),
        )
    )

    distance_cols = [c for c in table.columns if c.startswith("distance_to_")]
    coverage = {
        c.removeprefix("distance_to_").removesuffix("_m"): round(
            float(table[c].notna().mean() * 100), 1
        )
        for c in distance_cols
    }
    results.append(
        check(
            "Məsafə sütunları hesablanıb",
            len(distance_cols) == len(catalogue.SERVICE_RADIUS_M),
            ", ".join(f"{k} {v}%" for k, v in coverage.items()),
        )
    )

    levels = [
        {
            "res": 10,
            "role": "hesablama",
            "cells": int(n),
            "what": (
                f"{len(catalogue.DECAY)} kateqoriya skoru, {len(groups)} xam indeks, "
                f"{len(groups)} bal (1–10), {len(distance_cols)} məsafə"
            ),
        },
        *[
            {
                "res": r,
                "role": "yalnız ata kimliyi",
                "cells": int(table[f"h3_res{r}"].nunique()),
                "what": "cədvəldə sütun; ayrıca hesablama yoxdur",
            }
            for r in PARENT_RESOLUTIONS
        ],
        {
            "res": 9,
            "role": "yalnız xəritə",
            "cells": int(table["h3_index"].map(lambda c: h3.cell_to_parent(c, 9)).nunique()),
            "what": "H10 ballarının ortalaması; cədvəldə yoxdur",
        },
    ]

    payload = {
        "table": str(table_path.name),
        "rows": int(n),
        "columns": int(len(table.columns)),
        "groups": groups,
        "checks": results,
        "all_ok": all(r["ok"] for r in results),
        "levels": sorted(levels, key=lambda x: -x["res"]),
        "distance_coverage_pct": coverage,
        "model": json.loads(model_path.read_text(encoding="utf-8")).get("metadata", {}),
        "original_resolution": 10,
    }
    out = settings.paths.output / "h10_verification.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'HAMISI KEÇDİ' if payload['all_ok'] else 'UĞURSUZ YOXLAMA VAR'} → {out}")
    return 0 if payload["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
