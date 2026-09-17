#!/usr/bin/env python
"""Metro istasyonu listesini OpenStreetMap'ten üretir ve denetler.

Ham Overpass yanıtı önbelleğe alınır; önbellek varken ağ erişimi gerekmez.
Çıktı iki dosya: skorlamada kullanılan istasyon listesi ve her ham düğüm için
karar ile gerekçeyi taşıyan denetim kaydı.

Kullanım:
    python scripts/build_metro.py
    python scripts/build_metro.py --refresh    # önbelleği yok say
    python scripts/build_metro.py --no-merge   # aktarma komplekslerini ayrı say
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import config, console, metro, osm  # noqa: E402


def main() -> int:
    # Türkçe ilerleme satırları Windows konsolunda betiği düşürmesin.
    console.use_utf8()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Önbelleği yok say")
    parser.add_argument(
        "--no-merge", action="store_true", help="Aktarma komplekslerini ayrı istasyon say"
    )
    parser.add_argument("--out", type=Path, help="Çıktı dizini")
    args = parser.parse_args()

    try:
        settings = config.load()
    except config.ConfigError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2

    rules = settings.metro
    client = osm.OverpassClient(
        cache_dir=settings.paths.cache,
        mirrors=settings.overpass_mirrors or osm.DEFAULT_MIRRORS,
    )

    try:
        payload = client.query(
            osm.metro_query(settings.bbox), cache_key="metro_raw", refresh=args.refresh
        )
    except osm.OverpassError as exc:
        print(f"HATA: {exc}", file=sys.stderr)
        return 2

    records = osm.nodes_to_records(payload)
    report = metro.deduplicate(
        records,
        not_operational=tuple(rules.get("not_operational", ())),
        operational=tuple(rules.get("operational", ()) or ()),
        merge_interchanges=not args.no_merge and bool(rules.get("merge_interchanges", True)),
        duplicate_radius_m=float(rules.get("duplicate_radius_m", metro.DUPLICATE_RADIUS_M)),
        interchange_radius_m=float(rules.get("interchange_radius_m", metro.INTERCHANGE_RADIUS_M)),
    )

    print("=" * 78)
    print(f"METRO İSTASYONU DENETİMİ  —  {len(records)} ham düğüm")
    print("=" * 78)

    for decision, count in sorted(report.summary().items()):
        print(f"  {decision:<20} {count:3d}")

    if report.removed:
        print("\nÇıkarılanlar:")
        for record in sorted(report.removed, key=lambda r: (r.decision.value, r.name)):
            print(f"  {record.name:<32} {record.decision.value:<18} {record.reason}")

    print(f"\nTutulan istasyon: {len(report.kept)}")
    for record in sorted(report.kept, key=lambda r: r.name):
        print(f"  {record.name}")

    out_dir = args.out or settings.paths.reference
    out_dir.mkdir(parents=True, exist_ok=True)

    stations = out_dir / "metro_stations.csv"
    audit = out_dir / "metro_audit.csv"
    report.frame().to_csv(stations, index=False, encoding="utf-8")
    report.audit_frame().to_csv(audit, index=False, encoding="utf-8")

    print(f"\nİstasyon listesi : {stations}")
    print(f"Denetim kaydı    : {audit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
