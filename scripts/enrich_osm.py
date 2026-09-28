#!/usr/bin/env python
"""Yerel POI havuzunda eksik olanları OpenStreetMap'ten bulur.

Metro dışındaki bütün kategoriler için OSM çekilir, iş ortağının 2026
verisiyle karşılaştırılır ve yerelde karşılığı olmayan nesneler ayrılır.
Sonuç iki dosya:

- ``out/osm_additions.csv`` — havuza eklenecek nesneler
- ``out/osm_enrichment.json`` — kategori başına sayımlar

İndeks üreten betikler ek dosyayı bulursa havuza otomatik katar.

Kullanım:
    python scripts/enrich_osm.py
    python scripts/enrich_osm.py --refresh     # önbelleği yok say, OSM'i yeniden çek
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import pandas as pd  # noqa: E402

from urbangeoai import catalogue, config, console, enrich, grid, osm, pipeline  # noqa: E402

ADDITIONS_FILE = "osm_additions.csv"
REPORT_FILE = "osm_enrichment.json"


def load_local(base: Path) -> dict:
    """İş ortağının kategorileri, tekrarları atılmış (metro hariç)."""
    return pipeline.load_local(base, catalogue.SOURCES, quiet=True)


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="OSM önbelleğini yok say")
    args = parser.parse_args()

    settings = config.load()
    out_dir = settings.paths.output
    out_dir.mkdir(parents=True, exist_ok=True)

    print("yerel veri…")
    local = load_local(settings.paths.raw_current)

    print("OpenStreetMap…")
    client = osm.OverpassClient(
        cache_dir=settings.paths.cache,
        mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS,
        timeout=240,
    )
    payload = client.query(
        enrich.enrichment_query(settings.bbox), "osm_enrichment", refresh=args.refresh
    )
    boundary = grid.load_boundary(settings.paths.reference).to_crs(4326).geometry.union_all()
    raw = enrich.osm_candidates(payload, boundary)
    duplicates: list = []
    deduped = enrich.dedupe_osm(raw, report=duplicates)
    duplicate_table = (
        pd.concat(duplicates, ignore_index=True) if duplicates else raw.iloc[0:0].assign(reason="")
    )
    duplicate_table.to_csv(out_dir / "osm_duplicates.csv", index=False, encoding="utf-8")
    candidates, rejected = enrich.apply_rules(deduped)
    print(
        f"  {len(payload.get('elements', [])):,} nesne indi, sınır içinde {len(raw):,}, "
        f"tekrarlar atılınca {len(deduped):,}, süzgeçten sonra {len(candidates):,}"
    )

    additions, results = enrich.compare(local, candidates)
    filtered = rejected["category"].value_counts().to_dict()
    for r in results:
        r.filtered = int(filtered.get(r.category, 0))
    rejected.to_csv(out_dir / "osm_rejected.csv", index=False, encoding="utf-8")
    additions.to_csv(out_dir / ADDITIONS_FILE, index=False, encoding="utf-8")

    report = {
        "generated": date.today().isoformat(),
        "osm_elements": len(payload.get("elements", [])),
        "inside_boundary": len(raw),
        "after_dedupe": len(deduped),
        "duplicates_by_reason": duplicate_table["reason"].value_counts().to_dict(),
        "after_rules": len(candidates),
        "rejected_by_reason": rejected["reason"].value_counts().to_dict(),
        "match_radius_m": enrich.MATCH_RADIUS_M,
        "categories": [r.to_dict() for r in results],
        "totals": {
            "local": sum(r.local for r in results),
            "osm": sum(r.osm for r in results),
            "matched": sum(r.matched for r in results),
            "matched_by_name": sum(r.matched_by_name for r in results),
            "added": sum(r.added for r in results),
        },
    }
    (out_dir / REPORT_FILE).write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print()
    print(
        f"{'kateqoriya':<12}{'yerli':>8}{'OSM':>8}{'süzülən':>9}{'eşleşən':>9}"
        f"{'yeni':>8}{'cəmi':>8}{'artım':>9}"
    )
    print("-" * 71)
    for r in results:
        print(
            f"{r.category:<12}{r.local:>8,}{r.osm:>8,}{r.filtered:>9,}{r.matched:>9,}"
            f"{r.added:>8,}{r.total:>8,}{r.growth_pct:>8.1f}%"
        )
    t = report["totals"]
    print("-" * 71)
    print(
        f"{'CƏMİ':<12}{t['local']:>8,}{t['osm']:>8,}{'':>9}{t['matched']:>9,}"
        f"{t['added']:>8,}{t['local'] + t['added']:>8,}"
    )
    print(f"\nəlavələr : {out_dir / ADDITIONS_FILE}")
    print(f"hesabat  : {out_dir / REPORT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
