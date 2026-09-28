#!/usr/bin/env python
"""İş ortağının dosyalarındaki tekrar eden kayıtları raporlar.

Boru hattı tekrarları zaten atıyor (``pipeline.load_local``). Bu betik neyin,
neden atıldığını görünür kılar ki veri sahibi kaynağı da düzeltebilsin:

- ``out/duplicates_dropped.csv`` — atılan her kayıt: katıldığı kayıt, mesafe, neden
- ``out/duplicates_cross.csv``   — aynı yer iki yemək növündə (silinmez, soru)
- ``out/duplicates.json``        — kategori başına sayımlar (panel okur)
- ``out/name_standardization.csv`` — standart adı orijinalinden farklı olan adlar

Kullanım:
    python scripts/check_duplicates.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import catalogue, config, console, dedupe, enrich, names, pipeline  # noqa: E402


def main() -> int:
    console.use_utf8()
    settings = config.load()
    out = settings.paths.output
    out.mkdir(parents=True, exist_ok=True)

    results = pipeline.local_duplicates(settings.paths.raw_current, catalogue.SOURCES)
    dropped = [r.dropped.assign(category=name) for name, r in results.items() if len(r.dropped)]
    table = pd.concat(dropped, ignore_index=True) if dropped else pd.DataFrame()
    columns = ["category", "name", "kept_name", "distance_m", "reason", "lat", "lon"]
    table = table[columns] if len(table) else pd.DataFrame(columns=columns)
    table.to_csv(out / "duplicates_dropped.csv", index=False, encoding="utf-8")

    cleaned = {name: r.kept for name, r in results.items()}
    cross = dedupe.cross_duplicates(cleaned, enrich.FOOD)
    cross.to_csv(out / "duplicates_cross.csv", index=False, encoding="utf-8")

    # Ad standartlaştırması: değişen her ad ve aynı standart ada düşen farklı
    # yazılışlar. Kaynak olarak yerel veri ve OSM eklemeleri birlikte.
    raw = pipeline.load_raw(settings.paths.raw_current, catalogue.SOURCES, quiet=True)
    additions = pipeline.load_additions(settings)
    if additions is not None:
        raw = {**raw, **{f"osm:{c}": f for c, f in additions.groupby("category")}}
    changed = [names.changes(f).assign(category=c) for c, f in raw.items()]
    changed = pd.concat(changed, ignore_index=True)[["category", "before", "after"]]
    changed.to_csv(out / "name_standardization.csv", index=False, encoding="utf-8")
    collided = [names.collisions(f).assign(category=c) for c, f in raw.items()]
    collided = pd.concat(collided, ignore_index=True)

    osm_report = out / "osm_enrichment.json"
    osm = json.loads(osm_report.read_text(encoding="utf-8")) if osm_report.exists() else {}

    report = {
        "generated": date.today().isoformat(),
        "rules": {
            "same_point_m": dedupe.SAME_POINT_M,
            "similarity": dedupe.SIMILARITY,
            "generic_same_m": dedupe.GENERIC_SAME_M,
            "name_radius_m": dedupe.NAME_RADIUS_M,
        },
        "local": [r.summary() for r in results.values()],
        "local_total": {
            "before": sum(r.before for r in results.values()),
            "after": sum(r.after for r in results.values()),
            "dropped": sum(len(r.dropped) for r in results.values()),
        },
        "examples": table.head(25).to_dict(orient="records"),
        "cross_food": {
            "pairs": len(cross),
            "examples": cross.head(15).to_dict(orient="records"),
        },
        "names": {
            "changed": len(changed),
            "changed_by_source": {
                "yerli": int((~changed["category"].str.startswith("osm:")).sum()),
                "osm": int(changed["category"].str.startswith("osm:").sum()),
            },
            "collisions": collided.to_dict(orient="records"),
            "examples": changed.head(12).to_dict(orient="records"),
        },
        "osm": {
            "duplicates_by_reason": osm.get("duplicates_by_reason", {}),
            "matched_by_name": osm.get("totals", {}).get("matched_by_name", 0),
        },
    }
    (out / "duplicates.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=float), encoding="utf-8"
    )

    print(f"{'kateqoriya':<12}{'əvvəl':>8}{'sonra':>8}{'atılan':>8}")
    for r in results.values():
        print(f"{r.category:<12}{r.before:>8,}{r.after:>8,}{len(r.dropped):>8,}")
    t = report["local_total"]
    print(f"{'CƏMİ':<12}{t['before']:>8,}{t['after']:>8,}{t['dropped']:>8,}")
    print(f"\nyemək növləri arası eyni yer (silinmədi, sual): {len(cross)}")
    print(f"hesabat: {out / 'duplicates.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
