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
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import pandas as pd  # noqa: E402

from urbangeoai import catalogue, config, console, enrich, grid, osm, pipeline  # noqa: E402

ADDITIONS_FILE = "osm_additions.csv"
REPORT_FILE = "osm_enrichment.json"
CANDIDATES_FILE = "osm_candidates.csv"


def load_local(base: Path) -> dict:
    """İş ortağının kategorileri, tekrarları atılmış (metro hariç)."""
    return pipeline.load_local(base, catalogue.SOURCES, quiet=True)


def wikidata_images(ids: list[str], cache: Path) -> dict[str, str]:
    """Wikidata nesnelerinin resmi (P18) — Commons dosya adı. Önbellekli."""
    known = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    missing = [i for i in dict.fromkeys(ids) if i not in known]
    for start in range(0, len(missing), 50):
        chunk = missing[start : start + 50]
        url = (
            "https://www.wikidata.org/w/api.php?action=wbgetentities&props=claims&format=json&ids="
            + "|".join(chunk)
        )
        request = urllib.request.Request(url, headers={"User-Agent": "urbangeoai/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                entities = json.load(response).get("entities", {})
        except OSError as exc:
            print(f"  Wikidata alınamadı: {exc}", file=sys.stderr)
            break
        for qid in chunk:
            claims = entities.get(qid, {}).get("claims", {}).get("P18", [])
            value = claims[0]["mainsnak"].get("datavalue", {}).get("value") if claims else None
            known[qid] = f"File:{value}" if value else ""
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(known, ensure_ascii=False, indent=1), encoding="utf-8")
    return known


def add_images(candidates: pd.DataFrame, cache: Path) -> pd.DataFrame:
    """Resmi olmayan ama Wikidata bağlantısı olan nesnelere Commons resmini ekler."""
    infos = [json.loads(s) if s else {} for s in candidates["info"]]
    ids = [
        i["wikidata"] for i in infos if "wikidata" in i and not ({"image", "commons"} & i.keys())
    ]
    if not ids:
        return candidates
    images = wikidata_images(ids, cache)
    for info in infos:
        if "wikidata" in info and not ({"image", "commons"} & info.keys()):
            if images.get(info["wikidata"]):
                info["commons"] = images[info["wikidata"]]
    return candidates.assign(info=[json.dumps(i, ensure_ascii=False) if i else "" for i in infos])


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

    # Bütün adaylar (eklenenler ve yerelde karşılığı olanlar) — panel, yerel
    # bir kaydın OSM karşılığını bulup kartında site/telefon göstermek için okur.
    candidates = add_images(candidates, settings.paths.cache / "wikidata_images.json")
    candidates.to_csv(out_dir / CANDIDATES_FILE, index=False, encoding="utf-8")
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
